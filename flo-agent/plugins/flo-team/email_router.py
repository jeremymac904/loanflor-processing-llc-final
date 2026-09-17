"""Email → Flo router.

The Hermes email adapter (IMAP) already polls Gmail and turns each
inbound message into a ``MessageEvent`` for chat. This module is the
thin glue between that path and the existing
``flo_conditions_ingest`` / ``flo_ctc_email`` handlers.

One entry point: ``route_inbound_email(msg_data, *, match_kwargs=None,
agent_name="flo")``. The caller (currently the email adapter) passes
the structured message dict it already builds. The router:

  1. Runs two conservative detectors in parallel:
     - ``conditions_ingest.parse_conditions_blob``          → condition candidate
     - ``ctc.looks_like_lender_ctc``                       → CTC candidate
  2. Picks whichever candidate matters, or skips noisy email.
  3. Matches the email to a workspace via ``conditions_ingest.match_workspace``.
     High confidence  → push the proposal straight onto the file.
     Medium / none     → leave it for Ashley to pick (no card stored;
                        no write to the file).
  4. Calls ``flo_conditions_ingest action=propose`` (or
     ``flo_ctc_email action=propose``), which already knows how to
     store the pending card and return a structured result.

Email content is untrusted. Nothing here authorizes sends, deletes,
milestone changes, or any irreversible side-effect on its own. The
router's only job is to surface a card. Ashley is the gate.

This file intentionally has zero new infrastructure: it doesn't talk
to Gmail directly (the IMAP adapter does), doesn't run on a cron
(the adapter dispatches it per-message), and doesn't add a webhook /
poller. The auth path is the one the existing IMAP adapter requires
(EMAIL_ADDRESS + EMAIL_PASSWORD env, set once at install time).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


# Conservative heuristics that say "this email is plausibly about
# lender / UW conditions or CTC". Words like "loan", "borrower",
# "approval" alone are too noisy and would spam Ashley. The
# markers below are concrete phrases used in lender / UW notes.
CONDITION_HINT_PHRASES = (
    "conditional approval",
    "conditions of approval",
    "uw conditions",
    "underwriting conditions",
    "prior to doc",
    "prior to funding",
    "prior to closing",
    "ptd ",
    "ptf ",
    "conditions outstanding",
    "outstanding items",
    "items needed",
    "documentation needed",
    "need the following",
    "below are",
    # Subject-line / heading matches — strong signals even alone.
    "conditions",
    "uw notes",
    "underwriting notes",
    "uw update",
    "uw request",
    "new condition",
    "updated condition",
    "additional condition",
    "additionally need",
    # Lender note intro lines — common in approval letters and
    # condition-update emails.
    "following conditions",
    "have the following conditions",
    "we have conditions",
    "have conditions for",
    "conditions are:",
    "conditions listed",
    "conditions per",
    "conditions needed",
    "items needed to",
    # Provide / need / obtain / verify language the project spec calls
    # out as a condition signal.
    "please send",
    "please provide",
    "please obtain",
    "please verify",
    "please send ",
    "please obtain ",
    "send us",
    "send the updated",
    "need the updated",
    "obtain the",
)

CTC_HINT_PHRASES = (
    "clear to close",
    "ctc issued",
    "ctc approved",
    "ready to close",
    "final approval",
    "approved for closing",
)

LENDER_HINT_PHRASES = (
    "underwriter",
    "lender",
    "loan officer",
    "title company",
    "title commitment",
    "title endorsement",
    "appraisal",
    "verification of employment",
    "verification of deposit",
    "voe",
    "vvoe",
    "wvoe",
    "voa",
    "hoi",
)


def _norm(text: Any) -> str:
    return str(text or "").lower()


def _mentions_any(body: str, phrases: tuple) -> bool:
    """True when at least one phrase appears as a substring. Conservative;
    doesn't tokenize or fuzzy-match."""
    b = _norm(body)
    if not b:
        return False
    return any(p in b for p in phrases)


def is_actionable_lender_email(*, sender: str, subject: str, body: str) -> bool:
    """Conservative gate: actionable means FROM a lender / UW / title
    AND with content that looks like conditions / CTC / approval.

    Either path alone is not enough — a lender email with no
    condition / CTC content should NOT trigger a notification,
    otherwise Ashley will be spammed.
    """
    sender_l = _norm(sender)
    subject_l = _norm(subject)
    body_l = _norm(body)

    is_lender_sender = False

    if "@" in sender_l:
        domain = sender_l.rsplit("@", 1)[-1]
        handle = sender_l.split("@", 1)[0]
        second_level = domain.split(".", 1)[0] if "." in domain else domain
        handle_words = re.findall(r"[a-z]+", handle)
        lender_handle_words = {
            "uw", "underwriter", "underwriting", "loanofficer",
            "loan", "loanofcr", "titleco", "title", "closer", "closing",
            "funding", "processor", "docdept", "docs", "appraisal",
            "uwmailer", "lender", "mortgage", "creditunion",
        }
        if any(w in lender_handle_words for w in handle_words):
            is_lender_sender = True
        if second_level in lender_handle_words:
            is_lender_sender = True
        for tld in (".bank", ".lender", ".mortgage", ".creditunion",
                    ".fcu", ".title"):
            if domain.endswith(tld):
                is_lender_sender = True

    if not is_lender_sender:
        for phrase in LENDER_HINT_PHRASES:
            if phrase in sender_l or phrase in subject_l:
                is_lender_sender = True
                break
        if not is_lender_sender:
            for phrase in ("underwriter", "title company", "title endorsement",
                            "we have approved", "loan committee"):
                if phrase in body_l:
                    is_lender_sender = True
                    break

    if not is_lender_sender:
        return False

    # Sender is lender; now check whether the content is actionable.
    # Actionable = carries either a conditions signal or a CTC phrase.
    if looks_like_condition_email(body=body, subject=subject):
        return True
    if looks_like_ctc_email(body=body):
        return True
    return False


# Backwards-compat alias for callers/tests using the old name.
def is_lender_or_uw_email(*, sender: str, subject: str, body: str) -> bool:
    """Deprecated: prefer ``is_actionable_lender_email``. Kept for any
    external scripts; returns the actionable predicate by default."""
    return is_actionable_lender_email(sender=sender, subject=subject, body=body)


def looks_like_condition_email(*, body: str, subject: str = "") -> bool:
    """Conservative condition-email signal. Doesn't trigger on every
    lender update — only on messages that look like a condition
    list/letter. Subject is included so 'Conditions' alone is enough
    when the lender email is just a subject header."""
    haystack = (subject or "") + "\n" + (body or "")
    return _mentions_any(haystack, CONDITION_HINT_PHRASES)


def looks_like_ctc_email(*, body: str) -> bool:
    """Delegate to the deterministic detector. Negative phrases win."""
    from . import ctc as ctc_mod
    verdict = ctc_mod.looks_like_lender_ctc(body, sender=None, subject=None)
    return verdict["is_ctc"]


def extract_borrower_hints(*, workspaces: List[Dict[str, Any]],
                              sender: str, subject: str,
                              body: str) -> Dict[str, Any]:
    """Pull candidate signals for the workspace matcher from the email
    headers + body.

    Conservative best-effort:
      * If subject says 'on loan <name>' and that name matches a
        workspace's display_name, set borrower_name.
      * If subject or body contains a fully-qualified borrower name
        matching one of the workspaces' borrowers[] or display_name,
        set borrower_name.
      * Pass loan_number / property_address from the subject when
        'Loan #N' or '123 Main St' style strings are present.

    Returns a dict the caller can pass straight to
    ``conditions_ingest.match_workspace``.
    """
    import re
    plain_subject = _norm(subject)
    plain_body = _norm(body)
    plain_all = plain_subject + "\n" + plain_body

    borrower = None
    # Strongest signal: 'on loan <Name>' in the subject.
    m = re.search(r"\bon loan\s+([a-z][a-z' \-]+)\b", plain_subject)
    if m:
        candidate = m.group(1).strip()
        # Match against the seeded workspaces' display_name.
        for ws in workspaces or []:
            display = _norm(ws.get("display_name") or "").strip()
            if candidate == display:
                borrower = ws.get("display_name")
                break
        if borrower is None:
            # Heuristic: fall back to the candidate title-cased as-is.
            borrower = candidate.title()

    # Falling back: see if the subject line contains a workspace name
    # word for word — common when lenders reference the borrower
    # by name in their email subject.
    if borrower is None:
        for ws in workspaces or []:
            display = (ws.get("display_name") or "").strip()
            if display and _norm(display) in plain_subject:
                borrower = display
                break

    loan_number = None
    m = re.search(r"\b(?:loan\s*(?:#|number|no\.?)\s*)([\w-]{3,20})", plain_all)
    if m:
        loan_number = m.group(1).strip()

    property_address = None
    m = re.search(
        r"\b\d{1,5}\s+[a-z][a-z\.]*(?:\s+[a-z][a-z\.]*)*\s+(?:street|st|ave|avenue|road|rd|blvd|drive|dr|lane|ln|court|ct|cir|place|pl)\b",
        plain_all,
    )
    if m:
        property_address = m.group(0).strip()

    return {
        "borrower_name": borrower,
        "loan_number":   loan_number,
        "property_address": property_address,
        "sender":        sender,
    }


def route_inbound_email(
    msg_data: Dict[str, Any],
    *,
    state_root: Optional[Any] = None,
    agent_name: str = "flo",
) -> Dict[str, Any]:
    """Classify an inbound email and dispatch it to the correct Flo
    handler.

    ``msg_data`` matches the shape the IMAP adapter already builds in
    ``EmailAdapter._process_message``:
        sender_addr, sender_name, subject, body (plain text), message_id,
        thread_id, received_at, in_reply_to.

    Returns a structured result so the caller (and tests) can see why
    the email was handled the way it was. Never raises.
    """
    sender = str(msg_data.get("sender_addr") or msg_data.get("sender") or "")
    subject = str(msg_data.get("subject") or "")
    body    = str(msg_data.get("body") or msg_data.get("text") or "")
    message_id = str(msg_data.get("message_id") or "")
    thread_id  = str(msg_data.get("thread_id") or "")

    # Step 1: is this even a lender / UW email we should touch?
    if not is_lender_or_uw_email(sender=sender, subject=subject, body=body):
        return {
            "stage": "skipped",
            "reason": "sender / subject / body don't look like lender or UW — not our lane",
            "sender": sender,
            "subject": subject,
            "message_id": message_id,
        }

    # Step 2: classify (conditions vs CTC vs unknown). CTC and conditions
    # are checked independently. Both can fire (a lender note can carry
    # both) — handle them in priority order so the more "important"
    # card wins.
    ctc_hit   = looks_like_ctc_email(body=body)
    cond_hit  = looks_like_condition_email(body=body)

    # Hard stop: if the email body uses one of the explicit negative
    # CTC phrases ('not clear to close', 'cannot issue ctc', …) the
    # email is talking about a future CTC, not issuing one. Both the
    # CTC and conditions paths are suppressed — the email stays in
    # Gmail and Flo does not surface a notification. This is the
    # project's chosen behavior: better quiet than wrong.
    lowered = body.lower()
    _NEG = ("not clear to close", "cannot issue ctc", "almost clear to close",
            "ctc pending", "pending final approval",
            "subject to final approval", "awaiting final approval",
            "still waiting for final approval")
    if any(p in lowered for p in _NEG):
        return {
            "stage": "negative_ctc_skipped",
            "reason": ("email mentions an explicit 'not clear to close' / "
                        "'cannot issue ctc' / etc. — not a CTC notice; "
                        "no card surfaced"),
            "sender": sender, "subject": subject, "message_id": message_id,
        }

    # Step 3: workspace match. Same matcher the conditions_ingest
    # handler uses; the connector doesn't always know the loan in
    # advance.
    from .workspace import WorkspaceStore
    root = state_root if state_root is not None else _default_root()
    workspaces: List[Dict[str, Any]] = []
    try:
        ws_store = WorkspaceStore(root)
        for wid in ws_store.docs.ids():
            try:
                workspaces.append(ws_store.get(wid))
            except Exception:  # noqa: BLE001 - tolerate malformed workspaces
                continue
    except Exception:  # noqa: BLE001
        workspaces = []

    hints = extract_borrower_hints(
        workspaces=workspaces, sender=sender, subject=subject, body=body,
    )
    from . import conditions_ingest as ci
    match = ci.match_workspace(
        workspaces,
        borrower_name=hints.get("borrower_name"),
        property_address=hints.get("property_address"),
        loan_number=hints.get("loan_number"),
        sender=sender,
    )

    # Step 4: dispatch.
    dispatched: List[Dict[str, Any]] = []
    if ctc_hit:
        dispatched.append(_dispatch_ctc(
            sender=sender, subject=subject, body=body,
            message_id=message_id, thread_id=thread_id,
            match=match,
        ))
    if cond_hit:
        dispatched.append(_dispatch_conditions(
            sender=sender, subject=subject, body=body,
            message_id=message_id, thread_id=thread_id,
            match=match,
        ))

    if not dispatched:
        return {
            "stage": "lender_email_not_actionable",
            "reason": ("lender/UW email but no condition or CTC phrases — "
                       "leaving it in Gmail, not surfacing a card"),
            "sender": sender, "subject": subject, "message_id": message_id,
            "workspace_match": match,
        }

    return {
        "stage": "dispatched",
        "sender": sender, "subject": subject, "message_id": message_id,
        "thread_id": thread_id,
        "workspace_match": match,
        "dispatched": dispatched,
    }


# ── helpers ────────────────────────────────────────────────────────────────

def _dispatch_ctc(*, sender: str, subject: str, body: str,
                   message_id: str, thread_id: str,
                   match: Dict[str, Any]) -> Dict[str, Any]:
    """One-shot call into flo_ctc_email action=propose. The workspace
    match's confidence drives whether we store a confirm card on the
    high-confidence file, or stop short and ask Ashley."""
    target_wid = match.get("workspace_id") if match.get("confidence") == "high" else None
    kwargs = {
        "action": "propose",
        "raw_text": body,
        "subject": subject,
        "sender": sender,
        "received_at": _received_at_msg_safe({}),
        "source_ref": message_id or f"gmail:{thread_id}",
    }
    if target_wid:
        kwargs["workspace_id"] = target_wid
    out = _invoke("flo_ctc_email", kwargs)
    return {"kind": "ctc", "match": match,
            "workspace_id_for_card": target_wid, "tool_result": out}


def _dispatch_conditions(*, sender: str, subject: str, body: str,
                          message_id: str, thread_id: str,
                          match: Dict[str, Any]) -> Dict[str, Any]:
    target_wid = match.get("workspace_id") if match.get("confidence") == "high" else None
    kwargs: Dict[str, Any] = {
        "action": "propose",
        "raw_text": body,
        "sender": sender,
        "subject": subject,
        "received_at": _received_at_msg_safe({}),
        "source_ref": message_id or f"gmail:{thread_id}",
    }
    if target_wid:
        kwargs["workspace_id"] = target_wid
    out = _invoke("flo_conditions_ingest", kwargs)
    return {"kind": "conditions", "match": match,
            "workspace_id_for_card": target_wid, "tool_result": out}


def _invoke(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke a Flo tool handler directly (no gateway round-trip)."""
    from . import tools as tools_mod
    handler = getattr(tools_mod, "handle_" + tool_name, None)
    if handler is None:
        return {"error": f"{tool_name} not registered"}
    raw = handler(args)
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001 - keep the router failure-safe
        return {"raw": str(raw)}


def _default_root():
    """Fallback state root: the same one the email adapter uses.
    Resolved at call time so tests that rebind ``tools._root`` after
    import still pick up the rebound value."""
    import importlib
    tools_mod = importlib.import_module("flo_team.tools")
    return tools_mod._root()


def _received_at_msg_safe(_: Dict[str, Any]) -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
