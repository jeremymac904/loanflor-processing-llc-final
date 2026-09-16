"""CTC (Clear to Close) readiness.

Per project rule, Flo never grants CTC — the lender does. What Flo does:

  * Computes a *readiness* summary from open / waiting / needs-review
    conditions so Ashley sees a plain-English "almost there / all clear"
    line on the file view.
  * Recognizes a lender CTC notice in incoming email content (Gmail
    connector path) and proposes the milestone change for Ashley's
    confirmation. Flo never auto-promotes to Clear to Close from
    inference.
  * Records the milestone update with the lender-source attribution
    once Ashley confirms.

Inputs are the existing workspace dict. No new tables, no new fields
beyond what's already there (milestone, conditions[]).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# Phrases that suggest a real lender CTC notice. Conservative — at least
# one phrase must hit AND the message must be from the lender / UW /
# processing department of record. Patterns are intentionally narrow.
_LENDER_CTC_PHRASES = (
    "clear to close",
    "ctc issued",
    "ctc approved",
    "clear-to-close",
    "we have approved",
    "loan is approved and ready",
    "approval to close",
    "we are clear to close",
    "we're clear to close",
    "ready to close",
    "approved for closing",
    "final approval",
    "clear to fund",
)

_LENDER_CTC_NEGATIVE = (
    "not clear to close",
    "not yet clear",
    "not yet ctc",
    "cannot issue ctc",
    "still conditions",
    "outstanding conditions",
)


# Recognized lender / UW / processing department labels. Used only as a
# routing hint; the actual authorization is Flo policy, not the source.
_LENDER_SENDER_HINTS = (
    "underwriter",
    "uw@",
    "lender",
    "loan officer",
    "processor",
    "doc department",
    "docs@",
    "closer",
    "funding",
    "closing",
)


def _cond_state(c: Dict[str, Any]) -> str:
    return str(c.get("state") or c.get("status") or "open").lower()


def _is_waiting(c: Dict[str, Any]) -> bool:
    return _cond_state(c) == "waiting"


def _is_open(c: Dict[str, Any]) -> bool:
    return _cond_state(c) not in {"cleared", "waiting"}


def ctc_readiness(workspace_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Plain-English CTC readiness view.

    Returns::

        {
          "open_count":          int,
          "waiting_count":       int,
          "needs_review_count":  int,
          "cleared_count":       int,
          "all_tracked":         bool,   # True when every tracked condition
                                        # is cleared
          "summary":             str,    # one line for Ashley
        }

    Milestone is read for context only — Flo does not change it here.
    """
    conditions = [c for c in (workspace_doc.get("conditions") or []) if isinstance(c, dict)]
    open_count = sum(1 for c in conditions if _is_open(c) and not c.get("needs_review"))
    waiting_count = sum(1 for c in conditions if _is_waiting(c))
    needs_review_count = sum(1 for c in conditions if c.get("needs_review") and not _is_waiting(c))
    cleared_count = sum(1 for c in conditions if _cond_state(c) == "cleared")

    total_tracked = open_count + waiting_count + needs_review_count + cleared_count
    all_tracked = bool(total_tracked) and (open_count + waiting_count + needs_review_count) == 0

    if not total_tracked:
        summary = "CTC readiness: nothing tracked yet."
    elif all_tracked:
        summary = "Everything we're tracking is cleared. Waiting on the lender for Clear to Close."
    else:
        bits: List[str] = []
        if open_count:
            bits.append(f"{open_count} open")
        if waiting_count:
            bits.append(f"{waiting_count} waiting")
        if needs_review_count:
            bits.append(f"{needs_review_count} need{'s' if needs_review_count == 1 else ''} review")
        summary = f"CTC readiness: almost there ({', '.join(bits)})."

    return {
        "open_count": open_count,
        "waiting_count": waiting_count,
        "needs_review_count": needs_review_count,
        "cleared_count": cleared_count,
        "all_tracked": all_tracked,
        "summary": summary,
    }


# ── Lender CTC notice detection ────────────────────────────────────────────

def looks_like_lender_ctc(email_body: str, *, sender: Optional[str] = None,
                          subject: Optional[str] = None) -> Dict[str, Any]:
    """Conservative check: does this email look like a real Clear-to-Close
    notice from the lender / UW / processor?

    Returns::

        {"is_ctc": bool, "confidence": "high"|"medium"|"low",
         "matched_phrase": str|None, "reason": str}

    Flo never auto-promotes to Clear to Close on this signal — the result
    is fed to an Approvals card for Ashley to confirm.
    """
    body = (email_body or "").lower()
    subj = (subject or "").lower()
    sender_l = (sender or "").lower()
    haystack = " ".join((subj, body))

    # Quick reject on explicit negatives.
    for neg in _LENDER_CTC_NEGATIVE:
        if neg in haystack:
            return {"is_ctc": False, "confidence": "low",
                    "matched_phrase": None,
                    "reason": f"email says {neg!r}; not a CTC notice"}

    matched = next((p for p in _LENDER_CTC_PHRASES if p in haystack), None)
    if not matched:
        return {"is_ctc": False, "confidence": "low", "matched_phrase": None,
                "reason": "no lender CTC phrase found"}

    # Sender hint is optional — many lenders send CTC from a generic
    # address. When present it raises confidence; when absent we still
    # surface a "medium" signal for Ashley to confirm.
    sender_match = any(h in sender_l for h in _LENDER_SENDER_HINTS) if sender_l else False
    if sender_match:
        return {"is_ctc": True, "confidence": "high",
                "matched_phrase": matched, "reason": "phrase + lender-sender match"}
    return {"is_ctc": True, "confidence": "medium",
            "matched_phrase": matched,
            "reason": "phrase found but no recognized lender sender — confirm with Ashley"}


# ── Confirm Clear to Close (Ashley-gated) ──────────────────────────────────

def confirm_clear_to_close(
    workspace_doc: Dict[str, Any],
    *,
    confirmed_by: str = "ashley",
    source: str = "lender_email",
    source_ref: Optional[str] = None,
    evidence: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark the file Clear to Close. Requires an explicit Ashley confirmation
    in the caller. Returns a summary.

    Audit trail written onto the workspace::

        workspace["milestone"]              = "Clear to Close"
        workspace["ctc_confirmed_by"]       = "ashley"
        workspace["ctc_confirmed_at"]       = <iso>
        workspace["ctc_source"]             = "lender_email" | "manual" | …
        workspace["ctc_source_ref"]         = <opaque id>
        workspace["ctc_evidence"]            = <verbatim lender line>

    Idempotent: calling twice with the same evidence is a no-op.
    """
    if workspace_doc.get("milestone") == "Clear to Close":
        return {"already_ctc": True, "milestone": workspace_doc.get("milestone")}

    now_iso = datetime.now(timezone.utc).isoformat()
    workspace_doc["milestone"] = "Clear to Close"
    workspace_doc["ctc_confirmed_by"] = confirmed_by
    workspace_doc["ctc_confirmed_at"] = now_iso
    workspace_doc["ctc_source"] = source
    if source_ref:
        workspace_doc["ctc_source_ref"] = source_ref
    if evidence:
        workspace_doc["ctc_evidence"] = evidence[:400]

    return {
        "already_ctc": False,
        "milestone": "Clear to Close",
        "confirmed_by": confirmed_by,
        "confirmed_at": now_iso,
        "source": source,
    }


# ── Celebration message (Ashley-facing, short) ────────────────────────────

def ctc_celebration(workspace_doc: Dict[str, Any]) -> str:
    name = (workspace_doc.get("display_name")
            or workspace_doc.get("workspace_id")
            or "this file")
    return f"{name} is CTC. Boom. 💚"
