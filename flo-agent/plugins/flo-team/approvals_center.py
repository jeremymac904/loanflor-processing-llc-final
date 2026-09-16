"""Ashley Approval Center — one durable queue for every Yellow (CONFIRM) action.

Every external side effect proposed by any bot lands here as an action
proposal (``schemas/action_proposal.schema.json``: proposal_id, workspace_id,
agent, action_type, recipient_or_destination, summary, payload_hash,
data_categories, policy_result, approval_id).

Binding: ``payload_hash`` is the sha256 of the exact tool arguments plus the
structural fields. An approval records that hash; :meth:`ApprovalQueue.verify`
only passes when the hash of what is about to execute equals the approved
hash. Editing a material field (recipient, body, attachments, amounts) changes
the hash, so the previous approval is *invalidated* and a fresh card is
created. Approvals are single-use and expire.

Who may approve: only a human decision (``decided_by`` = "user:<id>") or a
configured administrator policy. There is deliberately no code path that turns
model output, a message from another bot, or retrieved content into an
approval.

Runtime wiring: the flo-team ``pre_tool_call`` hook files a card whenever the
role policy returns CONFIRM and returns Hermes' ``approve`` directive, so the
native human gate in the chat is the place Ashley clicks; the desktop Approval
Center page lists the same cards from this queue and deep-links to that chat.
The card's status is closed by ``post_tool_call`` (executed / blocked / failed)
— a bot's own words never change a card.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .store import JsonDocStore, JsonlLog, new_id, now_iso, utcnow

APPROVAL_TTL = timedelta(minutes=30)
STATUSES = ("pending", "approved", "rejected", "executed", "blocked", "failed", "invalidated", "expired", "denied")
MATERIAL_ARG_KEYS = (
    "to", "cc", "bcc", "recipient", "recipients", "subject", "body", "message", "text", "content",
    "attachments", "attachment", "file", "path", "destination", "dest", "amount", "vendor", "url",
    "instructions", "title", "description", "post", "caption", "html",
    # e-signature: binds the approval to the exact document version, template and target envelope
    # (recipients/message are already covered above).
    "document_id", "document_checksum", "template_key", "envelope_id", "request_id",
)
VALID_APPROVER_SOURCES = ("user", "administrator_policy")


def payload_hash(tool_name: str, args: Dict[str, Any]) -> str:
    material = {k: args.get(k) for k in sorted(args) if k in MATERIAL_ARG_KEYS} or dict(args)
    blob = json.dumps({"tool": tool_name, "args": material}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _preview(args: Dict[str, Any]) -> Dict[str, Any]:
    """Bounded, structural preview for the card — enough to decide, never the whole payload."""
    out: Dict[str, Any] = {}
    for key in MATERIAL_ARG_KEYS:
        if key in args:
            value = args[key]
            if isinstance(value, str):
                out[key] = value[:600] + ("…" if len(value) > 600 else "")
            elif isinstance(value, (list, tuple)):
                out[key] = [str(v)[:120] for v in value][:10]
            elif isinstance(value, dict):
                out[key] = {str(k): str(v)[:120] for k, v in list(value.items())[:10]}
            else:
                out[key] = value
    return out


class ApprovalError(ValueError):
    pass


class ApprovalQueue:
    def __init__(self, root) -> None:
        self.docs = JsonDocStore(root / "approvals")
        self.log = JsonlLog(root / "activity", "activity")

    # -- proposing --------------------------------------------------------

    def propose(
        self,
        *,
        agent: str,
        tool_name: str,
        args: Dict[str, Any],
        action_type: str,
        capability: str,
        policy_result: str,
        workspace_id: Optional[str] = None,
        summary: str = "",
        data_categories: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        args = dict(args or {})
        digest = payload_hash(tool_name, args)
        # A pending card for the identical payload from the same agent is reused
        # (retries must not spam Ashley); a changed payload is a new card.
        for existing in self.docs.all():
            if existing.get("status") == "pending" and existing.get("agent") == agent \
                    and existing.get("payload_hash") == digest and existing.get("tool_name") == tool_name:
                return existing
        card = {
            "proposal_id": new_id("prop"),
            "workspace_id": workspace_id,
            "agent": agent,
            "action_type": action_type,
            "capability": capability,
            "tool_name": tool_name,
            "recipient_or_destination": _destination(args),
            "summary": summary or f"{agent} wants to run {tool_name}",
            "payload_hash": digest,
            "payload_preview": _preview(args),
            "data_categories": list(data_categories or []),
            "policy_result": policy_result,
            "approval_id": None,
            "status": "pending" if policy_result == "confirm" else ("denied" if policy_result == "deny" else "executed"),
            "reason": reason,
            "session_id": session_id,
            "created_at": now_iso(),
            "expires_at": (utcnow() + APPROVAL_TTL).isoformat(),
            "decided_by": None,
            "decided_at": None,
            "execution_ref": None,
            "history": [{"at": now_iso(), "event": "proposed", "by": agent}],
        }
        self.docs.put(card["proposal_id"], card)
        self.log.append({"event": "approval.proposed", "actor": agent, "proposal_id": card["proposal_id"],
                         "workspace_id": workspace_id, "action_type": action_type, "status": card["status"]})
        return card

    # -- deciding (human only) ---------------------------------------------

    def decide(self, proposal_id: str, *, choice: str, decided_by: str, source: str = "user",
               now: Optional[datetime] = None) -> Dict[str, Any]:
        if source not in VALID_APPROVER_SOURCES:
            raise ApprovalError(f"approval source {source!r} cannot grant authority")
        if not decided_by or not decided_by.strip():
            raise ApprovalError("decided_by must identify the approver")
        card = self._get(proposal_id)
        if card["status"] != "pending":
            raise ApprovalError(f"card is {card['status']}, not pending")
        now = now or utcnow()
        if now >= datetime.fromisoformat(card["expires_at"]):
            self._set(card, "expired", "expiry")
            raise ApprovalError("approval card expired; the bot must propose again")
        choice = choice.strip().lower()
        if choice not in ("approve", "reject"):
            raise ApprovalError("choice must be approve or reject")
        card["decided_by"] = f"{source}:{decided_by.strip()}"
        card["decided_at"] = now.isoformat()
        if choice == "approve":
            card["approval_id"] = new_id("appr")
            self._set(card, "approved", card["decided_by"])
        else:
            self._set(card, "rejected", card["decided_by"])
        return card

    def edit(self, proposal_id: str, *, agent: str, new_args: Dict[str, Any], summary: Optional[str] = None) -> Dict[str, Any]:
        """A material edit invalidates the old card and creates a fresh pending one."""
        old = self._get(proposal_id)
        new_hash = payload_hash(old["tool_name"], new_args)
        if new_hash == old["payload_hash"]:
            return old
        if old["status"] in ("pending", "approved"):
            self._set(old, "invalidated", agent, note="material edit")
        return self.propose(
            agent=old["agent"], tool_name=old["tool_name"], args=new_args, action_type=old["action_type"],
            capability=old["capability"], policy_result="confirm", workspace_id=old.get("workspace_id"),
            summary=summary or old["summary"], data_categories=old.get("data_categories"),
            session_id=old.get("session_id"), reason=f"re-proposed after edit of {proposal_id}",
        )

    # -- verifying at execution time -------------------------------------

    def verify(self, proposal_id: str, *, tool_name: str, args: Dict[str, Any], now: Optional[datetime] = None) -> Tuple[bool, str]:
        card = self.docs.get(proposal_id)
        if card is None:
            return False, "no such approval card"
        if card["status"] != "approved":
            return False, f"card is {card['status']}"
        if card["tool_name"] != tool_name:
            return False, "approval is for a different tool"
        if card["payload_hash"] != payload_hash(tool_name, args):
            return False, "approval does not match this payload (material edit invalidates approval)"
        now = now or utcnow()
        if now >= datetime.fromisoformat(card["expires_at"]):
            self._set(card, "expired", "expiry")
            return False, "approval expired"
        return True, "ok"

    # -- closing (execution outcome only) ----------------------------------

    def close(self, proposal_id: str, *, status: str, execution_ref: Optional[str] = None, by: str = "policy") -> Optional[Dict[str, Any]]:
        if status not in ("executed", "blocked", "failed", "denied"):
            raise ApprovalError(f"cannot close a card with status {status!r}")
        card = self.docs.get(proposal_id)
        if card is None:
            return None
        if status == "executed":
            card["execution_ref"] = execution_ref or "confirmed-by-execution-tool"
        self._set(card, status, by)
        return card

    def find_pending(self, *, agent: str, tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        digest = payload_hash(tool_name, args)
        for card in self.docs.all():
            if card.get("agent") == agent and card.get("tool_name") == tool_name and card.get("payload_hash") == digest \
                    and card.get("status") in ("pending", "approved"):
                return card
        return None

    # -- views ------------------------------------------------------------

    def list(self, *, status: Optional[str] = None, agent: Optional[str] = None, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = []
        for card in self.docs.all():
            if status and card.get("status") != status:
                continue
            if agent and card.get("agent") != agent:
                continue
            if workspace_id and card.get("workspace_id") != workspace_id:
                continue
            rows.append({k: card.get(k) for k in (
                "proposal_id", "workspace_id", "agent", "action_type", "capability", "tool_name",
                "recipient_or_destination", "summary", "payload_hash", "payload_preview", "data_categories",
                "policy_result", "status", "created_at", "expires_at", "decided_by", "execution_ref", "session_id")})
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return rows

    # -- internals ---------------------------------------------------------

    def _get(self, proposal_id: str) -> Dict[str, Any]:
        card = self.docs.get(proposal_id)
        if card is None:
            raise ApprovalError(f"no such approval card {proposal_id}")
        return card

    def _set(self, card: Dict[str, Any], status: str, by: str, note: str = "") -> None:
        card["status"] = status
        card.setdefault("history", []).append({"at": now_iso(), "event": status, "by": by, **({"note": note} if note else {})})
        self.docs.put(card["proposal_id"], card)
        self.log.append({"event": f"approval.{status}", "actor": by, "proposal_id": card["proposal_id"],
                         "workspace_id": card.get("workspace_id"), "agent": card.get("agent"), "action_type": card.get("action_type")})


def _destination(args: Dict[str, Any]) -> Optional[str]:
    for key in ("to", "recipient", "recipients", "destination", "dest", "vendor", "url", "path", "channel"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:200]
        if isinstance(value, (list, tuple)) and value:
            return ", ".join(str(v) for v in value[:5])[:200]
    return None
