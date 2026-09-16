"""Golden Loan Path — the end-to-end vertical slice, run deterministically, per program.

W-2 base income + depository assets + AUS findings + minimum documentation +
File Prep/QC + guideline validation + borrower communication + submission-
readiness report, for Fannie (DU), Freddie (LPA), FHA (TOTAL or Manual),
VA (residual income) and USDA (annual / adjusted annual / repayment income,
GUS).

:func:`run` executes the same steps the bots take, through the plugin's own
tool handlers, switching the acting profile per step (the process-level
identity the hooks and tools use). It is the repeatable synthetic test and the
backbone the model-driven run follows:

    Flo:     open/use the Deal Room
    Flo →    Malcolm: File Prep handoff
    Malcolm: AUS findings, income (deterministic), assets (deterministic),
             matrix, readiness; guideline questions →
    Flo →    Sage: Guideline Cards (section-level, active slice)
    Malcolm: readiness report back to Flo
    Flo →    Whisper: missing-document request draft
    Flo:     synthesis for Ashley

Nothing here sends anything; the draft stays a draft and any send would stop
at the Approval Center. The program comes from the fixture (``workspace.agency``)
and is passed explicitly to every workbench so no Fannie binding can leak
into another program's file.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import assets as assets_mod
from . import aus as aus_mod
from . import calc as calc_mod
from . import fileprep
from . import sources
from .knowledge import KnowledgeState


class _Actor:
    """Temporarily act as a profile (HERMES_PROFILE_NAME) for one step."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.prev: Optional[str] = None

    def __enter__(self):
        self.prev = os.environ.get("HERMES_PROFILE_NAME")
        os.environ["HERMES_PROFILE_NAME"] = self.name
        return self

    def __exit__(self, *exc):
        if self.prev is None:
            os.environ.pop("HERMES_PROFILE_NAME", None)
        else:
            os.environ["HERMES_PROFILE_NAME"] = self.prev


def _j(text: str) -> Dict[str, Any]:
    return json.loads(text)


def _months_elapsed(ytd_through: Optional[str]) -> Decimal:
    if not ytd_through:
        return Decimal(0)
    y, m, d = (int(x) for x in str(ytd_through).split("-"))
    return Decimal(m - 1) + Decimal(d) / Decimal(30)


_BASE_FORMULA = {
    "fannie": ("fannie.base_income.monthly", {"gross_pay": "gross_current", "pay_frequency": "pay_frequency", "hours_per_week": "hours"}, "B3-3.3-01, B3-3.2-02"),
    "freddie": ("freddie.base_income.monthly", {"gross_pay": "gross_current", "pay_frequency": "pay_frequency", "hours_per_week": "hours"}, "5303.1(c)(i)"),
    "fha": ("fha.{method}.income.current_salary_monthly", {"current_salary_or_rate": "gross_current", "pay_frequency": "pay_frequency", "hours_per_week": "hours"}, "II.A.{n}.{l}"),
}


def income_review(documents: List[Dict[str, Any]], *, active_check, section_meta, program: str = "fannie", underwriting_method: Optional[str] = None,
                  fixture: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Malcolm's deterministic income prep for fixed base income, bound to one program."""
    program = (program or "fannie").lower()
    stubs = sorted([d for d in documents if d.get("type") == "paystub"], key=lambda d: d.get("pay_date") or "", reverse=True)
    w2s = sorted([d for d in documents if d.get("type") == "w2"], key=lambda d: int(d.get("tax_year") or 0), reverse=True)
    out: Dict[str, Any] = {"review": "income_base_fixed", "program": program, "underwriting_method": underwriting_method, "calc_ids": [], "traces": [], "warnings": [],
                           "status": "OK", "document_refs": []}
    if not stubs:
        out.update({"status": "MISSING", "note": "no paystub in file"})
        return out
    stub = stubs[0]
    out["document_refs"].append(stub["ref"])
    freq = str(stub.get("pay_frequency") or "").lower()

    def _run(fid, inputs, **kw):
        res = calc_mod.run(fid, inputs, document_refs=[stub["ref"]], active_check=active_check, source_meta=section_meta, program=program,
                           underwriting_method=underwriting_method, **kw)
        out["traces"].append(res.to_dict())
        if res.status == "SUCCESS":
            out["calc_ids"].append(res.calc_id)
        return res

    if program in _BASE_FORMULA:
        fid, mapping, cite = _BASE_FORMULA[program]
        if program == "fha":
            fid = fid.format(method=underwriting_method)
            cite = "II.A.4.c" if underwriting_method == "total" else "II.A.5.b"
        monthly = _run(fid, {k: stub.get(v) for k, v in mapping.items()})
        if monthly.status != "SUCCESS":
            out.update({"status": "SOURCE_GAP" if monthly.status in ("SOURCE_GAP", "UNSUPPORTED") else "NEEDS_INPUT", "note": "; ".join(monthly.warnings)})
            return out
        out["qualifying_monthly"] = monthly.result
        out["income_label"] = {"fannie": "qualifying monthly income", "freddie": "stable monthly income", "fha": "Effective Income"}[program]
    elif program == "va":
        if freq != "monthly":
            out.update({"status": "SOURCE_GAP", "note": "VA Chapter 4 as captured states no pay-period conversion table; supply gross monthly income directly (paystub pay_frequency 'monthly')"})
            return out
        out["qualifying_monthly"] = str(Decimal(str(stub["gross_current"])).quantize(Decimal("0.01")))
        out["income_label"] = "gross monthly income (Form 26-6393)"
        out["traces"].append({"op": "identity", "value": out["qualifying_monthly"], "rule": "monthly paystub gross used as gross monthly income; no conversion needed"})
        cite = "Chapter 4 Topic 2"
    elif program == "usda":
        if freq != "monthly":
            out.update({"status": "SOURCE_GAP", "note": "HB-1-3555 as captured states no pay-period conversion table; supply monthly income directly (paystub pay_frequency 'monthly')"})
            return out
        monthly_amt = Decimal(str(stub["gross_current"]))
        rep = _run("usda.repayment_income.monthly", {"note_party_monthly_incomes": [str(monthly_amt)]})
        if rep.status != "SUCCESS":
            out.update({"status": "SOURCE_GAP", "note": "; ".join(rep.warnings)})
            return out
        out["qualifying_monthly"] = rep.result
        out["income_label"] = "repayment income (note parties only)"
        household = fixture.get("household", {}) if fixture else {}
        adults = [str(monthly_amt * 12)] + [str(Decimal(str(a.get("annual_income") or 0))) for a in household.get("other_adult_members", [])]
        students = [str(Decimal(str(s.get("annual_earned_income") or 0))) for s in household.get("adult_full_time_students", [])]
        annual = _run("usda.annual_income.household", {"adult_member_annual_incomes": adults, "full_time_student_annual_incomes": students or None})
        adjusted = _run("usda.adjusted_annual_income", {"annual_income": annual.result, "eligible_deductions": household.get("eligible_deductions") or None}) if annual.status == "SUCCESS" else None
        out["household_income"] = {
            "annual_income": annual.result, "adjusted_annual_income": adjusted.result if adjusted and adjusted.status == "SUCCESS" else None,
            "repayment_income": rep.result, "calc_ids": [c for c in (annual.calc_id, adjusted.calc_id if adjusted else None) if c],
            "note": "three distinct figures: annual (all adult members) / adjusted annual (eligibility) / repayment (note parties); compare adjusted annual income to the area limit in GUS",
            "area_income_limit": household.get("area_income_limit"),
        }
        if household.get("area_income_limit") and adjusted and adjusted.status == "SUCCESS" and Decimal(adjusted.result) > Decimal(str(household["area_income_limit"])):
            out["status"] = "NEEDS_REVIEW"
            out["warnings"].append(f"adjusted annual income {adjusted.result} exceeds the stated area income limit {household['area_income_limit']} (9.5 / GUS eligibility)")
        usda_fx = (fixture or {}).get("usda") or {}
        ws_fx = (fixture or {}).get("workspace") or {}
        if ws_fx.get("pitia") and usda_fx.get("other_monthly_debts") is not None:
            ratios = _run("usda.ratios.piti_td", {"piti": ws_fx["pitia"], "other_monthly_debts": usda_fx["other_monthly_debts"], "repayment_income": rep.result})
            if ratios.status == "SUCCESS":
                piti_ratio = next((s.get("value") for s in ratios.steps if s.get("op") == "piti_ratio_result"), None)
                out["ratios"] = {"piti_ratio_percent": piti_ratio, "total_debt_ratio_percent": ratios.result, "calc_id": ratios.calc_id, "warnings": ratios.warnings}
                if any("exceeds 29/41" in w for w in ratios.warnings):
                    out["status"] = "NEEDS_REVIEW"
                    out["warnings"].append(f"PITI/TD ratios {piti_ratio}/{ratios.result} exceed 29/41 percent of repayment income: debt ratio waiver with compensating factors required (11.2/11.3)")
                    out["guideline_questions"] = out.get("guideline_questions", []) + ["USDA ratios above 29/41 percent of repayment income on a GUS Accept file: what does HB-1-3555 11.2/11.3 require for a debt ratio waiver and which compensating factors qualify?"]
        cite = "9.3 / 9.5 / 9.7-9.8"
    else:
        out.update({"status": "SOURCE_GAP", "note": f"no income binding for {program}"})
        return out

    monthly_result = Decimal(out["qualifying_monthly"])
    if program == "fannie":
        consistency = _run("fannie.income.ytd_consistency", {"qualifying_monthly": out["qualifying_monthly"], "ytd_amount": stub.get("ytd_gross"),
                                                            "ytd_months": str(_months_elapsed(stub.get("ytd_through") or stub.get("period_end")).quantize(Decimal("0.01")))})
        if consistency.status == "SUCCESS":
            out["ytd_ratio_percent"] = consistency.result
            if any("needs review" in w for w in consistency.warnings):
                out["status"] = "NEEDS_REVIEW"
                out["warnings"].append("YTD earnings are not consistent with the paystub-based monthly income; obtain an explanation (raise date, bonus in YTD, missed pay) before qualifying (B3-3.3-01).")
    else:
        months = _months_elapsed(stub.get("ytd_through") or stub.get("period_end"))
        if months > 0 and stub.get("ytd_gross"):
            ytd_monthly = (Decimal(str(stub["ytd_gross"])) / months).quantize(Decimal("0.01"))
            ratio = (ytd_monthly / monthly_result * 100).quantize(Decimal("0.1")) if monthly_result else None
            out["ytd_comparison"] = {"ytd_monthly_rate": str(ytd_monthly), "ratio_percent": str(ratio) if ratio is not None else None,
                                     "note": "arithmetic comparison for the processor; the program text requires documentation to support the calculation, it states no tolerance"}
            if ratio is not None and abs(ratio - 100) > 5:
                out["status"] = "NEEDS_REVIEW"
                out["warnings"].append(f"YTD monthly rate ({ytd_monthly}) differs from the paystub-based amount ({monthly_result}) by {abs(ratio - 100)}%: obtain an explanation before qualifying ({cite}).")
    if w2s:
        w2 = w2s[0]
        out["document_refs"].append(w2["ref"])
        annualized = monthly_result * 12
        prior = Decimal(str(w2.get("box1_wages") or 0))
        ratio = (annualized / prior * 100).quantize(Decimal("0.1")) if prior else None
        out["w2_comparison"] = {"tax_year": w2.get("tax_year"), "w2_wages": str(prior), "current_annualized": str(annualized.quantize(Decimal("0.01"))), "ratio_percent": str(ratio) if ratio else None}
        if ratio is not None and abs(ratio - 100) > 5:
            out["status"] = "NEEDS_REVIEW"
            out["warnings"].append(f"Current annualized base ({annualized.quantize(Decimal('0.01'))}) differs from the {w2.get('tax_year')} W-2 ({prior}) by {abs(ratio - 100)}%: document the raise/change ({cite}).")
            out["guideline_questions"] = out.get("guideline_questions", []) + [_raise_question(program, underwriting_method)]
    out["note"] = "; ".join(out["warnings"]) if out["warnings"] else f"{out.get('income_label', 'monthly income')} reconciled to YTD and prior-year W-2"
    return out


def _raise_question(program: str, method: Optional[str]) -> str:
    return {
        "fannie": "Fixed base income with a year-over-year increase: what documentation supports using the current rate (B3-3.3-01 fixed base income; B3-3.2-02 pay raises)?",
        "freddie": "Base non-fluctuating earnings with a year-over-year increase: what documentation supports the current pay rate and the income calculation (5303.1(c)(i); 5302.2 paystub/W-2)?",
        "fha": f"Salaried Effective Income with a year-over-year increase: what documentation supports using the current salary (II.A.{'4.c' if method == 'total' else '5.b'} Calculation of Effective Income; two-year employment verification)?",
        "va": "Effective income with a year-over-year increase: what verification supports the current income as stable and reliable (Chapter 4 Topic 2)?",
        "usda": "Repayment income with a year-over-year increase: is the increase supported and logical (HB-1-3555 9.8, 20 percent variance guidance)?",
    }[program]


def accounts_from_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group bank-statement documents into accounts (by last four) for the asset workbench."""
    merged: Dict[str, Dict[str, Any]] = {}
    for d in sorted([d for d in documents if d.get("type") == "bank_statement"], key=lambda d: d.get("statement_end") or ""):
        key = str(d.get("last_four") or d.get("ref"))
        period = {"start": d.get("statement_start"), "end": d.get("statement_end"), "pages_present": d.get("pages_present"), "pages_total": d.get("pages_total"),
                  "prior_ending_balance_shown": d.get("prior_ending_balance_shown")}
        if key not in merged:
            merged[key] = {"account_ref": f"{d.get('institution')} …{d.get('last_four')}", "type": d.get("account_type", "checking"), "institution": d.get("institution"),
                           "account_holder": d.get("account_holder"), "last_four": d.get("last_four"), "statement_periods": [], "deposits": [], "ending_balance": d.get("ending_balance"),
                           "vod": d.get("vod", False)}
        merged[key]["statement_periods"].append(period)
        merged[key]["deposits"] += d.get("deposits") or []
        merged[key]["ending_balance"] = d.get("ending_balance")  # sorted ascending: last wins = most recent
    return list(merged.values())


def va_residual_review(fixture: Dict[str, Any], gross_monthly: str, *, active_check, section_meta) -> Dict[str, Any]:
    """VA-only: required residual (tables), balance available for family support, check and DTI — all from Chapter 4."""
    va = fixture.get("va") or {}
    ws = fixture["workspace"]
    out: Dict[str, Any] = {"review": "va_residual_income", "calc_ids": [], "traces": [], "status": "OK", "warnings": []}

    def _run(fid, inputs):
        res = calc_mod.run(fid, inputs, active_check=active_check, source_meta=section_meta, program="va")
        out["traces"].append(res.to_dict())
        if res.status == "SUCCESS":
            out["calc_ids"].append(res.calc_id)
        return res

    required = _run("va.residual_income.required", {"family_size": va.get("family_size"), "loan_amount": ws.get("loan_amount"), "state": va.get("state")})
    residual = _run("va.residual_income.monthly", {"gross_monthly_income": gross_monthly, "federal_income_tax": va.get("federal_income_tax"), "state_income_tax": va.get("state_income_tax"),
                                                   "social_security_and_other_deductions": va.get("social_security_and_other_deductions"), "shelter_expense": ws.get("pitia"),
                                                   "gross_living_area_sqft": va.get("gross_living_area_sqft"), "maintenance_and_utilities": va.get("maintenance_and_utilities"),
                                                   "monthly_debts": va.get("monthly_debts")})
    if required.status != "SUCCESS" or residual.status != "SUCCESS":
        out.update({"status": "SOURCE_GAP" if "SOURCE_GAP" in (required.status, residual.status) else "NEEDS_INPUT", "note": "; ".join(required.warnings + residual.warnings)})
        return out
    check = _run("va.residual_income.check", {"residual_income": residual.result, "required_residual": required.result})
    dti = _run("va.dti.ratio", {"housing_expense": ws.get("pitia"), "installment_and_other_obligations": va.get("monthly_debts"), "gross_monthly_income": gross_monthly})
    out.update({"required_residual": required.result, "residual_income": residual.result, "percent_of_guideline": check.result, "dti_percent": dti.result,
                "region": next((s.get("value") for s in required.steps if s.get("op") == "region_lookup"), None)})
    notes = []
    if Decimal(check.result) < 100:
        out["status"] = "NEEDS_REVIEW"
        notes.append(f"residual income {residual.result} is below the Chapter 4 guideline {required.result}")
    if dti.status == "SUCCESS" and Decimal(dti.result) > 41 and Decimal(check.result) < 120:
        out["status"] = "NEEDS_REVIEW"
        notes.append(f"DTI {dti.result}% exceeds 41 percent and residual income does not exceed the guideline by 20 percent: supervisor justification statement required")
    out["warnings"] = notes
    out["note"] = "; ".join(notes) if notes else f"residual income {residual.result} meets the guideline {required.result} ({check.result}% of guideline); DTI {dti.result}%"
    return out


def run(fixture_path: Path, *, state_root: Path, knowledge_state: Optional[KnowledgeState] = None, tools=None, program: Optional[str] = None) -> Dict[str, Any]:
    """Execute the vertical slice for the fixture's program. ``tools`` is the flo_team.tools module (import lazily to avoid cycles)."""
    if tools is None:
        from . import tools as tools_mod

        tools = tools_mod
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    documents = fixture["documents"]
    ws_fx = fixture["workspace"]
    program = (program or ws_fx.get("agency") or "fannie").lower()
    method = (ws_fx.get("underwriting_method") or None)
    spec = sources.program_spec(program)
    kstate = knowledge_state or KnowledgeState(state_root)
    relevant_date = ws_fx.get("case_number_assignment_date") or ws_fx.get("relevant_date")
    active_check, section_meta = sources.checks_for(program, kstate, relevant_date=relevant_date, early_implementation=bool(ws_fx.get("early_implementation")))
    report_dates = {"relevant_date": relevant_date, "early_implementation": bool(ws_fx.get("early_implementation"))}
    aus_label = spec["aus_systems"][0]
    report: Dict[str, Any] = {"steps": [], "program": program, "underwriting_method": method}

    # 1. Flo opens the Deal Room
    with _Actor("flo"):
        ws = _j(tools.handle_flo_workspace({"action": "create", "display_name": ws_fx["display_name"],
                                            "fields": {"program": ws_fx["program"], "agency": ws_fx["agency"], "milestone": ws_fx["milestone"]}}))
        wid = ws["workspace_id"]
        tools.handle_flo_workspace({"action": "update", "workspace_id": wid, "fields": {"aus": {"path": aus_label, "recommendation_as_shown": None},
                                                                                        "status_summary": "File prep requested by Ashley"}})
        for doc in documents:
            tools.handle_flo_workspace({"action": "add", "workspace_id": wid, "list": "document_refs", "item": {"ref": doc["ref"], "type": doc["type"]}})
        handoff = _j(tools.handle_flo_handoff({"action": "create", "to": "malcolm", "workspace_id": wid, "urgency": "today", "return_format": "file_prep_report",
                                               "objective": f"Prep this file for submission and tell me what's missing ({spec['display']}, W-2 base income, {aus_label}" + (f" {method}" if method else "") + ").",
                                               "facts": [f"documents on file: {len(documents)}", f"{aus_label} findings present in document_refs", f"program: {program}" + (f"; underwriting method: {method}" if method else "")],
                                               "source_refs": [d["ref"] for d in documents]}))
        report["steps"].append({"step": "flo.handoff_to_malcolm", "task_id": handoff["task_id"], "send_with": handoff["send_with"]["tool"]})

    # 2. Malcolm reviews
    with _Actor("malcolm"):
        _j(tools.handle_flo_handoff({"action": "receive", "message": handoff["send_with"]["message"]}))
        aus_review = aus_mod.review(documents=documents, program=program, underwriting_method=method, active_check=active_check, section_meta=section_meta)
        income = income_review(documents, active_check=active_check, section_meta=section_meta, program=program, underwriting_method=method, fixture=fixture)
        residual = va_residual_review(fixture, income.get("qualifying_monthly") or "0", active_check=active_check, section_meta=section_meta) if program == "va" and income.get("qualifying_monthly") else None
        if residual:
            income["residual_income"] = residual
            if residual["status"] == "NEEDS_REVIEW":
                income["status"] = "NEEDS_REVIEW"
                income["warnings"] = income.get("warnings", []) + residual["warnings"]
        asset_review = assets_mod.review(accounts=accounts_from_documents(documents), transaction_type=ws_fx["transaction_type"],
                                         total_monthly_qualifying_income=income.get("qualifying_monthly") or "0", funds_needed=ws_fx["funds_needed"],
                                         application_date=ws_fx["application_date"], pitia=ws_fx.get("pitia"),
                                         aus_reserves_required=aus_review.get("reserves_required_to_be_verified"), active_check=active_check, section_meta=section_meta,
                                         program=program, underwriting_method=method, documentation_level=ws_fx.get("documentation_level"))
        matrix = fileprep.build_matrix(workspace={"workspace_id": wid, "estimated_note_date": ws_fx.get("estimated_note_date")}, documents=documents,
                                       application_date=ws_fx["application_date"], transaction_type=ws_fx["transaction_type"], income_review=income,
                                       asset_review=asset_review, active_check=active_check, section_meta=section_meta, program=program, underwriting_method=method,
                                       documentation_level=ws_fx.get("documentation_level"))
        tools.handle_flo_workspace({"action": "update", "workspace_id": wid, "fields": {"aus": {"path": aus_label, "recommendation_as_shown": aus_review.get("recommendation_as_shown"), "statement": aus_review.get("statement")}}})
        questions = income.get("guideline_questions", []) + [c["detail"] for c in aus_review.get("conflicts", [])]
        readiness = _j(tools.handle_flo_readiness({
            "workspace_id": wid, "checklist": fileprep.as_checklist(matrix),
            "aus_status": "present" if aus_review["present"] else "missing",
            "discrepancies": [w for w in income.get("warnings", [])] + [f"assets: {q}" for q in asset_review.get("sourcing_questions", [])],
            "income_prep_complete": income.get("status") == "OK", "assets_prep_complete": asset_review.get("status") == "OK",
            "open_questions": questions,
            "source_refs": [s.get("official_url") for s in matrix.get("sources", []) if s.get("official_url")],
        }))
        report["steps"].append({"step": "malcolm.review", "aus": aus_review["statement"], "income_status": income["status"], "assets_status": asset_review["status"],
                                "readiness": readiness["status"], "score": readiness["score"], "questions": questions})
        _j(tools.handle_flo_handoff({"action": "complete", "task_id": handoff["task_id"], "result": {
            "status": readiness["status"], "score": readiness["score"], "missing_items": [m["item"] for m in readiness["missing"]],
            "discrepancies": readiness["discrepancies"], "guideline_questions": questions, "external_action_status": "none"}}))

    # 3. Flo → Sage guideline questions
    cards = []
    with _Actor("flo"):
        for q in questions:
            h = _j(tools.handle_flo_handoff({"action": "create", "to": "sage", "workspace_id": wid, "objective": q, "return_format": "guideline_card", "urgency": "today"}))
            with _Actor("sage"):
                _j(tools.handle_flo_handoff({"action": "receive", "message": h["send_with"]["message"]}))
                card = _j(tools.handle_flo_guideline_card({"program": program, "topic": q, "aus_path": aus_label, "underwriting_method": method,
                                                           "aus_findings": [aus_review.get("statement")], "relevant_date": relevant_date,
                                                           "early_implementation": report_dates["early_implementation"]}))
                cards.append(card)
                _j(tools.handle_flo_handoff({"action": "complete", "task_id": h["task_id"], "result": {"status": "completed", "conclusion": card.get("conclusion"), "citations": [c["section"] for c in card.get("citations", [])]}}))
    report["steps"].append({"step": "sage.guideline_cards", "count": len(cards), "conclusions": [c.get("conclusion", "")[:120] for c in cards],
                            "sections": sorted({c["section"] for card in cards for c in card.get("citations", [])})})

    # 4. Flo → Whisper draft for missing borrower documents
    missing_borrower = [m for m in readiness["missing"] if m.get("owner") == "borrower"] + [
        {"item": f"{m.get('account_ref')}: {m.get('need')}", "owner": "borrower"} for m in asset_review.get("missing_statements_or_pages", [])]
    draft = None
    first_name = str(fixture.get("borrower", {}).get("first_name") or "there")
    with _Actor("flo"):
        h = _j(tools.handle_flo_handoff({"action": "create", "to": "whisper", "workspace_id": wid, "urgency": "today", "return_format": "communication_draft",
                                         "objective": "Draft the borrower request for the missing items: " + "; ".join(m["item"] for m in missing_borrower)}))
    with _Actor("whisper"):
        _j(tools.handle_flo_handoff({"action": "receive", "message": h["send_with"]["message"]}))
        body_lines = [f"Hi {first_name},", "", "We are close on your file. To keep things moving, we need:"] + [f"- {m['item']}" for m in missing_borrower] + [
            "", "You can reply to this email with the documents attached. Thank you!", "", "Ashley"]
        draft = _j(tools.handle_flo_draft({"action": "create", "workspace_id": wid, "audience": "borrower", "purpose": "missing document request",
                                           "body": "\n".join(body_lines), "urgency": "needs attention today", "needed": "; ".join(m["item"] for m in missing_borrower)}))
        _j(tools.handle_flo_handoff({"action": "complete", "task_id": h["task_id"], "result": {"status": "completed", "draft_id": draft["draft_id"], "external_action_status": "proposed"}}))
    report["steps"].append({"step": "whisper.draft", "draft_id": draft["draft_id"], "status": draft["status"]})

    # 5. Flo synthesis
    with _Actor("flo"):
        synthesis = {
            "program": spec["display"], "program_key": program, "underwriting_method": method, "aus_system": aus_label,
            "priority": readiness["best_next_move"],
            "status": f"{ws_fx['display_name']}: {readiness['status']} (readiness {readiness['score']}/100). {aus_review['statement']}",
            "readiness": {"status": readiness["status"], "score": readiness["score"], "components": readiness["score_components"], "disclaimer": readiness["disclaimer"]},
            "aus": {"statement": aus_review["statement"], "envelope": aus_review.get("envelope"), "requirements_missing": [r["text"] for r in aus_review.get("missing", [])], "conflicts": aus_review.get("conflicts", [])},
            "income": {"qualifying_monthly": income.get("qualifying_monthly"), "label": income.get("income_label"), "status": income["status"], "warnings": income.get("warnings", []),
                       "calc_ids": income.get("calc_ids", []), "w2_comparison": income.get("w2_comparison"), "residual_income": income.get("residual_income"), "household_income": income.get("household_income")},
            "assets": {"status": asset_review.get("status"), "available": asset_review.get("available_assets"), "eligible": asset_review.get("eligible_amount"), "funds_needed": asset_review.get("funds_needed"),
                       "sourcing_questions": asset_review.get("sourcing_questions", []), "missing_pages": asset_review.get("missing_statements_or_pages", []),
                       "reserves": (asset_review.get("reserves") or {}).get("months") or (asset_review.get("reserves") or {}).get("amount")},
            "missing_items": [m["item"] for m in readiness["missing"]],
            "risks": readiness["discrepancies"] + readiness.get("risks_questions", []),
            "best_next_move": readiness["best_next_move"],
            "draft_communication": {"draft_id": draft["draft_id"], "status": draft["status"], "audience": draft["audience"], "note": "sending stops at the Approval Center"},
            "source_links": sorted({c["official_url"] for card in cards for c in card.get("citations", []) if c.get("official_url")} | {s.get("official_url") for s in matrix.get("sources", []) if s.get("official_url")}),
            "guideline_cards": cards,
            "underwriting_decision": False,
        }
        tools.handle_flo_workspace({"action": "update", "workspace_id": wid, "fields": {"status_summary": synthesis["status"], "next_action": synthesis["best_next_move"]}})
    report.update({"workspace_id": wid, "synthesis": synthesis, "matrix": matrix, "asset_review": asset_review, "income_review": income, "aus_review": aus_review,
                   "du_review": aus_review if program == "fannie" else None, "readiness": readiness})
    return report
