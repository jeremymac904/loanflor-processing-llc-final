"""New Loan Submission intake — lfprocessing.net → Flo.

A Loan Officer submits the website form; the LoanFlow server validates it and
POSTs the versioned payload (schemaVersion 1.0, see LOAN_SUBMISSION_SCHEMA.md
in the website repo) to the private intake endpoint (``scripts/flo/intake_server.py``).
That endpoint calls :func:`receive`, which deterministically:

    1. creates the Loan Workspace / Deal Room (milestone Intake) — once per
       ``submissionId`` (idempotent; a retry or double delivery returns the
       same workspace);
    2. records the loan officer, borrowers, program/transaction, expected
       closing, LO-stated income, funds, credit notes and processing notes on
       the workspace as *references* (never SSNs or account numbers — the
       website already refuses them, and the workspace store rejects them
       again);
    3. attaches document references (files are listed, not uploaded, until
       secure storage exists);
    4. creates ONE task for Malcolm: "Review this new submission and tell
       Ashley what is missing." (return format file_prep_report);
    5. stores the handoff packet so Flo can send it with ``message_agent``
       (``flo_intake action=dispatch``).

Sage is not involved at intake; Malcolm asks Flo for a guideline question the
normal way if one comes up. Nothing here talks to a model.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .handoff import TaskRegistry, build_handoff, render_message
from .store import JsonDocStore, JsonlLog, now_iso
from .workspace import WorkspaceError, WorkspaceStore

SCHEMA_VERSION = "1.0"
SUPPORTED_SCHEMAS = {"1.0"}
_ID_RE = re.compile(r"^sub_[0-9a-f]{24}$")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# A digit run embedded in an alphanumeric token (hex ids like sub_582779223a8c…, checksums, storage keys) is not an account number.
_LONG_DIGITS_RE = re.compile(r"(?<![0-9A-Za-z])\d{8,}(?![0-9A-Za-z])")
PROGRAM_MAP = {"conventional": "conventional", "fha": "fha", "va": "va", "usda": "usda", "jumbo": "jumbo", "non_qm": "non_qm", "other": "other"}
AGENCY_MAP = {"fannie_mae": "fannie", "freddie_mac": "freddie"}
LABELS = {
    "transactionType": {"purchase": "Purchase", "refinance_rate_term": "Refinance (rate & term)", "refinance_cash_out": "Refinance (cash out)"},
    "program": {"conventional": "Conventional", "fha": "FHA", "va": "VA", "usda": "USDA", "jumbo": "Jumbo", "non_qm": "Non-QM", "other": "Other"},
    "aus": {"du": "DU", "lpa": "LPA", "total": "TOTAL", "gus": "GUS", "va_aus": "VA AUS", "manual": "Manual", "other": "Other / not sure"},
    "incomeType": {"w2": "W-2", "1099": "1099", "self_employed": "Self-employed", "rental": "Rental", "retirement_pension": "Retirement/pension",
                   "social_security": "Social Security", "military": "Military", "other": "Other"},
    "calculationBasis": {"two_year_average": "2-year average", "latest_year": "latest year", "current_income": "current income", "other_unknown": "basis unknown"},
    "fundsSourceType": {"gift_from_relative": "Gift from relative", "borrower_bank_account": "Borrower bank account", "retirement_withdrawal": "Retirement withdrawal",
                        "lender_credits": "Lender credits at closing", "other": "Other"},
    "creditStatus": {"as_per_credit_pull": "as per credit pull", "rescore_or_supplement": "rescore/supplement", "tradeline_omitted": "tradeline omitted", "other_issue": "other issue"},
    "documentCategory": {"loan_application": "1003", "credit_report": "Credit report", "aus_findings": "AUS findings", "income": "Income docs", "assets": "Asset docs",
                         "purchase_contract": "Purchase contract", "title_property": "Title/property", "insurance": "Insurance", "other": "Other"},
    "appraisalTiming": {"prior_to_inspection": "order PRIOR to inspection", "after_inspection": "order AFTER inspection"},
}


class IntakeError(ValueError):
    pass


def _label(group: str, value: Any) -> str:
    return LABELS.get(group, {}).get(str(value or ""), str(value or ""))


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.0f}" if value is not None and value != "" else ""
    except (TypeError, ValueError):
        return ""


def _scan_sensitive(value: Any, path: str = "") -> List[str]:
    hits: List[str] = []
    if isinstance(value, str):
        if _SSN_RE.search(value) or (not path.endswith("phone") and _LONG_DIGITS_RE.search(value) and len(_LONG_DIGITS_RE.search(value).group(0)) not in (10, 11)):
            hits.append(path)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            hits.extend(_scan_sensitive(v, f"{path}.{i}" if path else str(i)))
    elif isinstance(value, dict):
        for k, v in value.items():
            hits.extend(_scan_sensitive(v, f"{path}.{k}" if path else str(k)))
    return hits


def validate(payload: Any) -> List[str]:
    """Structural validation of the v1.0 payload. Returns a list of problems (empty = ok)."""
    problems: List[str] = []
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    if payload.get("schemaVersion") not in SUPPORTED_SCHEMAS:
        problems.append(f"unsupported schemaVersion {payload.get('schemaVersion')!r}")
    if not _ID_RE.match(str(payload.get("submissionId") or "")):
        problems.append("submissionId must look like sub_<24 hex>")
    lo = payload.get("loanOfficer") or {}
    if not isinstance(lo, dict) or not str(lo.get("name") or "").strip():
        problems.append("loanOfficer.name is required")
    borrowers = payload.get("borrowers")
    if not isinstance(borrowers, list) or not borrowers or not str((borrowers[0] or {}).get("name") or "").strip():
        problems.append("borrowers[0].name is required")
    loan = payload.get("loan") or {}
    if not isinstance(loan, dict) or not str(loan.get("propertyAddress") or "").strip():
        problems.append("loan.propertyAddress is required")
    if not isinstance(loan, dict) or loan.get("program") not in PROGRAM_MAP:
        problems.append("loan.program must be one of " + ", ".join(sorted(PROGRAM_MAP)))
    for key in ("income", "assets", "documentRefs"):
        if key in payload and not isinstance(payload.get(key), list):
            problems.append(f"{key} must be a list")
    sensitive = _scan_sensitive(payload)
    if sensitive:
        problems.append("sensitive data refused (full SSN / account number) at: " + ", ".join(sensitive[:5]))
    return problems


def _display_name(payload: Dict[str, Any]) -> str:
    name = str((payload.get("borrowers") or [{}])[0].get("name") or "").strip()
    parts = [p for p in re.split(r"\s+", name) if p]
    return parts[-1] if parts else "New submission"


def _urgency(expected_close: Optional[str], today: Optional[date] = None) -> str:
    try:
        close = date.fromisoformat(str(expected_close)) if expected_close else None
    except ValueError:
        close = None
    if close is None:
        return "this_week"
    days = (close - (today or date.today())).days
    return "today" if days <= 14 else ("tomorrow" if days <= 21 else "this_week")


def summary_lines(payload: Dict[str, Any]) -> List[str]:
    """Facts for Malcolm's packet — references and LO statements only, in plain English."""
    lo, loan, fees = payload.get("loanOfficer") or {}, payload.get("loan") or {}, payload.get("fees") or {}
    facts = [f"Submitted from {payload.get('source', 'lfprocessing.net')} by {lo.get('name')} ({lo.get('company') or 'company n/a'}); submission {payload.get('submissionId')}"]
    borrowers = payload.get("borrowers") or []
    facts.append("Borrowers: " + "; ".join(f"{b.get('name')} ({b.get('role', 'borrower').replace('_', ' ')})" for b in borrowers))
    program = _label("program", loan.get("program"))
    if loan.get("conventionalAgency"):
        program += f" ({AGENCY_MAP.get(loan['conventionalAgency'], loan['conventionalAgency']).title()})"
    if loan.get("programOther"):
        program += f" ({loan['programOther']})"
    facts.append(f"{_label('transactionType', loan.get('transactionType'))} • {program} • AUS {_label('aus', loan.get('aus')) or 'not stated'}"
                 + (f" • refinance type {loan.get('refinanceType')}" if loan.get("refinanceType") else ""))
    facts.append(f"Loan amount {_money(loan.get('loanAmount')) or 'n/a'}; rate {loan.get('interestRate') or 'n/a'}%; LTV {loan.get('ltv') or 'n/a'}%"
                 + (f"; CLTV {loan.get('cltv')}%" if loan.get("cltv") is not None else "") + f"; occupancy {loan.get('occupancy') or 'n/a'}; investor {loan.get('investor') or 'n/a'}")
    facts.append(f"Property: {loan.get('propertyAddress')}; home type {loan.get('homeType') or 'n/a'}; expected closing {loan.get('expectedClosingDate') or 'n/a'}")
    facts.append(f"Channel {fees.get('channel') or 'n/a'} {fees.get('compensation') or ''}; lender buying out the fee: {fees.get('lenderBuyingOutFee') or 'not stated'}"
                 + (f" ({fees.get('buyoutNotes')})" if fees.get("buyoutNotes") else ""))
    setup, ap = payload.get("setup") or {}, payload.get("appraisal") or {}
    facts.append(f"PMI {setup.get('pmi') or 'n/a'}; subordination {setup.get('subordinationRequired') or 'n/a'}; locked {setup.get('loanLocked') or 'n/a'}; escrow waiver {setup.get('escrowWaiver') or 'n/a'}; appraisal: {_label('appraisalTiming', ap.get('orderTiming')) or 'timing not stated'}")
    for s in payload.get("income") or []:
        who = "co-borrower" if s.get("borrower") == "co_borrower" else "borrower"
        facts.append(f"LO-stated income ({who}): {_label('incomeType', s.get('incomeType'))} at {s.get('employerOrSource') or 'source n/a'}, {_money(s.get('loStatedMonthlyIncome')) or 'amount n/a'}/mo, {_label('calculationBasis', s.get('calculationBasis')) or 'basis n/a'}; docs: {', '.join(s.get('documentsIncluded') or []) or 'none listed'} — NOT verified")
    for a in payload.get("assets") or []:
        facts.append(f"Funds: {_label('fundsSourceType', a.get('sourceType'))} — {a.get('nameOrInstitution') or 'n/a'} {('ref ' + a['accountReference']) if a.get('accountReference') else ''} {_money(a.get('amount'))}".strip())
    credit = payload.get("credit") or {}
    for who, key in (("borrower", "borrower"), ("co-borrower", "coBorrower")):
        c = credit.get(key) or {}
        if c.get("status") or c.get("omittedDebtsNotes"):
            facts.append(f"Credit ({who}): {', '.join(_label('creditStatus', s) for s in c.get('status') or []) or 'not stated'}" + (f"; notes: {c['omittedDebtsNotes']}" if c.get("omittedDebtsNotes") else ""))
    hoa = payload.get("hoa") or {}
    if hoa.get("present") == "yes":
        facts.append(f"HOA: {hoa.get('company') or 'company n/a'}; condo questionnaire {hoa.get('condoQuestionnaireStatus') or 'n/a'}")
    tp = (payload.get("parties") or {}).get("nonBorrowingTitleParty") or {}
    if tp.get("applies"):
        facts.append(f"Non-borrowing spouse / individual on title: {tp.get('name')} (on title: {tp.get('willBeOnTitle') or 'n/a'})")
    docs = payload.get("documentRefs") or []
    transferred = [d for d in docs if isinstance(d, dict) and d.get("fetchUrl")]
    listed_only = [d for d in docs if isinstance(d, dict) and not d.get("fetchUrl")]
    if transferred:
        facts.append(f"Documents attached by the LO on the website: {len(transferred)} file(s), pulled into the Deal Room (inventory below)")
    if listed_only:
        facts.append("Documents the LO listed but did not transfer: " + ", ".join(f"{_label('documentCategory', d.get('category'))}: {d.get('fileName')}" for d in listed_only))
    if not docs:
        facts.append("No documents attached by the LO")
    if payload.get("notes"):
        facts.append(f"LO notes: {payload['notes']}")
    return facts


def new_loan_line(name: str, documents: int) -> str:
    """Flo's line when a website submission lands (owner wording, 2026-09-09)."""
    from .today import new_loan_line as _line

    return _line(name, documents)


def document_facts(ingested: Dict[str, Any], inv: Dict[str, Any]) -> List[str]:
    """Document inventory lines for Malcolm's packet (references and statuses, never contents)."""
    docs = ingested.get("documents") or []
    if not docs:
        return ["Documents: none attached by the LO"]
    facts = [f"Documents received: {ingested.get('received', 0)} ({ingested.get('duplicates', 0)} duplicate)"]
    for d in docs[:30]:
        line = f"- {d['display_name']} [{d['category']}{'/' + d['subcategory'] if d.get('subcategory') else ''}{', ' + d['borrower_ref'] if d.get('borrower_ref') else ''}] status {d['status']}"
        if d.get("page_count"):
            line += f", {d['page_count']} page(s)"
        if d.get("text_chars"):
            line += ", text extracted"
        if d.get("notes"):
            line += f" — {d['notes']}"
        if (d.get("checks") or {}).get("suggested_classification"):
            s = d["checks"]["suggested_classification"]
            line += f" — looks like {s['category']}{'/' + s['subcategory'] if s.get('subcategory') else ''} ({s['source']})"
        facts.append(line)
    if inv.get("missing"):
        facts.append("Missing (active-rule backed): " + "; ".join(f"{w['label']} ({w['basis']})" for w in inv["missing"]))
    if inv.get("needs_clarification"):
        facts.append("Needs clarification: " + "; ".join(str(w.get("problem") or w.get("reason") or w["label"]) for w in inv["needs_clarification"]))
    return facts


def _submission_block(payload: Dict[str, Any]) -> Dict[str, Any]:
    lo, loan = payload.get("loanOfficer") or {}, payload.get("loan") or {}
    borrowers = payload.get("borrowers") or []
    return {
        "submission_id": payload.get("submissionId"), "schema_version": payload.get("schemaVersion"), "source": payload.get("source"),
        "submitted_at": payload.get("submittedAt"), "received_at": now_iso(),
        "loan_officer": {"name": lo.get("name"), "company": lo.get("company"), "email": lo.get("email"), "phone": lo.get("phone"), "nmls": lo.get("nmls")},
        "borrowers": [{"role": b.get("role"), "name": b.get("name"), "email": b.get("email"), "phone": b.get("phone")} for b in borrowers],
        "transaction_type": loan.get("transactionType"), "transaction_label": _label("transactionType", loan.get("transactionType")),
        "program_label": _label("program", loan.get("program")), "aus": loan.get("aus"), "expected_closing_date": loan.get("expectedClosingDate"),
        "loan_amount": loan.get("loanAmount"), "investor": loan.get("investor"), "occupancy": loan.get("occupancy"), "home_type": loan.get("homeType"),
        "fees": payload.get("fees"), "appraisal": payload.get("appraisal"), "setup": payload.get("setup"), "parties": payload.get("parties"),
        "communication_preferences": payload.get("communicationPreferences"), "hoa": payload.get("hoa"),
        "lo_stated_income": payload.get("income"), "funds_to_close": payload.get("assets"), "credit": payload.get("credit"),
        "title": payload.get("title"), "insurance": payload.get("insurance"), "agents": payload.get("agents"), "notes": payload.get("notes"),
        "review_status": "pending",  # Malcolm's readiness report flips this to reviewed
    }


class IntakeStore:
    """``<team root>/intake/<submission_id>.json`` — the idempotency record and the dispatch packet."""

    def __init__(self, root) -> None:
        self.root = Path(root)
        self.docs = JsonDocStore(self.root / "intake")
        self.log = JsonlLog(self.root / "activity", "activity")

    def get(self, submission_id: str) -> Optional[Dict[str, Any]]:
        return self.docs.get(submission_id) if _ID_RE.match(submission_id or "") else None

    def pending_dispatch(self) -> List[Dict[str, Any]]:
        return sorted([d for d in self.docs.all() if not d.get("dispatched_at")], key=lambda d: d.get("received_at") or "")

    def mark_dispatched(self, submission_id: str, *, by: str = "flo") -> Dict[str, Any]:
        rec = self.get(submission_id)
        if rec is None:
            raise IntakeError(f"unknown submission {submission_id}")
        rec["dispatched_at"] = now_iso()
        rec["dispatched_by"] = by
        self.docs.put(submission_id, rec)
        self.log.append({"event": "intake.dispatched", "actor": by, "submission_id": submission_id, "workspace_id": rec.get("workspace_id"), "task_id": rec.get("task_id")})
        return rec


def receive(root, payload: Dict[str, Any], *, actor: str = "flo", today: Optional[date] = None, document_fetch=None, document_token: Optional[str] = None,
            rule_check=None) -> Dict[str, Any]:
    """Create the workspace + Malcolm task for a submission, once, pulling the documents through the connector. Returns the intake record."""
    problems = validate(payload)
    if problems:
        raise IntakeError("; ".join(problems))
    store = IntakeStore(root)
    sid = str(payload["submissionId"])
    existing = store.get(sid)
    if existing:
        return {**existing, "duplicate": True}

    ws = WorkspaceStore(Path(root))
    loan = payload.get("loan") or {}
    program = PROGRAM_MAP[loan.get("program")]
    agency = AGENCY_MAP.get(str(loan.get("conventionalAgency") or ""), program if program in ("fha", "va", "usda") else None)
    doc = ws.create(display_name=_display_name(payload), program=program, agency=agency, milestone="Intake", actor=actor)
    wid = doc["workspace_id"]
    lo = payload.get("loanOfficer") or {}
    block = _submission_block(payload)
    summary = (f"New submission from {lo.get('name')}" + (f" ({lo.get('company')})" if lo.get("company") else "") + f". {block['transaction_label']} • {block['program_label']}"
               + (f". Expected close {loan.get('expectedClosingDate')}" if loan.get("expectedClosingDate") else "") + ".")
    ws.update_fields(wid, actor, {"status_summary": summary[:300], "next_action": "Malcolm is reviewing the new submission.", "aus": _label("aus", loan.get("aus")) or None})

    def _mutate(d):
        d["submission"] = block

    ws.docs.update(wid, _mutate)
    ws._activity(wid, actor, "submission.received", {"submission_id": sid, "source": payload.get("source")})

    # Documents: pull every referenced file through the authenticated connector, keep a private copy,
    # extract text, run the deterministic checks, and record the inventory on the workspace.
    from . import documents as documents_mod

    refs = [r for r in (payload.get("documentRefs") or []) if isinstance(r, dict) and r.get("fetchUrl")]
    ingested = documents_mod.ingest(root, wid, sid, refs, fetch=document_fetch, token=document_token, actor=actor) if refs else {"documents": [], "received": 0, "duplicates": 0}
    inv = documents_mod.inventory(root, wid, block, program=program, rule_check=rule_check)
    doc_count = ingested["received"]
    for d in ingested["documents"]:
        try:
            ws.add_item(wid, actor, "document_refs", {"ref": f"doc://{d['document_id']}", "document_id": d["document_id"], "category": d["category"], "subcategory": d.get("subcategory"),
                                                      "borrower_ref": d.get("borrower_ref"), "display_name": d["display_name"], "status": d["status"], "note": d.get("notes") or "",
                                                      "local_path": d.get("local_path"), "text_path": d.get("text_path"), "pages": d.get("page_count")})
        except WorkspaceError:
            continue
    for r in (payload.get("documentRefs") or []):
        if isinstance(r, dict) and not r.get("fetchUrl"):
            ws.add_item(wid, actor, "document_refs", {"ref": f"lo-listed://{sid}/{r.get('category')}/{r.get('fileName')}", "category": r.get("category"),
                                                      "display_name": r.get("fileName"), "status": "listed", "note": "listed by the loan officer; file not transferred"})

    def _summary(d):
        d["documents_summary"] = {"received": doc_count, "duplicates": ingested["duplicates"], "missing": [w["label"] for w in inv["missing"]],
                                  "needs_clarification": [w.get("problem") or w.get("reason") or w["label"] for w in inv["needs_clarification"]],
                                  "updated_at": now_iso()}

    ws.docs.update(wid, _summary)
    if payload.get("notes"):
        ws.add_item(wid, actor, "communication_refs", {"ref": f"submission://{sid}#notes", "text": str(payload["notes"])[:400], "from": lo.get("name"), "kind": "lo_note"})
    ws.add_item(wid, actor, "communication_refs", {"ref": f"submission://{sid}", "kind": "loan_submission", "from": lo.get("name"), "email": lo.get("email"), "phone": lo.get("phone")})

    handoff = build_handoff(
        sender=actor, recipient="malcolm", objective="Review this new submission and tell Ashley what is missing.",
        workspace_id=wid, urgency=_urgency(loan.get("expectedClosingDate"), today), facts=summary_lines(payload) + document_facts(ingested, inv),
        source_refs=[f"submission://{sid}"], return_format="file_prep_report",
        constraints=["This came straight from the loan officer's website form: LO-stated income and figures are claims, not verified facts.",
                     "Documents are already in the Deal Room: flo_documents action=list shows them, action=get reads the extracted text, action=update reclassifies or sets a status "
                     "(received, needs_review, reviewed, missing_pages, unreadable, duplicate, not_needed); action=inventory compares them with what the submission and active rules expect.",
                     "Confirm what is present, classify anything unclear, note missing pages and unreadable files, then use flo_readiness so the workspace shows readiness/missing items; "
                     "only an ACTIVE source rule makes a document 'required' — everything else is a clarification (SOURCE_GAP), never an invented requirement.",
                     "Finish with one clean File Prep summary for Flo: received count, missing items, biggest blocker, best next move. Ask Flo (not Sage directly) if a guideline question comes up."],
    )
    handoff.status = "sent"
    registry = TaskRegistry(Path(root))
    registry.save(handoff, "created", actor)
    ws.attach_task(wid, handoff.task_id, actor)

    record = {
        "submission_id": sid, "workspace_id": wid, "task_id": handoff.task_id, "received_at": now_iso(), "received_by": actor, "source": payload.get("source"),
        "borrower": _display_name(payload), "loan_officer": lo.get("name"), "expected_closing_date": loan.get("expectedClosingDate"),
        "send_with": {"tool": "message_agent", "target": "malcolm", "message": render_message(handoff)},
        "dispatched_at": None, "dispatched_by": None, "duplicate": False, "documents_received": doc_count,
        "ashley_line": new_loan_line(doc["display_name"], doc_count),
    }
    store.docs.put(sid, record)
    store.log.append({"event": "intake.received", "actor": actor, "submission_id": sid, "workspace_id": wid, "task_id": handoff.task_id, "source": payload.get("source")})
    return record


def dispatch(root, submission_id: str, *, by: str = "flo") -> Dict[str, Any]:
    """The packet Flo sends to Malcolm with message_agent; marks the record dispatched."""
    store = IntakeStore(root)
    rec = store.get(submission_id)
    if rec is None:
        raise IntakeError(f"unknown submission {submission_id}")
    if rec.get("dispatched_at"):
        return {**rec, "note": "already dispatched; do not send again"}
    return store.mark_dispatched(submission_id, by=by)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
