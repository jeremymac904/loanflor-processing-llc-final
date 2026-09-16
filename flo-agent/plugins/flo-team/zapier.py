"""Per-agent Zapier MCP scoping — two layers.

Layer 1 (Hermes-native): each profile's ``config.yaml`` carries
``mcp_servers.zapier.tools.include`` / ``tools.exclude`` (fnmatch globs on the
raw MCP tool name) so a specialist never even *sees* out-of-scope actions.

Layer 2 (this module, enforced in ``pre_tool_call``): the same manifest globs
are re-checked on every ``mcp__zapier__*`` call. If the profile config were
edited, or a tool slipped through a glob, the role scope still holds. Generic
"API by Zapier" requests are excluded for every role. Read-shaped actions are
ALLOW; write-shaped actions are CONFIRM/DENY per the role's external_writes
setting and the team autonomy level. A Zapier action being technically
available never overrides this.

Endpoint URLs (which carry the token) are never read or logged here.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Iterable, Optional, Tuple

from .manifest import RoleSpec

MCP_PREFIX = "mcp__"
ZAPIER_SERVER_KEYS = ("zapier",)
GENERIC_API_MARKERS = ("api_request", "raw_request", "custom_request", "webhook_by_zapier")
READ_MARKERS = ("find", "search", "get", "list", "retrieve", "lookup", "read", "fetch", "describe", "inspect", "discover")
WRITE_MARKERS = ("send", "create", "update", "add", "post", "publish", "delete", "remove", "schedule", "reply", "forward", "draft", "upload", "move", "share", "trash", "write", "execute", "run", "enable", "disable", "invite", "cancel")


def split_mcp_tool(tool_name: str) -> Optional[Tuple[str, str]]:
    """``mcp__<server>__<tool>`` → (server, tool); None for non-MCP names."""
    if not tool_name or not tool_name.startswith(MCP_PREFIX):
        return None
    rest = tool_name[len(MCP_PREFIX):]
    if "__" not in rest:
        return None
    server, tool = rest.split("__", 1)
    return server, tool


def is_zapier_tool(tool_name: str) -> bool:
    parsed = split_mcp_tool(tool_name)
    return bool(parsed and parsed[0] in ZAPIER_SERVER_KEYS)


def _match_any(name: str, patterns: Iterable[str]) -> bool:
    lowered = name.lower()
    for pattern in patterns:
        pattern = pattern.lower()
        if any(ch in pattern for ch in "*?[") and fnmatchcase(lowered, pattern):
            return True
        if pattern == lowered:
            return True
    return False


def is_generic_api(raw_tool: str) -> bool:
    lowered = raw_tool.lower()
    return any(marker in lowered for marker in GENERIC_API_MARKERS)


def is_read_shaped(raw_tool: str) -> bool:
    lowered = raw_tool.lower()
    if any(marker in lowered for marker in WRITE_MARKERS):
        return False
    return any(marker in lowered for marker in READ_MARKERS)


def in_scope(role: RoleSpec, raw_tool: str) -> Tuple[bool, str]:
    """Second-layer allowlist check on the RAW Zapier tool name."""
    if is_generic_api(raw_tool):
        return False, "generic API-by-Zapier requests are disabled for every Flo Team role until reviewed"
    if role.zapier_exclude and _match_any(raw_tool, role.zapier_exclude):
        return False, f"{raw_tool} is excluded for {role.display_name}"
    if role.zapier_include and not _match_any(raw_tool, role.zapier_include):
        return False, f"{raw_tool} is outside {role.display_name}'s Zapier scope"
    return True, "in scope"


def config_filter(role: RoleSpec) -> dict:
    """The ``mcp_servers.zapier.tools`` block for this role's config.yaml (layer 1)."""
    return {
        "include": list(role.zapier_include),
        "exclude": sorted(set(role.zapier_exclude) | {"*api_request*", "*raw_request*", "*webhook_by_zapier*"}),
    }
