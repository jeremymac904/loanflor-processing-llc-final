"""Flo Team tools — the model-callable surface of the team runtime.

Every handler returns a JSON string (Hermes convention). Handlers never send
anything, never touch Zapier and never approve anything: they record
structured state, run deterministic logic and tell the bot what the next
Hermes-native step is (``message_agent`` for a handoff, the native approval
prompt for a Yellow action). The acting profile is resolved from the process
(``manifest.current_role``) — a bot cannot pass a different identity.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from . import calc as calc_mod
from . import drafts as drafts_mod
from . import knowledge as knowledge_mod
from . import marketing as marketing_mod
from . import models as models_mod
from . import orders as orders_mod
from . import readiness as readiness_mod
from .approvals_center import ApprovalError, ApprovalQueue
from .handoff import RETURN_FORMATS, HandoffError, TaskRegistry, build_handoff, parse_message, render_message
from .manifest import current_role, hermes_home, manifest as _manifest, team_state_root
from .store import now_iso
from .workspace import WorkspaceError, WorkspaceStore

_STATE_ROOT_OVERRIDE = None


def _root():
    root = _STATE_ROOT_OVERRIDE or team_state_root()
    if root is None:
        raise RuntimeError("HERMES_HOME is not set; cannot locate the Flo Team state root")
    return root


def _result(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str)


def _error(message: str, **extra: Any) -> str:
    return _result({"error": message, **extra})


def _me():
    role = current_role()
    if role is None:
        raise HandoffError("this profile is not a Flo Team member (see plugins/flo-team/team.yaml)")
    return role


def _knowledge_state():
    # KnowledgeState appends its own "knowledge/" folder: docs live at <team root>/knowledge/,
    # the same place scripts/flo/activate_fannie_slice.py writes.
    return knowledge_mod.KnowledgeState(_root())


def _active_check(program: str = "fannie", relevant_date=None, early_implementation: bool = False):
    """``(active_check, section_meta)`` bound to one program's activated sections on this install, resolved for a relevant date."""
    from . import sources as sources_mod

    return sources_mod.checks_for(program or "fannie", _knowledge_state(), relevant_date=relevant_date, early_implementation=early_implementation)


def _program_args(args: dict):
    program = str(args.get("program") or "fannie").lower()
    method = args.get("underwriting_method")
    return program, (str(method).lower() if method else None)


def _date_args(args: dict):
    """Relevant date for effective-date resolution (FHA: case number assignment date) and the early-implementation election."""
    return (args.get("case_number_assignment_date") or args.get("relevant_date") or None), bool(args.get("early_implementation"))


_DATE_PROPS = {
    "relevant_date": {"type": "string", "description": "YYYY-MM-DD used to pick the section version in force (default today)"},
    "case_number_assignment_date": {"type": "string", "description": "fha: the case number assignment date governs which Handbook version applies"},
    "early_implementation": {"type": "boolean", "description": "fha: lender elected early implementation of a future-dated Handbook update"},
}


def _config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config_readonly  # type: ignore

        return load_config_readonly() or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# flo_team
# ---------------------------------------------------------------------------

FLO_TEAM_SCHEMA = {
    "name": "flo_team",
    "description": "Flo Team roster and status: who owns what, delegation edges, open tasks, autonomy level, pipeline heat map. Read-only. today = Ashley's Today view (top 3, fastest win, biggest risk, needs you, waiting on others, plain-English statuses) — use it for 'what should I work on next?'; file_summary = the one clean summary of a file — use it for 'where are we on X?'.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["roster", "floor", "heat_map", "activity", "today", "file_summary"], "description": "roster = roles and delegation rules; floor = Team Floor (open tasks per agent); heat_map = pipeline buckets; activity = recent team activity; today = Ashley's Today view; file_summary = plain-English summary of one file (workspace_id or display_name)"},
        "limit": {"type": "integer", "description": "activity rows (default 30)"},
        "workspace_id": {"type": "string", "description": "file_summary: the Deal Room id"},
        "display_name": {"type": "string", "description": "file_summary: the borrower/file name when the id is unknown"},
    }, "required": ["action"]},
}


def handle_flo_team(args: dict, **_: Any) -> str:
    team = _manifest()
    action = str(args.get("action") or "roster")
    try:
        if action in ("today", "file_summary"):
            me = _me()
            if not me.borrower_data_allowed:
                return _error(f"{me.display_name} is structurally excluded from borrower loan workspaces")
            from . import today as today_mod

            root = _root()
            if action == "today":
                return _result(today_mod.from_root(root))
            store = WorkspaceStore(root, team)
            wid = str(args.get("workspace_id") or "")
            wanted = str(args.get("display_name") or "").strip().lower()
            docs = list(store.docs.all())
            doc = next((d for d in docs if d.get("workspace_id") == wid), None) if wid else None
            if doc is None and wanted:
                doc = next((d for d in docs if wanted in str(d.get("display_name") or "").lower()), None)
            if doc is None:
                return _error("no such file; give the workspace_id or the borrower/file name as it appears in the pipeline")
            approvals = list(ApprovalQueue(root).docs.all())
            tasks = list(TaskRegistry(root).docs.all())
            return _result(today_mod.file_summary(doc, approvals, tasks))
        if action == "roster":
            return _result({
                "team": team.team_name, "leader": team.leader, "autonomy_level": team.autonomy_level,
                "max_delegation_depth": team.max_delegation_depth,
                "profiles": [{"name": s.name, "display_name": s.display_name, "title": s.title, "description": s.description,
                              "reports_to": s.reports_to, "delegates_to": list(s.delegates_to), "loan_workspace": s.loan_workspace,
                              "deal_rooms": s.deal_rooms, "external_writes": s.external_writes, "model_classes": list(s.model_classes)}
                             for s in team.profiles.values()],
                "handoff_transport": "message_agent (Hermes Bot Mode) with the packet from flo_handoff action=create",
            })
        registry = TaskRegistry(_root())
        if action == "floor":
            rows = []
            for spec in team.profiles.values():
                open_tasks = [t for t in registry.open_tasks(spec.name) if t.to_agent == spec.name]
                waiting_on = [t for t in registry.open_tasks(spec.name) if t.from_agent == spec.name]
                rows.append({"agent": spec.name, "title": spec.title, "current_assignment": (open_tasks[0].objective if open_tasks else None),
                             "open_tasks": len(open_tasks), "waiting_on": [f"{t.to_agent}: {t.task_id}" for t in waiting_on],
                             "attention": bool([t for t in open_tasks if t.status == "sent"])})
            return _result({"floor": rows})
        if action == "heat_map":
            return _result(WorkspaceStore(_root(), team).heat_map())
        if action == "activity":
            return _result({"activity": registry.log.tail(int(args.get("limit") or 30))})
        return _error(f"unknown action {action}")
    except Exception as exc:  # noqa: BLE001
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_handoff
# ---------------------------------------------------------------------------

FLO_HANDOFF_SCHEMA = {
    "name": "flo_handoff",
    "description": (
        "Structured, recursion-safe handoff between Flo Team bots. create -> returns the exact packet to send with "
        "message_agent (Flo -> specialist, or specialist -> Flo). receive -> parse an inbound packet and mark it received. "
        "complete -> close a task with a structured result (never claim sent/placed/published without an execution_ref). "
        "cancel -> cancel a task tree. status -> open tasks."
    ),
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["create", "receive", "complete", "cancel", "status"]},
        "to": {"type": "string", "description": "recipient profile (create)"},
        "objective": {"type": "string", "description": "one focused outcome (create)"},
        "workspace_id": {"type": "string", "description": "loan workspace id when the task is about a file"},
        "urgency": {"type": "string", "enum": ["today", "tomorrow", "this_week", "normal"]},
        "facts": {"type": "array", "items": {"type": "string"}, "description": "facts already established (references, not document bodies)"},
        "source_refs": {"type": "array", "items": {"type": "string"}},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "return_format": {"type": "string", "enum": list(RETURN_FORMATS)},
        "external_actions": {"type": "boolean", "description": "request permission to propose external actions (never grants execution)"},
        "parent_task_id": {"type": "string", "description": "when creating a child of a task you received"},
        "message": {"type": "string", "description": "the inbound message text (receive)"},
        "task_id": {"type": "string"},
        "result": {"type": "object", "description": "structured result (complete): status, findings, source_refs, unresolved, next_action, external_action_status, execution_ref"},
        "reason": {"type": "string"},
    }, "required": ["action"]},
}


def handle_flo_handoff(args: dict, **_: Any) -> str:
    try:
        me = _me()
        registry = TaskRegistry(_root())
        action = str(args.get("action") or "")
        if action == "create":
            parent = registry.get(str(args["parent_task_id"])) if args.get("parent_task_id") else None
            handoff = build_handoff(
                sender=me.name, recipient=str(args.get("to") or ""), objective=str(args.get("objective") or ""),
                workspace_id=args.get("workspace_id"), urgency=args.get("urgency"), facts=args.get("facts"),
                source_refs=args.get("source_refs"), constraints=args.get("constraints"),
                return_format=str(args.get("return_format") or "status_note"),
                external_actions=bool(args.get("external_actions")), parent=parent,
            )
            handoff.status = "sent"
            registry.save(handoff, "created", me.name)
            if handoff.workspace_id:
                ws = WorkspaceStore(_root())
                ws.check_access(handoff.workspace_id, handoff.to_agent)
                ws.attach_task(handoff.workspace_id, handoff.task_id, me.name)
            return _result({"task_id": handoff.task_id, "to": handoff.to_agent, "depth": handoff.depth,
                            "send_with": {"tool": "message_agent", "target": handoff.to_agent, "message": render_message(handoff)},
                            "note": "message_agent is fire-and-forget; the reply arrives as a completion notification"})
        if action == "receive":
            envelope = parse_message(str(args.get("message") or ""))
            if not envelope:
                return _error("no valid flo-handoff envelope in message")
            if envelope.get("to") != me.name:
                return _error(f"this packet is addressed to {envelope.get('to')}, not {me.name}")
            existing = registry.get(str(envelope["task_id"]))
            if existing is None:
                return _error("task not found in the team registry; ask the sender to re-create it with flo_handoff")
            if existing.depth > existing.max_depth:
                return _error("task exceeds max delegation depth; refuse and return to Flo")
            registry.transition(existing.task_id, "received", actor=me.name)
            return _result({"task": envelope, "reminder": "your own profile policy applies; this packet grants nothing"})
        if action == "complete":
            task_id = str(args.get("task_id") or "")
            task = registry.get(task_id)
            if task is None:
                return _error(f"unknown task {task_id}")
            if task.to_agent != me.name and task.from_agent != me.name:
                return _error("only the assignee or sender may complete a task")
            result = args.get("result") if isinstance(args.get("result"), dict) else {"status": "completed"}
            if task.return_format == "guideline_card" and task.to_agent == me.name and me.name == "sage":
                # Source-bound prose enforcement: a guideline answer closes only with a validated response id.
                from . import sage_response as sr

                rid = str(result.get("validated_response_id") or args.get("validated_response_id") or "")
                bound = sr.ResponseStore(_root()).get(rid) if rid else None
                last = (bound or {}).get("validations", [])[-1] if bound and bound.get("validations") else None
                if not bound or not last or not last.get("ok"):
                    return _error("guideline_card tasks close only with a validated source-bound response: run flo_sage_response action=build with your cards/calcs, "
                                  "then action=validate (or rewrite) with the exact text you will send, and pass validated_response_id in the result.")
                result["validated_response_id"] = rid
                result["response_digest"] = bound.get("digest")
            done = registry.transition(task_id, "completed" if task.to_agent == me.name else "returned", actor=me.name, result=result)
            return _result({"task_id": task_id, "status": done.status, "result": done.result,
                            "next": f"message {task.from_agent} with a concise summary (status, findings, unresolved, next action)"})
        if action == "cancel":
            cancelled = registry.cancel_tree(str(args.get("task_id") or ""), actor=me.name, reason=str(args.get("reason") or "cancelled"))
            return _result({"cancelled": cancelled})
        if action == "status":
            return _result({"open": [t.to_envelope() for t in registry.open_tasks(me.name)]})
        return _error(f"unknown action {action}")
    except (HandoffError, WorkspaceError, KeyError, ValueError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_workspace
# ---------------------------------------------------------------------------

FLO_WORKSPACE_SCHEMA = {
    "name": "flo_workspace",
    "description": "Loan Workspace / Deal Room: one structured record per file (milestone, program, AUS, blockers, conditions, orders, refs, tasks, approvals, activity). References only — never SSNs, account numbers or document bodies.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["create", "get", "list", "update", "add", "invite"]},
        "workspace_id": {"type": "string"},
        "display_name": {"type": "string", "description": "borrower last name or file nickname (create)"},
        "fields": {"type": "object", "description": "update: program, agency, aus, milestone, status_summary, next_action"},
        "list": {"type": "string", "enum": ["blockers", "conditions", "document_refs", "communication_refs", "source_refs"]},
        "item": {"type": "object", "description": "add: the item (text, ref, owner, ...)"},
        "agent": {"type": "string", "description": "invite: profile to add to the Deal Room"},
    }, "required": ["action"]},
}


def handle_flo_workspace(args: dict, **_: Any) -> str:
    try:
        me = _me()
        store = WorkspaceStore(_root())
        action = str(args.get("action") or "")
        if action == "create":
            if me.loan_workspace != "read_write":
                return _error(f"{me.display_name} cannot create loan workspaces")
            fields = args.get("fields") if isinstance(args.get("fields"), dict) else {}
            return _result(store.create(display_name=str(args.get("display_name") or ""), program=fields.get("program"),
                                        agency=fields.get("agency"), milestone=str(fields.get("milestone") or "Intake"),
                                        workspace_id=args.get("workspace_id"), actor=me.name))
        if action == "list":
            if not me.borrower_data_allowed:
                return _error(f"{me.display_name} is structurally excluded from borrower loan workspaces")
            return _result({"workspaces": store.list()})
        wid = str(args.get("workspace_id") or "")
        if action == "get":
            store.check_access(wid, me.name)
            return _result(store.get(wid))
        if action == "update":
            return _result(store.update_fields(wid, me.name, dict(args.get("fields") or {})))
        if action == "add":
            return _result(store.add_item(wid, me.name, str(args.get("list") or ""), dict(args.get("item") or {})))
        if action == "invite":
            store.check_access(wid, me.name)
            return _result(store.invite(wid, str(args.get("agent") or ""), actor=me.name))
        return _error(f"unknown action {action}")
    except (WorkspaceError, HandoffError, KeyError, ValueError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_approvals (read + edit; deciding is Ashley's, in the chat prompt / desktop)
# ---------------------------------------------------------------------------

FLO_APPROVALS_SCHEMA = {
    "name": "flo_approvals",
    "description": "Ashley Approval Center queue. list pending/decided cards; edit re-proposes with a changed payload (invalidates the old card). Bots cannot approve — Ashley decides in the approval prompt or the Approval Center page.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["list", "get", "edit"]},
        "status": {"type": "string", "enum": ["pending", "approved", "rejected", "executed", "blocked", "failed", "invalidated", "expired", "denied"]},
        "workspace_id": {"type": "string"},
        "proposal_id": {"type": "string"},
        "new_args": {"type": "object", "description": "edit: the corrected tool arguments"},
        "summary": {"type": "string"},
    }, "required": ["action"]},
}


def handle_flo_approvals(args: dict, **_: Any) -> str:
    try:
        me = _me()
        queue = ApprovalQueue(_root())
        action = str(args.get("action") or "list")
        if action == "list":
            rows = queue.list(status=args.get("status"), workspace_id=args.get("workspace_id"),
                              agent=None if me.is_leader else me.name)
            return _result({"cards": rows, "note": "approve/reject happen in Ashley's approval prompt; a bot cannot decide"})
        if action == "get":
            card = queue.docs.get(str(args.get("proposal_id") or ""))
            return _result(card or {"error": "no such card"})
        if action == "edit":
            return _result(queue.edit(str(args.get("proposal_id") or ""), agent=me.name,
                                      new_args=dict(args.get("new_args") or {}), summary=args.get("summary")))
        return _error(f"unknown action {action}")
    except (ApprovalError, HandoffError, ValueError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_readiness (Malcolm)
# ---------------------------------------------------------------------------

FLO_READINESS_SCHEMA = {
    "name": "flo_readiness",
    "description": "File Readiness report (FILE_PREP_REPORT): transparent checklist score from structured facts. Never an underwriting decision. Checklist items come from the handoff/Ashley (no approved doc matrix is loaded: SOURCE_GAP).",
    "parameters": {"type": "object", "properties": {
        "workspace_id": {"type": "string"},
        "checklist": {"type": "array", "items": {"type": "object", "properties": {
            "item": {"type": "string"}, "state": {"type": "string", "enum": ["complete", "missing", "expired", "conflicting", "unknown", "waived_by_ashley"]},
            "owner": {"type": "string"}, "source_ref": {"type": "string"}, "basis": {"type": "string"}}}},
        "discrepancies": {"type": "array", "items": {"type": "string"}},
        "aus_status": {"type": "string", "enum": ["present", "missing", "unknown"]},
        "income_prep_complete": {"type": "boolean"},
        "assets_prep_complete": {"type": "boolean"},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "source_refs": {"type": "array", "items": {"type": "string"}},
    }, "required": ["workspace_id", "checklist"]},
}


def handle_flo_readiness(args: dict, **_: Any) -> str:
    try:
        me = _me()
        store = WorkspaceStore(_root())
        wid = str(args.get("workspace_id") or "")
        store.check_access(wid, me.name, write=True)
        report = readiness_mod.build_report(
            workspace=store.get(wid), checklist=list(args.get("checklist") or []), discrepancies=args.get("discrepancies"),
            aus_status=str(args.get("aus_status") or "unknown"), income_prep_complete=args.get("income_prep_complete"),
            assets_prep_complete=args.get("assets_prep_complete"), open_questions=args.get("open_questions"),
            source_refs=args.get("source_refs"), agent=me.name,
        )
        store.set_readiness(wid, me.name, report)
        return _result(report)
    except (WorkspaceError, HandoffError, ValueError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_order (Chadwick)
# ---------------------------------------------------------------------------

FLO_ORDER_SCHEMA = {
    "name": "flo_order",
    "description": "Order proposals and tracking (title, HOI, WVOE/VOE, LOE request, custom). propose creates a requested order; transition moves state (approved needs approval_id; ordered/vendor_confirmed need an execution_ref from the tool that placed it); tracker lists by state.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["propose", "transition", "tracker"]},
        "workspace_id": {"type": "string"},
        "order_type": {"type": "string", "enum": ["title", "hoi", "wvoe", "voe", "loe_request", "custom"]},
        "inputs": {"type": "object", "description": "property_ref, borrower_ref, vendor, employer_ref, authorization_ref, agent_or_carrier_ref, topic, draft_ref, purpose"},
        "purpose": {"type": "string"},
        "urgency": {"type": "string"},
        "source_ref": {"type": "string"},
        "order_id": {"type": "string"},
        "state": {"type": "string", "enum": ["approved", "ordered", "vendor_confirmed", "pending", "received", "reconciled", "overdue", "cancelled"]},
        "approval_id": {"type": "string"},
        "execution_ref": {"type": "string"},
        "note": {"type": "string"},
    }, "required": ["action", "workspace_id"]},
}


def handle_flo_order(args: dict, **_: Any) -> str:
    try:
        me = _me()
        store = WorkspaceStore(_root())
        wid = str(args.get("workspace_id") or "")
        action = str(args.get("action") or "")
        if action == "propose":
            from . import intents as intents_mod

            store.check_access(wid, me.name, write=True)
            inputs = dict(args.get("inputs") or {})
            material = intents_mod.order_material(order_type=str(args.get("order_type") or ""), inputs=inputs)
            registry = intents_mod.IntentRegistry(_root())
            target = str(inputs.get("vendor") or inputs.get("agent_or_carrier_ref") or inputs.get("employer_ref") or "")
            check = registry.check(kind="order", workspace_id=wid, target=target, purpose=str(args.get("order_type") or ""), material=material, source_task=args.get("source_task"))
            if check["decision"] == "return_existing":
                existing = next((o for o in store.get(wid).get("orders", []) if o.get("order_id") == check["existing"].get("record_id")), None)
                return _result({**(existing or check["existing"]), "deduplicated": True, "decision": "return_existing", "intent_id": check["intent_id"], "note": check["reason"]})
            order = orders_mod.propose(workspace_id=wid, order_type=str(args.get("order_type") or ""), inputs=inputs,
                                       purpose=str(args.get("purpose") or ""), urgency=args.get("urgency"), source_ref=args.get("source_ref"), agent=me.name)
            order["intent_id"] = check["intent_id"]
            store.upsert_order(wid, me.name, order)
            registry.claim(kind="order", workspace_id=wid, target=target, purpose=str(args.get("order_type") or ""), material=material,
                           record_id=order["order_id"], agent=me.name, source_task=args.get("source_task"), state="pending")
            return _result({**order, "decision": "create_new", "next": "placing the order externally is a Yellow action: it will stop at Ashley's approval prompt"})
        if action == "transition":
            store.check_access(wid, me.name, write=True)
            doc = store.get(wid)
            current = next((o for o in doc.get("orders", []) if o.get("order_id") == args.get("order_id")), None)
            if current is None:
                return _error("unknown order_id")
            updated = orders_mod.transition(current, str(args.get("state") or ""), by=me.name, approval_id=args.get("approval_id"),
                                            execution_ref=args.get("execution_ref"), note=str(args.get("note") or ""))
            store.upsert_order(wid, me.name, updated)
            if updated.get("intent_id"):
                from . import intents as intents_mod

                mapped = {"approved": "approved", "ordered": "ordered", "vendor_confirmed": "ordered", "cancelled": "cancelled"}.get(updated["state"])
                if mapped:
                    try:
                        intents_mod.IntentRegistry(_root()).transition(updated["intent_id"], mapped, by=me.name, execution_ref=updated.get("execution_ref"))
                    except KeyError:
                        pass
            return _result(updated)
        if action == "tracker":
            store.check_access(wid, me.name)
            return _result(orders_mod.tracker(store.get(wid).get("orders", [])))
        return _error(f"unknown action {action}")
    except (WorkspaceError, HandoffError, orders_mod.OrderError, ValueError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_draft (Whisper)
# ---------------------------------------------------------------------------

FLO_DRAFT_SCHEMA = {
    "name": "flo_draft",
    "description": "Communication queue: create a draft (never sends), mark proposed/sent (sent needs an execution_ref from the sending tool), translate a lender condition into owner/action (flags needs_sage when meaning depends on a guideline), queue view.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["create", "mark", "translate_condition", "queue"]},
        "workspace_id": {"type": "string"},
        "audience": {"type": "string", "enum": ["borrower", "lo", "lender", "realtor", "title", "internal", "vendor"]},
        "purpose": {"type": "string"},
        "body": {"type": "string"},
        "milestone": {"type": "string"},
        "needed": {"type": "string"},
        "urgency": {"type": "string", "enum": ["needs attention today", "urgent tomorrow if not answered today", "can wait"]},
        "channel": {"type": "string"},
        "draft_id": {"type": "string"},
        "status": {"type": "string", "enum": ["draft", "proposed", "sent", "rejected"]},
        "proposal_id": {"type": "string"},
        "execution_ref": {"type": "string"},
        "condition_text": {"type": "string"},
        "owner_hint": {"type": "string"},
        "source_task": {"type": "string", "description": "handoff task id that asked for this communication (idempotency)"},
    }, "required": ["action"]},
}


def handle_flo_draft(args: dict, **_: Any) -> str:
    try:
        me = _me()
        action = str(args.get("action") or "")
        if action == "translate_condition":
            return _result(drafts_mod.translate_condition(str(args.get("condition_text") or ""), owner_hint=args.get("owner_hint")))
        store = WorkspaceStore(_root())
        wid = args.get("workspace_id")
        if action == "create":
            from . import intents as intents_mod

            draft = drafts_mod.create(audience=str(args.get("audience") or ""), purpose=str(args.get("purpose") or ""), body=str(args.get("body") or ""),
                                      workspace_id=wid, milestone=args.get("milestone"), needed=args.get("needed"),
                                      urgency=str(args.get("urgency") or "can wait"), channel=str(args.get("channel") or "email"), agent=me.name,
                                      source_task=args.get("source_task"))
            registry = intents_mod.IntentRegistry(_root())
            if wid:
                existing = drafts_mod.find_active_duplicate(store.get(str(wid)).get("drafts", []), draft["draft_intent_id"])
                if existing is not None:
                    return _result({**existing, "deduplicated": True, "decision": "return_existing",
                                    "note": f"an active draft with the same intent already exists ({existing['draft_id']}); no new draft was created. Edit it or mark it rejected to start over."})
                store.add_draft(str(wid), me.name, draft)
            material = intents_mod.draft_material(audience=draft["audience"], purpose=draft["purpose"], needed=draft["needed"], channel=draft["channel"])
            registry.claim(kind="draft", workspace_id=wid, target=draft["audience"], purpose=draft["purpose"], material=material,
                           record_id=draft["draft_id"], agent=me.name, source_task=args.get("source_task"), state="pending")
            return _result({**draft, "decision": "create_new", "next": "sending is a Yellow action: it stops at Ashley's approval prompt; status stays 'draft' until the send tool confirms"})
        if action == "mark":
            if not wid:
                return _error("workspace_id required")
            doc = store.get(str(wid))
            current = next((d for d in doc.get("drafts", []) if d.get("draft_id") == args.get("draft_id")), None)
            if current is None:
                return _error("unknown draft_id")
            updated = drafts_mod.mark(current, str(args.get("status") or ""), by=me.name, proposal_id=args.get("proposal_id"), execution_ref=args.get("execution_ref"))

            def _mutate(d):
                d["drafts"] = [updated if x.get("draft_id") == updated["draft_id"] else x for x in d.get("drafts", [])]

            store.docs.update(str(wid), _mutate)
            if updated.get("draft_intent_id"):
                from . import intents as intents_mod

                state = {"sent": "sent", "rejected": "rejected", "proposed": "proposed", "draft": "pending"}[updated["status"]]
                try:
                    intents_mod.IntentRegistry(_root()).transition(updated["draft_intent_id"], state, by=me.name, execution_ref=updated.get("execution_ref"))
                except KeyError:
                    pass
            return _result(updated)
        if action == "queue":
            if not wid:
                return _error("workspace_id required")
            store.check_access(str(wid), me.name)
            return _result(drafts_mod.queue_view(store.get(str(wid)).get("drafts", [])))
        return _error(f"unknown action {action}")
    except (WorkspaceError, HandoffError, drafts_mod.DraftError, ValueError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_guideline_card + flo_knowledge (Sage)
# ---------------------------------------------------------------------------

FLO_GUIDELINE_CARD_SCHEMA = {
    "name": "flo_guideline_card",
    "description": "Citation-capable Guideline Card for a program/topic. Layers agency baseline, lender overlay, investor/program guide, AUS findings and file conditions separately. Conclusion is SOURCE_GAP unless an ACTIVE approved source revision backs it. Never a loan approval.",
    "parameters": {"type": "object", "properties": {
        "program": {"type": "string", "enum": ["fannie", "freddie", "fha", "va", "usda", "non_qm", "jumbo", "specialty"]},
        "topic": {"type": "string"},
        "lender": {"type": "string"},
        "aus_path": {"type": "string", "description": "DU, LPA, TOTAL, GUS, manual"},
        "underwriting_method": {"type": "string", "description": "fha: total | manual (required to select the right FHA rules); others: du/lpa/aus/gus/manual"},
        "missing_documentation": {"type": "array", "items": {"type": "string"}},
        "workspace_id": {"type": "string", "description": "Deal Room: loan-specific AE/UW guidance for that room is shown in the file_condition layer"},
        "product": {"type": "string", "description": "product/program for overlay scope"},
        **_DATE_PROPS,
        "aus_findings": {"type": "array", "items": {"type": "string"}},
        "file_conditions": {"type": "array", "items": {"type": "string"}},
        "investor_source_id": {"type": "string", "description": "required for non_qm/jumbo/specialty"},
        "calculation_trace_ref": {"type": "string"},
    }, "required": ["program", "topic"]},
}


def handle_flo_guideline_card(args: dict, **_: Any) -> str:
    try:
        program = str(args.get("program") or "").lower()
        if program in ("fannie", "freddie", "fha", "va", "usda"):
            # Section-level cards from the activated program slice (standard card renderer).
            from . import cards as cards_mod

            rel, early = _date_args(args)
            card = cards_mod.guideline_card(
                program=program, topic=str(args.get("topic") or ""), state=_knowledge_state(), underwriting_method=args.get("underwriting_method"),
                lender=args.get("lender"), aus_path=args.get("aus_path"), aus_findings=args.get("aus_findings"), file_conditions=args.get("file_conditions"),
                calculation_trace_ref=args.get("calculation_trace_ref"), documentation=args.get("documentation") if isinstance(args.get("documentation"), dict) else None,
                missing_documentation=args.get("missing_documentation"), relevant_date=rel, early_implementation=early,
                team_root=_root(), workspace_id=args.get("workspace_id"), product=args.get("product"),
            )
            return _result(card)
        card = knowledge_mod.guideline_card(
            program=str(args.get("program") or ""), topic=str(args.get("topic") or ""), lender=args.get("lender"),
            aus_path=args.get("aus_path"), aus_findings=args.get("aus_findings"), file_conditions=args.get("file_conditions"),
            investor_source_id=args.get("investor_source_id"), calculation_trace_ref=args.get("calculation_trace_ref"),
        )
        return _result(card)
    except (knowledge_mod.KnowledgeError, ValueError) as exc:
        return _error(str(exc))


FLO_KNOWLEDGE_SCHEMA = {
    "name": "flo_knowledge",
    "description": "Sage's source registry and knowledge freshness: list official sources and lifecycle, detect a new revision (never activates), advance a revision (approval/activation is admin-only and refused for bots), freshness report.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["sources", "freshness", "detect", "advance", "revisions", "center", "diff", "impact"]},
        "program": {"type": "string"},
        "old_version": {"type": "string", "description": "diff: e.g. update-17"},
        "new_version": {"type": "string", "description": "diff: e.g. update-18"},
        "rule_ids": {"type": "array", "items": {"type": "string"}, "description": "impact: changed rule ids"},
        "sections": {"type": "array", "items": {"type": "string"}, "description": "impact: changed section keys"},
        "source_id": {"type": "string"},
        "version": {"type": "string"},
        "official_url": {"type": "string"},
        "checksum": {"type": "string"},
        "revision_id": {"type": "string"},
        "state": {"type": "string", "enum": ["pending_review", "regression", "approval", "active", "archived", "superseded"]},
        "regression_receipt": {"type": "string"},
    }, "required": ["action"]},
}


def handle_flo_knowledge(args: dict, **_: Any) -> str:
    try:
        me = _me()
        registry = knowledge_mod.load_registry()
        state = knowledge_mod.KnowledgeState(_root())
        action = str(args.get("action") or "sources")
        if action == "sources":
            from . import sources as sources_mod

            program = str(args.get("program") or "").lower() or None
            rows = knowledge_mod.sources_for(registry, program) if program else registry.get("sources", [])
            # Section-level activation state per program slice. Everything else in the registry is discovery metadata.
            programs = [program] if program in sources_mod.PROGRAMS else list(sources_mod.PROGRAMS)
            program_sections = {p: [sources_mod.section_status(p, s, state).to_dict() for s in sources_mod.load_sections(p)] for p in programs}
            active_by_program = {p: [s["section"] for s in rows_ if s["usable"]] for p, rows_ in program_sections.items()}
            not_in_force = {p: [s["section"] for s in rows_ if s["usable"] and s.get("in_force") is False] for p, rows_ in program_sections.items()}
            total_active = sum(len(v) for v in active_by_program.values())
            return _result({
                "sources": rows, "overlays": registry.get("overlays", {}),
                "program_sections": program_sections, "active_by_program": active_by_program, "not_yet_in_force": {k: v for k, v in not_in_force.items() if v},
                "fannie_sections": program_sections.get("fannie", []), "active_sections": active_by_program.get("fannie", []),
                "note": (", ".join(f"{sources_mod.program_spec(p)['display']}: {len(v)} active section(s)" for p, v in active_by_program.items() if v)
                         + "; citable at section level; registry entries are discovery metadata and everything not listed as active is SOURCE_GAP")
                        if total_active else "no source revision is active on this install; every guideline answer is SOURCE_GAP until an administrator activates one",
            })
        if action == "freshness":
            return _result({"freshness": state.freshness(registry)})
        if action == "center":
            from . import knowledge_center as kc

            return _result({"rows": kc.rows(state, None, programs=[args["program"]] if args.get("program") in ("fannie", "freddie", "fha", "va", "usda") else None),
                            "note": "read-only view; approve/activate run through scripts/flo/activate_sources.py by an administrator"})
        if action == "diff":
            from . import sourcediff

            program = str(args.get("program") or "")
            versions = sorted({v.get("version") for v in __import__("flo_team.sources", fromlist=["x"]).load_sections(program).values() if v.get("version")}) if program else []
            if args.get("old_version") and args.get("new_version"):
                return _result(sourcediff.compare_versions(program, str(args["old_version"]), str(args["new_version"]), state=state))
            if len(versions) >= 2:
                return _result(sourcediff.compare_versions(program, versions[-2], versions[-1], state=state))
            out = sourcediff.compare_with_snapshot(program, state=state)
            return _result(out or {"summary": f"{program}: no second version or previous snapshot to compare"})
        if action == "impact":
            from . import impact as impact_mod

            return _result(impact_mod.affected(str(args.get("program") or ""), changed_rule_ids=list(args.get("rule_ids") or []), changed_sections=list(args.get("sections") or []), state=state))
        if action == "detect":
            return _result(state.detect(source_id=str(args.get("source_id") or ""), version=str(args.get("version") or ""),
                                        official_url=str(args.get("official_url") or ""), detected_by=me.name, checksum=args.get("checksum")))
        if action == "advance":
            new_state = str(args.get("state") or "")
            if new_state in ("approval", "active"):
                return _error("approval and activation require a human administrator (hermes profile admin workflow); a bot cannot activate guidance")
            # A bot may move a revision through review/regression bookkeeping only; source="model"
            # makes approval/activation impossible even if the enum check above were bypassed.
            return _result(state.advance(str(args.get("revision_id") or ""), new_state, by=me.name, source="model",
                                         regression_receipt=args.get("regression_receipt")))
        if action == "revisions":
            return _result({"revisions": state.revisions()})
        return _error(f"unknown action {action}")
    except (knowledge_mod.KnowledgeError, HandoffError, ValueError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_calc (Sage / Malcolm)
# ---------------------------------------------------------------------------

FLO_CALC_SCHEMA = {
    "name": "flo_calc",
    "description": "Deterministic Calculation Workbench: run a registered formula (namespaces fannie.* freddie.* fha.total.* fha.manual.* va.* usda.*) with Decimal inputs and get inputs/steps/result/rounding/rule trace. Formulas run only while their official section is ACTIVE; a formula never runs for another program (fail closed). TEST_ONLY formulas run only with allow_test_only=true and are labelled synthetic.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["list", "run"]},
        "formula_id": {"type": "string"},
        "inputs": {"type": "object"},
        "program": {"type": "string", "description": "fannie | freddie | fha | va | usda — the file's program; must match the formula namespace"},
        "underwriting_method": {"type": "string", "description": "fha: total | manual"},
        **_DATE_PROPS,
        "allow_test_only": {"type": "boolean"},
        "rule_ref": {"type": "string"},
    }, "required": ["action"]},
}


def handle_flo_calc(args: dict, **_: Any) -> str:
    try:
        action = str(args.get("action") or "list")
        program, method = _program_args(args)
        rel, early = _date_args(args)
        active, meta = _active_check(program, rel, early)
        if action == "list":
            per_program = lambda p: _active_check(p)[0]  # noqa: E731
            return _result({"formulas": calc_mod.list_formulas(args.get("program")), "production_formulas_active": calc_mod.production_formulas(active_check_for=per_program, program=args.get("program")),
                            "production_formulas_all": calc_mod.production_formulas(program=args.get("program"))})
        if action == "run":
            fid = str(args.get("formula_id") or "")
            formula = calc_mod.FORMULAS.get(fid)
            requested = str(args.get("program") or "").lower() or (formula.program if formula and formula.program != "test" else None)
            if formula and formula.program not in ("test", program) and not args.get("program"):
                requested = formula.program
            active, meta = _active_check(requested or program, rel, early)
            return _result(calc_mod.run(fid, dict(args.get("inputs") or {}),
                                        allow_test_only=bool(args.get("allow_test_only")), rule_ref=args.get("rule_ref"),
                                        document_refs=list(args.get("document_refs") or []), active_check=active, source_meta=meta,
                                        program=str(args.get("program") or "").lower() or None, underwriting_method=method).to_dict())
        return _error(f"unknown action {action}")
    except ValueError as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_assets / flo_du / flo_fileprep (Malcolm, Golden Loan Path)
# ---------------------------------------------------------------------------

FLO_ASSETS_SCHEMA = {
    "name": "flo_assets",
    "description": "Basic Asset Workbench (depository accounts) bound to one program: statement completeness/pages/period, deposit-sourcing threshold, eligible funds vs funds needed, reserves. Fannie (DU), Freddie (LPA, Documentation Level), FHA (total|manual), VA, USDA. Requires that program's activated sections; other asset types return SOURCE_GAP.",
    "parameters": {"type": "object", "properties": {
        "program": {"type": "string", "description": "fannie | freddie | fha | va | usda (default fannie)"},
        "underwriting_method": {"type": "string", "description": "fha: total | manual"},
        **_DATE_PROPS,
        "documentation_level": {"type": "string", "description": "freddie: streamlined_accept | standard (from the Feedback Certificate)"},
        "accounts": {"type": "array", "items": {"type": "object"}, "description": "each: account_ref, type, institution, account_holder, last_four, vod, statement_periods[{start,end,pages_present,pages_total,prior_ending_balance_shown}], ending_balance, deposits[{date,amount,description,sourced,documented_amount,recurring}]"},
        "transaction_type": {"type": "string", "enum": ["purchase", "refinance"]},
        "total_monthly_qualifying_income": {"type": "string"},
        "funds_needed": {"type": "string"},
        "application_date": {"type": "string"},
        "pitia": {"type": "string"},
        "du_reserves_required": {"type": "string"},
        "aus_reserves_required": {"type": "string"},
    }, "required": ["accounts", "transaction_type", "total_monthly_qualifying_income", "funds_needed"]},
}


def handle_flo_assets(args: dict, **_: Any) -> str:
    try:
        me = _me()
        if not me.borrower_data_allowed:
            return _error(f"{me.display_name} is structurally excluded from borrower loan workspaces")
        from . import assets as assets_mod

        program, method = _program_args(args)
        rel, early = _date_args(args)
        active, meta = _active_check(program, rel, early)
        return _result(assets_mod.review(accounts=list(args.get("accounts") or []), transaction_type=str(args.get("transaction_type") or "purchase"),
                                         total_monthly_qualifying_income=args.get("total_monthly_qualifying_income") or "0", funds_needed=args.get("funds_needed") or "0",
                                         application_date=args.get("application_date"), pitia=args.get("pitia"), du_reserves_required=args.get("du_reserves_required"),
                                         aus_reserves_required=args.get("aus_reserves_required"), active_check=active, section_meta=meta, program=program,
                                         underwriting_method=method, documentation_level=args.get("documentation_level")))
    except (HandoffError, ValueError, ArithmeticError) as exc:
        return _error(str(exc))


FLO_DU_SCHEMA = {
    "name": "flo_du",
    "description": "AUS findings review (DU / LPA / TOTAL / VA AUS / GUS): normalizes the findings document into the common envelope (aus_system, aus_result as shown, aus_version, findings_ref, findings_date, program, messages[], source_document), records the result exactly as shown ('DU findings show Approve/Eligible' — never 'approved'), rejects findings from the wrong system for the program, lists verification messages vs documents on file, runs the activated resubmission-tolerance check, routes conflicts to Sage.",
    "parameters": {"type": "object", "properties": {
        "program": {"type": "string", "description": "fannie | freddie | fha | va | usda (default fannie)"},
        "underwriting_method": {"type": "string", "description": "fha: total | manual"},
        **_DATE_PROPS,
        "documents": {"type": "array", "items": {"type": "object"}, "description": "document inventory (type, ref, ... including a du_findings / lpa_findings / total_findings / va_aus_findings / gus_findings document)"},
        "recalculated_dti": {"type": "string"},
    }, "required": ["documents"]},
}


def handle_flo_du(args: dict, **_: Any) -> str:
    try:
        me = _me()
        if not me.borrower_data_allowed:
            return _error(f"{me.display_name} is structurally excluded from borrower loan workspaces")
        from . import aus as aus_mod

        program, method = _program_args(args)
        rel, early = _date_args(args)
        active, meta = _active_check(program, rel, early)
        return _result(aus_mod.review(documents=list(args.get("documents") or []), program=program, underwriting_method=method,
                                      recalculated_dti=args.get("recalculated_dti"), active_check=active, section_meta=meta))
    except (HandoffError, ValueError) as exc:
        return _error(str(exc))


FLO_FILEPREP_SCHEMA = {
    "name": "flo_fileprep",
    "description": "Malcolm's File Prep matrix (Fannie, Freddie, FHA total|manual, VA, USDA): every requirement with provenance (<program>:<section> | <aus>:<message> | workflow | ashley) and state complete/missing/needs_review/not_applicable/source_gap. Runs the deterministic income, AUS and asset reviews for the program first and stores the readiness report.",
    "parameters": {"type": "object", "properties": {
        "program": {"type": "string", "description": "fannie | freddie | fha | va | usda (default fannie)"},
        "underwriting_method": {"type": "string", "description": "fha: total | manual"},
        **_DATE_PROPS,
        "documentation_level": {"type": "string", "description": "freddie: streamlined_accept | standard"},
        "fixture": {"type": "object", "description": "optional whole intake object: va {family_size,state,federal_income_tax,state_income_tax,social_security_and_other_deductions,gross_living_area_sqft|maintenance_and_utilities,monthly_debts}; household {other_adult_members[{annual_income}],adult_full_time_students[{annual_earned_income}],eligible_deductions[],area_income_limit}; workspace {loan_amount,pitia}"},
        "workspace_id": {"type": "string"},
        "documents": {"type": "array", "items": {"type": "object"}},
        "application_date": {"type": "string"},
        "transaction_type": {"type": "string", "enum": ["purchase", "refinance"]},
        "funds_needed": {"type": "string"},
        "pitia": {"type": "string"},
        "estimated_note_date": {"type": "string"},
        "extra_items": {"type": "array", "items": {"type": "object"}},
        "store_readiness": {"type": "boolean"},
    }, "required": ["workspace_id", "documents"]},
}


def handle_flo_fileprep(args: dict, **_: Any) -> str:
    try:
        me = _me()
        store = WorkspaceStore(_root())
        wid = str(args.get("workspace_id") or "")
        store.check_access(wid, me.name, write=True)
        from . import assets as assets_mod
        from . import aus as aus_mod
        from . import fileprep as fileprep_mod
        from . import golden_path as gp

        program, method = _program_args(args)
        rel, early = _date_args(args)
        active, meta = _active_check(program, rel, early)
        documents = list(args.get("documents") or [])
        fixture = args.get("fixture") if isinstance(args.get("fixture"), dict) else None
        income = gp.income_review(documents, active_check=active, section_meta=meta, program=program, underwriting_method=method, fixture=fixture)
        if program == "va" and fixture and income.get("qualifying_monthly"):
            fx = dict(fixture)
            fx.setdefault("workspace", {})
            fx["workspace"] = {**fx["workspace"], "pitia": args.get("pitia") or fx["workspace"].get("pitia"), "loan_amount": fx["workspace"].get("loan_amount") or args.get("loan_amount")}
            residual = gp.va_residual_review(fx, income["qualifying_monthly"], active_check=active, section_meta=meta)
            income["residual_income"] = residual
            if residual["status"] == "NEEDS_REVIEW":
                income["status"] = "NEEDS_REVIEW"
                income["warnings"] = income.get("warnings", []) + residual["warnings"]
        du_review = aus_mod.review(documents=documents, program=program, underwriting_method=method, active_check=active, section_meta=meta)
        accounts = gp.accounts_from_documents(documents)
        asset_review = assets_mod.review(accounts=accounts, transaction_type=str(args.get("transaction_type") or "purchase"),
                                         total_monthly_qualifying_income=income.get("qualifying_monthly") or "0", funds_needed=args.get("funds_needed") or "0",
                                         application_date=args.get("application_date"), pitia=args.get("pitia"),
                                         aus_reserves_required=du_review.get("reserves_required_to_be_verified"), active_check=active, section_meta=meta,
                                         program=program, underwriting_method=method, documentation_level=args.get("documentation_level"))
        matrix = fileprep_mod.build_matrix(workspace={"workspace_id": wid, "estimated_note_date": args.get("estimated_note_date")}, documents=documents,
                                           application_date=args.get("application_date"), transaction_type=str(args.get("transaction_type") or "purchase"),
                                           income_review=income, asset_review=asset_review, extra_items=args.get("extra_items"), active_check=active, section_meta=meta,
                                           program=program, underwriting_method=method, documentation_level=args.get("documentation_level"))
        out = {"program": program, "underwriting_method": method, "matrix": matrix, "income_review": income, "asset_review": asset_review, "aus_review": du_review, "du_review": du_review if program == "fannie" else None}
        if args.get("store_readiness", True):
            out["readiness"] = json.loads(handle_flo_readiness({
                "workspace_id": wid, "checklist": fileprep_mod.as_checklist(matrix), "aus_status": "present" if du_review["present"] else "missing",
                "discrepancies": list(income.get("warnings", [])) + [f"assets: {q}" for q in asset_review.get("sourcing_questions", [])],
                "income_prep_complete": income.get("status") == "OK", "assets_prep_complete": asset_review.get("status") == "OK",
                "open_questions": income.get("guideline_questions", []) + [c["detail"] for c in du_review.get("conflicts", [])],
                "source_refs": [s.get("official_url") for s in matrix.get("sources", []) if s.get("official_url")],
            }))
        return _result(out)
    except (WorkspaceError, HandoffError, ValueError, ArithmeticError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_marketing (Franklin)
# ---------------------------------------------------------------------------

FLO_MARKETING_SCHEMA = {
    "name": "flo_marketing",
    "description": "Marketing Content Factory (social, newsletter, GBP, blog, campaign): create drafts with automatic claim/disclosure flags, advance stages (approved needs proposal_id; published needs an execution_ref), editorial calendar. No borrower data ever.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["create", "advance", "calendar", "scan"]},
        "channel": {"type": "string", "enum": ["social", "newsletter", "gbp", "blog", "campaign"]},
        "title": {"type": "string"},
        "body": {"type": "string"},
        "pillar": {"type": "string"},
        "scheduled_for": {"type": "string"},
        "content_id": {"type": "string"},
        "stage": {"type": "string", "enum": ["draft", "review", "approved", "published", "archived"]},
        "proposal_id": {"type": "string"},
        "execution_ref": {"type": "string"},
        "source_ids": {"type": "object", "description": "flag kind -> approved marketing source id"},
        "text": {"type": "string"},
    }, "required": ["action"]},
}


def handle_flo_marketing(args: dict, **_: Any) -> str:
    try:
        me = _me()
        if me.role != "marketing" and not me.is_leader:
            return _error(f"{me.display_name} does not own marketing content; hand it to Flo for Franklin")
        factory = marketing_mod.ContentFactory(_root())
        action = str(args.get("action") or "")
        if action == "create":
            return _result(factory.create(channel=str(args.get("channel") or ""), title=str(args.get("title") or ""), body=str(args.get("body") or ""),
                                          pillar=args.get("pillar"), scheduled_for=args.get("scheduled_for"), agent=me.name))
        if action == "advance":
            return _result(factory.advance(str(args.get("content_id") or ""), str(args.get("stage") or ""), by=me.name,
                                           proposal_id=args.get("proposal_id"), execution_ref=args.get("execution_ref"),
                                           source_ids=dict(args.get("source_ids") or {})))
        if action == "calendar":
            return _result(factory.calendar())
        if action == "scan":
            return _result({"flags": marketing_mod.scan(str(args.get("text") or ""))})
        return _error(f"unknown action {action}")
    except (marketing_mod.MarketingError, HandoffError, ValueError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_sage_response (Sage): source-bound prose
# ---------------------------------------------------------------------------

FLO_SAGE_RESPONSE_SCHEMA = {
    "name": "flo_sage_response",
    "description": ("Source-bound response for underwriting answers. build: fold your Guideline Cards, flo_calc traces, AUS envelope, overlays, file conditions and guidance items into "
                    "the allowed-facts structure (supported_claims, calculation_results, source_refs, warnings, source_gaps) and get a deterministic rendering. "
                    "validate: check the exact text you intend to send — every percentage, dollar amount, period, ratio and rule-like assertion must be supported; "
                    "rewrite: drop unsupported sentences. A guideline_card handoff closes only with a validated response id."),
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["build", "validate", "rewrite", "render", "get"]},
        "cards": {"type": "array", "items": {"type": "object"}},
        "calculations": {"type": "array", "items": {"type": "object"}},
        "aus_envelope": {"type": "object"},
        "overlays": {"type": "array", "items": {"type": "object"}},
        "file_conditions": {"type": "array", "items": {"type": "string"}},
        "guidance_items": {"type": "array", "items": {"type": "object"}},
        "workspace_id": {"type": "string"},
        "program": {"type": "string"},
        "response_id": {"type": "string"},
        "text": {"type": "string", "description": "validate/rewrite: the exact prose"},
    }, "required": ["action"]},
}


def handle_flo_sage_response(args: dict, **_: Any) -> str:
    try:
        import hashlib

        from . import sage_response as sr

        me = _me()
        store = sr.ResponseStore(_root())
        action = str(args.get("action") or "build")
        if action == "build":
            overlays = list(args.get("overlays") or [])
            guidance = list(args.get("guidance_items") or [])
            if args.get("workspace_id"):
                try:
                    from . import guidance as guidance_mod

                    guidance += guidance_mod.GuidanceStore(_root()).for_workspace(str(args["workspace_id"]))
                except Exception:  # noqa: BLE001
                    pass
            bound = sr.build(cards=list(args.get("cards") or []), calculations=list(args.get("calculations") or []), aus_envelope=args.get("aus_envelope"),
                             overlays=overlays, file_conditions=list(args.get("file_conditions") or []), guidance_items=guidance,
                             workspace_id=args.get("workspace_id"), program=args.get("program"))
            bound["built_by"] = me.name
            store.put(bound)
            return _result({**bound, "rendered": sr.render(bound), "next": "send only text that passes action=validate with this response_id"})
        bound = store.get(str(args.get("response_id") or ""))
        if bound is None:
            return _error("unknown response_id; run action=build first")
        if action == "render":
            return _result({"response_id": bound["response_id"], "text": sr.render(bound)})
        if action == "get":
            return _result(bound)
        text = str(args.get("text") or "")
        if action == "validate":
            result = sr.validate(text, bound)
            store.record_validation(bound["response_id"], result, hashlib.sha256(text.encode("utf-8")).hexdigest()[:16])
            return _result({**result, "next": "pass validated_response_id in flo_handoff complete" if result["ok"] else "remove or source the flagged statements, or use action=rewrite"})
        if action == "rewrite":
            rewritten = sr.rewrite(text, bound)
            result = sr.validate(rewritten["text"], bound)
            store.record_validation(bound["response_id"], result, hashlib.sha256(rewritten["text"].encode("utf-8")).hexdigest()[:16])
            return _result({**rewritten, "validation": result})
        return _error(f"unknown action {action}")
    except (HandoffError, ValueError, KeyError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_workflow (Flo): preflight, provider state, mid-chain failover
# ---------------------------------------------------------------------------

FLO_WORKFLOW_SCHEMA = {
    "name": "flo_workflow",
    "description": ("Team workflow reliability: preflight (readiness board: Team AI / Local Fast / Local Reasoning / Cloud Reasoning / Fallback / Sensitive-data route, "
                    "estimated specialist turns and latency class) before a complex workflow; providers (routing state machine: HEALTHY, DEGRADED, RATE_LIMITED, OUT_OF_CREDIT, "
                    "MODEL_UNAVAILABLE, OFFLINE, TOO_SLOW, CONTEXT_INSUFFICIENT, DATA_POLICY_BLOCKED with cooldowns); record_failure/record_success; stalled (tasks a specialist never finished); "
                    "resume (fail over a stalled task to another approved provider, preserving task/workspace state; fails closed for sensitive data: 'AI provider unavailable — your work is saved.'); "
                    "check (ingest provider errors from profile logs and resume every stalled task)."),
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["preflight", "providers", "record_failure", "record_success", "stalled", "resume", "check"]},
        "workspace_id": {"type": "string"},
        "roles": {"type": "array", "items": {"type": "string"}},
        "return_formats": {"type": "array", "items": {"type": "string"}},
        "task_id": {"type": "string"},
        "reason": {"type": "string"},
        "provider_id": {"type": "string"},
        "model": {"type": "string"},
        "error": {"type": "string"},
        "latency_ms": {"type": "number"},
        "discover": {"type": "boolean", "description": "preflight: run provider discovery first (slower)"},
        "exclude_providers": {"type": "array", "items": {"type": "string"}},
    }, "required": ["action"]},
}


def handle_flo_workflow(args: dict, **_: Any) -> str:
    try:
        from . import provider_state as ps
        from . import workflow as wf

        me = _me()
        root = _root()
        action = str(args.get("action") or "preflight")
        workspace = None
        if args.get("workspace_id"):
            store = WorkspaceStore(root)
            store.check_access(str(args["workspace_id"]), me.name)
            workspace = store.get(str(args["workspace_id"]))
        if action == "preflight":
            rows = None
            if args.get("discover"):
                from . import providers as providers_mod

                rows = providers_mod.discover(config=_config(), smoke=True)
            roles = list(args.get("roles") or ["malcolm", "sage", "whisper"])
            return _result(wf.preflight(root, roles=roles, workspace=workspace, discovery_rows=rows, expected_return_formats=list(args.get("return_formats") or [])))
        state = ps.ProviderState(root)
        if action == "providers":
            return _result({"providers": state.table(), "sensitive_route": state.select(classification="sensitive"), "non_sensitive_route": state.select(classification="non_sensitive")})
        if action == "record_failure":
            return _result(state.record_failure(str(args.get("provider_id") or ""), str(args.get("model") or ""), str(args.get("error") or "")))
        if action == "record_success":
            return _result(state.record_success(str(args.get("provider_id") or ""), str(args.get("model") or ""), latency_ms=args.get("latency_ms")).to_dict())
        if action == "stalled":
            return _result({"stalled": wf.stalled_tasks(root)})
        if action == "resume":
            if not me.is_leader:
                return _error(f"{me.display_name} cannot resume other bots' tasks; only Flo (or the operator) orchestrates failover")
            return _result(wf.resume_task(root, str(args.get("task_id") or ""), reason=str(args.get("reason") or "provider failure"), workspace=workspace,
                                          exclude_providers=list(args.get("exclude_providers") or []) or None, actor=me.name))
        if action == "check":
            if not me.is_leader:
                return _error("only Flo runs the failover check")
            profiles_root = hermes_home().parent if hermes_home() and hermes_home().parent.name == "profiles" else None
            wss = {w["workspace_id"]: w for w in WorkspaceStore(root).docs.all()}
            return _result(wf.check_and_failover(root, profiles_root=profiles_root, workspaces=wss, actor=me.name))
        return _error(f"unknown action {action}")
    except (HandoffError, WorkspaceError, ValueError, KeyError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_guidance (Flo / Sage): human guidance capture, never a global rule
# ---------------------------------------------------------------------------

FLO_GUIDANCE_SCHEMA = {
    "name": "flo_guidance",
    "description": ("Capture AE/UW clarifications as proposed knowledge (pending_review) with an explicit scope (loan_specific | product_specific | lender_specific | reusable_overlay) "
                    "and the communication reference. Never a global rule: only an administrator promotes an item (Knowledge Center / activate_sources.py). "
                    "list shows items for a Deal Room; overlays lists active AE-confirmed overlays for a program/lender."),
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["propose", "list", "pending", "overlays"]},
        "text": {"type": "string"},
        "scope": {"type": "string", "enum": ["loan_specific", "product_specific", "lender_specific", "reusable_overlay"]},
        "source_ref": {"type": "string", "description": "mail:// note:// call:// reference to the communication"},
        "workspace_id": {"type": "string"},
        "program": {"type": "string"},
        "product": {"type": "string"},
        "lender": {"type": "string"},
        "confirmed_by": {"type": "string", "description": "AE/UW name or role who confirmed"},
        "effective_date": {"type": "string"},
    }, "required": ["action"]},
}


def handle_flo_guidance(args: dict, **_: Any) -> str:
    try:
        from . import guidance as guidance_mod
        from . import overlays as overlays_mod

        me = _me()
        store = guidance_mod.GuidanceStore(_root())
        action = str(args.get("action") or "list")
        if action == "propose":
            if args.get("workspace_id"):
                WorkspaceStore(_root()).check_access(str(args["workspace_id"]), me.name)
            item = store.propose(text=str(args.get("text") or ""), scope=str(args.get("scope") or ""), source_ref=str(args.get("source_ref") or ""), recorded_by=me.name,
                                 workspace_id=args.get("workspace_id"), program=args.get("program"), product=args.get("product"), lender=args.get("lender"),
                                 confirmed_by=args.get("confirmed_by"), effective_date=args.get("effective_date"))
            return _result({**item, "next": "an administrator reviews it in the Knowledge Center; until then it applies only as a labelled file-specific note on this Deal Room"})
        if action == "list":
            if not args.get("workspace_id"):
                return _error("workspace_id required")
            return _result({"guidance": store.for_workspace(str(args["workspace_id"]))})
        if action == "pending":
            return _result({"pending": store.pending()})
        if action == "overlays":
            rows = overlays_mod.OverlayStore(_root()).active_for(str(args.get("program") or ""), args.get("lender"), product=args.get("product"))
            return _result(overlays_mod.overlay_layer(rows, args.get("lender")))
        return _error(f"unknown action {action}")
    except (guidance_mod.GuidanceError, overlays_mod.OverlayError, WorkspaceError, HandoffError, ValueError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_model_health
# ---------------------------------------------------------------------------

FLO_MODEL_HEALTH_SCHEMA = {
    "name": "flo_model_health",
    "description": "Local/cloud model routing for this bot: health-check the local provider (reachable, model listed, context >= 64K, id mapping, smoke completion) and show which model class a sensitive vs non-sensitive task would use. Sensitive tasks fail closed rather than falling back to cloud.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["check", "route", "classes", "discover"]},
        "sensitive": {"type": "boolean", "description": "route: does the task carry borrower data?"},
        "smoke": {"type": "boolean", "description": "check: run the one-token completion (default true)"},
    }, "required": ["action"]},
}


def handle_flo_model_health(args: dict, **_: Any) -> str:
    try:
        me = _me()
        action = str(args.get("action") or "check")
        if action == "classes":
            return _result({"classes": models_mod.class_summary(), "preferences": list(me.model_classes)})
        cfg = _config()
        if action == "discover":
            from . import providers as providers_mod

            rows = providers_mod.discover(config=cfg, smoke=args.get("smoke", True) is not False)
            return _result({"providers": [r.to_dict() for r in rows],
                            "route_sensitive": providers_mod.choose(me, rows, sensitive=True).to_dict(),
                            "route_non_sensitive": providers_mod.choose(me, rows, sensitive=False).to_dict()})
        block = models_mod.local_provider_config(cfg)
        report = models_mod.health_check(str(block.get("base_url") or ""), str(block.get("model") or block.get("default_model") or ""),
                                         declared_context=block.get("context_length"), smoke=args.get("smoke", True) is not False)
        if action == "check":
            return _result(report.to_dict())
        model_cfg = cfg.get("model") if isinstance(cfg.get("model"), dict) else {}
        cloud = {"provider": model_cfg.get("provider"), "model": model_cfg.get("model") or model_cfg.get("default"), "base_url": model_cfg.get("base_url")} if model_cfg else None
        if cloud and cloud.get("provider") == models_mod.LOCAL_PROVIDER_KEY:
            cloud = None
        return _result({"local": report.to_dict(), "route": models_mod.route(me, sensitive=bool(args.get("sensitive")), local_health=report, cloud=cloud).to_dict()})
    except (HandoffError, ValueError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# flo_intake (Flo) — website loan submissions
# ---------------------------------------------------------------------------

FLO_INTAKE_SCHEMA = {
    "name": "flo_intake",
    "description": "New loan submissions from lfprocessing.net. The intake endpoint already created the Deal Room and Malcolm's task; pending = submissions whose packet has not been sent to Malcolm yet; dispatch = get the exact message_agent packet for one submission (then send send_with.message to send_with.target); get = the intake record.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["pending", "dispatch", "get"]},
        "submission_id": {"type": "string"},
    }, "required": ["action"]},
}


def handle_flo_intake(args: dict, **_: Any) -> str:
    try:
        me = _me()
        if not me.is_leader:
            return _error("only Flo handles website intake")
        from . import intake as intake_mod

        action = str(args.get("action") or "pending")
        store = intake_mod.IntakeStore(_root())
        if action == "pending":
            rows = store.pending_dispatch()
            return _result({"pending": [{k: r.get(k) for k in ("submission_id", "workspace_id", "task_id", "borrower", "loan_officer", "expected_closing_date", "received_at", "ashley_line")} for r in rows],
                            "next": "for each: flo_intake action=dispatch submission_id=<id>, then message_agent to malcolm with send_with.message" if rows else "nothing waiting"})
        sid = str(args.get("submission_id") or "")
        if action == "get":
            rec = store.get(sid)
            return _result(rec or {"error": "no such submission"})
        if action == "dispatch":
            rec = intake_mod.dispatch(_root(), sid, by=me.name)
            return _result({k: rec.get(k) for k in ("submission_id", "workspace_id", "task_id", "borrower", "send_with", "ashley_line", "dispatched_at", "note")})
        return _error(f"unknown action {action}")
    except (intake_mod.IntakeError, HandoffError, ValueError) as exc:  # type: ignore[name-defined]
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_documents (Malcolm / Flo / Ashley) — the loan's document inventory
# ---------------------------------------------------------------------------

FLO_DOCUMENTS_SCHEMA = {
    "name": "flo_documents",
    "description": "Loan documents in a Deal Room (pulled at intake through the secure connector). list = every document with category/subtype/status/pages/notes; get = one record plus its extracted text (bounded); update = reclassify (category/subcategory/borrower_ref), set status (received, needs_review, reviewed, missing_pages, unreadable, duplicate, not_needed), display_name or notes — the original file is never altered; inventory = received / missing / needs-clarification against the submission and ACTIVE source rules (never invented requirements); add = copy a file from this machine into the Deal Room (Ashley's Upload Missing Doc); refetch = retry a document whose transfer failed.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["list", "get", "update", "inventory", "add", "refetch"]},
        "workspace_id": {"type": "string"},
        "document_id": {"type": "string"},
        "fields": {"type": "object", "description": "update: category, subcategory, borrower_ref, status, display_name, notes"},
        "path": {"type": "string", "description": "add: absolute path of the file on this machine"},
        "category": {"type": "string"}, "subcategory": {"type": "string"}, "borrower_ref": {"type": "string"},
        "max_chars": {"type": "integer", "description": "get: extracted text limit (default 6000)"},
    }, "required": ["action", "workspace_id"]},
}


def handle_flo_documents(args: dict, **_: Any) -> str:
    try:
        me = _me()
        if not me.borrower_data_allowed:
            return _error(f"{me.display_name} is structurally excluded from borrower loan workspaces")
        from . import documents as documents_mod

        root = _root()
        wid = str(args.get("workspace_id") or "")
        WorkspaceStore(root).check_access(wid, me.name)
        action = str(args.get("action") or "list")
        store = documents_mod.DocumentStore(root)
        public = lambda d: {k: d.get(k) for k in ("document_id", "category", "subcategory", "borrower_ref", "display_name", "original_filename", "status", "notes", "page_count", "text_chars", "classification_source", "received_at", "checks")}  # noqa: E731
        if action == "list":
            return _result({"documents": [public(d) for d in store.list(wid)], "note": "statuses: received, needs_review, reviewed, missing_pages, unreadable, duplicate, not_needed"})
        if action == "inventory":
            ws = WorkspaceStore(root).get(wid)
            return _result(documents_mod.inventory(root, wid, ws.get("submission") or {}, program=ws.get("program")))
        if action == "add":
            rec = documents_mod.add_local(root, wid, str(args.get("path") or ""), category=str(args.get("category") or "other"), subcategory=args.get("subcategory"),
                                          borrower_ref=args.get("borrower_ref"), by=me.name)
            WorkspaceStore(root).add_item(wid, me.name, "document_refs", {"ref": f"doc://{rec['document_id']}", "document_id": rec["document_id"], "category": rec["category"],
                                                                          "subcategory": rec.get("subcategory"), "display_name": rec["display_name"], "status": rec["status"],
                                                                          "local_path": rec.get("local_path"), "text_path": rec.get("text_path"), "pages": rec.get("page_count"), "note": rec.get("notes") or ""})
            return _result(public(rec))
        did = str(args.get("document_id") or "")
        if action == "get":
            rec = store.get(wid, did)
            if rec is None:
                return _error("no such document")
            text = ""
            if rec.get("text_path"):
                try:
                    text = Path(rec["text_path"]).read_text(encoding="utf-8")[: int(args.get("max_chars") or 6000)]
                except OSError:
                    text = ""
            return _result({**public(rec), "text": text, "text_note": None if text else "no extracted text (image, scan without text layer, or office file)"})
        if action == "update":
            rec = store.update(wid, did, dict(args.get("fields") or {}), by=me.name)
            ws = WorkspaceStore(root)

            def _sync(d):
                for item in d.get("document_refs") or []:
                    if item.get("document_id") == did:
                        item.update({"category": rec["category"], "subcategory": rec.get("subcategory"), "borrower_ref": rec.get("borrower_ref"), "display_name": rec["display_name"], "status": rec["status"], "note": rec.get("notes") or ""})
                inv = documents_mod.inventory(root, wid, d.get("submission") or {}, program=d.get("program"))
                d["documents_summary"] = {"received": inv["counts"]["documents"], "duplicates": inv["counts"].get("duplicate", 0), "missing": [w["label"] for w in inv["missing"]],
                                          "needs_clarification": [w.get("problem") or w.get("reason") or w["label"] for w in inv["needs_clarification"]], "updated_at": now_iso()}

            ws.docs.update(wid, _sync)
            return _result(public(rec))
        if action == "refetch":
            rec = documents_mod.refetch(root, wid, did, token=os.environ.get("FLO_INTAKE_TOKEN"), by=me.name)
            return _result(public(rec))
        return _error(f"unknown action {action}")
    except (WorkspaceError, HandoffError, KeyError, ValueError, FileNotFoundError) as exc:
        return _error(str(exc))


# ---------------------------------------------------------------------------
# flo_esign / flo_esign_send / flo_esign_remind / flo_esign_cancel — Documenso
# ---------------------------------------------------------------------------
# "Send for Signature" end to end. flo_esign itself never sends anything (list,
# prepare, status and retrieve are all read-only from the borrower's point of
# view — no email goes out, nothing is signed on anyone's behalf); the three
# side-effecting actions are separate tools so the existing flo-team role
# policy (roles.EXTERNAL_TOOLS) gates them exactly like any other outbound
# action: a Yellow approval card, bound by the exact document/recipients/
# message/template (approvals_center.MATERIAL_ARG_KEYS), and the generic
# tool-call idempotency in __init__.py's pre_tool_call hook (a duplicate send
# is blocked before this code ever runs again). See esign.py and FLO_ESIGN.md.

FLO_ESIGN_SCHEMA = {
    "name": "flo_esign",
    "description": "Electronic signatures for one loan's documents, via Documenso (self-hosted). list = every signature request for this file, in Ashley's words (Ready to send / Waiting for signature / Signed / Needs attention); prepare = build the exact request (document, template, recipients, message) for Ashley to review — raises 'This document needs signing setup.' if no approved template matches; status = authenticated re-check against Documenso (never trusts anything else); retrieve = download the completed PDF + evidence once signed and file it as a document on this loan (idempotent — never re-downloads once filed). Sending, reminding and cancelling are separate tools (flo_esign_send / flo_esign_remind / flo_esign_cancel) because those go out to the borrower and stop at Ashley's approval.",
    "parameters": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["list", "prepare", "status", "retrieve", "templates"]},
        "workspace_id": {"type": "string"},
        "document_id": {"type": "string", "description": "prepare: the source document to send"},
        "template_key": {"type": "string", "description": "prepare: which configured template (see action=templates); this phase has exactly one, 'loe'"},
        "recipients": {"type": "array", "description": "prepare: [{name, email, role}], prefilled from the loan but Ashley must confirm them", "items": {"type": "object"}},
        "message": {"type": "string", "description": "prepare: the short email message shown to the recipient"},
        "request_id": {"type": "string", "description": "status/retrieve: the signature request id"},
    }, "required": ["action", "workspace_id"]},
}


def _esign_client():
    from . import esign as esign_mod

    return esign_mod.default_client()


def _esign_public(rec: dict) -> dict:
    return {k: rec.get(k) for k in ("request_id", "workspace_id", "source_document_id", "template_key", "recipients", "message",
                                    "documenso_envelope_id", "status", "recipient_status", "signed_document_id", "evidence_path",
                                    "notes", "created_at", "sent_at", "retrieved_at", "last_reminded_at")}


def handle_flo_esign(args: dict, **_: Any) -> str:
    try:
        me = _me()
        if not me.borrower_data_allowed:
            return _error(f"{me.display_name} is structurally excluded from borrower loan workspaces")
        from . import documents as documents_mod
        from . import esign as esign_mod

        root = _root()
        wid = str(args.get("workspace_id") or "")
        ws_store = WorkspaceStore(root)
        ws_store.check_access(wid, me.name)
        action = str(args.get("action") or "list")
        if action == "templates":
            return _result({"templates": {k: {kk: vv for kk, vv in v.items() if kk != "documenso_template_id"} | {"configured": bool(v.get("documenso_template_id"))} for k, v in esign_mod.load_templates(root).items()}})
        if action == "list":
            ws = ws_store.get(wid)
            return _result({"requests": esign_mod.board(ws)})
        req_store = esign_mod.SignatureRequestStore(root)
        if action == "prepare":
            did = str(args.get("document_id") or "")
            doc = documents_mod.DocumentStore(root).get(wid, did)
            if doc is None:
                return _error("no such document on this loan")
            prepared = esign_mod.prepare(root, workspace_id=wid, document=doc, template_key=str(args.get("template_key") or ""),
                                         recipients=list(args.get("recipients") or []), message=str(args.get("message") or ""), by=me.name)
            return _result(prepared)
        rid = str(args.get("request_id") or "")
        if action == "status":
            rec = esign_mod.refresh_status(root, _esign_client(), workspace_id=wid, request_id=rid, by=me.name)
            ws_store.upsert_esign(wid, me.name, rec)
            return _result(_esign_public(rec))
        if action == "retrieve":
            rec = esign_mod.retrieve_completed(root, _esign_client(), workspace_id=wid, request_id=rid, by=me.name)
            ws_store.upsert_esign(wid, me.name, rec)
            return _result(_esign_public(rec))
        return _error(f"unknown action {action}")
    except (WorkspaceError, HandoffError, KeyError, ValueError, FileNotFoundError) as exc:
        return _error(str(exc))


FLO_ESIGN_SEND_SCHEMA = {
    "name": "flo_esign_send",
    "description": "Send one document out for electronic signature via Documenso. Yellow action: stops at Ashley's approval prompt bound to this exact document version, these recipients, this template and this message — a material change requires a fresh call. Idempotent: a duplicate call with the identical payload never creates a second envelope or a second email.",
    "parameters": {"type": "object", "properties": {
        "workspace_id": {"type": "string"}, "document_id": {"type": "string"}, "document_checksum": {"type": "string"},
        "template_key": {"type": "string"}, "recipients": {"type": "array", "items": {"type": "object"}}, "message": {"type": "string"},
    }, "required": ["workspace_id", "document_id", "template_key", "recipients"]},
}


def handle_flo_esign_send(args: dict, **_: Any) -> str:
    try:
        me = _me()
        if not me.borrower_data_allowed:
            return _error(f"{me.display_name} is structurally excluded from borrower loan workspaces")
        from . import documents as documents_mod
        from . import esign as esign_mod

        root = _root()
        wid = str(args.get("workspace_id") or "")
        ws_store = WorkspaceStore(root)
        ws_store.check_access(wid, me.name)
        did = str(args.get("document_id") or "")
        doc = documents_mod.DocumentStore(root).get(wid, did)
        if doc is None:
            return _error("no such document on this loan")
        rec = esign_mod.create_and_send(root, _esign_client(), workspace_id=wid, document=doc, template_key=str(args.get("template_key") or ""),
                                        recipients=list(args.get("recipients") or []), message=str(args.get("message") or ""), by=me.name)
        ws_store.upsert_esign(wid, me.name, rec)
        return _result({**_esign_public(rec), "ref": rec.get("documenso_envelope_id") or rec.get("request_id")})
    except (WorkspaceError, HandoffError, KeyError, ValueError, FileNotFoundError) as exc:
        return _error(str(exc))


FLO_ESIGN_REMIND_SCHEMA = {
    "name": "flo_esign_remind",
    "description": "Send an approved reminder for a signature request already sent. Yellow action: stops at Ashley's approval prompt. Operates on the existing request only — never creates a new envelope.",
    "parameters": {"type": "object", "properties": {"workspace_id": {"type": "string"}, "request_id": {"type": "string"}}, "required": ["workspace_id", "request_id"]},
}


def handle_flo_esign_remind(args: dict, **_: Any) -> str:
    try:
        me = _me()
        if not me.borrower_data_allowed:
            return _error(f"{me.display_name} is structurally excluded from borrower loan workspaces")
        from . import esign as esign_mod

        root = _root()
        wid = str(args.get("workspace_id") or "")
        ws_store = WorkspaceStore(root)
        ws_store.check_access(wid, me.name)
        rec = esign_mod.remind(root, _esign_client(), workspace_id=wid, request_id=str(args.get("request_id") or ""), by=me.name)
        ws_store.upsert_esign(wid, me.name, rec)
        return _result({**_esign_public(rec), "ref": rec.get("documenso_envelope_id")})
    except (WorkspaceError, HandoffError, KeyError, ValueError, FileNotFoundError) as exc:
        return _error(str(exc))


FLO_ESIGN_CANCEL_SCHEMA = {
    "name": "flo_esign_cancel",
    "description": "Cancel (void) a signature request that has not completed. Yellow action: stops at Ashley's approval prompt. A changed document needs a brand new request, not editing a signed or cancelled one.",
    "parameters": {"type": "object", "properties": {"workspace_id": {"type": "string"}, "request_id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["workspace_id", "request_id"]},
}


def handle_flo_esign_cancel(args: dict, **_: Any) -> str:
    try:
        me = _me()
        if not me.borrower_data_allowed:
            return _error(f"{me.display_name} is structurally excluded from borrower loan workspaces")
        from . import esign as esign_mod

        root = _root()
        wid = str(args.get("workspace_id") or "")
        ws_store = WorkspaceStore(root)
        ws_store.check_access(wid, me.name)
        rec = esign_mod.cancel(root, _esign_client(), workspace_id=wid, request_id=str(args.get("request_id") or ""), reason=str(args.get("reason") or ""), by=me.name)
        ws_store.upsert_esign(wid, me.name, rec)
        return _result({**_esign_public(rec), "ref": rec.get("request_id")})
    except (WorkspaceError, HandoffError, KeyError, ValueError, FileNotFoundError) as exc:
        return _error(str(exc))


TOOLS = (
    ("flo_team", FLO_TEAM_SCHEMA, handle_flo_team, "🌿"),
    ("flo_intake", FLO_INTAKE_SCHEMA, handle_flo_intake, "📥"),
    ("flo_documents", FLO_DOCUMENTS_SCHEMA, handle_flo_documents, "📄"),
    ("flo_esign", FLO_ESIGN_SCHEMA, handle_flo_esign, "✍️"),
    ("flo_esign_send", FLO_ESIGN_SEND_SCHEMA, handle_flo_esign_send, "✍️"),
    ("flo_esign_remind", FLO_ESIGN_REMIND_SCHEMA, handle_flo_esign_remind, "✍️"),
    ("flo_esign_cancel", FLO_ESIGN_CANCEL_SCHEMA, handle_flo_esign_cancel, "✍️"),
    ("flo_handoff", FLO_HANDOFF_SCHEMA, handle_flo_handoff, "🤝"),
    ("flo_workspace", FLO_WORKSPACE_SCHEMA, handle_flo_workspace, "🗂️"),
    ("flo_approvals", FLO_APPROVALS_SCHEMA, handle_flo_approvals, "✅"),
    ("flo_readiness", FLO_READINESS_SCHEMA, handle_flo_readiness, "📋"),
    ("flo_order", FLO_ORDER_SCHEMA, handle_flo_order, "📦"),
    ("flo_draft", FLO_DRAFT_SCHEMA, handle_flo_draft, "✉️"),
    ("flo_guideline_card", FLO_GUIDELINE_CARD_SCHEMA, handle_flo_guideline_card, "📖"),
    ("flo_knowledge", FLO_KNOWLEDGE_SCHEMA, handle_flo_knowledge, "🔎"),
    ("flo_calc", FLO_CALC_SCHEMA, handle_flo_calc, "🧮"),
    ("flo_assets", FLO_ASSETS_SCHEMA, handle_flo_assets, "🏦"),
    ("flo_du", FLO_DU_SCHEMA, handle_flo_du, "🧾"),
    ("flo_fileprep", FLO_FILEPREP_SCHEMA, handle_flo_fileprep, "🗃️"),
    ("flo_marketing", FLO_MARKETING_SCHEMA, handle_flo_marketing, "📣"),
    ("flo_model_health", FLO_MODEL_HEALTH_SCHEMA, handle_flo_model_health, "🩺"),
    ("flo_sage_response", FLO_SAGE_RESPONSE_SCHEMA, handle_flo_sage_response, "🧷"),
    ("flo_workflow", FLO_WORKFLOW_SCHEMA, handle_flo_workflow, "🛟"),
    ("flo_guidance", FLO_GUIDANCE_SCHEMA, handle_flo_guidance, "📝"),
)


def _available() -> bool:
    return current_role() is not None


def register_tools(ctx) -> None:
    for name, schema, handler, emoji in TOOLS:
        ctx.register_tool(name=name, toolset="flo-team", schema=schema, handler=handler, check_fn=_available, emoji=emoji)
