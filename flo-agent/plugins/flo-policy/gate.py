"""The execution gate: proposal → policy → (approval) → executor → result.

This is the contract the future Flo Google connector and portal adapters must
call. An executor never receives free-form model text; it receives an
:class:`ActionProposal` that policy has already decided on, plus (for
``CONFIRM``) an :class:`Approval` that verified against that exact proposal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from .approvals import Approval, ApprovalStore, verify_approval
from .audit import AuditEvent, AuditLog, NullAuditLog
from .policy import (
    ActionProposal,
    Decision,
    PolicyDecision,
    PolicyTable,
    evaluate,
    utcnow,
)

Executor = Callable[[ActionProposal], Any]


@dataclass
class ExecutionResult:
    proposal_id: str
    status: str                          # executed | blocked | denied | failed | pending_confirmation
    decision: Decision
    approval_id: Optional[str] = None
    started_at: datetime = field(default_factory=utcnow)
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    result_ref: Optional[str] = None     # opaque pointer (message id, file id) — never the payload
    reason: str = ""

    @property
    def executed(self) -> bool:
        return self.status == "executed"


class PolicyGate:
    """Deterministic gate. Model text cannot reach ``executor`` unfiltered."""

    def __init__(
        self,
        table: Optional[PolicyTable] = None,
        *,
        approvals: Optional[ApprovalStore] = None,
        audit: Optional[AuditLog] = None,
        profile: Optional[str] = None,
    ) -> None:
        self.table = table or PolicyTable.default()
        self.approvals = approvals or ApprovalStore()
        self.audit = audit or NullAuditLog()
        self.profile = profile

    # -- decisions --------------------------------------------------------

    def decide(self, proposal: ActionProposal, *, session_id: Optional[str] = None) -> PolicyDecision:
        decision = evaluate(proposal, self.table)
        self.audit.write(AuditEvent(
            event_type="policy_decision",
            actor=proposal.created_by,
            tool_name=proposal.tool_name,
            capability=proposal.capability.value,
            operation=proposal.operation,
            policy_decision=decision.decision.value,
            approval_state="requested" if decision.decision is Decision.CONFIRM else "none",
            proposal_id=proposal.proposal_id,
            loan_ref=proposal.loan_ref,
            profile=self.profile,
            session_id=session_id,
            resource_meta=_resource_meta(proposal),
            reason=decision.reason,
        ))
        return decision

    # -- execution --------------------------------------------------------

    def execute(
        self,
        proposal: ActionProposal,
        executor: Executor,
        *,
        approval: Optional[Approval] = None,
        session_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> ExecutionResult:
        decision = self.decide(proposal, session_id=session_id)
        result = ExecutionResult(
            proposal_id=proposal.proposal_id,
            status="blocked",
            decision=decision.decision,
            reason=decision.reason,
        )

        if decision.decision is Decision.DENY:
            result.status = "denied"
            return self._finish(result, proposal, session_id)

        if decision.decision is Decision.CONFIRM:
            ok, why = verify_approval(approval, proposal, now=now)
            if not ok:
                result.status = "pending_confirmation"
                result.reason = why
                self.audit.write(AuditEvent(
                    event_type="approval",
                    actor="policy",
                    tool_name=proposal.tool_name,
                    capability=proposal.capability.value,
                    operation=proposal.operation,
                    policy_decision=decision.decision.value,
                    approval_state="denied" if approval is not None else "requested",
                    proposal_id=proposal.proposal_id,
                    approval_id=approval.approval_id if approval else None,
                    loan_ref=proposal.loan_ref,
                    profile=self.profile,
                    session_id=session_id,
                    reason=why,
                ))
                return self._finish(result, proposal, session_id)
            assert approval is not None
            result.approval_id = approval.approval_id

        try:
            outcome = executor(proposal)
            result.status = "executed"
            result.result_ref = _result_ref(outcome)
        except Exception as exc:  # noqa: BLE001 - surfaced in the result, never swallowed silently
            result.status = "failed"
            result.error = f"{type(exc).__name__}: {exc}"
        finally:
            if approval is not None and decision.decision is Decision.CONFIRM:
                # Consume even on failure: a retry needs a fresh human decision.
                self.approvals.consume(approval, now=now)
                self.audit.write(AuditEvent(
                    event_type="approval",
                    actor=f"user:{approval.approved_by}",
                    tool_name=proposal.tool_name,
                    capability=proposal.capability.value,
                    operation=proposal.operation,
                    policy_decision=decision.decision.value,
                    approval_state="consumed",
                    proposal_id=proposal.proposal_id,
                    approval_id=approval.approval_id,
                    loan_ref=proposal.loan_ref,
                    profile=self.profile,
                    session_id=session_id,
                ))
        return self._finish(result, proposal, session_id)

    def _finish(self, result: ExecutionResult, proposal: ActionProposal, session_id: Optional[str]) -> ExecutionResult:
        result.finished_at = utcnow()
        self.audit.write(AuditEvent(
            event_type="execution",
            actor="policy",
            tool_name=proposal.tool_name,
            capability=proposal.capability.value,
            operation=proposal.operation,
            policy_decision=result.decision.value,
            result_status=result.status,
            proposal_id=proposal.proposal_id,
            approval_id=result.approval_id,
            loan_ref=proposal.loan_ref,
            profile=self.profile,
            session_id=session_id,
            resource_meta={**_resource_meta(proposal), "result_ref": result.result_ref},
            reason=result.error or result.reason,
        ))
        return result


def _resource_meta(proposal: ActionProposal) -> dict:
    return {
        "resource": proposal.resource,
        "destination": proposal.destination,
        "data_categories": list(proposal.data_categories),
        "args_digest": proposal.args_digest[:16] if proposal.args_digest else None,
    }


def _result_ref(outcome: Any) -> Optional[str]:
    if outcome is None:
        return None
    if isinstance(outcome, str):
        return outcome[:128]
    if isinstance(outcome, dict):
        for key in ("id", "message_id", "file_id", "ref", "result_ref"):
            value = outcome.get(key)
            if isinstance(value, (str, int)):
                return str(value)[:128]
    return type(outcome).__name__
