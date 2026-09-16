"""flo-team plugin — the six-profile Flo Team runtime on Hermes Bot Mode.

What it adds (all additive, no core edits):

* ``pre_tool_call`` role overlay (``roles.py``): folder boundaries, Franklin's
  structural loan-workspace exclusion, per-agent Zapier scope (second layer
  over the profile's ``mcp_servers.zapier.tools`` filter), specialist
  delegation denial, and the Shadow/Assisted/Trusted external-action rule.
  CONFIRM files an Approval Center card and returns Hermes' ``approve``
  directive (the native human gate); DENY returns ``block``. Fail-closed.
* ``post_tool_call`` closes the card from the *tool result* only (executed /
  blocked / failed) — a bot's words never mark something sent.
* Twelve ``flo_*`` tools (``tools.py``) for handoffs, workspaces, approvals,
  readiness, orders, drafts, guideline cards, knowledge, calculations,
  marketing and model health.

Profiles opt in through ``plugins.enabled: [flo-policy, flo-team]``. Outside
a Flo Team profile the hooks are inert and the tools are unavailable.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from . import manifest as manifest_mod
from . import roles
from .approvals_center import ApprovalQueue
from .manifest import current_role, team_state_root
from .store import JsonlLog

manifest = manifest_mod.manifest

logger = logging.getLogger(__name__)


class FloTeamHooks:
    def __init__(self, *, root=None) -> None:
        self._root = root
        self._pending: Dict[str, str] = {}

    def _queue(self) -> Optional[ApprovalQueue]:
        root = self._root or team_state_root()
        return ApprovalQueue(root) if root else None

    def _log(self) -> Optional[JsonlLog]:
        root = self._root or team_state_root()
        return JsonlLog(root / "activity", "activity") if root else None

    def pre_tool_call(self, tool_name: str = "", args: Any = None, session_id: str = "", tool_call_id: str = "", **_: Any) -> Optional[Dict[str, str]]:
        role = current_role()
        if role is None:
            return None  # not a team profile: inert
        try:
            verdict = roles.decide(role, tool_name, args if isinstance(args, dict) else {}, team=manifest())
            log = self._log()
            if log and verdict.layer != "none":
                log.append({"event": "role_policy", "actor": role.name, "tool": tool_name, "decision": verdict.decision,
                            "layer": verdict.layer, "capability": verdict.capability, "session_id": session_id or None})
            if verdict.decision == "allow":
                return None
            if verdict.decision == "confirm":
                queue = self._queue()
                card_id = None
                # Side-effect idempotency: the same material payload already executed recently is never
                # re-run because of a provider retry or a duplicate delivery.
                root = self._root or team_state_root()
                if root is not None:
                    from .intents import IntentRegistry, tool_material

                    check = IntentRegistry(root).check(kind="tool_call", workspace_id=_workspace_hint(args), target=None, purpose=tool_name,
                                                       material=tool_material(tool_name, args if isinstance(args, dict) else {}))
                    if check["decision"] == "return_existing" and check["existing"].get("state") in ("executed", "sent", "ordered", "published"):
                        return {"action": "block", "message": (f"DUPLICATE side effect prevented: {tool_name} with this exact payload already executed "
                                                               f"(execution_ref {check['existing'].get('execution_ref') or 'recorded'}); nothing was sent, ordered or published twice.")}
                if queue is not None:
                    card = queue.propose(agent=role.name, tool_name=tool_name, args=args if isinstance(args, dict) else {},
                                         action_type=verdict.capability or tool_name, capability=verdict.capability,
                                         policy_result="confirm", workspace_id=_workspace_hint(args),
                                         summary=f"{role.display_name}: {tool_name}", session_id=session_id or None, reason=verdict.reason)
                    card_id = card["proposal_id"]
                    if tool_call_id:
                        self._pending[tool_call_id] = card_id
                    if root is not None:
                        IntentRegistry(root).claim(kind="tool_call", workspace_id=_workspace_hint(args), target=None, purpose=tool_name,
                                                   material=tool_material(tool_name, args if isinstance(args, dict) else {}), record_id=card_id,
                                                   agent=role.name, state="pending")
                return {
                    "action": "approve",
                    "message": f"{verdict.reason} (Approval Center card {card_id or 'n/a'})",
                    "rule_key": f"flo-team:{role.name}:{verdict.capability}",
                }
            return {"action": "block", "message": f"BLOCKED by Flo Team role policy: {verdict.reason}"}
        except Exception as exc:  # noqa: BLE001 - fail closed
            logger.error("flo-team: pre_tool_call failed for %s: %s", tool_name, exc)
            return {"action": "block", "message": f"BLOCKED by Flo Team role policy: evaluation failed for {tool_name}; nothing was executed."}

    def post_tool_call(self, tool_name: str = "", result: Any = None, tool_call_id: str = "", **_: Any) -> None:
        card_id = self._pending.pop(tool_call_id, None) if tool_call_id else None
        if not card_id:
            return
        try:
            queue = self._queue()
            if queue is None:
                return
            status, ref = _classify(result)
            queue.close(card_id, status=status, execution_ref=ref)
            root = self._root or team_state_root()
            if root is not None:
                from .intents import IntentRegistry

                registry = IntentRegistry(root)
                intent = registry.find_by_record(card_id)
                if intent is not None:
                    registry.transition(intent["intent_id"], "executed" if status == "executed" else "cancelled", by="post_tool_call", execution_ref=ref)
        except Exception as exc:  # noqa: BLE001
            logger.debug("flo-team: post_tool_call close failed: %s", exc)


def _workspace_hint(args: Any) -> Optional[str]:
    if isinstance(args, dict):
        value = args.get("workspace_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _classify(result: Any):
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except (ValueError, TypeError):
            return "executed", result[:120]
        if isinstance(parsed, dict):
            if parsed.get("error"):
                text = str(parsed["error"])
                return ("blocked" if text.startswith("BLOCKED") else "failed"), None
            for key in ("id", "message_id", "result_ref", "ref", "status"):
                if parsed.get(key):
                    return "executed", str(parsed[key])[:120]
    return "executed", None


def build_hooks(root=None) -> FloTeamHooks:
    return FloTeamHooks(root=root)


def _quiet_url_loggers() -> None:
    """Keep MCP endpoint URLs (which carry the Zapier token) out of profile logs.

    Upstream's HTTP client logs every request line at INFO, URL included. The
    pack rule is that MCP URLs stay outside model-visible logs, so the team
    plugin raises those loggers to WARNING for the process it runs in.
    """
    for name in ("httpx", "httpx2", "httpcore", "mcp.client.streamable_http"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _install_redaction() -> None:
    """Register credential-bearing MCP hosts + a root-logger redaction filter (see redaction.py)."""
    try:
        from . import redaction

        config = None
        try:
            from hermes_cli.config import load_config_readonly  # type: ignore

            config = load_config_readonly()
        except Exception:  # noqa: BLE001
            config = None
        redaction.install(config)
    except Exception as exc:  # noqa: BLE001 - never block plugin load
        logger.debug("flo-team: redaction install skipped: %s", exc)


def register(ctx) -> None:
    _install_redaction()
    _quiet_url_loggers()
    hooks = build_hooks()
    ctx.register_hook("pre_tool_call", hooks.pre_tool_call)
    ctx.register_hook("post_tool_call", hooks.post_tool_call)
    # Tools are normally registered by the loader through tools.register_tools
    # (manifest declares provides_tools). Register here only when that path did
    # not run, so a direct/legacy load still gets the tools without shadowing.
    try:
        from tools.registry import registry as _registry  # type: ignore

        from .tools import TOOLS, register_tools

        if all(_registry.get_entry(name) is None for name, *_ in TOOLS):
            register_tools(ctx)
    except Exception as exc:  # noqa: BLE001
        logger.debug("flo-team: tool registration via register() skipped: %s", exc)
