"""Self-employed and rental income — data structures only (no formulas).

The program expansion directive asks for the architecture and data
structures for self-employment (Schedule C, Form 1065, 1120, 1120-S, K-1,
P&L, balance sheet) and rental income (Schedule E, lease, appraisal rent
schedule, subject vs non-subject property, departing residence, rental loss)
without implementing calculations. Every calculation entry point here
returns ``SOURCE_GAP``: the applicable official sections (Fannie B3-3.2-01/
B3-3.4-*, B3-3.1-08; Freddie 5304.1, 5306.1; FHA II.A.4.c.x / II.A.5.b.x;
VA Chapter 4 Topic 2; USDA 9-A) are not in any activated slice, and no
formula may exist without a section binding.

The dataclasses are the typed inputs a future calculator will consume; they
carry document references so a trace can cite the exact form and tax year.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .store import new_id, now_iso

SELF_EMPLOYMENT_FORMS = ("schedule_c", "form_1065", "form_1120", "form_1120s", "schedule_k1", "profit_and_loss", "balance_sheet")
RENTAL_DOCUMENTS = ("schedule_e", "lease", "appraisal_rent_schedule_1007", "appraisal_rent_schedule_1025")
RENTAL_PROPERTY_ROLES = ("subject", "non_subject", "departing_residence")


@dataclass
class TaxFormRef:
    form: str                      # one of SELF_EMPLOYMENT_FORMS
    tax_year: int
    document_ref: str
    business_name: Optional[str] = None
    ownership_percent: Optional[str] = None
    line_items: Dict[str, str] = field(default_factory=dict)   # e.g. {"net_profit": "42000.00", "depreciation": "3100.00"}
    signed: Optional[bool] = None
    transcript_matched: Optional[bool] = None


@dataclass
class ProfitAndLoss:
    document_ref: str
    period_start: str
    period_end: str
    prepared_by: Optional[str] = None   # borrower | accountant | cpa_audited
    gross_revenue: Optional[str] = None
    net_income: Optional[str] = None


@dataclass
class BalanceSheet:
    document_ref: str
    as_of: str
    total_assets: Optional[str] = None
    total_liabilities: Optional[str] = None


@dataclass
class SelfEmploymentIncome:
    borrower_ref: str
    business_name: str
    entity_type: str                    # sole_proprietor | partnership | s_corp | c_corp
    ownership_percent: Optional[str]
    years_in_business: Optional[str]
    tax_forms: List[TaxFormRef] = field(default_factory=list)
    profit_and_loss: Optional[ProfitAndLoss] = None
    balance_sheet: Optional[BalanceSheet] = None
    program: Optional[str] = None
    underwriting_method: Optional[str] = None
    structure_id: str = field(default_factory=lambda: new_id("sei"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RentalProperty:
    property_ref: str
    role: str                           # subject | non_subject | departing_residence
    units: int = 1
    schedule_e: Optional[TaxFormRef] = None
    leases: List[Dict[str, Any]] = field(default_factory=list)          # {document_ref, monthly_rent, term_start, term_end, tenant_present}
    appraisal_rent_schedule: Optional[Dict[str, Any]] = None           # {document_ref, form: 1007|1025, market_rent}
    monthly_pitia: Optional[str] = None
    reported_rental_loss: Optional[str] = None
    program: Optional[str] = None
    structure_id: str = field(default_factory=lambda: new_id("rent"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def validate_self_employment(structure: SelfEmploymentIncome) -> Dict[str, Any]:
    issues = []
    if structure.entity_type not in ("sole_proprietor", "partnership", "s_corp", "c_corp"):
        issues.append("entity_type must be sole_proprietor | partnership | s_corp | c_corp")
    for form in structure.tax_forms:
        if form.form not in SELF_EMPLOYMENT_FORMS:
            issues.append(f"{form.document_ref}: unknown form {form.form}")
    years = sorted({f.tax_year for f in structure.tax_forms})
    return {"ok": not issues, "issues": issues, "tax_years_present": years, "profit_and_loss_present": structure.profit_and_loss is not None,
            "balance_sheet_present": structure.balance_sheet is not None}


def validate_rental(structure: RentalProperty) -> Dict[str, Any]:
    issues = []
    if structure.role not in RENTAL_PROPERTY_ROLES:
        issues.append("role must be subject | non_subject | departing_residence")
    if structure.schedule_e is None and not structure.leases and structure.appraisal_rent_schedule is None:
        issues.append("no rental evidence: Schedule E, lease or appraisal rent schedule")
    return {"ok": not issues, "issues": issues}


def source_gap(kind: str, program: Optional[str], *, structure_id: Optional[str] = None) -> Dict[str, Any]:
    """Every income calculation for these structures is SOURCE_GAP until the relevant sections are activated."""
    sections = {
        "self_employment": {"fannie": "B3-3.2-01, B3-3.4-01 through B3-3.4-04, B3-3.1-08", "freddie": "5304.1", "fha": "II.A.4.c.x (TOTAL) / II.A.5.b.x (Manual)",
                            "va": "Chapter 4 Topic 2 (self-employed)", "usda": "Attachment 9-A (self-employment)"},
        "rental": {"fannie": "B3-3.1-08", "freddie": "5306.1", "fha": "II.A.4.c.xii / II.A.5.b.xii (rental income)", "va": "Chapter 4 Topic 2 (rental income)",
                   "usda": "Attachment 9-A (rental income)"},
    }[kind]
    return {
        "status": "SOURCE_GAP", "kind": kind, "program": program, "structure_id": structure_id, "generated_at": now_iso(),
        "reason": f"no activated {kind} income section for {program or 'any program'}; formulas are not implemented by design",
        "official_sections_to_activate": sections.get((program or "").lower(), "program-specific self-employment/rental sections"),
        "underwriting_decision": False,
    }
