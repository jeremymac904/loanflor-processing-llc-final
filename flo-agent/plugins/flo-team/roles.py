"""Role policy overlay — the deterministic decision for one tool call by one bot.

Layers, evaluated in order (each may only tighten):

1. Folder boundaries (``folders.py``) for file-shaped tools.
2. Loan-workspace exclusion for ``flo_workspace``/``flo_readiness``/... calls
   from a profile with ``loan_workspace: deny`` (Franklin).
3. Zapier scope (``zapier.py``) for ``mcp__zapier__*`` calls.
4. External side effects: any write-shaped Zapier action, the Hermes
   ``send_message`` tool, and the ``flo_*_send``/``flo_portal_submit``
   connector names are "Yellow" — CONFIRM under the *assisted* autonomy level,
   DENY under *shadow*, and ALLOW under *trusted* only for capabilities the
   manifest lists as trusted. A role with ``external_writes: deny`` (Malcolm,
   Sage) is DENY regardless of level.
5. Delegation: ``delegate_task`` (Hermes in-profile subagents) is denied for
   specialists — the team delegates through Flo with ``message_agent``.

The Flo capability policy (plugins/flo-policy) runs alongside; Hermes takes
the first block/approve directive, so both layers hold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from . import folders, zapier
from .manifest import RoleSpec, TeamManifest, manifest as _manifest

EXTERNAL_TOOLS = {
    "send_message": "outbound_message",
    "react_to_message": "outbound_message",
    "flo_email_send": "email_send",
    "flo_email_modify": "email_modify",
    "flo_drive_upload": "drive_upload",
    "flo_drive_share": "drive_share_external",
    "flo_calendar_write": "calendar_write",
    "flo_portal_submit": "portal_submit",
    "flo_status_update": "external_status_change",
    "flo_esign_send": "esign_send",
    "flo_esign_remind": "esign_remind",
    "flo_esign_cancel": "esign_cancel",
}
LOAN_WORKSPACE_TOOLS = {"flo_workspace", "flo_readiness", "flo_order", "flo_draft", "flo_calc"}
SPECIALIST_DENIED_TOOLS = {"delegate_task": "specialists return work to Flo; they do not spawn sub-agents"}


@dataclass(frozen=True)
class RoleDecision:
    decision: str            # allow | confirm | deny
    reason: str
    layer: str               # folders | workspace | zapier | external | delegation | none
    capability: str = ""
    external: bool = False


def _external_decision(role: RoleSpec, team: TeamManifest, capability: str) -> RoleDecision:
    if role.external_writes == "deny":
        return RoleDecision("deny", f"{role.display_name} has no external-write authority ({capability}); propose it to Flo instead", "external", capability, True)
    level = team.autonomy_level
    if level == "shadow":
        return RoleDecision("deny", f"team is in Shadow mode: {capability} is propose-only", "external", capability, True)
    if level == "trusted" and capability in team.trusted_capabilities:
        return RoleDecision("allow", f"{capability} is a trusted capability", "external", capability, True)
    return RoleDecision("confirm", f"{role.display_name} needs Ashley's approval before {capability.replace('_', ' ')}", "external", capability, True)


def decide(role: RoleSpec, tool_name: str, args: Optional[Dict[str, Any]], *, team: Optional[TeamManifest] = None) -> RoleDecision:
    team = team or _manifest()
    args = dict(args) if isinstance(args, dict) else {}
    name = (tool_name or "").strip()

    # 5. delegation
    if name in SPECIALIST_DENIED_TOOLS and not role.is_leader:
        return RoleDecision("deny", SPECIALIST_DENIED_TOOLS[name], "delegation", "delegation")

    # 1. folders
    mode, path = folders.classify_file_tool(name, args)
    if mode and path:
        verdict = folders.check_path(role, path, mode=mode, team=team)
        if not verdict.allowed:
            return RoleDecision("deny", verdict.reason, "folders", f"local_{mode}")
    elif mode == "delete":
        return RoleDecision("deny", "permanent deletion is disabled for every Flo Team bot", "folders", "local_delete")

    # 2. loan workspace exclusion
    if name in LOAN_WORKSPACE_TOOLS and not role.borrower_data_allowed:
        return RoleDecision("deny", f"{role.display_name} is structurally excluded from borrower loan workspaces", "workspace", "loan_workspace")

    # 3./4. Zapier
    if zapier.is_zapier_tool(name):
        _server, raw = zapier.split_mcp_tool(name)  # type: ignore[misc]
        ok, why = zapier.in_scope(role, raw)
        if not ok:
            return RoleDecision("deny", why, "zapier", "zapier_out_of_scope")
        if zapier.is_read_shaped(raw):
            return RoleDecision("allow", "read/search action inside role scope", "zapier", "zapier_read")
        return _external_decision(role, team, f"zapier_{raw}")

    # 4. other external tools
    if name in EXTERNAL_TOOLS:
        return _external_decision(role, team, EXTERNAL_TOOLS[name])

    return RoleDecision("allow", "no role restriction", "none")
