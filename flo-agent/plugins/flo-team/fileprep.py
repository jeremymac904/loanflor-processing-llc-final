"""Malcolm's File Prep matrix — one builder, one binding per program.

Every requirement carries provenance:

* ``<program>:<section>`` — an ACTIVE official rule (knowledge/<program>/rules.json);
* ``<aus>:<message id>`` — a file-specific AUS findings verification message
  (du/lpa/total/gus/aus);
* ``workflow`` — LoanFlow internal workflow items (the supplied workflow
  source defines milestones only, so these are ``source_gap`` unless Ashley
  supplied them, in which case they carry ``ashley`` provenance).

States: complete | missing | needs_review | not_applicable | source_gap.
The matrix never invents a generic checklist: if a program's section is not
active, its items are ``source_gap`` naming the section. Fannie behaviour is
unchanged; the other bindings come from the captured official text.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from . import aus as aus_mod
from .store import now_iso

CATEGORIES = ("identity_application", "income", "employment", "assets", "aus", "property", "disclosures_workflow")

BINDINGS: Dict[str, Dict[str, Any]] = {
    "fannie": {
        "paystub": {"section": "B3-3.2-01", "rule": "fannie.docs.paystub", "age_days": 30, "age_from": "application",
                    "item": "Most recent paystub (dated within 30 days of application, with YTD earnings)"},
        "w2": {"section": "B3-3.2-01", "rule": "fannie.docs.w2", "years": 1, "item": "Most recent W-2 (tax year {year})"},
        "voe": {"section": "B3-3.3-01", "rule": "fannie.base_income.documentation", "item": "Verbal verification of employment (or Form 1005)", "kinds": ("voe", "verbal_voe")},
        "income_calc": {"section": "B3-3.3-01", "rule": "fannie.base_income.ytd_consistency", "item": "Base income calculation reconciled to YTD and W-2"},
        "assets": {"section": "B3-4.2-01", "rule": "fannie.assets.statement_period", "large_section": "B3-4.2-02", "large_rule": "fannie.assets.large_deposit_purchase",
                   "item": "Bank statements: most recent full {months}-month period, complete (all transactions and ending balance)", "months": {"purchase": 2, "refinance": 1}},
        "aus": {"section": "B3-2-11", "rule": "fannie.du.findings_report", "item": "DU Underwriting Findings report in file", "prefix": "du"},
        "age": {"section": "B1-1-03", "rule": "fannie.docs.age_four_months", "days": 120, "from": "note", "item": "Credit documents no more than four months old at the note date"},
        "matrix": "fannie_golden_loan_path",
    },
    "freddie": {
        "paystub": {"section": "5302.2", "rule": "freddie.docs.paystub", "age_days": 30, "age_from": "application",
                    "item": "Year-to-date paystub (dated within 30 days of the Application Received Date, with complete YTD earnings)"},
        "w2": {"section": "5302.2", "rule": "freddie.docs.w2", "years": 1, "item": "W-2 for the most recent calendar year ({year})"},
        "voe": {"section": "5302.2", "rule": "freddie.docs.ten_day_pcv", "item": "10-day pre-closing verification (Form 90 verbal VOE, e-mail VOE or written VOE)", "kinds": ("voe", "verbal_voe", "pcv", "ten_day_pcv")},
        "income_calc": {"section": "5303.1", "rule": "freddie.base_income.calc_table", "item": "Stable monthly income calculation by pay frequency, reconciled to YTD and W-2"},
        "assets": {"section": "5501.3", "rule": "freddie.assets.depository_documentation", "large_section": "5501.1", "large_rule": "freddie.assets.large_deposit_purchase",
                   "item": "Depository account statements per Documentation Level ({months}-month period) or VOD", "months": {"streamlined_accept": 1, "standard": 2}},
        "aus": {"section": "5101.1", "rule": "freddie.lpa.feedback_certificate", "item": "Loan Product Advisor Feedback Certificate (Last Feedback Certificate) in file", "prefix": "lpa"},
        "age": {"section": "5102.4", "rule": "freddie.docs.age_120_days", "days": 120, "from": "note", "item": "Verifications no more than 120 calendar days before the Note Date"},
        "matrix": "freddie_golden_loan_path",
    },
    "fha": {
        "total": {
            "paystub": {"section": "II.A.4.c", "rule": "fha.total.income.alternative_documentation", "age_days": None, "age_from": "application",
                        "item": "Most recent pay stub showing year-to-date earnings"},
            "w2": {"section": "II.A.4.c", "rule": "fha.total.income.alternative_documentation", "years": 2, "item": "Original IRS Form W-2s for the previous two years ({year} and prior)"},
            "voe": {"section": "II.A.4.c", "rule": "fha.total.income.traditional_documentation", "item": "Employment verification (WVOE/EVOE covering two years, or telephone verification) and Reverification of Employment within 10 Days prior to the Note", "kinds": ("voe", "verbal_voe", "wvoe", "evoe", "reverification")},
            "income_calc": {"section": "II.A.4.c", "rule": "fha.total.income.salary_calculation", "item": "Effective Income calculation (current salary / hourly rule) reconciled to YTD and W-2"},
            "assets": {"section": "II.A.4.d", "rule": "fha.total.assets.checking_savings_documentation", "large_section": "II.A.4.d", "large_rule": "fha.total.assets.checking_savings_large_deposits",
                       "item": "Checking/savings: VOD + most recent statement, or statement showing the previous month's ending balance (else two months)", "months": {"default": 1}},
            "aus": {"section": "II.A.4.a", "rule": "fha.total.scorecard.not_an_aus", "item": "TOTAL Mortgage Scorecard Feedback Certificate/Finding Report in the case binder", "prefix": "total"},
            "age": {"section": "II.A.1.a.i(A)(1)", "rule": "fha.docs.age_120_days", "days": 120, "from": "disbursement", "item": "Documents no more than 120 Days old at the Disbursement Date"},
            "matrix": "fha_total_golden_loan_path",
        },
        "manual": {
            "paystub": {"section": "II.A.5.b", "rule": "fha.manual.income.alternative_documentation", "age_days": None, "age_from": "application",
                        "item": "Most recent pay stubs showing year-to-date earnings (28 consecutive Days if paid weekly or biweekly)"},
            "w2": {"section": "II.A.5.b", "rule": "fha.manual.income.alternative_documentation", "years": 2, "item": "Original IRS Form W-2s for the previous two years ({year} and prior)"},
            "voe": {"section": "II.A.5.b", "rule": "fha.manual.income.traditional_documentation", "item": "Employment verification (WVOE/EVOE covering two years, or telephone verification) and Reverification of Employment within 10 Days prior to the Note", "kinds": ("voe", "verbal_voe", "wvoe", "evoe", "reverification")},
            "income_calc": {"section": "II.A.5.b", "rule": "fha.manual.income.salary_calculation", "item": "Effective Income calculation (current salary / hourly rule) reconciled to YTD and W-2"},
            "assets": {"section": "II.A.5.c", "rule": "fha.manual.assets.checking_savings_documentation", "large_section": "II.A.5.c", "large_rule": "fha.manual.assets.checking_savings_large_deposits",
                       "item": "Checking/savings: VOD + most recent statement, or statement showing the previous month's ending balance (else two months)", "months": {"default": 1}},
            "aus": {"section": "II.A.5.d", "rule": "fha.manual.ratios.pti_dti_definition", "item": "Manual underwriting: Approvable Ratio (PTI/DTI) worksheet and compensating factors documented", "prefix": "total"},
            "age": {"section": "II.A.1.a.i(A)(1)", "rule": "fha.docs.age_120_days", "days": 120, "from": "disbursement", "item": "Documents no more than 120 Days old at the Disbursement Date"},
            "matrix": "fha_manual_golden_loan_path",
        },
    },
    "va": {
        "paystub": {"section": "Chapter 4", "rule": "va.docs.standard_verification", "age_days": None, "age_from": "application",
                    "item": "Paystub(s) covering the most recent 30-day period with year-to-date information"},
        "w2": None,
        "voe": {"section": "Chapter 4", "rule": "va.docs.standard_verification", "item": "VA Form 26-8497 Request for Verification of Employment (or equivalent employment verification)", "kinds": ("voe", "verbal_voe", "va_voe", "26-8497")},
        "income_calc": {"section": "Chapter 4", "rule": "va.residual_income.definition", "item": "VA Form 26-6393 Loan Analysis: residual income and debt-to-income ratio worksheet"},
        "assets": {"section": "Chapter 4", "rule": "va.assets.verification", "large_section": None, "large_rule": None,
                   "item": "VA Form 26-8497a Verification of Deposit or the last two bank statements", "months": {"default": 2}},
        "aus": {"section": "Chapter 4", "rule": "va.aus.reduced_documentation", "item": "AUS findings (DU or LPA) with the VA risk classification in file", "prefix": "aus"},
        "age": {"section": "Chapter 4", "rule": "va.docs.age_120_days", "days": 120, "from": "closing", "item": "VOE, paystubs and deposit verifications no more than 120 days old at closing (180 for new construction)"},
        "matrix": "va_golden_loan_path",
    },
    "usda": {
        "paystub": {"section": "9.3", "rule": "usda.docs.paystub_30_days", "age_days": 30, "age_from": "application",
                    "item": "Paystub(s)/earning statement(s) with year-to-date earnings, dated within 30 days of the initial application"},
        "w2": {"section": "9.3", "rule": "usda.docs.paystub_30_days", "years": 1, "item": "W-2 for the most recent year ({year}) identifying applicant and employer"},
        "voe": {"section": "9.3", "rule": "usda.docs.verbal_voe_10_days", "item": "Verbal verification of employment within 10 business days of closing", "kinds": ("voe", "verbal_voe", "vvoe")},
        "income_calc": {"section": "9.7-9.8", "rule": "usda.repayment_income.definition", "item": "Annual, adjusted annual and repayment income calculated as three distinct figures"},
        "assets": {"section": "9-A", "rule": "usda.assets.depository_documentation", "large_section": "9-A", "large_rule": "usda.assets.deposit_investigation",
                   "item": "Two months of recent bank statements (or VOD + recent statement)", "months": {"default": 2}},
        "aus": {"section": "5.3", "rule": "usda.gus.recommendation", "item": "GUS underwriting recommendation / findings in file", "prefix": "gus"},
        "age": None,
        "matrix": "usda_golden_loan_path",
    },
}


def _date(v) -> Optional[date]:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v)).date()
    except ValueError:
        return None


def _docs(documents: List[Dict[str, Any]], kind: str) -> List[Dict[str, Any]]:
    return [d for d in documents or [] if str(d.get("type") or "").lower() == kind]


def _binding(program: str, underwriting_method: Optional[str]) -> Dict[str, Any]:
    program = (program or "fannie").lower()
    if program not in BINDINGS:
        raise ValueError(f"no file-prep binding for program {program!r}")
    b = BINDINGS[program]
    if program == "fha":
        method = (underwriting_method or "").lower()
        if method not in b:
            raise ValueError("fha file prep requires underwriting_method 'total' or 'manual'")
        return b[method]
    return b


def build_matrix(
    *,
    workspace: Dict[str, Any],
    documents: List[Dict[str, Any]],
    application_date: Optional[str] = None,
    transaction_type: str = "purchase",
    income_review: Optional[Dict[str, Any]] = None,
    asset_review: Optional[Dict[str, Any]] = None,
    extra_items: Optional[List[Dict[str, Any]]] = None,
    active_check: Optional[Callable[[str], bool]] = None,
    section_meta: Optional[Callable[[str], Dict[str, Any]]] = None,
    program: str = "fannie",
    underwriting_method: Optional[str] = None,
    documentation_level: Optional[str] = None,
) -> Dict[str, Any]:
    program = (program or "fannie").lower()
    b = _binding(program, underwriting_method)
    active_check = active_check or (lambda s: False)
    meta = section_meta or (lambda s: {"section": s})
    app = _date(application_date)
    items: List[Dict[str, Any]] = []

    def add(category, item, state, provenance, basis, evidence=None, owner="borrower", note=None):
        items.append({"category": category, "item": item, "state": state, "provenance": provenance, "basis": basis,
                      "evidence": evidence or [], "owner": owner, **({"note": note} if note else {})})

    def prov(section):
        return f"{program}:{section}"

    # --- Income / employment -------------------------------------------------
    ps, w2b, voe_b, ic = b["paystub"], b.get("w2"), b["voe"], b["income_calc"]
    if active_check(ps["section"]) and active_check(ic["section"]):
        stubs = _docs(documents, "paystub")
        latest = max(stubs, key=lambda d: d.get("pay_date") or "", default=None)
        if latest:
            state, note = "complete", None
            pd = _date(latest.get("pay_date"))
            if ps.get("age_days") and app and pd and (app - pd).days > ps["age_days"]:
                state, note = "needs_review", f"most recent paystub is dated more than {ps['age_days']} days before the application ({ps['section']})"
            if not latest.get("ytd_gross"):
                state, note = "needs_review", f"paystub does not show year-to-date earnings ({ps['section']})"
            add("income", ps["item"], state, prov(ps["section"]), ps["rule"], [latest.get("ref")], note=note)
        else:
            add("income", ps["item"], "missing", prov(ps["section"]), ps["rule"])
        if w2b:
            w2s = _docs(documents, "w2")
            current_year = (app or date.today()).year
            wanted = [current_year - 1 - k for k in range(w2b["years"])]
            have = [w for w in w2s if int(w.get("tax_year") or 0) in wanted]
            missing_years = [y for y in wanted if not any(int(w.get("tax_year") or 0) == y for w in w2s)]
            add("income", w2b["item"].format(year=current_year - 1), "complete" if not missing_years else ("needs_review" if have else "missing"), prov(w2b["section"]), w2b["rule"],
                [w.get("ref") for w in have], note=(f"W-2 missing for {', '.join(str(y) for y in missing_years)}" if missing_years else None))
        voe = [d for d in documents if str(d.get("type") or "").lower() in voe_b["kinds"]]
        add("employment", voe_b["item"], "complete" if voe else "missing", prov(voe_b["section"]), voe_b["rule"], [v.get("ref") for v in voe], owner="processor")
        if income_review:
            st = income_review.get("status")
            add("income", ic["item"], "complete" if st == "OK" else ("needs_review" if st == "NEEDS_REVIEW" else "missing"), prov(ic["section"]), ic["rule"],
                income_review.get("calc_ids", []), owner="processor", note=income_review.get("note"))
    else:
        for item in (ps["item"], (w2b or {}).get("item", "W-2").format(year="prior"), voe_b["item"]):
            add("income", item, "source_gap", prov(ps["section"]), "section not active on this install")

    # --- Assets ---------------------------------------------------------------
    ab = b["assets"]
    if active_check(ab["section"]) and (not ab.get("large_section") or active_check(ab["large_section"])):
        if program == "fannie":
            months = ab["months"].get(transaction_type, 2)
        elif program == "freddie":
            months = ab["months"].get((documentation_level or "standard").lower().replace(" ", "_"), 2)
        else:
            months = ab["months"]["default"]
        stmts = _docs(documents, "bank_statement")
        if asset_review:
            missing_pages = asset_review.get("missing_statements_or_pages") or []
            state = "needs_review" if (missing_pages or asset_review.get("sourcing_questions")) else ("complete" if stmts else "missing")
            note = "; ".join(m.get("need", "") + (f" ({m.get('statement_end')})" if m.get("statement_end") else "") for m in missing_pages) or None
        else:
            state = "complete" if len(stmts) >= months else "missing"
            note = None
        add("assets", ab["item"].format(months=months), state, prov(ab["section"]), ab["rule"], [s.get("ref") for s in stmts], note=note)
        if asset_review and asset_review.get("sourcing_questions") and ab.get("large_section"):
            add("assets", "Deposit sourcing / explanation", "needs_review", prov(ab["large_section"]), ab["large_rule"], [], note="; ".join(asset_review["sourcing_questions"])[:400])
        elif asset_review and asset_review.get("sourcing_questions"):
            add("assets", "Deposit sourcing / explanation", "needs_review", "workflow", "deposit questions raised by the workbench; no activated threshold rule", [], note="; ".join(asset_review["sourcing_questions"])[:400])
    else:
        add("assets", "Bank statements", "source_gap", prov(ab["section"]), "section not active on this install")

    # --- AUS -----------------------------------------------------------------
    aus_b = b["aus"]
    aus_review = aus_mod.review(documents=documents, program=program, underwriting_method=underwriting_method, active_check=active_check, section_meta=section_meta)
    aus_active = active_check(aus_b["section"])
    add("aus", aus_b["item"], "complete" if aus_review["present"] and aus_review["status"] != "mismatch" else ("needs_review" if aus_review["status"] == "mismatch" else "missing"),
        prov(aus_b["section"]) if aus_active else "workflow", aus_b["rule"] if aus_active else "file fact: findings document present/absent",
        [aus_review.get("document_ref")] if aus_review.get("document_ref") else [], owner="processor", note=aus_review.get("statement") if aus_review["status"] != "mismatch" else "; ".join(aus_review["warnings"]))
    prefix = (aus_review.get("aus_system") or aus_b["prefix"] or "aus").lower().replace("va_aus", "aus")
    for req in aus_review.get("requirements", []):
        add("aus", f"{prefix.upper()} message: {req['text']}", "complete" if req["state"] == "satisfied" else ("needs_review" if req["state"] in ("unknown", "needs_review") else "missing"),
            f"{prefix}:{req.get('message_id') or 'msg'}", "file-specific AUS verification message", req.get("evidence", []), note=req.get("note"))

    # --- Document age ---------------------------------------------------------
    age_b = b.get("age")
    if age_b and active_check(age_b["section"]):
        anchor = _date(workspace.get("estimated_note_date")) or _date(workspace.get("estimated_closing_date")) or (app + timedelta(days=45) if app else None)
        stale = []
        for d in documents:
            dd = _date(d.get("pay_date") or d.get("statement_end") or d.get("date"))
            if dd and anchor and (anchor - dd).days > age_b["days"]:
                stale.append(d.get("ref"))
        add("disclosures_workflow", age_b["item"], "needs_review" if stale else "complete", prov(age_b["section"]), age_b["rule"], stale, owner="processor",
            note=(f"documents that would exceed {age_b['days']} days at the estimated {age_b['from']} date: " + ", ".join(str(s) for s in stale)) if stale else None)
    elif age_b is None:
        add("disclosures_workflow", "Document age policy", "source_gap", "workflow", f"no document-age section in the activated {program} slice", owner="processor")

    # --- Program-specific processor worksheets -------------------------------
    if program == "va" and active_check("Chapter 4") and income_review:
        ri = income_review.get("residual_income") or {}
        add("income", "Residual income vs Chapter 4 guideline (Form 26-6393 Item 43)", "complete" if ri.get("status") == "OK" else ("needs_review" if ri else "missing"),
            prov("Chapter 4"), "va.residual_income.tables", ri.get("calc_ids", []), owner="processor", note=ri.get("note"))
    if program == "usda" and active_check("9.3") and income_review:
        hh = income_review.get("household_income") or {}
        add("income", "Annual and adjusted annual household income vs area income limit (GUS)", "needs_review" if hh else "missing", prov("9.3"), "usda.annual_income.definition",
            hh.get("calc_ids", []), owner="processor", note=hh.get("note"))

    # --- Identity / application / property / disclosures: workflow items ------
    add("identity_application", "Loan application (Form 1003) and identification", "source_gap", "workflow", "LoanFlow workflow source defines milestones only; no document requirement supplied", owner="processor")
    add("property", "Property documents (contract, appraisal) when available", "source_gap", "workflow", "not part of the activated slice", owner="processor")
    for extra in extra_items or []:
        add(str(extra.get("category") or "disclosures_workflow"), str(extra.get("item") or ""), str(extra.get("state") or "missing"), "ashley", "supplied by handoff/Ashley", extra.get("evidence") or [], owner=str(extra.get("owner") or "processor"))

    counts = {s: len([i for i in items if i["state"] == s]) for s in ("complete", "missing", "needs_review", "not_applicable", "source_gap")}
    bound_sections = sorted({v["section"] for k, v in b.items() if isinstance(v, dict) and v.get("section")} | {v["large_section"] for v in [b["assets"]] if v.get("large_section")})
    return {
        "matrix": b["matrix"], "program": program, "underwriting_method": underwriting_method, "workspace_id": workspace.get("workspace_id"), "generated_at": now_iso(),
        "items": items, "counts": counts, "du": aus_review if program == "fannie" else None, "aus": aus_review,
        "sources": [meta(s) for s in bound_sections if active_check(s)], "underwriting_decision": False,
    }


def as_checklist(matrix: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert matrix items to the readiness checklist shape (source_gap items excluded from the score)."""
    out = []
    for item in matrix.get("items", []):
        if item["state"] == "source_gap":
            continue
        state = {"complete": "complete", "missing": "missing", "needs_review": "conflicting" if item.get("note") and "discrep" in item["note"].lower() else "unknown", "not_applicable": "waived_by_ashley"}[item["state"]]
        out.append({"item": item["item"], "state": state, "owner": item.get("owner", "processor"), "source_ref": item["provenance"], "basis": item["basis"]})
    return out
