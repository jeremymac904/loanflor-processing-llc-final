"""Action-level idempotency for every side-effect proposal and executor.

An *intent* is the stable identity of "what the team is trying to do", derived
from the relevant factors — never from exact prose:

    kind            draft | order | send_email | title_order | hoi_request | wvoe |
                    calendar_event | upload | publish_gbp | publish_newsletter |
                    publish_blog | publish_social | marketing_content | tool_call
    workspace_id    the Deal Room (None for marketing)
    target          recipient / vendor / destination (normalized)
    purpose         normalized purpose category
    source_task     the handoff task that asked for it (optional)
    material        the material payload hash (recipient list, amounts, items,
                    attachments, property/borrower refs) — wording excluded

``intent_id = sha256(kind|workspace|target|purpose|material)[:16]``.

The registry (``<team root>/intents/``) records every claim and its outcome.
Before a new proposal is created or an executor runs, the caller asks
:meth:`IntentRegistry.check`; the answer is ``create_new`` or ``return_existing``
(with the existing record). A provider retry, a duplicate ``message_agent``
delivery, a resubmitted task or a re-run tool call therefore lands on the same
intent and never sends, orders or publishes twice. Materially edited,
rejected, sent/executed-and-expired intents follow the explicit policy below.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional

from .store import JsonDocStore, JsonlLog, now_iso, utcnow

KINDS = ("draft", "order", "send_email", "title_order", "hoi_request", "wvoe", "calendar_event", "upload", "publish_gbp",
         "publish_newsletter", "publish_blog", "publish_social", "marketing_content", "tool_call")
ACTIVE_STATES = ("pending", "proposed", "approved")           # an active intent: reuse it
TERMINAL_STATES = ("executed", "sent", "ordered", "published")  # done: a retry must not repeat it
REOPEN_STATES = ("rejected", "cancelled", "expired", "invalidated")  # explicit new intent allowed
EXECUTED_REUSE_WINDOW = timedelta(days=30)   # a retry inside this window returns the executed record instead of acting again


def normalize_text(value: Any) -> str:
    text = " ".join(str(value or "").lower().split())
    text = re.sub(r"[^a-z0-9@./:+ -]", "", text)
    return text.strip()


def normalize_items(items: Iterable[Any]) -> List[str]:
    """Order-insensitive, wording-insensitive list of requested items (first 8 content words each)."""
    out = set()
    for item in items or []:
        words = [w for w in re.findall(r"[a-z0-9\-]+", normalize_text(item)) if w not in ("the", "a", "an", "of", "for", "and", "to", "with", "your", "please", "provide", "most", "recent")]
        if words:
            out.add(" ".join(words[:8]))
    return sorted(out)


def material_hash(material: Dict[str, Any]) -> str:
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def intent_id(*, kind: str, workspace_id: Optional[str], target: Optional[str], purpose: Optional[str], material: Dict[str, Any]) -> str:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    blob = "|".join([kind, normalize_text(workspace_id), normalize_text(target), normalize_text(purpose), material_hash(material)])
    return "intent_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class IntentRegistry:
    def __init__(self, root) -> None:
        self.docs = JsonDocStore(root / "intents")
        self.log = JsonlLog(root / "activity", "activity")

    def check(self, *, kind: str, workspace_id: Optional[str], target: Optional[str], purpose: Optional[str], material: Dict[str, Any],
              source_task: Optional[str] = None, now=None) -> Dict[str, Any]:
        """Decide before acting: ``return_existing`` (active or recently executed) or ``create_new``."""
        iid = intent_id(kind=kind, workspace_id=workspace_id, target=target, purpose=purpose, material=material)
        existing = self.docs.get(iid)
        now = now or utcnow()
        if existing:
            state = existing.get("state")
            if state in ACTIVE_STATES:
                return {"decision": "return_existing", "intent_id": iid, "existing": existing, "reason": f"an active {kind} intent already exists ({state})"}
            if state in TERMINAL_STATES:
                done_at = existing.get("executed_at") or existing.get("updated_at") or ""
                try:
                    from datetime import datetime

                    recent = now - datetime.fromisoformat(done_at) < EXECUTED_REUSE_WINDOW
                except Exception:
                    recent = True
                if recent:
                    return {"decision": "return_existing", "intent_id": iid, "existing": existing,
                            "reason": f"this {kind} was already {state} ({existing.get('execution_ref') or 'no ref'}); a retry must not repeat it"}
            # rejected / cancelled / expired / invalidated, or executed long ago: a fresh instance is allowed
            return {"decision": "create_new", "intent_id": iid, "existing": existing, "reason": f"previous intent is {state}; a new instance is allowed"}
        return {"decision": "create_new", "intent_id": iid, "existing": None, "reason": "no prior intent"}

    def claim(self, *, kind: str, workspace_id: Optional[str], target: Optional[str], purpose: Optional[str], material: Dict[str, Any],
              record_id: str, agent: str, source_task: Optional[str] = None, state: str = "pending") -> Dict[str, Any]:
        """Record the intent → record binding (draft_id / order_id / proposal_id …)."""
        iid = intent_id(kind=kind, workspace_id=workspace_id, target=target, purpose=purpose, material=material)
        row = self.docs.get(iid) or {"intent_id": iid, "kind": kind, "workspace_id": workspace_id, "target": target, "purpose": purpose,
                                     "material_hash": material_hash(material), "material": material, "created_at": now_iso(), "history": []}
        row.update({"record_id": record_id, "state": state, "agent": agent, "source_task": source_task or row.get("source_task")})
        row["history"].append({"at": now_iso(), "state": state, "record_id": record_id, "by": agent, "source_task": source_task})
        self.docs.put(iid, row)
        self.log.append({"event": "intent.claimed", "actor": agent, "intent_id": iid, "kind": kind, "workspace_id": workspace_id, "record_id": record_id, "state": state})
        return row

    def transition(self, iid: str, state: str, *, by: str, execution_ref: Optional[str] = None, note: str = "") -> Dict[str, Any]:
        row = self.docs.get(iid)
        if row is None:
            raise KeyError(iid)
        row["state"] = state
        if execution_ref:
            row["execution_ref"] = execution_ref
        if state in TERMINAL_STATES:
            row["executed_at"] = now_iso()
        row.setdefault("history", []).append({"at": now_iso(), "state": state, "by": by, **({"execution_ref": execution_ref} if execution_ref else {}), **({"note": note} if note else {})})
        self.docs.put(iid, row)
        self.log.append({"event": f"intent.{state}", "actor": by, "intent_id": iid, "kind": row.get("kind"), "workspace_id": row.get("workspace_id"), "execution_ref": execution_ref})
        return row

    def find_by_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        for row in self.docs.all():
            if row.get("record_id") == record_id:
                return row
        return None

    def list(self, *, workspace_id: Optional[str] = None, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = [r for r in self.docs.all() if (not workspace_id or r.get("workspace_id") == workspace_id) and (not kind or r.get("kind") == kind)]
        rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        return rows


# --- material extractors -------------------------------------------------------

def draft_material(*, audience: str, purpose: str, needed: Optional[str], channel: str, items: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Material payload of a communication: audience, purpose category, the requested items — not the wording."""
    wanted = list(items or [])
    if not wanted and needed:
        wanted = [p for p in re.split(r";|\n|,(?=\s*[A-Za-z])", str(needed)) if p.strip()]
    return {"audience": normalize_text(audience), "channel": normalize_text(channel), "purpose": normalize_text(purpose), "items": normalize_items(wanted)}


def order_material(*, order_type: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("property_ref", "borrower_ref", "vendor", "agent_or_carrier_ref", "employer_ref", "authorization_ref", "topic", "draft_ref", "purpose")
    return {"order_type": normalize_text(order_type), **{k: normalize_text(inputs.get(k)) for k in keys if inputs.get(k)}}


def tool_material(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    from .approvals_center import MATERIAL_ARG_KEYS

    material = {k: args.get(k) for k in sorted(args) if k in MATERIAL_ARG_KEYS} or dict(args)
    return {"tool": tool_name, "args": json.loads(json.dumps(material, default=str))}
