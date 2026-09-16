"""flo-policy plugin — deterministic action policy for the Flo distribution.

Wires two hooks:

* ``pre_tool_call`` — classifies every tool call into a Flo capability,
  evaluates the deterministic policy table and returns the matching Hermes
  directive:

  - ``ALLOW``   → ``None`` (the call proceeds, decision is audited)
  - ``CONFIRM`` → ``{"action": "approve", ...}`` which Hermes escalates to
    its existing human-approval gate (``tools.approval.request_tool_approval``).
    The model cannot skip it; a denied/timed-out gate fails closed.
  - ``DENY``    → ``{"action": "block", ...}`` — the tool never runs and the
    reason becomes the tool result the model sees.

* ``post_tool_call`` — audits the outcome (success / error) as metadata only.

Fail-closed: any internal error in the hook returns a ``block`` directive.
Hermes' dispatcher would otherwise treat a raised exception as "no
directive" and let the call through.

Policy overrides: ``<HERMES_HOME>/flo/policy.yaml`` (see ``policy.py``) may
tighten capabilities; it cannot relax the confirm/deny floors. Audit events
land in ``<HERMES_HOME>/flo/audit/audit-YYYY-MM-DD.jsonl``. Neither location is
writable through the agent's own file tools (that write is itself classified
as ``policy_disable`` and denied).

The Ashley profile enables this plugin via ``plugins.enabled`` in its
``config.yaml`` (see ``.flo/profile/ashley/config.yaml``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .approvals import (  # noqa: F401 - public API re-export
    Approval,
    ApprovalStore,
    bind_approval,
    verify_approval,
)
from .audit import AuditEvent, AuditLog, NullAuditLog, redact  # noqa: F401
from .gate import ExecutionResult, PolicyGate  # noqa: F401
from .policy import (  # noqa: F401
    DEFAULT_CAPABILITY_POLICY,
    ActionProposal,
    Capability,
    Decision,
    PolicyDecision,
    PolicyTable,
    classify_tool_call,
    evaluate,
)

logger = logging.getLogger(__name__)

POLICY_FILE_NAME = "policy.yaml"
FLO_STATE_DIRNAME = "flo"


def _hermes_home() -> Optional[Path]:
    try:
        from hermes_constants import get_hermes_home  # type: ignore

        return Path(get_hermes_home())
    except Exception:  # pragma: no cover - only outside a Hermes checkout
        raw = os.environ.get("HERMES_HOME")
        return Path(raw) if raw else None


def load_policy_table(home: Optional[Path] = None) -> PolicyTable:
    """Default table, tightened by ``<home>/flo/policy.yaml`` when present.

    A malformed policy file is a hard error for the *file* (logged) but the
    plugin keeps the default table — defaults are the safe direction.
    """
    home = home or _hermes_home()
    if home is None:
        return PolicyTable.default()
    path = home / FLO_STATE_DIRNAME / POLICY_FILE_NAME
    if not path.exists():
        return PolicyTable.default()
    try:
        import yaml  # type: ignore

        with open(path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        if not isinstance(raw, dict):
            raise ValueError("policy file must be a mapping")
        return PolicyTable.from_mapping(raw)
    except Exception as exc:
        logger.error("flo-policy: ignoring invalid %s (%s); using defaults", path, exc)
        return PolicyTable.default()


def _audit_log(home: Optional[Path]) -> AuditLog:
    if home is None:
        return NullAuditLog()
    return AuditLog(home / FLO_STATE_DIRNAME / "audit")


class FloPolicyHooks:
    """Hook callbacks bound to one policy table + audit log."""

    def __init__(self, table: PolicyTable, audit: AuditLog, *, profile: Optional[str] = None) -> None:
        self.table = table
        self.audit = audit
        self.profile = profile
        self._pending: Dict[str, ActionProposal] = {}

    # -- pre_tool_call ----------------------------------------------------

    def pre_tool_call(
        self,
        tool_name: str = "",
        args: Any = None,
        session_id: str = "",
        tool_call_id: str = "",
        **_: Any,
    ) -> Optional[Dict[str, str]]:
        try:
            proposal = classify_tool_call(tool_name, args if isinstance(args, dict) else {}, table=self.table)
            decision = evaluate(proposal, self.table)
            self.audit.write(AuditEvent(
                event_type="policy_decision",
                actor="model",
                tool_name=proposal.tool_name,
                capability=proposal.capability.value,
                operation=proposal.operation,
                policy_decision=decision.decision.value,
                approval_state="requested" if decision.decision is Decision.CONFIRM else "none",
                proposal_id=proposal.proposal_id,
                profile=self.profile,
                session_id=session_id or None,
                resource_meta={
                    "resource": proposal.resource,
                    "destination": proposal.destination,
                    "data_categories": list(proposal.data_categories),
                    "args_digest": proposal.args_digest[:16],
                },
                reason=decision.reason,
            ))
            if tool_call_id:
                self._pending[tool_call_id] = proposal

            if decision.decision is Decision.ALLOW:
                return None
            if decision.decision is Decision.CONFIRM:
                return {
                    "action": "approve",
                    "message": decision.reason,
                    # Grain for Hermes' "[a]lways" allowlist: capability +
                    # target digest, never the bare tool name, so approving one
                    # recipient/file never blankets the tool.
                    "rule_key": _rule_key(proposal),
                }
            return {"action": "block", "message": f"BLOCKED by Flo policy: {decision.reason}"}
        except Exception as exc:  # noqa: BLE001 - fail closed
            logger.error("flo-policy: pre_tool_call failed for %s: %s", tool_name, exc)
            return {
                "action": "block",
                "message": f"BLOCKED by Flo policy: policy evaluation failed for {tool_name}; nothing was executed.",
            }

    # -- post_tool_call ---------------------------------------------------

    def post_tool_call(
        self,
        tool_name: str = "",
        result: Any = None,
        session_id: str = "",
        tool_call_id: str = "",
        **_: Any,
    ) -> None:
        try:
            proposal = self._pending.pop(tool_call_id, None) if tool_call_id else None
            status = _classify_result(result)
            self.audit.write(AuditEvent(
                event_type="tool_result",
                actor="policy",
                tool_name=tool_name,
                capability=proposal.capability.value if proposal else "unknown",
                operation=proposal.operation if proposal else "call",
                result_status=status,
                proposal_id=proposal.proposal_id if proposal else None,
                profile=self.profile,
                session_id=session_id or None,
            ))
        except Exception as exc:  # noqa: BLE001 - observer must never break the loop
            logger.debug("flo-policy: post_tool_call audit failed: %s", exc)


def _rule_key(proposal: ActionProposal) -> str:
    target = proposal.destination or proposal.resource or ""
    digest = hashlib.sha256(target.encode("utf-8")).hexdigest()[:10] if target else "any"
    return f"flo:{proposal.capability.value}:{digest}"


def _classify_result(result: Any) -> str:
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except (ValueError, TypeError):
            return "executed"
        if isinstance(parsed, dict) and parsed.get("error"):
            text = str(parsed.get("error"))
            if text.startswith("BLOCKED"):
                return "blocked"
            return "failed"
    return "executed"


def _profile_name(home: Optional[Path]) -> Optional[str]:
    """Best-effort acting profile for audit rows (env → HERMES_HOME layout → None)."""
    for var in ("HERMES_PROFILE_NAME", "HERMES_PROFILE"):
        value = os.environ.get(var, "").strip()
        if value:
            return value.lower()
    if home is not None and home.parent.name == "profiles":
        return home.name.lower()
    return None


def build_hooks(home: Optional[Path] = None, *, profile: Optional[str] = None) -> FloPolicyHooks:
    home = home or _hermes_home()
    return FloPolicyHooks(load_policy_table(home), _audit_log(home), profile=profile or _profile_name(home))


def register(ctx) -> None:
    hooks = build_hooks()
    ctx.register_hook("pre_tool_call", hooks.pre_tool_call)
    ctx.register_hook("post_tool_call", hooks.post_tool_call)
