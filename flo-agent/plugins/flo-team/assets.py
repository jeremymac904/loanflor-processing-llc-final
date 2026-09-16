"""Basic Asset Workbench — depository accounts, one code path per program binding.

Every program binding names the ACTIVE official sections it relies on; the
workbench refuses to conclude (``SOURCE_GAP``) when any is not active and
never applies one program's rule to another program's file.

Bindings (all from captured official text; see knowledge/<program>/rules.json):

* fannie  — B3-4.2-01 statement content/period (2 months purchase, 1 refinance;
  45-day supplemental rule), B3-4.2-02 large deposit > 50% of qualifying
  income (purchase), B3-4.1-01 reserves in months of PITIA, B1-1-03 age.
* freddie — 5501.3 statement period by Documentation Level (Streamlined
  Accept: one-month statement or VOD; Standard: two-month statements or
  VOD), 5501.1(f) large deposit > 50% of (qualifying income + asset-derived
  amount) on purchases within 60 days before the Application Received Date,
  5501.2 reserves in months of the monthly payment amount, 5102.4 age.
* fha     — II.A.4.d (TOTAL) or II.A.5.c (Manual): VOD + most recent
  statement, or a statement showing the previous month's ending balance
  (else two months); deposits > 50% of total monthly Effective Income need
  documentation; reserves = liquid assets - funds required at closing.
* va      — Chapter 4: VOD or the last two bank statements, verifications no
  more than 120 days old; deposit-sourcing thresholds are SOURCE_GAP (not in
  the captured chapter).
* usda    — Attachment 9-A: two months of statements or VOD + recent
  statement; investigate non-recurring deposits over $1,000 and every
  recurring non-wage deposit.

Not implemented for any program (SOURCE_GAP): gifts, retirement, business
funds, sale proceeds, virtual currency, stock.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from . import calc as calc_mod
from .store import now_iso

UNSUPPORTED_TYPES = ("gift", "retirement", "business", "sale_proceeds", "crypto", "stock", "other")

# Legacy name kept for the Fannie Golden Loan Path tests.
REQUIRED_SECTIONS = ("B3-4.2-01", "B3-4.2-02", "B3-4.1-01", "B1-1-03")

BINDINGS: Dict[str, Dict[str, Any]] = {
    "fannie": {
        "sections": {"statement": "B3-4.2-01", "large_deposit": "B3-4.2-02", "reserves": "B3-4.1-01", "age": "B1-1-03"},
        "threshold_formula": "fannie.assets.large_deposit_threshold", "threshold_input": "total_monthly_qualifying_income",
        "reserves_formula": "fannie.reserves.months", "reserves_inputs": ("liquid_reserves", "pitia"),
        "months": {"purchase": 2, "refinance": 1}, "stale_days_before_application": 45, "large_deposit_scope": "purchase",
        "large_deposit_window_days": None, "reserves_note": "no minimum reserve requirement for a DU one-unit principal residence (B3-4.1-01); DU's Reserves Required to be Verified governs the file",
        "aus_reserves_label": "du_reserves_required",
    },
    "freddie": {
        "sections": {"statement": "5501.3", "large_deposit": "5501.1", "reserves": "5501.2", "age": "5102.4"},
        "threshold_formula": "freddie.assets.large_deposit_threshold", "threshold_input": "total_monthly_qualifying_income",
        "reserves_formula": "freddie.reserves.months", "reserves_inputs": ("reserves", "monthly_payment_amount"),
        "months": {"streamlined_accept": 1, "standard": 2}, "stale_days_before_application": None, "large_deposit_scope": "purchase",
        "large_deposit_window_days": 60, "reserves_note": "for Loan Product Advisor Mortgages verify all reserves required on the Feedback Certificate (5501.2(b)); manual one-unit primary residence: none required",
        "aus_reserves_label": "lpa_reserves_required",
    },
    "fha": {
        "sections": {"total": {"statement": "II.A.4.d", "large_deposit": "II.A.4.d", "reserves": "II.A.4.d", "age": "II.A.1.a.i(A)(1)"},
                     "manual": {"statement": "II.A.5.c", "large_deposit": "II.A.5.c", "reserves": "II.A.5.c", "age": "II.A.1.a.i(A)(1)"}},
        "threshold_formula": {"total": "fha.total.assets.large_deposit_threshold", "manual": "fha.manual.assets.large_deposit_threshold"},
        "threshold_input": "total_monthly_effective_income", "reserves_formula": None,
        "months": {"vod": 1, "prior_ending_balance_shown": 1, "default": 2}, "stale_days_before_application": None, "large_deposit_scope": "all",
        "large_deposit_window_days": None, "reserves_note": "Reserves = verified liquid assets minus funds required at closing (II.A.4.d/II.A.5.c); minimum months apply only to 1-unit with ADU using rental income (2) and 3-4 units (3)",
        "aus_reserves_label": "aus_reserves_required",
    },
    "va": {
        "sections": {"statement": "Chapter 4", "large_deposit": None, "reserves": None, "age": "Chapter 4"},
        "threshold_formula": None, "threshold_input": None, "reserves_formula": None,
        "months": {"default": 2}, "stale_days_before_application": None, "large_deposit_scope": "none",
        "large_deposit_window_days": None, "reserves_note": "VA Chapter 4 as captured states no reserve-months requirement for a one-unit purchase; reserves are a compensating factor",
        "aus_reserves_label": "aus_reserves_required",
    },
    "usda": {
        "sections": {"statement": "9-A", "large_deposit": "9-A", "reserves": None, "age": None},
        "threshold_formula": None, "threshold_input": None, "fixed_threshold": Decimal("1000"), "reserves_formula": None,
        "months": {"default": 2}, "stale_days_before_application": None, "large_deposit_scope": "all",
        "large_deposit_window_days": None, "reserves_note": "cash reserves are not required for SFHGLP eligibility (HB-1-3555 5.3(E)); GUS may consider them",
        "aus_reserves_label": "gus_reserves_required",
    },
}


def _d(v) -> Decimal:
    return Decimal(str(v))


def _date(v) -> Optional[date]:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v)).date()
    except ValueError:
        return None


def _binding(program: str, underwriting_method: Optional[str]) -> Dict[str, Any]:
    program = (program or "fannie").lower()
    if program not in BINDINGS:
        raise ValueError(f"no asset binding for program {program!r}")
    b = dict(BINDINGS[program])
    if program == "fha":
        method = (underwriting_method or "").lower()
        if method not in ("total", "manual"):
            raise ValueError("fha asset review requires underwriting_method 'total' or 'manual'")
        b["sections"] = b["sections"][method]
        b["threshold_formula"] = b["threshold_formula"][method]
    return b


def review(
    *,
    accounts: List[Dict[str, Any]],
    transaction_type: str,
    total_monthly_qualifying_income: Any,
    funds_needed: Any,
    application_date: Optional[str] = None,
    pitia: Any = None,
    du_reserves_required: Any = None,
    active_check: Optional[Callable[[str], bool]] = None,
    section_meta: Optional[Callable[[str], Dict[str, Any]]] = None,
    program: str = "fannie",
    underwriting_method: Optional[str] = None,
    documentation_level: Optional[str] = None,
    aus_reserves_required: Any = None,
) -> Dict[str, Any]:
    program = (program or "fannie").lower()
    b = _binding(program, underwriting_method)
    active_check = active_check or (lambda s: False)
    sections = {k: v for k, v in b["sections"].items() if v}
    required = sorted(set(sections.values()))
    inactive = [s for s in required if not active_check(s)]
    out: Dict[str, Any] = {
        "workbench": "assets_depository", "program": program, "underwriting_method": underwriting_method, "transaction_type": transaction_type,
        "generated_at": now_iso(), "sources": [], "warnings": [], "sourcing_questions": [], "missing_statements_or_pages": [], "unsupported": [],
        "source_gaps": [], "underwriting_decision": False,
    }
    if inactive:
        out["status"] = "SOURCE_GAP"
        out["warnings"].append(f"{program} official sections not active on this install: {', '.join(inactive)}; no asset conclusion.")
        return out
    for s in required:
        out["sources"].append(section_meta(s) if section_meta else {"section": s})
    for key in ("large_deposit", "reserves", "age"):
        if not b["sections"].get(key):
            out["source_gaps"].append(f"{key}: no activated {program} section in the slice; not evaluated")

    transaction_type = (transaction_type or "").lower()
    if program == "fannie":
        months_required = 2 if transaction_type == "purchase" else 1
        months_basis = f"{months_required} month(s) for a {transaction_type} (B3-4.2-01)"
    elif program == "freddie":
        level = (documentation_level or "standard").lower().replace(" ", "_")
        months_required = b["months"].get(level, 2)
        months_basis = f"{months_required} month(s) under {level.replace('_', ' ')} documentation (5501.3(a))" + ("" if documentation_level else "; Documentation Level not supplied, Standard assumed")
    elif program == "fha":
        months_required = 1
        months_basis = "VOD + most recent statement, or a statement showing the previous month's ending balance; otherwise two months (" + sections["statement"] + ")"
    elif program == "va":
        months_required = 2
        months_basis = "VOD (VA Form 26-8497a) or the last two bank statements (Chapter 4 Topic 4)"
    else:
        months_required = 2
        months_basis = "two months of recent bank statements, or VOD plus a recent statement (Attachment 9-A)"
    out["statement_requirement"] = months_basis

    income = _d(total_monthly_qualifying_income or 0)
    threshold: Optional[Decimal] = None
    if b.get("threshold_formula"):
        threshold_calc = calc_mod.run(b["threshold_formula"], {b["threshold_input"]: str(income)}, active_check=active_check, source_meta=section_meta,
                                      program=program, underwriting_method=underwriting_method)
        threshold = _d(threshold_calc.result) if threshold_calc.status == "SUCCESS" else None
        out["large_deposit_threshold"] = threshold_calc.to_dict()
    elif b.get("fixed_threshold") is not None:
        threshold = b["fixed_threshold"]
        out["large_deposit_threshold"] = {"status": "SUCCESS", "result": str(threshold), "basis": "Attachment 9-A: investigate individual (non-recurring) deposits greater than $1,000", "section": sections["large_deposit"]}
    else:
        out["large_deposit_threshold"] = {"status": "SOURCE_GAP", "note": f"no deposit-sourcing threshold in the activated {program} slice"}
    app_date = _date(application_date)

    available = Decimal(0)
    undocumented = Decimal(0)
    rows = []
    for acct in accounts or []:
        atype = str(acct.get("type") or "checking").lower()
        ref = acct.get("account_ref") or acct.get("ref") or "account"
        if atype in UNSUPPORTED_TYPES:
            out["unsupported"].append({"account_ref": ref, "type": atype, "note": f"SOURCE_GAP: asset type not in the activated {program} slice"})
            continue
        balance = _d(acct.get("ending_balance") or 0)
        row = {"account_ref": ref, "type": atype, "ending_balance": str(balance), "issues": [], "large_deposits": []}
        for field_name in ("institution", "account_holder", "last_four"):
            if not acct.get(field_name):
                row["issues"].append(f"statement missing {field_name} ({sections['statement']})")
        periods = acct.get("statement_periods") or []
        need = months_required
        if program == "fha" and periods and not (acct.get("vod") or periods[-1].get("prior_ending_balance_shown")):
            need = 2
        if acct.get("vod"):
            need = min(need, 1)
        if len(periods) < need:
            row["issues"].append(f"{len(periods)} statement period(s) on file; {need} required ({months_basis})")
            out["missing_statements_or_pages"].append({"account_ref": ref, "need": f"{need - len(periods)} more monthly statement(s)"})
        latest_end = None
        for p in periods:
            pages_present, pages_total = p.get("pages_present"), p.get("pages_total")
            if pages_total and pages_present is not None and int(pages_present) < int(pages_total):
                row["issues"].append(f"statement {p.get('end')} has {pages_present} of {pages_total} pages: incomplete, so it cannot show all transactions and the ending balance ({sections['statement']})")
                out["missing_statements_or_pages"].append({"account_ref": ref, "statement_end": p.get("end"), "need": f"pages {int(pages_present) + 1}-{pages_total}"})
            end = _date(p.get("end"))
            if end and (latest_end is None or end > latest_end):
                latest_end = end
        stale = b.get("stale_days_before_application")
        if stale and app_date and latest_end and (app_date - latest_end).days > stale:
            row["issues"].append(f"latest statement is more than {stale} days before application: supplemental bank-generated documentation required ({sections['statement']})")
        # Deposits
        for dep in acct.get("deposits") or []:
            amount = _d(dep.get("amount") or 0)
            dep_date = _date(dep.get("date"))
            recurring_wage = bool(dep.get("recurring")) or ("payroll" in str(dep.get("description") or "").lower())
            if program == "usda" and not recurring_wage and dep.get("recurring") and not dep.get("sourced"):
                out["sourcing_questions"].append(f"{ref}: recurring non-wage deposit {amount} on {dep.get('date')} must be investigated to rule out undisclosed income (Attachment 9-A; no tolerance)")
            if threshold is None or amount <= threshold or recurring_wage:
                continue
            sourced = bool(dep.get("sourced"))
            documented_portion = _d(dep.get("documented_amount") or (amount if sourced else 0))
            unsourced = amount - documented_portion
            entry = {"date": dep.get("date"), "amount": str(amount), "sourced": sourced, "unsourced_portion": str(unsourced)}
            row["large_deposits"].append(entry)
            if unsourced <= 0:
                continue
            scope = b["large_deposit_scope"]
            window = b.get("large_deposit_window_days")
            in_window = True if not window else (app_date is not None and dep_date is not None and 0 <= (app_date - dep_date).days <= window)
            if scope == "purchase" and transaction_type == "purchase" and (program == "fannie" or in_window) and unsourced > threshold:
                undocumented += unsourced
                out["sourcing_questions"].append(f"{ref}: deposit of {amount} on {dep.get('date')} exceeds the large-deposit threshold ({threshold}); source it or reduce verified funds by {unsourced} ({sections['large_deposit']})")
            elif scope == "purchase" and transaction_type == "purchase" and unsourced > threshold:
                out["sourcing_questions"].append(f"{ref}: large deposit {amount} on {dep.get('date')} falls outside the {window}-day window before the Application Received Date; not a documentation trigger under {sections['large_deposit']}, but identify any borrowed funds")
            elif scope == "purchase" and unsourced > threshold:
                out["sourcing_questions"].append(f"{ref}: large deposit {amount} on {dep.get('date')}; documentation not required on a refinance, but identify any borrowed funds/liabilities ({sections['large_deposit']})")
            elif scope == "all" and unsourced > threshold:
                undocumented += unsourced
                out["sourcing_questions"].append(f"{ref}: deposit of {amount} on {dep.get('date')} exceeds {threshold}; documentation/investigation required ({sections['large_deposit']})")
        available += balance
        rows.append(row)
    out["accounts"] = rows
    eligible = available - undocumented if b["large_deposit_scope"] in ("purchase", "all") and (transaction_type == "purchase" or b["large_deposit_scope"] == "all") else available
    needed = _d(funds_needed or 0)
    out["available_assets"] = str(available)
    out["undocumented_large_deposits"] = str(undocumented)
    out["eligible_amount"] = str(eligible)
    out["funds_needed"] = str(needed)
    out["surplus_after_funds_needed"] = str(eligible - needed)
    if eligible < needed:
        out["warnings"].append(f"eligible verified funds {eligible} are below funds needed {needed}")
    aus_req = aus_reserves_required if aus_reserves_required is not None else du_reserves_required
    if pitia and b.get("reserves_formula"):
        k_res, k_pay = b["reserves_inputs"]
        reserves = calc_mod.run(b["reserves_formula"], {k_res: str(max(eligible - needed, Decimal(0))), k_pay: str(pitia)}, active_check=active_check, source_meta=section_meta, program=program)
        out["reserves"] = {"months": reserves.result, "trace": reserves.to_dict(), b["aus_reserves_label"]: (str(aus_req) if aus_req is not None else None), "note": b["reserves_note"]}
        if program == "fannie" and aus_req is not None and (eligible - needed) < _d(aus_req) * Decimal("0.9"):
            out["warnings"].append("verified reserves are below 90% of DU's Reserves Required to be Verified: resubmission required (B3-2-10)")
        if program == "freddie" and aus_req is not None and (eligible - needed) < _d(aus_req):
            out["warnings"].append("verified reserves are below the reserves required on the Feedback Certificate: resubmission to Loan Product Advisor required (5101.3(b))")
    elif pitia:
        amount = max(eligible - needed, Decimal(0))
        out["reserves"] = {"amount": str(amount), "months": None, b["aus_reserves_label"]: (str(aus_req) if aus_req is not None else None), "note": b["reserves_note"],
                           "months_basis": "SOURCE_GAP: no months-of-reserves formula bound to an activated section for this program"}
    out["status"] = "NEEDS_REVIEW" if (out["sourcing_questions"] or out["missing_statements_or_pages"] or any(r["issues"] for r in rows) or out["warnings"]) else "OK"
    return out
