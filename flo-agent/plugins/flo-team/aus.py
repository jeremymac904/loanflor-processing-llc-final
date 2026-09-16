"""AUS normalization — one envelope for DU, LPA, TOTAL (via an AUS), VA AUS and GUS.

The envelope preserves the system's own wording (``aus_result`` is the
recommendation exactly as shown; the statement is "<system> findings show
<result>.") and never maps results to a fake universal "approved". Program
and system must agree (``EXPECTED_SYSTEMS``); a DU findings document on a
Freddie file is a mismatch, not a normalization.

Envelope fields: aus_system, aus_result, aus_version, findings_ref,
findings_date, program, underwriting_method, messages[], source_document,
statement, plus the file-specific figures the systems report (dti, ltv,
funds/reserves to verify) when present.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from . import calc as calc_mod
from .store import now_iso

SYSTEMS = {
    "DU": {"display": "DU", "long": "Desktop Underwriter", "programs": ("fannie", "va", "fha"), "doc_types": ("du_findings",)},
    "LPA": {"display": "LPA", "long": "Loan Product Advisor", "programs": ("freddie", "va", "fha"), "doc_types": ("lpa_findings", "lpa_feedback_certificate")},
    "TOTAL": {"display": "TOTAL Mortgage Scorecard", "long": "TOTAL Mortgage Scorecard (via DU or LPA)", "programs": ("fha",), "doc_types": ("total_findings", "fha_total_findings")},
    "GUS": {"display": "GUS", "long": "Guaranteed Underwriting System", "programs": ("usda",), "doc_types": ("gus_findings",)},
    "VA_AUS": {"display": "AUS", "long": "VA-approved AUS (DU or LPA)", "programs": ("va",), "doc_types": ("va_aus_findings",)},
}
# The AUS a program's own guide describes; findings from any other system are a mismatch.
EXPECTED_SYSTEMS = {"fannie": ("DU",), "freddie": ("LPA",), "fha": ("TOTAL",), "va": ("VA_AUS", "DU", "LPA"), "usda": ("GUS",)}
GENERIC_TYPES = ("aus_findings",)
RESULT_FIELDS = ("recommendation", "risk_class", "result", "aus_result", "underwriting_recommendation")

DOC_KEYWORDS = {
    "paystub": ("paystub", "pay stub", "earnings statement"),
    "w2": ("w-2", "w2"),
    "bank_statement": ("bank statement", "asset statement", "depository", "account statement"),
    "voe": ("verification of employment", "verbal voe", "voe", "reverification"),
    "tax_return": ("tax return", "1040"),
    "credit_report": ("credit report",),
    "appraisal": ("appraisal",),
    "identification": ("identification", "photo id"),
}


def _system_for(doc: Dict[str, Any]) -> Optional[str]:
    explicit = str(doc.get("aus_system") or doc.get("system") or "").upper().replace(" ", "_")
    if explicit in SYSTEMS:
        return explicit
    if explicit in ("LOAN_PRODUCT_ADVISOR", "LP"):
        return "LPA"
    if explicit in ("DESKTOP_UNDERWRITER",):
        return "DU"
    dtype = str(doc.get("type") or "").lower()
    for key, spec in SYSTEMS.items():
        if dtype in spec["doc_types"]:
            return key
    return None


def detect(documents: List[Dict[str, Any]], program: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The first AUS findings document in the inventory (any system)."""
    for doc in documents or []:
        dtype = str(doc.get("type") or "").lower()
        if dtype in GENERIC_TYPES or _system_for(doc):
            return doc
    return None


def normalize(doc: Dict[str, Any], *, program: str, underwriting_method: Optional[str] = None) -> Dict[str, Any]:
    """Build the common envelope from a findings document without changing its wording."""
    program = (program or "").lower()
    system = _system_for(doc)
    result = next((str(doc[f]).strip() for f in RESULT_FIELDS if doc.get(f)), "")
    messages = []
    for msg in doc.get("documentation_messages") or doc.get("messages") or []:
        if isinstance(msg, dict):
            messages.append({"id": msg.get("id"), "text": str(msg.get("text") or ""), "category": msg.get("category")})
        else:
            messages.append({"id": None, "text": str(msg), "category": None})
    display = SYSTEMS[system]["display"] if system else "AUS"
    env: Dict[str, Any] = {
        "envelope": "aus_findings",
        "aus_system": system,
        "aus_system_display": display,
        "aus_result": result or None,
        "aus_version": doc.get("aus_version") or doc.get("version") or doc.get("scorecard_version"),
        "findings_ref": doc.get("ref"),
        "findings_date": doc.get("date") or doc.get("findings_date"),
        "casefile_id": doc.get("casefile_id") or doc.get("key_number") or doc.get("loan_id"),
        "submission_number": doc.get("submission_number"),
        "program": program,
        "underwriting_method": underwriting_method or doc.get("underwriting_method"),
        "messages": messages,
        "source_document": {"type": doc.get("type"), "ref": doc.get("ref")},
        "dti": doc.get("dti"), "ltv": doc.get("ltv"),
        "funds_required_to_close": doc.get("funds_required_to_close"),
        "reserves_required_to_be_verified": doc.get("reserves_required_to_be_verified"),
        "statement": (f"{display} findings show {result}." if result else f"{display} findings are present but the result field is blank."),
        "mismatch": None,
        "underwriting_decision": False,
        "note": "AUS results are file-specific evidence recorded verbatim; no system result is ever restated as 'approved'",
    }
    expected = EXPECTED_SYSTEMS.get(program, ())
    if system is None:
        env["mismatch"] = "findings document does not identify its AUS; cannot bind it to a program"
    elif system not in expected:
        env["mismatch"] = f"{display} findings cannot be applied to a {program} file (expected {', '.join(SYSTEMS[e]['display'] for e in expected)})"
    return env


def _match_message(text: str) -> Optional[str]:
    lowered = text.lower()
    for kind, words in DOC_KEYWORDS.items():
        if any(w in lowered for w in words):
            return kind
    return None


# Program → (section that describes the AUS, tolerance formula id, section for the guide-vs-findings VOE check)
_BINDINGS = {
    "fannie": {"aus_section": "B3-2-11", "tolerance_formula": "fannie.du.dti_resubmission_check", "voe_section": "B3-3.3-01",
               "voe_note": "B3-3.3-01 requires a verbal VOE for base income"},
    "freddie": {"aus_section": "5101.1", "tolerance_formula": "freddie.lpa.dti_resubmission_check", "voe_section": "5302.2",
                "voe_note": "5302.2(d) requires a 10-day pre-closing verification of employment"},
    "fha": {"aus_section": "II.A.4.a", "tolerance_formula": None, "voe_section": "II.A.4.c",
            "voe_note": "II.A.4.c requires Reverification of Employment within 10 Days prior to the Note"},
    "va": {"aus_section": "Chapter 4", "tolerance_formula": None, "voe_section": "Chapter 4",
           "voe_note": "Chapter 4 Topic 8 requires telephone contact verifying the current employer"},
    "usda": {"aus_section": "5.3", "tolerance_formula": None, "voe_section": "9.3",
             "voe_note": "9.3 requires a verbal verification of employment within 10 business days of closing"},
}


def review(
    *,
    documents: List[Dict[str, Any]],
    program: str,
    underwriting_method: Optional[str] = None,
    recalculated_dti: Any = None,
    active_check: Optional[Callable[[str], bool]] = None,
    section_meta: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Program-aware findings review: envelope + message-vs-inventory + tolerance + guide conflicts."""
    program = (program or "").lower()
    binding = _BINDINGS.get(program, {})
    findings = detect(documents, program)
    out: Dict[str, Any] = {"review": "aus_findings", "program": program, "generated_at": now_iso(), "underwriting_decision": False, "warnings": [], "conflicts": []}
    if findings is None:
        expected = ", ".join(SYSTEMS[e]["display"] for e in EXPECTED_SYSTEMS.get(program, ()))
        out.update({"present": False, "status": "missing", "statement": f"{expected or 'AUS'} findings are not in the file.", "requirements": [], "missing": [],
                    "next": f"obtain the {expected or 'AUS'} findings report before prep can be completed", "envelope": None})
        return out
    env = normalize(findings, program=program, underwriting_method=underwriting_method)
    out.update({"present": True, "status": "present", "envelope": env, "statement": env["statement"], "recommendation_as_shown": env["aus_result"],
                "aus_system": env["aus_system"], "casefile_id": env["casefile_id"], "submission_number": env["submission_number"], "findings_date": env["findings_date"],
                "document_ref": env["findings_ref"], "dti": env["dti"], "ltv": env["ltv"], "funds_required_to_close": env["funds_required_to_close"],
                "reserves_required_to_be_verified": env["reserves_required_to_be_verified"]})
    if env["mismatch"]:
        out["status"] = "mismatch"
        out["warnings"].append(env["mismatch"])
        out["requirements"] = []
        out["missing"] = []
        return out
    aus_section = binding.get("aus_section")
    out["source"] = (section_meta(aus_section) if (section_meta and active_check and aus_section and active_check(aus_section))
                     else {"section": aus_section, "note": "section not active; findings recorded as file-specific evidence only"})
    inventory: Dict[str, List[Dict[str, Any]]] = {}
    for doc in documents:
        inventory.setdefault(str(doc.get("type") or "").lower(), []).append(doc)
    requirements = []
    for msg in env["messages"]:
        kind = _match_message(msg["text"])
        have = inventory.get(kind or "", [])
        state = "satisfied" if have else ("unknown" if kind is None else "missing")
        note = None
        if have and kind == "bank_statement":
            incomplete = [d.get("ref") for d in have if d.get("pages_total") and d.get("pages_present") is not None and int(d["pages_present"]) < int(d["pages_total"])]
            if incomplete:
                state, note = "needs_review", f"incomplete statement(s): {', '.join(str(r) for r in incomplete)}"
        requirements.append({"message_id": msg["id"], "text": msg["text"], "document_kind": kind, "scope": "file_specific", "state": state,
                             "evidence": [d.get("ref") for d in have], **({"note": note} if note else {})})
    out["requirements"] = requirements
    out["missing"] = [r for r in requirements if r["state"] == "missing"]
    formula = binding.get("tolerance_formula")
    if recalculated_dti is not None and env.get("dti") is not None:
        if formula:
            tol = calc_mod.run(formula, {"du_dti" if program == "fannie" else "aus_dti": str(env["dti"]), "recalculated_dti": str(recalculated_dti)},
                               active_check=active_check, source_meta=section_meta, program=program)
            out["dti_tolerance"] = tol.to_dict()
            if tol.status == "SUCCESS" and any("Resubmission" in w for w in tol.warnings):
                out["warnings"].append(f"{env['aus_system_display']} resubmission required per the activated tolerance rule; do not treat the current findings as final")
        else:
            out["dti_tolerance"] = {"status": "SOURCE_GAP", "note": f"no activated resubmission-tolerance rule for {program}; compare DTI manually"}
    voe_section = binding.get("voe_section")
    if active_check and voe_section and active_check(voe_section) and not any(r["document_kind"] == "voe" for r in requirements):
        out["conflicts"].append({"kind": "findings_vs_guide", "route_to": "sage",
                                 "detail": f"{env['aus_system_display']} messages do not mention an employment verification; {binding.get('voe_note')}. Route to Sage/Flo; the guide requirement stands unless Sage cites an exception."})
    return out
