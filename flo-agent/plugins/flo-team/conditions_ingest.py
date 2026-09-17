"""Lender / UW email → conditions → workspace.

Two-stage flow:

  1. ``flo_conditions_ingest`` — *propose only*. Parses the email body
     into structured conditions, matches the email to a workspace, dedupes
     against the workspace's existing conditions, and returns a diff. Does
     **not** mutate the workspace.

  2. ``flo_conditions_apply`` — Ashley-confirmed. Writes the proposed
     conditions into the workspace and normalizes them.

Email content is untrusted: it can DESCRIBE conditions, but it cannot
authorize sending, ordering, deleting, or milestone changes. Ashley's
confirmation is the gate between propose and apply.

Dedup uses a stable identity per condition so that Gmail's retry
behavior (the same email arriving twice) doesn't double-write. The
identity is ``sha256(condition_type | normalized_text | owner)``.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


from . import conditions_normalize as cn


# ── identity ───────────────────────────────────────────────────────────────

def _norm_for_id(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation tails, drop
    leading boilerplate verbs that lenders rephrase on each delivery
    ('need', 'provide', 'kindly provide', …). Stable across re-sends
    of the same condition."""
    s = re.sub(r"\s+", " ", (text or "")).strip().lower()
    s = re.sub(r"[\.\!\?;:,]+$", "", s)
    # Strip common lender-leading verbs so 'Need paystub' and
    # 'Provide paystub' collapse to the same identity.
    s = re.sub(
        r"^(?:please|kindly|we\s+need|need|provide|provided|must\s+provide|"
        r"to\s+provide|the\s+borrower\s+(?:needs|must)\s+to\s+provide|"
        r"borrower\s+(?:needs|must)\s+to\s+provide)\s+",
        "",
        s,
    )
    return s


def condition_identity(parsed: Dict[str, Any]) -> str:
    """Stable hash that survives Gmail retries / re-deliveries."""
    ctype = parsed.get("condition_type") or "other"
    owner = parsed.get("owner") or "Other"
    text = _norm_for_id(parsed.get("original_text") or parsed.get("plain_english") or "")
    payload = f"{ctype}|{owner}|{text}".encode("utf-8")
    return "cond_" + hashlib.sha256(payload).hexdigest()[:16]


def email_identity(source: str, source_ref: Optional[str], raw_text: str) -> str:
    """Identity for the email itself. Used to skip already-processed messages."""
    payload = f"{source}|{source_ref or ''}|{raw_text[:4000]}".encode("utf-8")
    return "email_" + hashlib.sha256(payload).hexdigest()[:16]


# ── ingestion ──────────────────────────────────────────────────────────────

def parse_email_to_conditions(
    raw_text: str,
    *,
    source: str = "lender_email",
    source_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Convenience wrapper that returns parsed + identity-stamped conditions."""
    rows = cn.parse_conditions_blob(raw_text, source=source, source_date=source_date)
    for r in rows:
        r["identity"] = condition_identity(r)
    return rows


# ── workspace matching ─────────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()
    return re.sub(r"\s+", " ", s)


def match_workspace(
    workspaces: Iterable[Dict[str, Any]],
    *,
    borrower_name: Optional[str] = None,
    property_address: Optional[str] = None,
    loan_number: Optional[str] = None,
    sender: Optional[str] = None,
) -> Dict[str, Any]:
    """Pick the workspace this email belongs to.

    Returns::

        {"confidence": "high"|"medium"|"none",
         "workspace_id": str|None,
         "candidates": [<wid, signal>],
         "reason": str}

    Never picks silently on weak signals — "medium" and below means
    Ashley must confirm.
    """
    candidates: List[Tuple[str, List[str]]] = []
    borrower_norm = _normalize_name(borrower_name or "")
    address_norm = _normalize_name(property_address or "")
    loan_num = (loan_number or "").strip()

    for ws in workspaces or []:
        wid = ws.get("workspace_id")
        if not wid:
            continue
        signals: List[str] = []
        ws_name = _normalize_name(ws.get("display_name") or "")
        # 1. Loan number (strongest)
        ws_loan = str(ws.get("loan_number") or "").strip()
        if loan_num and ws_loan and loan_num == ws_loan:
            signals.append("loan_number")
        # 2. Borrower name (display_name is usually borrower last name)
        if borrower_norm and ws_name and (borrower_norm in ws_name or ws_name in borrower_norm):
            signals.append("borrower_name")
        # 3. Property address
        ws_address = _normalize_name(ws.get("property_address") or "")
        if address_norm and ws_address and (address_norm in ws_address or ws_address in address_norm):
            signals.append("property_address")
        # 4. Sender domain match against the lender record. Match on the
        #    core domain (the part before .tld) so lender_name = "First
        #    National Bank" matches sender = "uw@firstnational.example".
        ws_lender = (ws.get("lender_name") or "").lower()
        if sender and ws_lender:
            sender_dom = sender.split("@")[-1].lower()
            # take the leading label(s) of the sender domain
            core = sender_dom.split(".")[0]
            lender_core = re.sub(r"[^a-z0-9]+", "", ws_lender)
            if core and lender_core and core in lender_core:
                signals.append("sender_domain")
        for borrower in ws.get("borrowers") or []:
            bn = _normalize_name(borrower.get("name") or "")
            if borrower_norm and bn and (borrower_norm in bn or bn in borrower_norm):
                signals.append("borrower_name")
                break
        if signals:
            candidates.append((wid, signals))

    if not candidates:
        return {"confidence": "none", "workspace_id": None, "candidates": [],
                "reason": "no workspace signals matched (borrower / property / loan # / sender domain)"}

    # strongest signal wins
    by_strength = sorted(
        candidates,
        key=lambda c: -len(c[1]),
    )
    top_wid, top_signals = by_strength[0]
    # Two candidates with equal-best → medium (Ashley picks)
    if len(by_strength) > 1 and len(by_strength[0][1]) == len(by_strength[1][1]):
        return {
            "confidence": "medium",
            "workspace_id": None,
            "candidates": [{"workspace_id": wid, "signals": s} for wid, s in by_strength[:3]],
            "reason": "multiple workspaces match with equal strength — Ashley must confirm",
        }
    return {
        "confidence": "high",
        "workspace_id": top_wid,
        "candidates": [{"workspace_id": top_wid, "signals": top_signals}],
        "reason": "; ".join(top_signals) + " match",
    }


# ── dedupe ─────────────────────────────────────────────────────────────────

def diff_against_workspace(
    parsed: List[Dict[str, Any]],
    workspace_doc: Dict[str, Any],
    *,
    email_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare a parsed batch against the workspace's existing conditions
    and split into new / duplicates / needs_review.

    Duplicate key: condition ``identity`` (sha256 of type|owner|text).
    The duplicate-text-with-different-owner case is **not** a duplicate
    — it lands in ``needs_review`` so a human decides.

    Already-applied guard: an ``email_id`` that's already on a stored
    condition's ``source_refs`` OR on a still-pending
    ``pending_email_ingests`` card is treated as the same email
    re-delivered — Gmail's retry behavior. The propose path then
    returns ``email_already_applied=True`` and the desktop does not
    stack a second card.
    """
    existing = workspace_doc.get("conditions") or []
    seen_by_identity: Dict[str, Dict[str, Any]] = {}
    for c in existing:
        if not isinstance(c, dict):
            continue
        cid = c.get("identity") or condition_identity({
            "condition_type": c.get("condition_type") or c.get("kind") or "other",
            "owner":          c.get("owner") or "Other",
            "original_text":  c.get("text") or c.get("original_text") or c.get("plain_english") or "",
        })
        seen_by_identity.setdefault(cid, c)
    seen_email_ids: set = set()
    if email_id:
        for c in existing:
            if not isinstance(c, dict):
                continue
            for src in (c.get("source_refs") or []):
                if isinstance(src, dict) and src.get("email_id") == email_id:
                    seen_email_ids.add(email_id)
        # Also: a still-pending ingest card for the same email_id
        # represents a Gmail retry of the same message — treat as a
        # duplicate even though the conditions haven't been written yet.
        for card in workspace_doc.get("pending_email_ingests") or []:
            if not isinstance(card, dict):
                continue
            if card.get("email_id") == email_id and card.get("status") == "pending":
                seen_email_ids.add(email_id)

    new_rows: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    needs_review: List[Dict[str, Any]] = []

    for row in parsed:
        cid = row.get("identity") or condition_identity(row)
        if cid in seen_by_identity:
            duplicates.append({"identity": cid, "matched_existing_id": seen_by_identity[cid].get("id")})
            continue
        # Same email already applied? skip the whole batch.
        if email_id and email_id in seen_email_ids:
            duplicates.append({"identity": cid, "email_already_applied": True})
            continue
        # Already in new_rows this batch? skip
        if any(n.get("identity") == cid for n in new_rows):
            continue
        new_rows.append(row)

    return {
        "new": new_rows,
        "duplicates": duplicates,
        "needs_review": needs_review,
        "email_id": email_id,
        "email_already_applied": email_id in seen_email_ids if email_id else False,
    }


# ── apply (post-Ashley-confirmation) ───────────────────────────────────────

def apply_proposed(
    workspace_doc: Dict[str, Any],
    proposed: List[Dict[str, Any]],
    *,
    actor: str = "ashley",
    source: str = "lender_email",
    source_ref: Optional[str] = None,
    email_id: Optional[str] = None,
    source_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Write proposed conditions into the workspace and stamp them with
    source attribution. Idempotent via ``identity``: same-identity rows
    are skipped, so calling this twice is safe.

    Returns the list of condition objects actually written (with their
    new IDs / timestamps).
    """
    from .store import new_id, now_iso
    existing_identities = {
        (c.get("identity") if isinstance(c, dict) else None)
        for c in (workspace_doc.get("conditions") or [])
    }
    written: List[Dict[str, Any]] = []
    for row in proposed or []:
        if row.get("identity") in existing_identities:
            continue
        cond = dict(row)
        cond.setdefault("id", new_id("cond"))
        cond.setdefault("added_by", actor)
        cond.setdefault("added_at", now_iso())
        cond["state"] = cond.get("state") or "open"
        cond["status"] = cond.get("status") or "Open"
        cond["source"] = source
        if source_date:
            cond["source_date"] = source_date
        if source_ref:
            cond["source_ref"] = source_ref
        if email_id:
            # Stamp every source attribution for traceability
            refs = list(cond.get("source_refs") or [])
            if not any(isinstance(r, dict) and r.get("email_id") == email_id for r in refs):
                refs.append({"email_id": email_id, "received_at": source_date or now_iso()})
            cond["source_refs"] = refs
        workspace_doc.setdefault("conditions", []).append(cond)
        existing_identities.add(cond["identity"])
        written.append(cond)
    # Clear any pending email-ingest proposal that produced these rows —
    # once applied, the card has served its purpose.
    if written:
        clear_pending_email_ingest(workspace_doc, email_id=email_id)
    return written


# ── Pending proposals (Ashley-facing UI state) ─────────────────────────────
#
# When the Gmail connector recognizes a lender / UW email, the tool
# handler stores a "pending" card on the workspace so the desktop can
# render it inline. Ashley's [Add to File] / [Confirm CTC] / [Not Now]
# click clears the pending card and (for Add / Confirm) writes to the
# file.

def store_pending_email_ingest(
    workspace_doc: Dict[str, Any],
    *,
    email_id: str,
    sender: Optional[str],
    subject: Optional[str],
    received_at: Optional[str],
    workspace_match: Dict[str, Any],
    proposed: List[Dict[str, Any]],
    duplicate_count: int = 0,
    email_already_applied: bool = False,
) -> Dict[str, Any]:
    """Save a pending email-conditions proposal on the workspace. The
    desktop reads this card and shows it under the file's Conditions
    section. Idempotent on ``email_id`` — re-storing the same email
    replaces the existing proposal rather than appending a second one.
    """
    card = {
        "kind": "conditions_email",
        "email_id": email_id,
        "sender": sender,
        "subject": subject,
        "received_at": received_at,
        "workspace_match": workspace_match,
        "proposed": proposed,
        "duplicate_count": duplicate_count,
        "email_already_applied": email_already_applied,
        "status": "pending",
        "stored_at": datetime_now_iso(),
    }
    pendings = [c for c in (workspace_doc.get("pending_email_ingests") or [])
                if isinstance(c, dict) and c.get("email_id") != email_id]
    pendings.append(card)
    workspace_doc["pending_email_ingests"] = pendings
    return card


def clear_pending_email_ingest(
    workspace_doc: Dict[str, Any],
    *,
    email_id: Optional[str] = None,
    status: str = "applied",
) -> int:
    """Mark pending email-ingest cards as decided. If ``email_id`` is
    provided, only that one card is touched; otherwise every pending
    card of the requested status is updated. Returns the count cleared."""
    count = 0
    for c in (workspace_doc.get("pending_email_ingests") or []):
        if not isinstance(c, dict):
            continue
        if c.get("status") != "pending":
            continue
        if email_id is None or c.get("email_id") == email_id:
            c["status"] = status
            c["decided_at"] = datetime_now_iso()
            count += 1
    return count


def pending_email_ingest(
    workspace_doc: Dict[str, Any],
    email_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return pending email-ingest cards on this workspace. If
    ``email_id`` is given, only that one."""
    out: List[Dict[str, Any]] = []
    for c in (workspace_doc.get("pending_email_ingests") or []):
        if not isinstance(c, dict):
            continue
        if c.get("status") != "pending":
            continue
        if email_id is not None and c.get("email_id") != email_id:
            continue
        out.append(c)
    return out


def store_pending_ctc_proposal(
    workspace_doc: Dict[str, Any],
    *,
    email_id: str,
    sender: Optional[str],
    subject: Optional[str],
    received_at: Optional[str],
    is_ctc: bool,
    confidence: str,
    matched_phrase: Optional[str],
    reason: Optional[str],
    raw_text_excerpt: Optional[str],
) -> Dict[str, Any]:
    """Save a pending CTC proposal on the workspace. Replaces any
    existing pending CTC proposal for the same email_id."""
    card = {
        "kind": "ctc_email",
        "email_id": email_id,
        "sender": sender,
        "subject": subject,
        "received_at": received_at,
        "is_ctc": is_ctc,
        "confidence": confidence,
        "matched_phrase": matched_phrase,
        "reason": reason,
        "raw_text_excerpt": (raw_text_excerpt or "")[:400],
        "status": "pending",
        "stored_at": datetime_now_iso(),
    }
    pendings = [c for c in (workspace_doc.get("pending_ctc_proposals") or [])
                if isinstance(c, dict) and c.get("email_id") != email_id]
    pendings.append(card)
    workspace_doc["pending_ctc_proposals"] = pendings
    return card


def clear_pending_ctc_proposal(
    workspace_doc: Dict[str, Any],
    *,
    email_id: Optional[str] = None,
    status: str = "confirmed",
) -> int:
    count = 0
    for c in (workspace_doc.get("pending_ctc_proposals") or []):
        if not isinstance(c, dict):
            continue
        if c.get("status") != "pending":
            continue
        if email_id is None or c.get("email_id") == email_id:
            c["status"] = status
            c["decided_at"] = datetime_now_iso()
            count += 1
    return count


def pending_ctc_proposals(
    workspace_doc: Dict[str, Any],
    email_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in (workspace_doc.get("pending_ctc_proposals") or []):
        if not isinstance(c, dict):
            continue
        if c.get("status") != "pending":
            continue
        if email_id is not None and c.get("email_id") != email_id:
            continue
        out.append(c)
    return out


def datetime_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
