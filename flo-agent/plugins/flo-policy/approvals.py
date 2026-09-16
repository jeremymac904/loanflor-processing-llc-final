"""Approval binding for Flo ``CONFIRM`` decisions.

An :class:`Approval` is only ever minted by code that has an authenticated
user decision in hand (``source == "user"``). It is bound to the sha256 of
the proposal's structural fields, single-use, and time-limited, so:

* an approval for one recipient / file / operation cannot be reused for
  another (binding hash mismatch);
* a stale approval cannot be replayed (expiry);
* one approval executes at most once (consumption).

Nothing in this module accepts free text. There is intentionally no helper
that builds an approval from a message, document, or tool result.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from .policy import ActionProposal, utcnow

DEFAULT_APPROVAL_TTL = timedelta(minutes=15)
VALID_APPROVAL_SOURCES = frozenset({"user", "administrator_policy"})


@dataclass
class Approval:
    proposal_id: str
    binding_hash: str
    approved_by: str
    source: str = "user"
    approved_at: datetime = field(default_factory=utcnow)
    expires_at: datetime = field(default_factory=lambda: utcnow() + DEFAULT_APPROVAL_TTL)
    consumed_at: Optional[datetime] = None
    approval_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def consumed(self) -> bool:
        return self.consumed_at is not None


def bind_approval(
    proposal: ActionProposal,
    *,
    approved_by: str,
    source: str = "user",
    ttl: timedelta = DEFAULT_APPROVAL_TTL,
    now: Optional[datetime] = None,
) -> Approval:
    """Mint an approval bound to ``proposal``.

    ``approved_by`` must identify the authenticated human (or the configured
    administrator policy). ``source`` is restricted to
    :data:`VALID_APPROVAL_SOURCES`; anything else (``"email"``,
    ``"document"``, ``"tool_output"``, ``"model"``) is rejected outright.
    """
    if source not in VALID_APPROVAL_SOURCES:
        raise ValueError(f"approval source {source!r} cannot grant authority")
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by must identify the approver")
    now = now or utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return Approval(
        proposal_id=proposal.proposal_id,
        binding_hash=proposal.binding_hash(),
        approved_by=approved_by.strip(),
        source=source,
        approved_at=now,
        expires_at=now + ttl,
    )


def verify_approval(
    approval: Optional[Approval],
    proposal: ActionProposal,
    *,
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """Return ``(ok, reason)``; ``ok`` is True only for a live, exact match."""
    if approval is None:
        return False, "no approval"
    if approval.source not in VALID_APPROVAL_SOURCES:
        return False, "approval source cannot grant authority"
    if approval.proposal_id != proposal.proposal_id:
        return False, "approval is for a different proposal"
    if approval.binding_hash != proposal.binding_hash():
        return False, "approval does not match this action's target or arguments"
    now = now or utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if now >= approval.expires_at:
        return False, "approval expired"
    if approval.consumed:
        return False, "approval already used"
    return True, "ok"


class ApprovalStore:
    """In-memory single-process store. A durable store is a later phase."""

    def __init__(self) -> None:
        self._by_id: Dict[str, Approval] = {}

    def add(self, approval: Approval) -> Approval:
        self._by_id[approval.approval_id] = approval
        return approval

    def get(self, approval_id: str) -> Optional[Approval]:
        return self._by_id.get(approval_id)

    def for_proposal(self, proposal_id: str) -> Optional[Approval]:
        for approval in self._by_id.values():
            if approval.proposal_id == proposal_id and not approval.consumed:
                return approval
        return None

    def consume(self, approval: Approval, *, now: Optional[datetime] = None) -> None:
        approval.consumed_at = now or utcnow()
