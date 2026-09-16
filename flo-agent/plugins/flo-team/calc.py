"""Deterministic Calculation Workbench — code does the arithmetic, the model never does.

Contract (from .flo/docs/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md and the pack):

* A request names a ``formula_id`` from the formula registry, gives typed
  inputs (Decimal strings), and references the rule/source it relies on.
* The result records inputs, formula id/version, ordered arithmetic steps
  with intermediate values, rounding, the result, the rule/source reference
  and a status: ``SUCCESS | NEEDS_INPUT | SOURCE_GAP | UNSUPPORTED``.
* The trace is an auditable arithmetic record, not chain-of-thought.
* ``null`` is never zero: a missing input is ``NEEDS_INPUT``.
* PRODUCTION formulas are bound to one **program** (``fannie`` | ``freddie``
  | ``fha`` | ``va`` | ``usda``), for FHA to one **underwriting method**
  (``total`` | ``manual``), and to an official section through
  ``requires_section``. They run only while that section's revision is
  ACTIVE on this install; otherwise the result is ``SOURCE_GAP`` naming the
  section. A call for another program (or method) is refused —
  ``UNSUPPORTED`` with a program-mismatch warning — never silently re-bound.
* TEST_ONLY formulas (generic arithmetic) need ``allow_test_only=True`` and
  are labelled synthetic.
* Table values (VA residual income) are parsed from the cached official text
  at run time; no guideline number is typed into code.
* No runtime eval of model-generated formulas or source text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Optional, Tuple

from .store import new_id, now_iso

CALC_VERSION = "0.3.0"
STATUSES = ("SUCCESS", "NEEDS_INPUT", "SOURCE_GAP", "UNSUPPORTED")
FREQUENCIES = ("annual", "monthly", "twice_monthly", "semi_monthly", "biweekly", "weekly", "hourly")
PROGRAMS = ("fannie", "freddie", "fha", "va", "usda")


class SourceGap(Exception):
    """Raised inside a formula when the cached official text cannot supply a required value."""


@dataclass(frozen=True)
class Formula:
    formula_id: str
    version: str
    description: str
    inputs: Tuple[str, ...]
    tier: str                      # TEST_ONLY | PRODUCTION
    rule_ref: Optional[str]        # rule id from knowledge/<program>/rules.json when PRODUCTION
    steps: Callable[[Dict[str, Any], List[Dict[str, Any]], List[str]], Decimal]
    unit: str = "USD"
    period: str = "monthly"
    requires_section: Optional[str] = None
    optional_inputs: Tuple[str, ...] = ()
    text_inputs: Tuple[str, ...] = ()
    list_inputs: Tuple[str, ...] = ()
    program: str = "fannie"
    underwriting_method: Optional[str] = None


@dataclass
class CalcResult:
    calc_id: str
    formula_id: Optional[str]
    formula_version: Optional[str]
    status: str
    inputs: Dict[str, Optional[str]]
    steps: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[str] = None
    unit: Optional[str] = None
    period: Optional[str] = None
    rounding: str = "ROUND_HALF_UP to 0.01 at final step only"
    rule_ref: Optional[str] = None
    source: Optional[Dict[str, Any]] = None
    tier: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    missing_inputs: List[str] = field(default_factory=list)
    document_refs: List[str] = field(default_factory=list)
    program: Optional[str] = None
    underwriting_method: Optional[str] = None
    calculator_version: str = CALC_VERSION
    generated_at: str = field(default_factory=now_iso)
    underwriting_decision: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calc_id": self.calc_id, "formula_id": self.formula_id, "formula_version": self.formula_version,
            "status": self.status, "inputs": self.inputs, "steps": self.steps, "result": self.result,
            "unit": self.unit, "period": self.period, "rounding": self.rounding, "rule_ref": self.rule_ref, "source": self.source,
            "tier": self.tier, "warnings": self.warnings, "missing_inputs": self.missing_inputs, "document_refs": self.document_refs,
            "program": self.program, "underwriting_method": self.underwriting_method,
            "calculator_version": self.calculator_version, "generated_at": self.generated_at,
            "underwriting_decision": False,
            "note": "arithmetic trace only; does not establish eligibility or approval",
        }


def _d(value: Any) -> Optional[Decimal]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"not a decimal: {value!r}")


def _dlist(value: Any) -> Optional[List[Decimal]]:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        text = value.strip()
        try:
            value = json.loads(text) if text.startswith("[") else [p for p in text.split(",") if p.strip()]
        except json.JSONDecodeError:
            raise ValueError(f"not a list of decimals: {value!r}")
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"not a list of decimals: {value!r}")
    return [Decimal(str(v)) for v in value]


def _step(steps, op, **kw):
    steps.append({"op": op, **{k: (str(v) if isinstance(v, Decimal) else v) for k, v in kw.items()}})


def _monthly_from_frequency(amt: Decimal, freq: str, hours: Optional[Decimal], steps, label: str) -> Decimal:
    """Pay-period → monthly arithmetic shared by the programs whose guide states it (or, for FHA, plain annualization)."""
    if freq == "annual":
        v = amt / Decimal(12)
        _step(steps, "divide", left=amt, right="12", value=v, rule=f"{label}: annual gross pay / 12 months")
    elif freq == "monthly":
        v = amt
        _step(steps, "identity", value=v, rule=f"{label}: use monthly gross pay")
    elif freq in ("twice_monthly", "semi_monthly"):
        annual = amt * 24
        _step(steps, "multiply", left=amt, right="24", value=annual, rule=f"{label}: semi-monthly gross pay x 24")
        v = annual / Decimal(12)
        _step(steps, "divide", left=annual, right="12", value=v)
    elif freq == "biweekly":
        annual = amt * 26
        _step(steps, "multiply", left=amt, right="26", value=annual, rule=f"{label}: bi-weekly gross pay x 26")
        v = annual / Decimal(12)
        _step(steps, "divide", left=annual, right="12", value=v)
    elif freq == "weekly":
        annual = amt * 52
        _step(steps, "multiply", left=amt, right="52", value=annual, rule=f"{label}: weekly gross pay x 52")
        v = annual / Decimal(12)
        _step(steps, "divide", left=annual, right="12", value=v)
    elif freq == "hourly":
        if hours is None:
            raise KeyError("hours_per_week")
        weekly = amt * hours
        _step(steps, "multiply", left=amt, right=hours, value=weekly, rule=f"{label}: hourly rate x hours per week")
        annual = weekly * 52
        _step(steps, "multiply", left=weekly, right="52", value=annual, rule="x 52 weeks")
        v = annual / Decimal(12)
        _step(steps, "divide", left=annual, right="12", value=v, rule="/ 12 months")
    else:
        raise ValueError(f"pay_frequency must be one of {FREQUENCIES}")
    return v


# --- TEST_ONLY generic arithmetic (no mortgage rule semantics) ---------------

def _average_of_periods(i, steps, warnings) -> Decimal:
    if i["period_count"] <= 0:
        raise ValueError("period_count must be > 0")
    v = i["total_amount"] / i["period_count"]
    _step(steps, "divide", left=i["total_amount"], right=i["period_count"], value=v)
    return v


def _ratio_percent(i, steps, warnings) -> Decimal:
    if i["denominator"] == 0:
        raise ValueError("denominator must not be zero")
    v = i["numerator"] / i["denominator"] * 100
    _step(steps, "divide", left=i["numerator"], right=i["denominator"], value=i["numerator"] / i["denominator"])
    _step(steps, "multiply", right="100", value=v)
    return v


# --- PRODUCTION: Fannie Mae Selling Guide B3-3.3-01 (Base Income) -----------

def _base_income_monthly(i, steps, warnings) -> Decimal:
    """Monthly income by pay frequency — the B3-3.3-01 calculation table."""
    freq = str(i["pay_frequency"]).lower()
    if freq == "semi_monthly":
        freq = "twice_monthly"
    if freq == "twice_monthly":
        v = i["gross_pay"] * 2
        _step(steps, "multiply", left=i["gross_pay"], right="2", value=v, rule="B3-3.3-01: twice-monthly gross pay x 2 pay periods")
        return v
    return _monthly_from_frequency(i["gross_pay"], freq, i.get("hours_per_week"), steps, "B3-3.3-01")


def _variable_average_income(i, steps, warnings) -> Decimal:
    """B3-3.3-01 variable base income, average income method with trend."""
    ytd, ytd_m, prior, prior_m = i["ytd_amount"], i["ytd_months"], i["prior_year_amount"], i["prior_year_months"]
    if ytd_m <= 0 or prior_m <= 0:
        raise ValueError("months must be > 0")
    ytd_monthly = ytd / ytd_m
    prior_monthly = prior / prior_m
    _step(steps, "divide", left=ytd, right=ytd_m, value=ytd_monthly, rule="year-to-date monthly rate")
    _step(steps, "divide", left=prior, right=prior_m, value=prior_monthly, rule="prior-year monthly rate")
    total_months = ytd_m + prior_m
    if total_months < 12:
        raise ValueError("the calculation must include a minimum of 12 months' income (B3-3.3-01)")
    if ytd_monthly < prior_monthly:
        trend = "decreasing"
        v = ytd_monthly
        _step(steps, "trend", value="decreasing", rule="decreasing: use year-to-date income / months elapsed; confirm stabilization (B3-3.3-01)")
        warnings.append("Declining trend: qualifying only if the current income level has stabilized after the decline (B3-3.3-01); otherwise not eligible. Confirm with UW.")
    else:
        trend = "stable_or_increasing"
        v = (ytd + prior) / total_months
        _step(steps, "add", left=ytd, right=prior, value=ytd + prior)
        _step(steps, "divide", left=ytd + prior, right=total_months, value=v, rule="average over months covered (stable/increasing)")
    _step(steps, "trend_result", value=trend)
    return v


def _variable_average_hours(i, steps, warnings) -> Decimal:
    """B3-3.3-01 average hours method: avg monthly hours (>=12 months) x current fixed hourly rate."""
    if i["months_of_hours_history"] < 12:
        raise ValueError("average hours must be based on at least the most recent 12 months (B3-3.3-01)")
    v = i["average_monthly_hours"] * i["hourly_rate"]
    _step(steps, "multiply", left=i["average_monthly_hours"], right=i["hourly_rate"], value=v, rule="average monthly hours x current fixed hourly rate")
    return v


def _ytd_consistency(i, steps, warnings) -> Decimal:
    """B3-3.3-01: qualifying income must be consistent with YTD base earnings; returns the ratio (%)."""
    q, ytd, ytd_m = i["qualifying_monthly"], i["ytd_amount"], i["ytd_months"]
    if ytd_m <= 0 or q == 0:
        raise ValueError("ytd_months must be > 0 and qualifying_monthly non-zero")
    ytd_monthly = ytd / ytd_m
    _step(steps, "divide", left=ytd, right=ytd_m, value=ytd_monthly, rule="year-to-date monthly rate")
    ratio = ytd_monthly / q * 100
    _step(steps, "divide", left=ytd_monthly, right=q, value=ytd_monthly / q)
    _step(steps, "multiply", right="100", value=ratio, rule="YTD rate as % of qualifying monthly")
    tol = i.get("review_tolerance_percent")
    if tol is None:
        tol = Decimal(5)
        warnings.append("review_tolerance_percent defaulted to 5: an internal review threshold, not a Selling Guide number; the guide requires consistency without stating a percentage.")
    if abs(ratio - 100) > tol:
        warnings.append(f"YTD rate differs from qualifying monthly by more than {tol}%: needs review / explanation (B3-3.3-01 consistency).")
    if ytd_m * 30 < 30:
        warnings.append("YTD reflects fewer than 30 days of earnings: confirm consistency with the prior year's earnings (B3-3.3-01).")
    return ratio


def _large_deposit_threshold(i, steps, warnings) -> Decimal:
    v = i["total_monthly_qualifying_income"] * Decimal("0.5")
    _step(steps, "multiply", left=i["total_monthly_qualifying_income"], right="0.50", value=v, rule="large deposit = single deposit > 50% of total monthly qualifying income (B3-4.2-02)")
    return v


def _du_dti_resubmission(i, steps, warnings) -> Decimal:
    """B3-2-10: resubmit if recalculated DTI > 45% or increased by >= 3 points. Returns the point change."""
    delta = i["recalculated_dti"] - i["du_dti"]
    _step(steps, "subtract", left=i["recalculated_dti"], right=i["du_dti"], value=delta, rule="DTI change in percentage points")
    if i["recalculated_dti"] > 45 or delta >= 3:
        warnings.append("Resubmission to DU required: recalculated DTI exceeds 45% or increased by 3 or more percentage points (B3-2-10).")
    else:
        warnings.append("Within DU tolerance (B3-2-10): no resubmission required for DTI.")
    return delta


def _reserves_months(i, steps, warnings) -> Decimal:
    if i["pitia"] <= 0:
        raise ValueError("pitia must be > 0")
    v = i["liquid_reserves"] / i["pitia"]
    _step(steps, "divide", left=i["liquid_reserves"], right=i["pitia"], value=v, rule="months of PITIA from liquid reserves (B3-4.1-01)")
    return v


# --- PRODUCTION: Freddie Mac Guide 5303.1 / 5501.x / 5101.3 / 5401.2 -----------

def _freddie_base_monthly(i, steps, warnings) -> Decimal:
    """5303.1(c)(i) calculation table: weekly x52/12, bi-weekly x26/12, semi-monthly x24/12, monthly, annual/12."""
    freq = str(i["pay_frequency"]).lower()
    if freq == "twice_monthly":
        freq = "semi_monthly"
    if freq == "hourly":
        # 5303.1 treats a fixed hourly rate with guaranteed/minimum hours as non-fluctuating; conversion uses the weekly row.
        hours = i.get("hours_per_week")
        if hours is None:
            raise KeyError("hours_per_week")
        weekly = i["gross_pay"] * hours
        _step(steps, "multiply", left=i["gross_pay"], right=hours, value=weekly, rule="5303.1(c)(i): hourly rate x documented minimum/required hours per week = weekly gross pay")
        return _monthly_from_frequency(weekly, "weekly", None, steps, "5303.1(c)(i)")
    return _monthly_from_frequency(i["gross_pay"], freq, None, steps, "5303.1(c)(i)")


def _freddie_fluctuating_hourly(i, steps, warnings) -> Decimal:
    """5303.1(d)(i): average most recent year(s) + YTD for consistent/increasing trends; YTD only for declining; fluctuation bands."""
    ytd, ytd_m, prior, prior_m = i["ytd_amount"], i["ytd_months"], i["prior_year_amount"], i["prior_year_months"]
    if ytd_m <= 0 or prior_m <= 0:
        raise ValueError("months must be > 0")
    ytd_monthly = ytd / ytd_m
    prior_monthly = prior / prior_m
    _step(steps, "divide", left=ytd, right=ytd_m, value=ytd_monthly, rule="YTD monthly rate")
    _step(steps, "divide", left=prior, right=prior_m, value=prior_monthly, rule="prior-year monthly rate")
    if prior_monthly == 0:
        raise ValueError("prior_year_amount must be > 0 for trend analysis (5303.1(d)(i))")
    fluctuation = (ytd_monthly - prior_monthly) / prior_monthly * 100
    _step(steps, "fluctuation_percent", left=ytd_monthly, right=prior_monthly, value=fluctuation, rule="degree of fluctuation = (YTD rate - prior rate) / prior rate")
    if ytd_monthly < prior_monthly:
        v = ytd_monthly
        _step(steps, "trend", value="declining", rule="5303.1(d)(i) declining trend: use the YTD income; do not include the previous higher level")
        if abs(fluctuation) > 10:
            warnings.append("Declining trend exceeds 10%: the Seller must analyze the reason for the decline and support that current income has stabilized (5303.1(d)(i)); the YTD-based amount is not usable until then.")
        else:
            warnings.append("Declining trend (10% or less): YTD income used per 5303.1(d)(i); document the reason.")
    else:
        total_months = ytd_m + prior_m
        if ytd_m + prior_m < 12:
            warnings.append("Fewer than 12 months averaged: base fluctuating hourly earnings need at least a 12-month history (5303.1(d)(i)).")
        v = (ytd + prior) / total_months
        _step(steps, "add", left=ytd, right=prior, value=ytd + prior)
        _step(steps, "divide", left=ytd + prior, right=total_months, value=v, rule="5303.1(d)(i): average the most recent year(s) and YTD income")
        if fluctuation <= 10:
            _step(steps, "trend", value="consistent", rule="degree of fluctuation <= 10%: consistent; no additional analysis")
        elif fluctuation <= 30:
            _step(steps, "trend", value="increasing_10_to_30")
            warnings.append("Degree of fluctuation above 10% and up to 30%: acceptable without more analysis only when supported by a verified pay raise or documented income breakdown; otherwise additional analysis is required (5303.1(d)(i)).")
        else:
            _step(steps, "trend", value="increasing_over_30")
            warnings.append("Degree of fluctuation above 30%: additional analysis is required and additional documentation will likely be necessary (5303.1(d)(i)).")
    return v


def _freddie_large_deposit_threshold(i, steps, warnings) -> Decimal:
    base = i["total_monthly_qualifying_income"] + (i.get("asset_derived_monthly_amount") or Decimal(0))
    _step(steps, "add", left=i["total_monthly_qualifying_income"], right=i.get("asset_derived_monthly_amount") or Decimal(0), value=base,
          rule="5501.1(f)(ii): total monthly qualifying income + asset-derived amount used for the DTI ratio")
    v = base * Decimal("0.5")
    _step(steps, "multiply", left=base, right="0.50", value=v, rule="large deposit = any single deposit exceeding 50% of that sum")
    return v


def _freddie_reserves_months(i, steps, warnings) -> Decimal:
    if i["monthly_payment_amount"] <= 0:
        raise ValueError("monthly_payment_amount must be > 0")
    v = i["reserves"] / i["monthly_payment_amount"]
    _step(steps, "divide", left=i["reserves"], right=i["monthly_payment_amount"], value=v, rule="5501.2(a): reserves in months of the monthly payment amount")
    return v


def _freddie_lpa_dti_resubmission(i, steps, warnings) -> Decimal:
    delta = i["recalculated_dti"] - i["aus_dti"]
    _step(steps, "subtract", left=i["recalculated_dti"], right=i["aus_dti"], value=delta, rule="DTI change in percentage points")
    if i["recalculated_dti"] > 45 or delta > 3:
        warnings.append("Resubmission to Loan Product Advisor required: the new total DTI exceeds 45% or the total DTI changed by more than 3 percentage points (5101.3(b)).")
    else:
        warnings.append("Within Loan Product Advisor resubmission tolerance (5101.3(b)): DTI not above 45% and change not more than 3 points.")
    return delta


def _freddie_dti(i, steps, warnings) -> Decimal:
    if i["stable_monthly_income"] <= 0:
        raise ValueError("stable_monthly_income must be > 0")
    total = i["monthly_housing_expense"] + i["monthly_liabilities"]
    _step(steps, "add", left=i["monthly_housing_expense"], right=i["monthly_liabilities"], value=total, rule="5401.2: monthly housing expense + monthly liability payments")
    v = total / i["stable_monthly_income"] * 100
    _step(steps, "divide", left=total, right=i["stable_monthly_income"], value=total / i["stable_monthly_income"])
    _step(steps, "multiply", right="100", value=v, rule="DTI ratio (%)")
    if v > 45:
        warnings.append("DTI above 45%: a manually underwritten Mortgage is ineligible for sale to Freddie Mac (5401.2); for LPA Mortgages the Feedback Certificate governs.")
    elif v > 36:
        warnings.append("DTI above 36%: for manually underwritten Mortgages the Seller must document justification for the higher ratio (5401.2).")
    return v


# --- PRODUCTION: FHA Handbook 4000.1 II.A.4 (TOTAL) / II.A.5 (Manual) --------

def _fha_current_salary(i, steps, warnings) -> Decimal:
    """II.A.4.c / II.A.5.b (C)(1)-(2): current salary, or current hourly rate when hours do not vary."""
    freq = str(i["pay_frequency"]).lower()
    v = _monthly_from_frequency(i["current_salary_or_rate"], freq, i.get("hours_per_week"), steps, "Handbook 4000.1: current salary / current hourly rate")
    warnings.append("Handbook 4000.1 states 'use the current salary' / 'current hourly rate'; the pay-period-to-month conversion is plain annualization arithmetic, not a Handbook table.")
    return v


def _fha_hourly_varying(i, steps, warnings) -> Decimal:
    """II.A.4.c / II.A.5.b (C)(2): hours vary → average of the previous two years; with a documented raise, 12-month average hours x current rate."""
    if i.get("documented_pay_increase") and i.get("average_monthly_hours_12mo") is not None and i.get("current_hourly_rate") is not None:
        v = i["average_monthly_hours_12mo"] * i["current_hourly_rate"]
        _step(steps, "multiply", left=i["average_monthly_hours_12mo"], right=i["current_hourly_rate"], value=v,
              rule="documented pay-rate increase: most recent 12-month average of hours x current pay rate")
        return v
    total = i["prior_year_1_total"] + i["prior_year_2_total"]
    _step(steps, "add", left=i["prior_year_1_total"], right=i["prior_year_2_total"], value=total, rule="previous two years of income")
    v = total / Decimal(24)
    _step(steps, "divide", left=total, right="24", value=v, rule="average of the income over the previous two years (24 months)")
    return v


def _fha_overtime_bonus_tip(i, steps, warnings) -> Decimal:
    """(C): lesser of the two-year average (or the shorter period earned) and the one-year average."""
    months = i["months_earned"]
    if months <= 0 or months > 24:
        raise ValueError("months_earned must be between 1 and 24")
    if months < 12:
        warnings.append("Overtime/bonus/tip income earned for less than one year is not Effective Income unless consistently earned for at least one year and reasonably likely to continue.")
    avg_long = i["total_earned_period"] / months
    _step(steps, "divide", left=i["total_earned_period"], right=months, value=avg_long, rule="average over the previous two years or the period earned")
    avg_year = i["previous_year_total"] / Decimal(12)
    _step(steps, "divide", left=i["previous_year_total"], right="12", value=avg_year, rule="average over the previous year")
    v = min(avg_long, avg_year)
    _step(steps, "lesser_of", left=avg_long, right=avg_year, value=v, rule="Effective Income = the lesser of the two averages")
    return v


def _fha_large_deposit_threshold(i, steps, warnings) -> Decimal:
    v = i["total_monthly_effective_income"] * Decimal("0.5")
    _step(steps, "multiply", left=i["total_monthly_effective_income"], right="0.50", value=v, rule="deposits of more than 50 percent of the total monthly Effective Income must be documented")
    return v


def _fha_manual_ratios(i, steps, warnings) -> Decimal:
    """II.A.5.d(vii)-(viii): PTI = total Mortgage Payment / Effective Income; DTI = total fixed payment / Effective Income. Returns DTI."""
    if i["effective_income"] <= 0:
        raise ValueError("effective_income must be > 0")
    pti = i["total_mortgage_payment"] / i["effective_income"] * 100
    _step(steps, "divide", left=i["total_mortgage_payment"], right=i["effective_income"], value=pti / 100)
    _step(steps, "multiply", right="100", value=pti, rule="PTI: Total Mortgage Payment to Effective Income ratio (%)")
    fixed = i["total_mortgage_payment"] + i["other_monthly_obligations"]
    _step(steps, "add", left=i["total_mortgage_payment"], right=i["other_monthly_obligations"], value=fixed, rule="total fixed payment = total Mortgage Payment + monthly obligations")
    dti = fixed / i["effective_income"] * 100
    _step(steps, "divide", left=fixed, right=i["effective_income"], value=dti / 100)
    _step(steps, "multiply", right="100", value=dti, rule="DTI: Total Fixed Payment to Effective Income ratio (%)")
    _step(steps, "pti_result", value=pti.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if pti > 31 or dti > 43:
        warnings.append(f"PTI/DTI {pti.quantize(Decimal('0.1'))}/{dti.quantize(Decimal('0.1'))} exceeds 31/43: per the Approvable Ratio Requirements (Manual) chart this needs the listed compensating factors and a credit score of 580 or above (37/47 with one factor, 40/40 with no discretionary debt, 40/50 with two factors); below 580 or no score may not exceed 31/43.")
    else:
        warnings.append("PTI/DTI within 31/43: no compensating factors required under the Approvable Ratio Requirements (Manual) chart.")
    return dti


# --- PRODUCTION: VA Pamphlet 26-7 Chapter 4 (residual income, DTI) -------------

_VA_REGIONS = ("Northeast", "Midwest", "South", "West")


def va_residual_tables(text: str) -> Dict[str, Any]:
    """Parse Tables 9-11 from the cached official Chapter 4 text (no values typed into code)."""
    def _table(label: str):
        m = re.search(re.escape(label) + r".*?\|\s*Family Size\s*\|\s*Northeast\s*\|\s*Midwest\s*\|\s*South\s*\|\s*West\s*\|(.*?)For Family Size Over 5:\s*Add \$(\d+)", text, re.S)
        if not m:
            raise SourceGap(f"residual income table '{label}' not found in the cached official Chapter 4 text")
        rows = {}
        cells = [c.strip() for c in m.group(1).split("|") if c.strip()]
        for idx in range(0, len(cells) - 4, 5):
            size = int(cells[idx])
            rows[size] = {r: Decimal(cells[idx + 1 + j].replace("$", "").replace(",", "")) for j, r in enumerate(_VA_REGIONS)}
        return {"rows": rows, "over_5_increment": Decimal(m.group(2))}
    low = _table("Table 9: Table of Residual Incomes by Region for Loan Amounts of $79,999 and Below")
    high = _table("Table 10: Table of Residual Incomes by Region for Loan Amounts of $80,000 and Above")
    km = re.search(r"Table 11: Key to Geographic Regions.*?\|\s*Geographic Region\s*\|\s*States\s*\|(.*?)(?:Examples|$)", text, re.S)
    if not km:
        raise SourceGap("Table 11 (key to geographic regions) not found in the cached official Chapter 4 text")
    state_region: Dict[str, str] = {}
    cells = [c.strip() for c in km.group(1).split("|") if c.strip()]
    for idx in range(0, len(cells) - 1, 2):
        region = cells[idx]
        if region in _VA_REGIONS:
            for st in cells[idx + 1].split(","):
                state_region[st.strip().lower()] = region
    return {"below_80k": low, "80k_and_above": high, "state_region": state_region, "max_family_size": 7}


def _va_required_residual(i, steps, warnings) -> Decimal:
    tables = i["_va_tables"]
    state = str(i["state"]).strip().lower()
    region = tables["state_region"].get(state)
    if region is None:
        region_in = str(i.get("region") or "").strip().title()
        if region_in in _VA_REGIONS:
            region = region_in
        else:
            raise ValueError(f"state {i['state']!r} is not in Table 11 and no valid region was given")
    _step(steps, "region_lookup", left=i["state"], value=region, rule="Table 11: key to geographic regions")
    table = tables["below_80k"] if i["loan_amount"] < Decimal(80000) else tables["80k_and_above"]
    _step(steps, "loan_amount_category", left=i["loan_amount"], value="below_80k" if i["loan_amount"] < Decimal(80000) else "80k_and_above",
          rule="Table 9 for loan amounts of $79,999 and below; Table 10 for $80,000 and above")
    size = int(i["family_size"])
    if size < 1:
        raise ValueError("family_size must be >= 1")
    capped = min(size, tables["max_family_size"])
    base_size = min(capped, 5)
    v = table["rows"][base_size][region]
    _step(steps, "table_lookup", left=f"family size {base_size}", right=region, value=v, rule="residual income guideline from the table")
    if capped > 5:
        extra = table["over_5_increment"] * (capped - 5)
        _step(steps, "add", left=v, right=extra, value=v + extra, rule=f"family size over 5: add ${table['over_5_increment']} per additional member up to a family of seven")
        v = v + extra
    if size > tables["max_family_size"]:
        warnings.append(f"Family size {size}: members beyond seven are not considered in the calculation (Chapter 4 Topic 9).")
    return v


def _va_residual_income(i, steps, warnings) -> Decimal:
    """VA Form 26-6393 flow: gross income less taxes/deductions, shelter expense, maintenance & utilities and debts = balance available for family support."""
    gross = i["gross_monthly_income"]
    taxes = i["federal_income_tax"] + i["state_income_tax"] + i["social_security_and_other_deductions"]
    _step(steps, "add", value=taxes, rule="Items 32-35: Federal income tax + state income tax + social security/other deductions")
    net = gross - taxes
    _step(steps, "subtract", left=gross, right=taxes, value=net, rule="net take-home pay")
    mu = i.get("maintenance_and_utilities")
    if mu is None:
        sqft = i.get("gross_living_area_sqft")
        if sqft is None:
            raise KeyError("maintenance_and_utilities")
        mu = sqft * Decimal("0.14")
        _step(steps, "multiply", left=sqft, right="0.14", value=mu, rule="Item 19: maintenance and utilities at 14 cents per square foot of gross living area")
    shelter = i["shelter_expense"] + mu
    _step(steps, "add", left=i["shelter_expense"], right=mu, value=shelter, rule="total monthly shelter expense (PITI/other + maintenance and utilities)")
    v = net - shelter - i["monthly_debts"]
    _step(steps, "subtract", left=net, right=shelter + i["monthly_debts"], value=v, rule="Item 43: balance available for family support = net income - shelter expense - debts and obligations")
    return v


def _va_residual_check(i, steps, warnings) -> Decimal:
    """Residual income vs guideline: percent of guideline (>=100 meets; >=120 satisfies the 20% rule)."""
    if i["required_residual"] <= 0:
        raise ValueError("required_residual must be > 0")
    pct = i["residual_income"] / i["required_residual"] * 100
    _step(steps, "divide", left=i["residual_income"], right=i["required_residual"], value=pct / 100)
    _step(steps, "multiply", right="100", value=pct, rule="residual income as % of the guideline amount")
    if pct < 100:
        warnings.append("Residual income is below the guideline; inadequate residual income alone can be a basis for disapproval (Chapter 4 Topic 10) — the guideline is not an automatic trigger either way.")
    elif pct >= 120:
        warnings.append("Residual income exceeds the guideline by at least 20 percent: a DTI above 41 percent does not require the supervisor's justification statement (Chapter 4 Topic 10).")
    else:
        warnings.append("Residual income meets the guideline by less than 20 percent: a DTI above 41 percent still needs the supervisor's justification statement (Chapter 4 Topic 10).")
    return pct


def _va_dti(i, steps, warnings) -> Decimal:
    if i["gross_monthly_income"] <= 0:
        raise ValueError("gross_monthly_income must be > 0")
    total = i["housing_expense"] + i["installment_and_other_obligations"]
    _step(steps, "add", left=i["housing_expense"], right=i["installment_and_other_obligations"], value=total, rule="total monthly debt payments (housing expense, installment debts, other section D obligations)")
    v = total / i["gross_monthly_income"] * 100
    _step(steps, "divide", left=total, right=i["gross_monthly_income"], value=total / i["gross_monthly_income"])
    _step(steps, "multiply", right="100", value=v, rule="VA debt-to-income ratio (%)")
    if v > 41:
        warnings.append("Ratio above 41 percent requires close scrutiny and a supervisor-signed justification unless residual income exceeds the guideline by at least 20 percent (Chapter 4 Topic 10); DTI is secondary to residual income.")
    return v


# --- PRODUCTION: USDA HB-1-3555 (annual, adjusted annual, repayment income; ratios) -----

def _usda_annual_income(i, steps, warnings) -> Decimal:
    total = Decimal(0)
    for idx, amt in enumerate(i["adult_member_annual_incomes"]):
        total += amt
        _step(steps, "add", left=f"adult member {idx + 1}", right=amt, value=total, rule="9.3(B): gross annual income of every adult household member (not only note parties)")
    for idx, amt in enumerate(i.get("full_time_student_annual_incomes") or []):
        counted = min(amt, Decimal(480))
        total += counted
        _step(steps, "add", left=f"adult full-time student {idx + 1} (earned {amt})", right=counted, value=total, rule="9.3(B): include only the first $480 of an adult full-time student's earned income")
    return total


def _usda_adjusted_annual_income(i, steps, warnings) -> Decimal:
    deductions = Decimal(0)
    for idx, amt in enumerate(i.get("eligible_deductions") or []):
        deductions += amt
        _step(steps, "add", left=f"eligible deduction {idx + 1}", right=amt, value=deductions, rule="9.5: eligible deductions under 7 CFR 3555.152(c) (dependents, child care, elderly household, disability care, medical)")
    v = i["annual_income"] - deductions
    _step(steps, "subtract", left=i["annual_income"], right=deductions, value=v, rule="9.5: adjusted annual income = annual income - eligible deductions")
    warnings.append("Compare adjusted annual income to the published area income limit for the household size, county and state (GUS/Agency limits are not in the cache; SOURCE_GAP for the limit itself).")
    return v


def _usda_repayment_income(i, steps, warnings) -> Decimal:
    total = Decimal(0)
    for idx, amt in enumerate(i["note_party_monthly_incomes"]):
        total += amt
        _step(steps, "add", left=f"note party {idx + 1}", right=amt, value=total, rule="9.7: repayment income = stable and dependable monthly income of the applicants who will be parties to the note")
    return total


def _usda_ratios(i, steps, warnings) -> Decimal:
    if i["repayment_income"] <= 0:
        raise ValueError("repayment_income must be > 0")
    piti_ratio = i["piti"] / i["repayment_income"] * 100
    _step(steps, "divide", left=i["piti"], right=i["repayment_income"], value=piti_ratio / 100)
    _step(steps, "multiply", right="100", value=piti_ratio, rule="11.2(A): PITI ratio (%) of repayment income")
    total = i["piti"] + i["other_monthly_debts"]
    _step(steps, "add", left=i["piti"], right=i["other_monthly_debts"], value=total, rule="11.2(B): total debts = PITI + other monthly obligations")
    td = total / i["repayment_income"] * 100
    _step(steps, "divide", left=total, right=i["repayment_income"], value=td / 100)
    _step(steps, "multiply", right="100", value=td, rule="11.2(B): total debt ratio (%) of repayment income")
    _step(steps, "piti_ratio_result", value=piti_ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if piti_ratio > 29 or td > 41:
        warnings.append(f"PITI/TD {piti_ratio.quantize(Decimal('0.1'))}/{td.quantize(Decimal('0.1'))} exceeds 29/41: a debt ratio waiver with compensating factors is required (11.3); GUS Accept files follow the GUS findings.")
    else:
        warnings.append("PITI and total debt ratios within 29/41 (11.2).")
    return td


def _P(fid, version, desc, inputs, rule_ref, fn, *, program, section, method=None, **kw):
    return Formula(fid, version, desc, inputs, "PRODUCTION", rule_ref, fn, program=program, requires_section=section, underwriting_method=method, **kw)


FORMULAS: Dict[str, Formula] = {
    f.formula_id: f for f in (
        Formula("test.average_of_periods", "1", "TEST_ONLY: total_amount / period_count", ("total_amount", "period_count"), "TEST_ONLY", None, _average_of_periods, program="test"),
        Formula("test.ratio_percent", "1", "TEST_ONLY: numerator / denominator * 100", ("numerator", "denominator"), "TEST_ONLY", None, _ratio_percent, unit="percent", period="n/a", program="test"),
        # Fannie Mae
        _P("fannie.base_income.monthly", "2026.09", "Monthly base income by pay frequency (annual, monthly, twice_monthly, biweekly, weekly, hourly)",
           ("gross_pay", "pay_frequency"), "fannie.base_income.calc_table", _base_income_monthly, program="fannie", section="B3-3.3-01",
           optional_inputs=("hours_per_week",), text_inputs=("pay_frequency",)),
        _P("fannie.variable_income.average_income", "2026.09", "Variable base income, average income method with trend (YTD + prior year over months covered, min 12 months)",
           ("ytd_amount", "ytd_months", "prior_year_amount", "prior_year_months"), "fannie.base_income.variable_average_income", _variable_average_income, program="fannie", section="B3-3.3-01"),
        _P("fannie.variable_income.average_hours", "2026.09", "Variable base income, average hours method (avg monthly hours over >= 12 months x fixed hourly rate)",
           ("average_monthly_hours", "hourly_rate", "months_of_hours_history"), "fannie.base_income.variable_average_hours", _variable_average_hours, program="fannie", section="B3-3.3-01"),
        _P("fannie.income.ytd_consistency", "2026.09", "YTD base earnings vs qualifying monthly income (ratio %, review flag)",
           ("qualifying_monthly", "ytd_amount", "ytd_months"), "fannie.base_income.ytd_consistency", _ytd_consistency, program="fannie", section="B3-3.3-01",
           unit="percent", period="n/a", optional_inputs=("review_tolerance_percent",)),
        _P("fannie.assets.large_deposit_threshold", "2026.09", "Large deposit threshold = 50% of total monthly qualifying income",
           ("total_monthly_qualifying_income",), "fannie.assets.large_deposit_definition", _large_deposit_threshold, program="fannie", section="B3-4.2-02"),
        _P("fannie.du.dti_resubmission_check", "2026.09", "DU tolerance: DTI change in points and resubmission flag",
           ("du_dti", "recalculated_dti"), "fannie.du.resubmit_dti", _du_dti_resubmission, program="fannie", section="B3-2-10", unit="percentage_points", period="n/a"),
        _P("fannie.reserves.months", "2026.09", "Months of reserves = liquid reserves / PITIA",
           ("liquid_reserves", "pitia"), "fannie.reserves.definition", _reserves_months, program="fannie", section="B3-4.1-01", unit="months", period="n/a"),
        # Freddie Mac
        _P("freddie.base_income.monthly", "2026.09", "Base non-fluctuating earnings by pay period type (weekly x52/12, bi-weekly x26/12, semi-monthly x24/12, monthly, annual/12; hourly with documented required hours)",
           ("gross_pay", "pay_frequency"), "freddie.base_income.calc_table", _freddie_base_monthly, program="freddie", section="5303.1",
           optional_inputs=("hours_per_week",), text_inputs=("pay_frequency",)),
        _P("freddie.fluctuating_hourly.average", "2026.09", "Base fluctuating hourly earnings: average of most recent year(s) + YTD with degree-of-fluctuation bands; YTD only for a declining trend",
           ("ytd_amount", "ytd_months", "prior_year_amount", "prior_year_months"), "freddie.fluctuating_hourly.average_consistent_increasing", _freddie_fluctuating_hourly, program="freddie", section="5303.1"),
        _P("freddie.assets.large_deposit_threshold", "2026.09", "Large deposit threshold = 50% of (total monthly qualifying income + asset-derived DTI amount)",
           ("total_monthly_qualifying_income",), "freddie.assets.large_deposit_definition", _freddie_large_deposit_threshold, program="freddie", section="5501.1",
           optional_inputs=("asset_derived_monthly_amount",)),
        _P("freddie.reserves.months", "2026.09", "Reserves in months of the monthly payment amount",
           ("reserves", "monthly_payment_amount"), "freddie.reserves.definition", _freddie_reserves_months, program="freddie", section="5501.2", unit="months", period="n/a"),
        _P("freddie.lpa.dti_resubmission_check", "2026.09", "Loan Product Advisor resubmission tolerance: new DTI above 45% or change of more than 3 points requires resubmission",
           ("aus_dti", "recalculated_dti"), "freddie.lpa.resubmit_dti_tolerance", _freddie_lpa_dti_resubmission, program="freddie", section="5101.3", unit="percentage_points", period="n/a"),
        _P("freddie.dti.ratio", "2026.09", "Monthly debt payment-to-income ratio (housing expense + liabilities) / stable monthly income",
           ("monthly_housing_expense", "monthly_liabilities", "stable_monthly_income"), "freddie.dti.definition", _freddie_dti, program="freddie", section="5401.2", unit="percent", period="n/a"),
        # FHA — TOTAL
        _P("fha.total.income.current_salary_monthly", "2026.09", "TOTAL: current salary (or current hourly rate when hours do not vary) as monthly Effective Income",
           ("current_salary_or_rate", "pay_frequency"), "fha.total.income.salary_calculation", _fha_current_salary, program="fha", section="II.A.4.c", method="total",
           optional_inputs=("hours_per_week",), text_inputs=("pay_frequency",)),
        _P("fha.total.income.hourly_varying_average", "2026.09", "TOTAL: hourly with varying hours — average of the previous two years, or 12-month average hours x current rate with a documented raise",
           ("prior_year_1_total", "prior_year_2_total"), "fha.total.income.hourly_calculation", _fha_hourly_varying, program="fha", section="II.A.4.c", method="total",
           optional_inputs=("average_monthly_hours_12mo", "current_hourly_rate", "documented_pay_increase")),
        _P("fha.total.income.overtime_bonus_tip", "2026.09", "TOTAL: overtime/bonus/tip — lesser of the two-year (or period earned) average and the one-year average",
           ("total_earned_period", "months_earned", "previous_year_total"), "fha.total.income.overtime_bonus_tip", _fha_overtime_bonus_tip, program="fha", section="II.A.4.c", method="total"),
        _P("fha.total.assets.large_deposit_threshold", "2026.09", "TOTAL: deposits above 50 percent of total monthly Effective Income require documentation",
           ("total_monthly_effective_income",), "fha.total.assets.checking_savings_large_deposits", _fha_large_deposit_threshold, program="fha", section="II.A.4.d", method="total"),
        # FHA — Manual
        _P("fha.manual.income.current_salary_monthly", "2026.09", "Manual: current salary (or current hourly rate when hours do not vary) as monthly Effective Income",
           ("current_salary_or_rate", "pay_frequency"), "fha.manual.income.salary_calculation", _fha_current_salary, program="fha", section="II.A.5.b", method="manual",
           optional_inputs=("hours_per_week",), text_inputs=("pay_frequency",)),
        _P("fha.manual.income.hourly_varying_average", "2026.09", "Manual: hourly with varying hours — average of the previous two years, or 12-month average hours x current rate with a documented raise",
           ("prior_year_1_total", "prior_year_2_total"), "fha.manual.income.hourly_calculation", _fha_hourly_varying, program="fha", section="II.A.5.b", method="manual",
           optional_inputs=("average_monthly_hours_12mo", "current_hourly_rate", "documented_pay_increase")),
        _P("fha.manual.income.overtime_bonus_tip", "2026.09", "Manual: overtime/bonus/tip — lesser of the two-year (or period earned) average and the one-year average",
           ("total_earned_period", "months_earned", "previous_year_total"), "fha.manual.income.overtime_bonus_tip", _fha_overtime_bonus_tip, program="fha", section="II.A.5.b", method="manual"),
        _P("fha.manual.assets.large_deposit_threshold", "2026.09", "Manual: deposits above 50 percent of total monthly Effective Income require documentation",
           ("total_monthly_effective_income",), "fha.manual.assets.checking_savings_large_deposits", _fha_large_deposit_threshold, program="fha", section="II.A.5.c", method="manual"),
        _P("fha.manual.ratios.pti_dti", "2026.09", "Manual: PTI and DTI against the Approvable Ratio Requirements (Manual) chart (returns DTI; PTI in steps)",
           ("total_mortgage_payment", "other_monthly_obligations", "effective_income"), "fha.manual.ratios.pti_dti_definition", _fha_manual_ratios, program="fha", section="II.A.5.d", method="manual",
           unit="percent", period="n/a"),
        # VA
        _P("va.residual_income.required", "2026.09", "Required residual income from Tables 9/10/11 (family size, region by state, loan amount category; over-5 increments)",
           ("family_size", "loan_amount", "state"), "va.residual_income.tables", _va_required_residual, program="va", section="Chapter 4",
           optional_inputs=("region",), text_inputs=("state", "region")),
        _P("va.residual_income.monthly", "2026.09", "Balance available for family support (Form 26-6393): gross income - taxes/deductions - shelter expense - maintenance & utilities (14 cents/sqft) - debts",
           ("gross_monthly_income", "federal_income_tax", "state_income_tax", "social_security_and_other_deductions", "shelter_expense", "monthly_debts"),
           "va.residual_income.definition", _va_residual_income, program="va", section="Chapter 4", optional_inputs=("maintenance_and_utilities", "gross_living_area_sqft")),
        _P("va.residual_income.check", "2026.09", "Residual income as % of the guideline (100 = meets; 120 = exceeds by 20% for the DTI > 41% rule)",
           ("residual_income", "required_residual"), "va.residual_income.guide_not_trigger", _va_residual_check, program="va", section="Chapter 4", unit="percent", period="n/a"),
        _P("va.dti.ratio", "2026.09", "VA debt-to-income ratio (housing expense + installment/other obligations) / gross monthly income",
           ("housing_expense", "installment_and_other_obligations", "gross_monthly_income"), "va.dti.definition", _va_dti, program="va", section="Chapter 4", unit="percent", period="n/a"),
        # USDA
        _P("usda.annual_income.household", "2026.09", "Annual (household) income: gross annual income of every adult household member; first $480 of each adult full-time student",
           ("adult_member_annual_incomes",), "usda.annual_income.definition", _usda_annual_income, program="usda", section="9.3", period="annual",
           optional_inputs=("full_time_student_annual_incomes",), list_inputs=("adult_member_annual_incomes", "full_time_student_annual_incomes")),
        _P("usda.adjusted_annual_income", "2026.09", "Adjusted annual income = annual income - eligible 7 CFR 3555.152(c) deductions (eligibility income, never repayment income)",
           ("annual_income",), "usda.adjusted_annual_income.definition", _usda_adjusted_annual_income, program="usda", section="9.5", period="annual",
           optional_inputs=("eligible_deductions",), list_inputs=("eligible_deductions",)),
        _P("usda.repayment_income.monthly", "2026.09", "Repayment income: stable and dependable monthly income of the note parties only",
           ("note_party_monthly_incomes",), "usda.repayment_income.definition", _usda_repayment_income, program="usda", section="9.7-9.8", list_inputs=("note_party_monthly_incomes",)),
        _P("usda.ratios.piti_td", "2026.09", "PITI ratio and total debt ratio of repayment income against 29/41 (returns TD; PITI ratio in steps)",
           ("piti", "other_monthly_debts", "repayment_income"), "usda.ratios.total_debt_41", _usda_ratios, program="usda", section="11.2-11.3", unit="percent", period="n/a"),
    )
}


def list_formulas(program: Optional[str] = None) -> List[Dict[str, Any]]:
    return [{"formula_id": f.formula_id, "version": f.version, "tier": f.tier, "program": f.program, "underwriting_method": f.underwriting_method,
             "inputs": list(f.inputs), "optional_inputs": list(f.optional_inputs), "list_inputs": list(f.list_inputs),
             "description": f.description, "rule_ref": f.rule_ref, "requires_section": f.requires_section}
            for f in FORMULAS.values() if program is None or f.program == program.lower()]


def production_formulas(*, active_check: Optional[Callable[[str], bool]] = None, program: Optional[str] = None,
                        active_check_for: Optional[Callable[[str], Callable[[str], bool]]] = None) -> List[str]:
    """Production formulas whose section is active (all of them when no checker is given).

    ``active_check`` applies to every program (legacy, Fannie-only callers); ``active_check_for(program)``
    returns a per-program checker.
    """
    out = []
    for f in FORMULAS.values():
        if f.tier != "PRODUCTION" or (program and f.program != program.lower()):
            continue
        check = active_check_for(f.program) if active_check_for else active_check
        if check is not None and f.requires_section and not check(f.requires_section):
            continue
        out.append(f.formula_id)
    return out


def _default_active_check(program: str) -> Callable[[str], bool]:
    try:
        from . import sources

        return lambda section: sources.is_active(program, section)
    except Exception:  # pragma: no cover
        return lambda section: False


def _default_source_meta(program: str) -> Callable[[str], Dict[str, Any]]:
    def meta(section: str) -> Dict[str, Any]:
        try:
            from . import sources

            st = sources.section_status(program, section)
            return {"program": program, "section": st.section, "title": st.title, "official_url": st.official_url, "page_date": st.page_date,
                    "effective_date": st.effective_date, "in_force": st.in_force, "revision_id": st.revision_id, "checksum": (st.checksum or "")[:12]}
        except Exception:  # pragma: no cover
            return {"program": program, "section": section}
    return meta


def run(
    formula_id: str,
    inputs: Dict[str, Any],
    *,
    allow_test_only: bool = False,
    rule_ref: Optional[str] = None,
    document_refs: Optional[List[str]] = None,
    active_check: Optional[Callable[[str], bool]] = None,
    source_meta: Optional[Callable[[str], Dict[str, Any]]] = None,
    program: Optional[str] = None,
    underwriting_method: Optional[str] = None,
    source_text: Optional[Callable[[str], Optional[str]]] = None,
) -> CalcResult:
    calc_id = new_id("calc")
    raw_inputs = {str(k): (None if v is None else (json.dumps(v) if isinstance(v, (list, dict)) else str(v))) for k, v in (inputs or {}).items()}
    formula = FORMULAS.get(formula_id or "")
    if formula is None:
        return CalcResult(calc_id, formula_id, None, "UNSUPPORTED", raw_inputs, program=program, underwriting_method=underwriting_method,
                          warnings=[f"unknown formula {formula_id!r}; available: {sorted(FORMULAS)}"])
    base = CalcResult(calc_id, formula.formula_id, formula.version, "SOURCE_GAP", raw_inputs, tier=formula.tier,
                      rule_ref=rule_ref or formula.rule_ref, document_refs=list(document_refs or []),
                      program=formula.program, underwriting_method=formula.underwriting_method)
    # Fail closed on program / underwriting-method mismatch: a formula is never re-bound to another program.
    if program and formula.program != "test" and program.lower() != formula.program:
        base.status = "UNSUPPORTED"
        base.warnings.append(f"program mismatch: formula {formula.formula_id} is bound to {formula.program}; refusing to run it for {program.lower()} (fail closed)")
        return base
    if formula.underwriting_method:
        if not underwriting_method:
            base.status = "NEEDS_INPUT"
            base.missing_inputs = ["underwriting_method"]
            base.warnings.append(f"formula {formula.formula_id} is bound to the {formula.underwriting_method} underwriting method; state underwriting_method explicitly")
            return base
        if underwriting_method.lower() != formula.underwriting_method:
            base.status = "UNSUPPORTED"
            base.warnings.append(f"underwriting method mismatch: formula {formula.formula_id} is bound to {formula.underwriting_method}; refusing to run it for {underwriting_method.lower()} (fail closed)")
            return base
    if formula.tier == "TEST_ONLY" and not allow_test_only:
        base.warnings.append("formula is TEST_ONLY: no source backs it; it cannot produce qualifying income. Pass allow_test_only=true for a synthetic demonstration trace.")
        return base
    if formula.tier == "PRODUCTION" and formula.requires_section:
        check = active_check or _default_active_check(formula.program)
        if not check(formula.requires_section):
            from . import sources as _sources

            title = _sources.program_spec(formula.program)["source_title"]
            base.warnings.append(f"{title} {formula.requires_section} is not ACTIVE on this install; the formula is locked until a human activates the source revision.")
            return base
        base.source = (source_meta or _default_source_meta(formula.program))(formula.requires_section)
        if isinstance(base.source, dict) and base.source.get("in_force") is False:
            base.warnings.append(f"Section {formula.requires_section} as captured is effective {base.source.get('effective_date')} (not yet in force); the currently effective text is not in the cache.")
    typed: Dict[str, Any] = {}
    missing: List[str] = []
    for name in formula.inputs + formula.optional_inputs:
        raw = inputs.get(name) if inputs else None
        try:
            if name in formula.text_inputs:
                if raw is None or not str(raw).strip():
                    if name in formula.inputs:
                        missing.append(name)
                    continue
                typed[name] = str(raw).strip().lower()
                continue
            if name in formula.list_inputs:
                value = _dlist(raw)
            elif name == "documented_pay_increase":
                value = None if raw is None else bool(raw in (True, "true", "True", "1", 1, "yes"))
            else:
                value = _d(raw)
        except ValueError as exc:
            base.status = "NEEDS_INPUT"
            base.warnings.append(str(exc))
            return base
        if value is None:
            if name in formula.inputs:
                missing.append(name)
        else:
            typed[name] = value
    if missing:
        base.status = "NEEDS_INPUT"
        base.missing_inputs = missing
        base.warnings.append("missing inputs are not zero")
        return base
    if formula.formula_id == "va.residual_income.required":
        text = (source_text or _default_source_text(formula.program))(formula.requires_section)
        if not text:
            base.warnings.append("official Chapter 4 text is not in the private cache; residual income tables cannot be read")
            return base
        try:
            typed["_va_tables"] = va_residual_tables(text)
        except SourceGap as exc:
            base.warnings.append(str(exc))
            return base
    steps: List[Dict[str, Any]] = []
    warnings: List[str] = list(base.warnings)
    try:
        value = formula.steps(typed, steps, warnings)
    except KeyError as exc:
        base.status = "NEEDS_INPUT"
        base.missing_inputs = [str(exc).strip("'")]
        base.steps = steps
        return base
    except SourceGap as exc:
        base.status = "SOURCE_GAP"
        base.steps = steps
        base.warnings.append(str(exc))
        return base
    except (ValueError, ZeroDivisionError, InvalidOperation) as exc:
        base.status = "NEEDS_INPUT"
        base.steps = steps
        base.warnings.append(str(exc))
        return base
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    steps.append({"op": "round", "value": str(rounded), "mode": "ROUND_HALF_UP", "places": 2})
    if formula.tier == "TEST_ONLY":
        warnings.append("TEST_ONLY result: synthetic demonstration, not a guideline-supported calculation")
    base.status = "SUCCESS"
    base.steps = steps
    base.result = str(rounded)
    base.unit = formula.unit
    base.period = formula.period
    base.warnings = warnings
    return base


def _default_source_text(program: str) -> Callable[[str], Optional[str]]:
    def text(section: str) -> Optional[str]:
        try:
            from . import sources

            return sources.cached_text(program, section)
        except Exception:  # pragma: no cover
            return None
    return text
