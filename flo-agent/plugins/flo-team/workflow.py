"""Workflow preflight and mid-chain provider failover.

Preflight (:func:`preflight`) — before a complex team workflow starts:
estimate the specialist turns, check provider health from the routing state
machine (``provider_state.py``), classify the data, pick a route per role,
and report a readiness board::

    Team AI: Ready | Local Fast: … | Local Reasoning: … | Cloud Reasoning: … |
    Fallback: … | Sensitive-data route: …

Failover (:func:`stalled_tasks`, :func:`resume_task`) — when a provider fails
between agents (Malcolm completed, Sage's turn dies with 429/402/…):

1. the handoff/task state is preserved (the task stays ``received`` with its
   objective, workspace and source refs);
2. the data classification is determined (synthetic / non-sensitive /
   sensitive) from the workspace;
3. another approved provider is selected from the state machine;
4. the unfinished specialist turn is resumed by re-entering that profile's
   Bot Chat with a continuation instruction naming the task id;
5. workspace and source references travel with the task record;
6. the provider transition is recorded on the task and in the activity log;
7. completed external actions are never repeated (intents.py guards them).

If no policy-compliant provider is available the workflow fails closed and
Ashley sees: "AI provider unavailable — your work is saved."
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import provider_state as ps
from .handoff import TaskRegistry
from .manifest import manifest as _manifest
from .store import JsonlLog, now_iso, utcnow

STALL_AFTER = timedelta(minutes=8)
TURN_ESTIMATE = {"file_prep_report": 2, "guideline_card": 1, "communication_draft": 1, "order_proposal": 1, "calculation_trace": 1, "marketing_brief": 1, "status_note": 1}
_ERROR_LINE = re.compile(r"(HTTP \d{3}[^\n]{0,200}|Error code: \d{3}[^\n]{0,200}|Model is unavailable[^\n]{0,120}|Insufficient available credits[^\n]{0,160}|usage limit[^\n]{0,120})", re.I)


def classify_workspace(workspace: Optional[Dict[str, Any]]) -> str:
    """synthetic | non_sensitive | sensitive — a real borrower Deal Room is sensitive unless marked synthetic."""
    if not workspace:
        return "non_sensitive"
    name = str(workspace.get("display_name") or "").lower()
    if workspace.get("synthetic") or name.startswith("synthetic"):
        return "synthetic"
    return "sensitive" if (workspace.get("document_refs") or workspace.get("borrower_ref")) else "non_sensitive"


def preflight(root, *, roles: List[str], workspace: Optional[Dict[str, Any]] = None, discovery_rows: Optional[List[Any]] = None,
              expected_return_formats: Optional[List[str]] = None) -> Dict[str, Any]:
    """Lightweight readiness assessment before a multi-agent workflow starts."""
    state = ps.ProviderState(root)
    if discovery_rows:
        for row in discovery_rows:
            state.record_health(row.provider_id, row.hermes_provider, row.available_model or row.model or "", kind=row.kind, status=row.status,
                                latency_ms=row.latency_ms, sensitive_allowed=row.sensitive_data_permission, context_capacity=row.context_capability, error=row.error)
    classification = classify_workspace(workspace)
    turns = sum(TURN_ESTIMATE.get(f, 1) for f in (expected_return_formats or [])) or max(len(roles), 1)
    routes: Dict[str, Any] = {}
    blockers: List[str] = []
    for role in roles:
        choice = state.select(classification=classification)
        routes[role] = choice
        if choice["status"] != "OK":
            blockers.append(f"{role}: {choice['reason']}")
    table = state.table()

    def _class_status(kind: str, prefer_health: Optional[str] = None) -> str:
        rows = [r for r in table if r["kind"] == kind]
        if not rows:
            return "Not configured"
        best = sorted(rows, key=lambda r: (0 if r["health"] == "HEALTHY" else 1 if r["health"] == "DEGRADED" else 2, r.get("latency_ms") or 0))[0]
        return {"HEALTHY": "Healthy", "DEGRADED": "Degraded", "TOO_SLOW": "Slow", "RATE_LIMITED": "Rate limited", "OUT_OF_CREDIT": "Out of credit",
                "MODEL_UNAVAILABLE": "Model unavailable", "OFFLINE": "Offline", "CONTEXT_INSUFFICIENT": "Context too small", "DATA_POLICY_BLOCKED": "Blocked by data policy"}.get(best["health"], best["health"])

    sensitive_route = state.select(classification="sensitive")
    fallbacks = [r for r in table if r["health"] in ps.USABLE_STATES]
    latency = [r.get("latency_ms") for r in fallbacks if r.get("latency_ms")]
    latency_class = "fast" if latency and min(latency) < 20_000 else ("normal" if latency and min(latency) < 60_000 else "slow" if latency else "unknown")
    ready = not blockers
    board = {
        "Team AI": "Ready" if ready else "Not ready",
        "Local Fast": _class_status("local"),
        "Local Reasoning": _class_status("local"),
        "Cloud Reasoning": _class_status("cloud"),
        "Fallback": "Available" if len(fallbacks) > 1 else ("Single route" if fallbacks else "None"),
        "Sensitive-data route": ("Local only" if sensitive_route["status"] == "OK" and any(r["kind"] == "local" for r in fallbacks if "sensitive" in r["data_classification_allowed"])
                                 else ("Approved cloud" if sensitive_route["status"] == "OK" else "Fails closed (no approved route)")),
    }
    return {"ready": ready, "classification": classification, "estimated_specialist_turns": turns, "expected_latency_class": latency_class,
            "estimated_minutes": round(turns * (max(latency or [30_000]) / 1000) * 2.5 / 60, 1), "routes": routes, "blockers": blockers,
            "board": board, "providers": table, "message": None if ready else ps.FAIL_CLOSED_MESSAGE, "generated_at": now_iso()}


def scan_profile_log(profile_home: Path, *, since: Optional[datetime] = None, limit_bytes: int = 400_000) -> List[Dict[str, Any]]:
    """Provider errors from a profile's agent.log tail (Hermes logs the HTTP status and provider/model)."""
    log = Path(profile_home) / "logs" / "agent.log"
    if not log.exists():
        return []
    data = log.read_bytes()[-limit_bytes:].decode("utf-8", "replace")
    out = []
    for line in data.splitlines():
        m = _ERROR_LINE.search(line)
        if not m or "API call failed" not in line and "Non-retryable" not in line and "Error code" not in line:
            continue
        prov = re.search(r"provider=([A-Za-z0-9_\-]+)", line)
        model = re.search(r"model=([^\s]+)", line)
        stamp = line[:19]
        try:
            when = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            when = None
        if since and when and when < since:
            continue
        out.append({"at": stamp, "provider": prov.group(1) if prov else None, "model": model.group(1) if model else None, "error": m.group(1)[:200],
                    "classification": ps.classify_error(m.group(1))})
    return out


def ingest_profile_errors(root, profiles_root: Path, profiles: List[str]) -> List[Dict[str, Any]]:
    """Fold the latest provider errors from each profile's log into the state machine."""
    state = ps.ProviderState(root)
    recorded = []
    for name in profiles:
        for row in scan_profile_log(Path(profiles_root) / name, since=utcnow() - timedelta(hours=2))[-5:]:
            if row["provider"] and row["model"]:
                rec = state.record_failure(row["provider"], row["model"], row["error"], hermes_provider=row["provider"])
                recorded.append({"profile": name, **row, "health": rec["health"]})
    return recorded


def stalled_tasks(root, *, now: Optional[datetime] = None, stall_after: timedelta = STALL_AFTER) -> List[Dict[str, Any]]:
    """Specialist tasks that were received (or sent) but not completed within the stall window."""
    registry = TaskRegistry(root)
    now = now or utcnow()
    out = []
    for task in registry.open_tasks():
        if task.status not in ("sent", "received", "in_progress"):
            continue
        try:
            updated = datetime.fromisoformat(task.updated_at)
        except ValueError:
            continue
        if now - updated >= stall_after:
            out.append({"task_id": task.task_id, "to_agent": task.to_agent, "from_agent": task.from_agent, "status": task.status, "workspace_id": task.workspace_id,
                        "return_format": task.return_format, "stalled_minutes": round((now - updated).total_seconds() / 60, 1), "objective": task.objective[:200]})
    return out


def continuation_message(task, *, reason: str) -> str:
    return (f"Continuation of handoff {task.task_id} ({task.return_format}) after a provider failure ({reason}). Your previous turn on this task did not complete. "
            f"The task state, Deal Room {task.workspace_id or 'n/a'} and source refs are preserved; do not repeat any external action already recorded "
            f"(flo_workspace/flo_draft/flo_order show what exists). Objective: {task.objective}. When done, call flo_handoff action=complete with task_id={task.task_id} "
            f"and message {task.from_agent} the summary.")


def default_spawner(profile: str, *, provider: str, model: str, message: str, timeout: int = 900) -> Dict[str, Any]:
    """Re-enter a profile's Bot Chat with an explicit provider/model (blocking; used by the resume command)."""
    exe = Path(sys.executable).parent / ("hermes.exe" if os.name == "nt" else "hermes")
    cmd = [str(exe), "-p", profile, "chat", "--in", str(Path.home()), "-c", "Bot Chat", "-Q", "--oneshot", "--provider", provider, "--model", model, "-q", message]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(Path.home()))
        return {"ok": proc.returncode == 0, "returncode": proc.returncode, "stdout_tail": (proc.stdout or "")[-1500:], "stderr_tail": (proc.stderr or "")[-800:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": None, "error": f"resume turn exceeded {timeout}s"}


def resume_task(root, task_id: str, *, reason: str, workspace: Optional[Dict[str, Any]] = None, exclude_providers: Optional[List[str]] = None,
                spawner: Optional[Callable[..., Dict[str, Any]]] = None, actor: str = "workflow") -> Dict[str, Any]:
    """Select another approved provider and resume the unfinished specialist turn, recording the transition."""
    registry = TaskRegistry(root)
    task = registry.get(task_id)
    if task is None:
        return {"status": "ERROR", "message": f"unknown task {task_id}"}
    if task.status in ("completed", "returned", "cancelled", "refused"):
        return {"status": "NOOP", "message": f"task {task_id} is already {task.status}; nothing to resume"}
    classification = classify_workspace(workspace)
    state = ps.ProviderState(root)
    choice = state.select(classification=classification, exclude=exclude_providers)
    log = JsonlLog(Path(root) / "activity", "activity")
    if choice["status"] != "OK":
        # Fail closed: state preserved, nothing routed anywhere unapproved.
        registry.transition(task_id, "in_progress", actor=actor, result={"status": "waiting_for_provider", "message": ps.FAIL_CLOSED_MESSAGE, "classification": classification})
        log.append({"event": "workflow.failover.blocked", "actor": actor, "task_id": task_id, "classification": classification, "reason": choice["reason"]})
        return {"status": "FAIL_CLOSED", "message": ps.FAIL_CLOSED_MESSAGE, "task_id": task_id, "classification": classification, "reason": choice["reason"], "state_preserved": True}
    route = choice["route"]
    transition = {"at": now_iso(), "task_id": task_id, "from_provider": exclude_providers, "to_provider": route["provider_id"], "model": route["model"],
                  "reason": reason, "classification": classification}
    handoff = registry.get(task_id)
    handoff.result = {**(handoff.result or {}), "provider_transitions": ((handoff.result or {}).get("provider_transitions") or []) + [transition]}
    registry.save(handoff, "provider_failover", actor)
    log.append({"event": "workflow.failover", "actor": actor, **transition})
    outcome = (spawner or default_spawner)(task.to_agent, provider=route["hermes_provider"], model=route["model"], message=continuation_message(task, reason=reason))
    if outcome.get("ok"):
        state.record_success(route["provider_id"], route["model"], hermes_provider=route["hermes_provider"])
    else:
        state.record_failure(route["provider_id"], route["model"], outcome.get("error") or outcome.get("stderr_tail") or "resume failed", hermes_provider=route["hermes_provider"])
    return {"status": "RESUMED" if outcome.get("ok") else "RESUME_FAILED", "task_id": task_id, "route": route, "classification": classification, "transition": transition, "outcome": outcome}


def check_and_failover(root, *, profiles_root: Optional[Path] = None, workspaces: Optional[Dict[str, Dict[str, Any]]] = None,
                       spawner: Optional[Callable[..., Dict[str, Any]]] = None, actor: str = "workflow") -> Dict[str, Any]:
    """One orchestration pass: ingest provider errors, find stalled tasks, resume each on an approved route."""
    ingested = ingest_profile_errors(root, profiles_root, [r for r in _manifest().profiles]) if profiles_root else []
    results = []
    for stalled in stalled_tasks(root):
        ws = (workspaces or {}).get(stalled["workspace_id"] or "")
        failed = sorted({i["provider"] for i in ingested if i.get("provider")})
        results.append(resume_task(root, stalled["task_id"], reason="; ".join(sorted({i["error"] for i in ingested})) or "stalled specialist turn",
                                   workspace=ws, exclude_providers=failed or None, spawner=spawner, actor=actor))
    return {"ingested_errors": ingested, "stalled": [s["task_id"] for s in stalled_tasks(root)], "results": results, "generated_at": now_iso()}
