"""Loan Workspaces and Deal Rooms — one loan truth, many specialists.

A Loan Workspace is the structured record from ``schemas/loan_workspace.schema.json``
(workspace_id, display_name, program, agency, aus, milestone, status_summary,
next_action, blockers[], conditions[], orders[], document_refs[],
communication_refs[], source_refs[], agent_tasks[], approvals[]) plus the Deal
Room membership, an activity timeline and readiness/order/draft sub-records.

Membership rules (team/TEAM_OPERATING_SYSTEM.md): Flo always; Malcolm,
Chadwick, Whisper, Sage when needed; Franklin never. The optional Hermes group
chat is created by the desktop (``Group: <roomId>`` sessions) — the structured
workspace, not the transcript, is the source of truth.

Workspaces store references (``doc://``, ``mail://``, ``drive://`` ids) and
display names — never SSNs, account numbers or document bodies.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .manifest import TeamManifest, manifest as _manifest
from .store import JsonDocStore, JsonlLog, new_id, now_iso, safe_id

MILESTONES = ("Intake", "Application", "Processing", "Conditional Approval", "Clear to Close", "Closed")
_SSN = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b")
_LONG_DIGITS = re.compile(r"\b\d{8,}\b")


class WorkspaceError(ValueError):
    pass


def _reject_npi(text: str, what: str) -> None:
    if _SSN.search(text or "") or _LONG_DIGITS.search(text or ""):
        raise WorkspaceError(f"{what} looks like it contains an SSN or account number; use a reference instead")


def default_members(team: TeamManifest) -> List[str]:
    return [n for n, spec in team.profiles.items() if spec.deal_rooms in ("always", "throughout")]


class WorkspaceStore:
    def __init__(self, root, team: Optional[TeamManifest] = None) -> None:
        self.team = team or _manifest()
        self.docs = JsonDocStore(root / "workspaces")
        self.log = JsonlLog(root / "activity", "activity")

    # -- lifecycle --------------------------------------------------------

    def create(self, *, display_name: str, program: Optional[str] = None, agency: Optional[str] = None,
               milestone: str = "Intake", workspace_id: Optional[str] = None, actor: str = "flo") -> Dict[str, Any]:
        display_name = " ".join(str(display_name or "").split())
        if not display_name:
            raise WorkspaceError("display_name is required (borrower last name or file nickname, no NPI)")
        _reject_npi(display_name, "display_name")
        if milestone not in MILESTONES:
            raise WorkspaceError(f"milestone must be one of {MILESTONES}")
        wid = safe_id(workspace_id) if workspace_id else new_id("loan")
        _reject_npi(wid, "workspace_id")
        if self.docs.get(wid):
            raise WorkspaceError(f"workspace {wid} already exists")
        doc = {
            "workspace_id": wid,
            "display_name": display_name,
            "program": program,
            "agency": agency,
            "aus": None,
            "milestone": milestone,
            "status_summary": None,
            "next_action": None,
            "blockers": [],
            "conditions": [],
            "orders": [],
            "document_refs": [],
            "communication_refs": [],
            "source_refs": [],
            "agent_tasks": [],
            "approvals": [],
            "members": default_members(self.team),
            "excluded_members": [n for n, s in self.team.profiles.items() if s.deal_rooms == "never"],
            "activity": [],
            "readiness": None,
            "drafts": [],
            "created_at": now_iso(),
            "created_by": actor,
        }
        self.docs.put(wid, doc)
        self._activity(wid, actor, "workspace.created", {"display_name": display_name, "milestone": milestone})
        return self.docs.get(wid)  # type: ignore[return-value]

    def get(self, workspace_id: str) -> Dict[str, Any]:
        doc = self.docs.get(workspace_id)
        if doc is None:
            raise WorkspaceError(f"unknown workspace {workspace_id}")
        return doc

    def list(self) -> List[Dict[str, Any]]:
        return [
            {k: d.get(k) for k in ("workspace_id", "display_name", "program", "agency", "milestone",
                                    "status_summary", "next_action", "members", "updated_at")}
            | {"blockers": len(d.get("blockers") or []), "open_orders": len([o for o in d.get("orders") or [] if o.get("state") not in ("reconciled",)]),
               "readiness_score": (d.get("readiness") or {}).get("score")}
            for d in self.docs.all()
        ]

    # -- access control ---------------------------------------------------

    def check_access(self, workspace_id: str, agent: str, *, write: bool = False) -> None:
        spec = self.team.role(agent)
        if spec.loan_workspace == "deny":
            raise WorkspaceError(f"{spec.display_name} is structurally excluded from borrower loan workspaces")
        if write and spec.loan_workspace != "read_write":
            raise WorkspaceError(f"{spec.display_name} has read-only access to loan workspaces")
        doc = self.get(workspace_id)
        if agent in (doc.get("excluded_members") or []):
            raise WorkspaceError(f"{spec.display_name} is excluded from Deal Room {workspace_id}")

    def invite(self, workspace_id: str, agent: str, *, actor: str) -> Dict[str, Any]:
        spec = self.team.role(agent)
        if spec.deal_rooms == "never" or spec.loan_workspace == "deny":
            raise WorkspaceError(f"{spec.display_name} cannot join borrower Deal Rooms")

        def _mutate(doc):
            if agent not in doc["members"]:
                doc["members"].append(agent)

        self.docs.update(workspace_id, _mutate)
        self._activity(workspace_id, actor, "deal_room.invited", {"agent": agent})
        return self.get(workspace_id)

    # -- structured updates ----------------------------------------------

    def update_fields(self, workspace_id: str, agent: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        self.check_access(workspace_id, agent, write=True)
        allowed = {"program", "agency", "aus", "milestone", "status_summary", "next_action"}
        unknown = set(fields) - allowed
        if unknown:
            raise WorkspaceError(f"cannot set {sorted(unknown)}; use add_* actions for lists")
        if "milestone" in fields and fields["milestone"] not in MILESTONES:
            raise WorkspaceError(f"milestone must be one of {MILESTONES}")
        for key, value in fields.items():
            if isinstance(value, str):
                _reject_npi(value, key)

        def _mutate(doc):
            doc.update(fields)

        self.docs.update(workspace_id, _mutate)
        self._activity(workspace_id, agent, "workspace.updated", {"fields": sorted(fields)})
        return self.get(workspace_id)

    def add_item(self, workspace_id: str, agent: str, list_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        self.check_access(workspace_id, agent, write=True)
        lists = {"blockers", "conditions", "document_refs", "communication_refs", "source_refs"}
        if list_name not in lists:
            raise WorkspaceError(f"list must be one of {sorted(lists)}")
        item = dict(item)
        item.setdefault("id", new_id(list_name[:4]))
        item.setdefault("added_by", agent)
        item.setdefault("added_at", now_iso())
        for value in item.values():
            if isinstance(value, str):
                _reject_npi(value, list_name)
        if list_name == "conditions":
            # A file-specific UW condition is a checklist entry, never a rule.
            item.setdefault("scope", "file_specific")
            item["global_rule"] = False

        def _mutate(doc):
            doc.setdefault(list_name, []).append(item)

        self.docs.update(workspace_id, _mutate)
        self._activity(workspace_id, agent, f"{list_name}.added", {"id": item["id"]})
        return item

    def attach_task(self, workspace_id: str, task_id: str, agent: str) -> None:
        def _mutate(doc):
            if task_id not in doc.setdefault("agent_tasks", []):
                doc["agent_tasks"].append(task_id)

        self.docs.update(workspace_id, _mutate)
        self._activity(workspace_id, agent, "task.attached", {"task_id": task_id})

    def attach_approval(self, workspace_id: str, proposal_id: str, agent: str, status: str) -> None:
        def _mutate(doc):
            rows = doc.setdefault("approvals", [])
            for row in rows:
                if row.get("proposal_id") == proposal_id:
                    row["status"] = status
                    row["updated_at"] = now_iso()
                    return
            rows.append({"proposal_id": proposal_id, "agent": agent, "status": status, "updated_at": now_iso()})

        self.docs.update(workspace_id, _mutate)

    def set_readiness(self, workspace_id: str, agent: str, report: Dict[str, Any]) -> None:
        self.check_access(workspace_id, agent, write=True)

        def _mutate(doc):
            doc["readiness"] = report
            # A website submission's placeholder next step is replaced by the report's best next move,
            # and the submission is marked reviewed so Ashley's screens stop saying "Malcolm is reviewing".
            if doc.get("submission"):
                doc["submission"]["review_status"] = "reviewed"
                doc["submission"]["reviewed_at"] = now_iso()
                if str(doc.get("next_action") or "").startswith("Malcolm is reviewing"):
                    doc["next_action"] = report.get("best_next_move") or None

        self.docs.update(workspace_id, _mutate)
        self._activity(workspace_id, agent, "readiness.updated", {"score": report.get("score"), "status": report.get("status")})

    def upsert_order(self, workspace_id: str, agent: str, order: Dict[str, Any]) -> None:
        self.check_access(workspace_id, agent, write=True)

        def _mutate(doc):
            rows = doc.setdefault("orders", [])
            for i, row in enumerate(rows):
                if row.get("order_id") == order.get("order_id"):
                    rows[i] = order
                    return
            rows.append(order)

        self.docs.update(workspace_id, _mutate)
        self._activity(workspace_id, agent, "order.updated", {"order_id": order.get("order_id"), "state": order.get("state")})

    def upsert_esign(self, workspace_id: str, agent: str, request: Dict[str, Any]) -> None:
        """Signature-request records for Ashley's Documents section (``esign.py``). Communications-shaped,
        like a draft: no full write access required, matching ``add_draft`` below."""
        self.check_access(workspace_id, agent, write=False)

        def _mutate(doc):
            rows = doc.setdefault("esign_requests", [])
            for i, row in enumerate(rows):
                if row.get("request_id") == request.get("request_id"):
                    rows[i] = request
                    return
            rows.append(request)

        self.docs.update(workspace_id, _mutate)
        self._activity(workspace_id, agent, "esign.updated", {"request_id": request.get("request_id"), "status": request.get("status")})

    def add_draft(self, workspace_id: str, agent: str, draft: Dict[str, Any]) -> None:
        self.check_access(workspace_id, agent, write=False)

        def _mutate(doc):
            doc.setdefault("drafts", []).append(draft)

        self.docs.update(workspace_id, _mutate)
        self._activity(workspace_id, agent, "draft.added", {"draft_id": draft.get("draft_id"), "status": draft.get("status")})

    # -- activity ---------------------------------------------------------

    def _activity(self, workspace_id: str, actor: str, event: str, meta: Dict[str, Any]) -> None:
        entry = {"timestamp": now_iso(), "actor": actor, "event": event, **meta}

        def _mutate(doc):
            doc.setdefault("activity", []).append(entry)
            doc["activity"] = doc["activity"][-200:]

        try:
            self.docs.update(workspace_id, _mutate)
        except KeyError:
            pass
        self.log.append({"workspace_id": workspace_id, **entry})

    def heat_map(self) -> Dict[str, List[Dict[str, Any]]]:
        """Pipeline heat map buckets — derived, not judged."""
        buckets: Dict[str, List[Dict[str, Any]]] = {"today": [], "at_risk": [], "waiting": [], "blocked": [], "closing_pressure": [], "fastest_wins": []}
        for doc in self.docs.all():
            row = {"workspace_id": doc["workspace_id"], "display_name": doc.get("display_name"), "milestone": doc.get("milestone")}
            open_orders = [o for o in doc.get("orders") or [] if o.get("state") not in ("reconciled", "received")]
            overdue = [o for o in open_orders if o.get("state") == "overdue"]
            if doc.get("blockers"):
                buckets["blocked"].append(row)
            elif overdue:
                buckets["at_risk"].append(row)
            elif open_orders:
                buckets["waiting"].append(row)
            if doc.get("milestone") in ("Clear to Close",):
                buckets["closing_pressure"].append(row)
            readiness = doc.get("readiness") or {}
            if readiness.get("missing_count") == 1:
                buckets["fastest_wins"].append(row)
            if doc.get("next_action"):
                buckets["today"].append(row)
        return buckets
