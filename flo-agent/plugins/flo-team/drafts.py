"""Whisper's communication queue — a draft is never "sent".

Each draft follows COMMUNICATION_DRAFT: audience, purpose, milestone, exactly
what is needed, urgency, body, approval required. Status vocabulary:
``draft`` → ``proposed`` (an Approval Center card exists) → ``sent`` (only when
an execution_ref from the sending tool is recorded) or ``rejected``.

``translate_condition`` is a structural helper: it produces the owner/action
skeleton for a lender condition and flags ``needs_sage`` when the condition
text mentions guideline-dependent vocabulary — it never explains the guideline
itself.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .store import new_id, now_iso

AUDIENCES = ("borrower", "lo", "lender", "realtor", "title", "internal", "vendor")
STATUSES = ("draft", "proposed", "sent", "rejected")
COMPLIANCE_TEMPLATE = "Your loan is progressing. We will update you at next milestone."
_GUIDELINE_WORDS = re.compile(
    r"\b(guideline|overlay|dti|ltv|reserves?|seasoning|sourced|large deposit|self[- ]employ|schedule|k-1|1084|"
    r"rental income|averag|trend|variable income|gift|non-occupant|manual underwrit|aus|du\b|lpa\b)\b", re.I)
_URGENCY = ("needs attention today", "urgent tomorrow if not answered today", "can wait")


class DraftError(ValueError):
    pass


def find_active_duplicate(existing: List[Dict[str, Any]], intent: str) -> Optional[Dict[str, Any]]:
    """An active draft (draft/proposed) with the same intent id; sent/rejected drafts do not block a new one."""
    for d in existing or []:
        if d.get("draft_intent_id") == intent and d.get("status") in ("draft", "proposed"):
            return d
    return None


def create(*, audience: str, purpose: str, body: str, workspace_id: Optional[str] = None,
           milestone: Optional[str] = None, needed: Optional[str] = None, urgency: str = "can wait",
           channel: str = "email", agent: str = "whisper", source_task: Optional[str] = None) -> Dict[str, Any]:
    audience = (audience or "").lower()
    if audience not in AUDIENCES:
        raise DraftError(f"audience must be one of {AUDIENCES}")
    if urgency not in _URGENCY:
        raise DraftError(f"urgency must be one of {_URGENCY}")
    body = str(body or "").strip()
    if not body:
        raise DraftError("body is required")
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", body) or re.search(r"\b\d{9,}\b", body):
        raise DraftError("draft contains an SSN- or account-shaped number; use last four digits or a reference")
    from . import intents

    material = intents.draft_material(audience=audience, purpose=purpose, needed=needed, channel=channel)
    intent = intents.intent_id(kind="draft", workspace_id=workspace_id, target=audience, purpose=purpose, material=material)
    return {
        "draft_id": new_id("draft"),
        "draft_intent_id": intent,
        "idempotency_key": intent,
        "source_task": source_task,
        "workspace_id": workspace_id,
        "audience": audience,
        "channel": channel,
        "purpose": str(purpose or "")[:300],
        "milestone": milestone,
        "needed": str(needed or "")[:400],
        "urgency": urgency,
        "body": body[:6000],
        "status": "draft",
        "approval_required": True,
        "proposal_id": None,
        "execution_ref": None,
        "borrower_facing_template_used": audience == "borrower" and COMPLIANCE_TEMPLATE in body,
        "created_by": agent,
        "created_at": now_iso(),
        "history": [{"at": now_iso(), "status": "draft", "by": agent}],
    }


def mark(draft: Dict[str, Any], status: str, *, by: str, proposal_id: Optional[str] = None,
         execution_ref: Optional[str] = None) -> Dict[str, Any]:
    if status not in STATUSES:
        raise DraftError(f"unknown status {status!r}")
    if status == "sent" and not execution_ref:
        raise DraftError("a draft becomes 'sent' only with an execution_ref from the sending tool")
    if status == "proposed" and not proposal_id:
        raise DraftError("'proposed' requires the Approval Center proposal_id")
    draft = dict(draft)
    draft["status"] = status
    if proposal_id:
        draft["proposal_id"] = proposal_id
    if execution_ref:
        draft["execution_ref"] = execution_ref
    draft.setdefault("history", []).append({"at": now_iso(), "status": status, "by": by})
    return draft


def translate_condition(condition_text: str, *, owner_hint: Optional[str] = None) -> Dict[str, Any]:
    text = " ".join(str(condition_text or "").split())
    if not text:
        raise DraftError("condition text is required")
    needs_sage = bool(_GUIDELINE_WORDS.search(text))
    owner = owner_hint or _guess_owner(text)
    return {
        "condition": text[:800],
        "plain_language": "SOURCE_GAP" if needs_sage else f"Provide: {text[:200]}",
        "owner": owner,
        "action": "ask Flo to engage Sage before translating (meaning depends on a guideline)" if needs_sage else "collect the named item and attach it to the file",
        "needs_sage": needs_sage,
        "scope": "file_specific",
        "global_rule": False,
    }


def _guess_owner(text: str) -> str:
    lowered = text.lower()
    if any(w in lowered for w in ("paystub", "bank statement", "letter of explanation", "loe", "borrower", "id ", "w-2", "w2")):
        return "borrower"
    if any(w in lowered for w in ("title", "cpl", "closing protection", "wire", "commitment")):
        return "title"
    if any(w in lowered for w in ("insurance", "hoi", "binder", "declarations")):
        return "insurance agent"
    if any(w in lowered for w in ("appraisal", "appraiser")):
        return "lender/AMC"
    return "processor"


def queue_view(drafts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {s: [] for s in STATUSES}
    for d in drafts or []:
        out.setdefault(d.get("status", "draft"), []).append(
            {k: d.get(k) for k in ("draft_id", "workspace_id", "audience", "purpose", "urgency", "status", "proposal_id", "execution_ref")})
    return out
