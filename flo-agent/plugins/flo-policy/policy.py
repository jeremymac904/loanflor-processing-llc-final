"""Flo deterministic action policy — pure, dependency-free.

Contract (see ``.flo/docs/07_SECURITY_AND_PERMISSIONS.md`` and ADR-005/006):

* The model may *propose* an action (an :class:`ActionProposal`).
* :func:`evaluate` maps that proposal to exactly one :class:`Decision`
  (``ALLOW`` / ``CONFIRM`` / ``DENY``) using only **structured fields**.
  It never reads free-form text, so text retrieved from email, PDFs, Drive,
  web pages, MCP servers or tool output cannot change the outcome.
* ``CONFIRM`` never executes on its own; it needs an :class:`Approval`
  (``approvals.py``) that is bound to the exact proposal.

This module deliberately imports nothing from Hermes so it can be unit-tested
and reused by the future Google connector without the agent runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

POLICY_VERSION = 1


class Decision(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------
# Capability ids are the policy vocabulary. Tool names are mapped onto these
# (see ``classify_tool_call``); the policy table is keyed by capability, not
# by tool name, so the Flo connector can add tools without editing policy.

class Capability(str, Enum):
    # No external side effect
    LOCAL_READ = "local_read"
    LOCAL_UI = "local_ui"
    LOCAL_NOTE = "local_note"            # todo / memory / session search
    WEB_READ = "web_read"
    EMAIL_SEARCH = "email_search"
    EMAIL_READ = "email_read"
    EMAIL_DRAFT = "email_draft"
    DRIVE_SEARCH = "drive_search"
    DRIVE_READ = "drive_read"
    CALENDAR_READ = "calendar_read"
    # External side effects (confirm)
    EMAIL_SEND = "email_send"
    EMAIL_MODIFY = "email_modify"
    DRIVE_UPLOAD = "drive_upload"
    DRIVE_MOVE_OR_RENAME = "drive_move_or_rename"
    DOCUMENT_EDIT = "document_edit"
    LOCAL_FILE_WRITE = "local_file_write"
    CALENDAR_WRITE = "calendar_write"
    EXTERNAL_STATUS_CHANGE = "external_status_change"
    PORTAL_SUBMIT = "portal_submit"
    OUTBOUND_MESSAGE = "outbound_message"
    SCHEDULE_JOB = "schedule_job"
    # Deny by default
    DRIVE_SHARE_EXTERNAL = "drive_share_external"
    DRIVE_DELETE_PERMANENT = "drive_delete_permanent"
    MASS_OUTBOUND = "mass_outbound"
    TERMINAL_HOST = "terminal_host"
    COMPUTER_USE = "computer_use"
    DELEGATION = "delegation"
    SELF_MODIFICATION = "self_modification"
    POLICY_DISABLE = "policy_disable"
    CREDENTIAL_EXPOSURE = "credential_exposure"
    UNKNOWN = "unknown"


#: Default decision per capability.
#:
#: Owner directive (2026-09-08): Flo must be easy and unrestricted for Ashley.
#: Everything runs and is audited; the only things that stop for a one-click
#: confirmation are actions that cannot be undone (an email leaving the
#: building, a permanent delete, sharing outside the org, a mass send) and the
#: two things that would silently weaken Flo itself (rewriting its policy /
#: audit, exposing stored credentials). Nothing is denied by default.
DEFAULT_CAPABILITY_POLICY: Dict[Capability, Decision] = {
    Capability.LOCAL_READ: Decision.ALLOW,
    Capability.LOCAL_UI: Decision.ALLOW,
    Capability.LOCAL_NOTE: Decision.ALLOW,
    Capability.WEB_READ: Decision.ALLOW,
    Capability.EMAIL_SEARCH: Decision.ALLOW,
    Capability.EMAIL_READ: Decision.ALLOW,
    Capability.EMAIL_DRAFT: Decision.ALLOW,
    Capability.DRIVE_SEARCH: Decision.ALLOW,
    Capability.DRIVE_READ: Decision.ALLOW,
    Capability.CALENDAR_READ: Decision.ALLOW,
    Capability.EMAIL_MODIFY: Decision.ALLOW,
    Capability.DRIVE_UPLOAD: Decision.ALLOW,
    Capability.DRIVE_MOVE_OR_RENAME: Decision.ALLOW,
    Capability.DOCUMENT_EDIT: Decision.ALLOW,
    Capability.LOCAL_FILE_WRITE: Decision.ALLOW,
    Capability.CALENDAR_WRITE: Decision.ALLOW,
    Capability.EXTERNAL_STATUS_CHANGE: Decision.ALLOW,
    Capability.PORTAL_SUBMIT: Decision.ALLOW,
    Capability.OUTBOUND_MESSAGE: Decision.ALLOW,
    Capability.SCHEDULE_JOB: Decision.ALLOW,
    Capability.TERMINAL_HOST: Decision.ALLOW,
    Capability.COMPUTER_USE: Decision.ALLOW,
    Capability.DELEGATION: Decision.ALLOW,
    Capability.SELF_MODIFICATION: Decision.ALLOW,
    Capability.UNKNOWN: Decision.ALLOW,
    # One click before the irreversible / self-weakening ones.
    Capability.EMAIL_SEND: Decision.CONFIRM,
    Capability.MASS_OUTBOUND: Decision.CONFIRM,
    Capability.DRIVE_SHARE_EXTERNAL: Decision.CONFIRM,
    Capability.DRIVE_DELETE_PERMANENT: Decision.CONFIRM,
    Capability.POLICY_DISABLE: Decision.CONFIRM,
    Capability.CREDENTIAL_EXPOSURE: Decision.CONFIRM,
}

#: Capabilities an operator policy file may not relax below CONFIRM (the
#: irreversible ones). Everything else may be set to any decision.
_FLOOR_CONFIRM = frozenset({
    Capability.MASS_OUTBOUND, Capability.DRIVE_SHARE_EXTERNAL,
    Capability.DRIVE_DELETE_PERMANENT,
})
_FLOOR_DENY: frozenset = frozenset()

_RANK = {Decision.ALLOW: 0, Decision.CONFIRM: 1, Decision.DENY: 2}


@dataclass(frozen=True)
class PolicyTable:
    """Capability -> Decision mapping plus a few numeric thresholds."""

    decisions: Mapping[Capability, Decision]
    mass_outbound_threshold: int = 10
    version: int = POLICY_VERSION

    @classmethod
    def default(cls) -> "PolicyTable":
        return cls(decisions=dict(DEFAULT_CAPABILITY_POLICY))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "PolicyTable":
        """Build a table from a parsed ``flo/policy.yaml`` document.

        Shape::

            version: 1
            mass_outbound_threshold: 5
            capabilities:
              email_send: confirm
              drive_share_external: deny

        Unknown capability names raise ``ValueError`` (a typo must not
        silently leave the default in place). Decisions below the floor for
        the capability also raise — an operator file can tighten policy but
        never relax the load-bearing gates.
        """
        decisions = dict(DEFAULT_CAPABILITY_POLICY)
        caps = raw.get("capabilities") or {}
        if not isinstance(caps, Mapping):
            raise ValueError("policy 'capabilities' must be a mapping")
        for key, value in caps.items():
            try:
                cap = Capability(str(key))
            except ValueError as exc:
                raise ValueError(f"unknown capability in policy file: {key!r}") from exc
            try:
                decision = Decision(str(value).strip().lower())
            except ValueError as exc:
                raise ValueError(f"invalid decision for {key!r}: {value!r}") from exc
            if cap in _FLOOR_DENY and decision is not Decision.DENY:
                raise ValueError(f"{cap.value} cannot be relaxed below deny")
            if cap in _FLOOR_CONFIRM and _RANK[decision] < _RANK[Decision.CONFIRM]:
                raise ValueError(f"{cap.value} cannot be relaxed below confirm")
            decisions[cap] = decision
        threshold = raw.get("mass_outbound_threshold", 10)
        if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold < 1:
            raise ValueError("mass_outbound_threshold must be a positive integer")
        version = raw.get("version", POLICY_VERSION)
        if version != POLICY_VERSION:
            raise ValueError(f"unsupported policy version {version!r}")
        return cls(decisions=decisions, mass_outbound_threshold=threshold, version=version)

    def decision_for(self, capability: Capability) -> Decision:
        return self.decisions.get(capability, DEFAULT_CAPABILITY_POLICY[Capability.UNKNOWN])


# ---------------------------------------------------------------------------
# Action proposals
# ---------------------------------------------------------------------------

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def canonical_digest(value: Any) -> str:
    """Stable sha256 of a JSON-serialisable value (sorted keys)."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ActionProposal:
    """What the model wants to do, reduced to structured, auditable fields.

    ``args_digest`` pins the exact tool arguments without carrying their
    content (which may hold borrower data). Approval binding covers every
    field below except ``proposal_id``/``created_at``/``summary``, so an
    approval for one recipient or one file cannot be replayed for another.
    """

    capability: Capability
    tool_name: str
    operation: str
    resource: Optional[str] = None
    destination: Optional[str] = None
    data_categories: Tuple[str, ...] = ()
    args_digest: str = ""
    loan_ref: Optional[str] = None
    summary: str = ""
    created_by: str = "model"
    proposal_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime = field(default_factory=utcnow)

    def binding_fields(self) -> Dict[str, Any]:
        return {
            "capability": self.capability.value,
            "tool_name": self.tool_name,
            "operation": self.operation,
            "resource": self.resource,
            "destination": self.destination,
            "data_categories": list(self.data_categories),
            "args_digest": self.args_digest,
            "loan_ref": self.loan_ref,
        }

    def binding_hash(self) -> str:
        return canonical_digest(self.binding_fields())


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    capability: Capability
    rule: str
    reason: str
    proposal_id: str

    @property
    def executable_without_approval(self) -> bool:
        return self.decision is Decision.ALLOW


# ---------------------------------------------------------------------------
# Tool classification
# ---------------------------------------------------------------------------
# Hermes core tool names -> capability. Names not listed fall to UNKNOWN
# (confirm). Flo connector tool names (``flo_*``) are the contract for the
# future least-privilege Google connector; they do not exist yet.

_TOOL_CAPABILITIES: Dict[str, Capability] = {
    # Hermes read-only / local
    "read_file": Capability.LOCAL_READ,
    "search_files": Capability.LOCAL_READ,
    "skills_list": Capability.LOCAL_READ,
    "skill_view": Capability.LOCAL_READ,
    "tool_search": Capability.LOCAL_READ,
    "tool_describe": Capability.LOCAL_READ,
    "session_search": Capability.LOCAL_NOTE,
    "todo": Capability.LOCAL_NOTE,
    "memory": Capability.LOCAL_NOTE,
    "clarify": Capability.LOCAL_UI,
    "tip": Capability.LOCAL_UI,
    "tour": Capability.LOCAL_UI,
    "focus_pane": Capability.LOCAL_UI,
    "desktop_preview": Capability.LOCAL_UI,
    "drive_preview": Capability.LOCAL_UI,
    "read_window_below": Capability.LOCAL_UI,
    "annotate_preview": Capability.LOCAL_UI,
    "apply_layout": Capability.LOCAL_UI,
    "vision_analyze": Capability.LOCAL_READ,
    "video_analyze": Capability.LOCAL_READ,
    "text_to_speech": Capability.LOCAL_UI,
    "web_search": Capability.WEB_READ,
    "web_extract": Capability.WEB_READ,
    "x_search": Capability.WEB_READ,
    # Hermes side effects
    "write_file": Capability.LOCAL_FILE_WRITE,
    "patch": Capability.LOCAL_FILE_WRITE,
    "send_message": Capability.OUTBOUND_MESSAGE,
    "react_to_message": Capability.OUTBOUND_MESSAGE,
    "cronjob": Capability.SCHEDULE_JOB,
    # Hermes deny-by-default
    "terminal": Capability.TERMINAL_HOST,
    "execute_code": Capability.TERMINAL_HOST,
    "process": Capability.TERMINAL_HOST,
    "close_terminal": Capability.TERMINAL_HOST,
    "read_terminal": Capability.TERMINAL_HOST,
    "computer_use": Capability.COMPUTER_USE,
    "browser_exec": Capability.COMPUTER_USE,
    "browser_cdp": Capability.COMPUTER_USE,
    "delegate_task": Capability.DELEGATION,
    "skill_manage": Capability.SELF_MODIFICATION,
    "setup_mcp": Capability.SELF_MODIFICATION,
    # Flo connector contract (future; see .flo/docs/08_GOOGLE_WORKSPACE_INTEGRATION.md)
    "flo_email_search": Capability.EMAIL_SEARCH,
    "flo_email_read": Capability.EMAIL_READ,
    "flo_email_create_draft": Capability.EMAIL_DRAFT,
    "flo_email_send": Capability.EMAIL_SEND,
    "flo_email_modify": Capability.EMAIL_MODIFY,
    "flo_drive_search": Capability.DRIVE_SEARCH,
    "flo_drive_read": Capability.DRIVE_READ,
    "flo_drive_upload": Capability.DRIVE_UPLOAD,
    "flo_drive_move": Capability.DRIVE_MOVE_OR_RENAME,
    "flo_drive_rename": Capability.DRIVE_MOVE_OR_RENAME,
    "flo_drive_share": Capability.DRIVE_SHARE_EXTERNAL,
    "flo_drive_delete": Capability.DRIVE_DELETE_PERMANENT,
    "flo_document_edit": Capability.DOCUMENT_EDIT,
    "flo_calendar_read": Capability.CALENDAR_READ,
    "flo_calendar_write": Capability.CALENDAR_WRITE,
    "flo_portal_submit": Capability.PORTAL_SUBMIT,
    "flo_status_update": Capability.EXTERNAL_STATUS_CHANGE,
}

_PREFIX_CAPABILITIES: Tuple[Tuple[str, Capability], ...] = (
    ("browser_", Capability.COMPUTER_USE),
    ("kanban_", Capability.DELEGATION),
    ("discord", Capability.OUTBOUND_MESSAGE),
    ("yb_send", Capability.OUTBOUND_MESSAGE),
    ("feishu_drive_", Capability.DOCUMENT_EDIT),
    ("ha_call", Capability.EXTERNAL_STATUS_CHANGE),
)

#: Files under HERMES_HOME (or anywhere) whose write disables policy/audit or
#: whose read exposes credentials. Matched case-insensitively on the
#: normalised path.
_PROTECTED_WRITE_PATTERNS = (
    re.compile(r"(^|[\\/])config\.ya?ml$", re.I),
    re.compile(r"(^|[\\/])\.env(\..*)?$", re.I),
    re.compile(r"(^|[\\/])flo[\\/]policy\.ya?ml$", re.I),
    re.compile(r"(^|[\\/])flo[\\/]audit([\\/]|$)", re.I),
    re.compile(r"(^|[\\/])plugins([\\/]|$)", re.I),
    re.compile(r"(^|[\\/])skills([\\/]|$)", re.I),
    re.compile(r"(^|[\\/])SOUL\.md$", re.I),
)
_CREDENTIAL_READ_PATTERNS = (
    re.compile(r"(^|[\\/])\.env(\..*)?$", re.I),
    re.compile(r"token[^\\/]*\.json$", re.I),
    re.compile(r"credential[^\\/]*\.json$", re.I),
    re.compile(r"client_secret[^\\/]*\.json$", re.I),
    re.compile(r"auth\.json$", re.I),
    re.compile(r"(^|[\\/])\.ssh([\\/]|$)", re.I),
)

_PATH_ARGS = ("path", "file_path", "target", "source", "dest", "destination")
_RECIPIENT_ARGS = ("to", "recipients", "recipient", "cc", "bcc", "target", "email")


def _first_str(args: Mapping[str, Any], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _recipient_count(args: Mapping[str, Any]) -> int:
    total = 0
    for key in _RECIPIENT_ARGS:
        value = args.get(key)
        if isinstance(value, str):
            total += len([p for p in re.split(r"[,;\s]+", value) if p])
        elif isinstance(value, (list, tuple, set)):
            total += len(value)
    return total


def _matches(path: str, patterns: Iterable[re.Pattern[str]]) -> bool:
    norm = path.replace("\\", "/")
    return any(p.search(norm) for p in patterns)


def classify_tool_call(
    tool_name: str,
    args: Optional[Mapping[str, Any]],
    *,
    table: Optional[PolicyTable] = None,
    loan_ref: Optional[str] = None,
) -> ActionProposal:
    """Reduce a raw tool call to an :class:`ActionProposal`.

    Only *structural* facts are used: the tool name, argument **keys**, path
    shapes, and recipient counts. Free text (email bodies, document content,
    "notes" arguments) is digested, never interpreted.
    """
    table = table or PolicyTable.default()
    args = dict(args) if isinstance(args, Mapping) else {}
    name = (tool_name or "").strip()

    capability = _TOOL_CAPABILITIES.get(name)
    if capability is None:
        for prefix, cap in _PREFIX_CAPABILITIES:
            if name.startswith(prefix):
                capability = cap
                break
    if capability is None:
        capability = Capability.UNKNOWN

    resource = _first_str(args, _PATH_ARGS)
    destination = _first_str(args, _RECIPIENT_ARGS) if capability in (
        Capability.EMAIL_SEND, Capability.OUTBOUND_MESSAGE, Capability.MASS_OUTBOUND,
        Capability.DRIVE_SHARE_EXTERNAL, Capability.CALENDAR_WRITE,
    ) else None
    operation = str(args.get("action") or args.get("operation") or "call")

    # Structural escalations. These only tighten; they never relax.
    if capability in (Capability.LOCAL_FILE_WRITE, Capability.SELF_MODIFICATION) and resource \
            and _matches(resource, _PROTECTED_WRITE_PATTERNS):
        capability = Capability.POLICY_DISABLE
    elif capability is Capability.LOCAL_READ and resource \
            and _matches(resource, _CREDENTIAL_READ_PATTERNS):
        capability = Capability.CREDENTIAL_EXPOSURE
    elif capability in (Capability.EMAIL_SEND, Capability.OUTBOUND_MESSAGE) \
            and _recipient_count(args) >= table.mass_outbound_threshold:
        capability = Capability.MASS_OUTBOUND
    elif name == "flo_drive_delete" and not args.get("permanent", True):
        # Trash is reversible; only permanent deletion is the denied class.
        capability = Capability.DRIVE_MOVE_OR_RENAME

    data_categories = []
    if capability.value.startswith("email") or capability in (Capability.OUTBOUND_MESSAGE, Capability.MASS_OUTBOUND):
        data_categories.append("correspondence")
    if capability.value.startswith("drive") or capability in (Capability.DOCUMENT_EDIT, Capability.LOCAL_FILE_WRITE):
        data_categories.append("documents")
    if args.get("attachments") or args.get("attachment"):
        data_categories.append("attachments")

    return ActionProposal(
        capability=capability,
        tool_name=name,
        operation=operation,
        resource=resource,
        destination=destination,
        data_categories=tuple(data_categories),
        args_digest=canonical_digest(args),
        loan_ref=loan_ref,
        summary=f"{name} ({capability.value})",
    )


def evaluate(proposal: ActionProposal, table: Optional[PolicyTable] = None) -> PolicyDecision:
    """Deterministically decide a proposal. Structured inputs only."""
    table = table or PolicyTable.default()
    decision = table.decision_for(proposal.capability)
    rule = f"capability:{proposal.capability.value}"
    if decision is Decision.ALLOW:
        reason = f"{proposal.tool_name} has no external side effect."
    elif decision is Decision.CONFIRM:
        target = proposal.destination or proposal.resource or "the target shown"
        reason = (
            f"Flo needs your OK before it runs {proposal.tool_name} "
            f"({proposal.capability.value.replace('_', ' ')}) on {target}."
        )
    else:
        reason = (
            f"{proposal.tool_name} is disabled in this Flo profile "
            f"({proposal.capability.value.replace('_', ' ')} is deny-by-default)."
        )
    return PolicyDecision(
        decision=decision,
        capability=proposal.capability,
        rule=rule,
        reason=reason,
        proposal_id=proposal.proposal_id,
    )
