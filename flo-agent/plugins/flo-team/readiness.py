"""Malcolm's File Readiness report — transparent, deterministic, never an approval.

Inputs are structured facts already in the Loan Workspace plus a checklist the
caller supplies (the minimum-document checklist is a SOURCE_GAP until an
approved matrix exists, so the checklist items come from the handoff or from
Ashley — the tool does not invent one). Output = the pack's FILE_PREP_REPORT
shape plus a 0–100 score computed from visible counts. The report's status
vocabulary is deliberately not an underwriting decision: ``READY_FOR_NEXT_STEP``
means "nothing on the checklist is missing", never "approved".
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .store import now_iso

STATUSES = ("NOT_STARTED", "IN_PROGRESS", "BLOCKED", "READY_FOR_NEXT_STEP")
DISCLAIMER = (
    "File Readiness is a processing checklist score, not an underwriting decision. "
    "It never means the loan, income or a condition is approved."
)
AUS_STATES = ("present", "missing", "unknown")


def build_report(
    *,
    workspace: Dict[str, Any],
    checklist: List[Dict[str, Any]],
    discrepancies: Optional[List[str]] = None,
    aus_status: str = "unknown",
    income_prep_complete: Optional[bool] = None,
    assets_prep_complete: Optional[bool] = None,
    open_questions: Optional[List[str]] = None,
    source_refs: Optional[List[str]] = None,
    agent: str = "malcolm",
) -> Dict[str, Any]:
    if aus_status not in AUS_STATES:
        raise ValueError(f"aus_status must be one of {AUS_STATES}")
    items = []
    for raw in checklist or []:
        if not isinstance(raw, dict) or not str(raw.get("item") or "").strip():
            continue
        state = str(raw.get("state") or "missing").lower()
        if state not in ("complete", "missing", "expired", "conflicting", "unknown", "waived_by_ashley"):
            state = "unknown"
        items.append({
            "item": str(raw["item"]).strip()[:200],
            "state": state,
            "owner": str(raw.get("owner") or "unknown")[:40],
            "source_ref": (str(raw.get("source_ref"))[:200] if raw.get("source_ref") else None),
            "basis": str(raw.get("basis") or "checklist supplied by handoff/Ashley; no approved document matrix loaded (SOURCE_GAP)")[:300],
        })
    complete = [i for i in items if i["state"] in ("complete", "waived_by_ashley")]
    missing = [i for i in items if i["state"] in ("missing", "expired")]
    conflicting = [i for i in items if i["state"] == "conflicting"]
    unknown = [i for i in items if i["state"] == "unknown"]
    discrepancies = [str(d)[:300] for d in (discrepancies or []) if str(d).strip()]
    open_questions = [str(q)[:300] for q in (open_questions or []) if str(q).strip()]

    # Transparent score: each component is shown with its weight.
    components = []
    if items:
        doc_pct = len(complete) / len(items)
        components.append({"component": "checklist_complete", "value": round(doc_pct, 3), "weight": 50, "points": round(50 * doc_pct)})
    else:
        components.append({"component": "checklist_complete", "value": None, "weight": 50, "points": 0, "note": "no checklist supplied"})
    aus_points = {"present": 15, "unknown": 5, "missing": 0}[aus_status]
    components.append({"component": "aus_findings", "value": aus_status, "weight": 15, "points": aus_points})
    disc_points = max(0, 15 - 5 * (len(discrepancies) + len(conflicting)))
    components.append({"component": "no_discrepancies", "value": len(discrepancies) + len(conflicting), "weight": 15, "points": disc_points})
    inc_points = 10 if income_prep_complete else (5 if income_prep_complete is None else 0)
    components.append({"component": "income_prep", "value": income_prep_complete, "weight": 10, "points": inc_points})
    ast_points = 10 if assets_prep_complete else (5 if assets_prep_complete is None else 0)
    components.append({"component": "assets_prep", "value": assets_prep_complete, "weight": 10, "points": ast_points})
    penalty = min(20, 4 * len(open_questions))
    components.append({"component": "open_questions", "value": len(open_questions), "weight": -20, "points": -penalty})
    score = max(0, min(100, sum(int(c["points"]) for c in components)))

    if not items and aus_status == "unknown":
        status = "NOT_STARTED"
    elif conflicting or (workspace.get("blockers") or []):
        status = "BLOCKED"
    elif not missing and not unknown and aus_status == "present" and not discrepancies:
        status = "READY_FOR_NEXT_STEP"
    else:
        status = "IN_PROGRESS"

    next_move = _next_move(missing, conflicting, unknown, discrepancies, aus_status, open_questions)
    ashley_output = {
        "status": (f"Needs {len(missing)} item{'s' if len(missing) != 1 else ''}" if missing else
                   "Blocked" if conflicting or (workspace.get("blockers") or []) else
                   "Ready" if status == "READY_FOR_NEXT_STEP" else "In progress"),
        "missing_items": [str(i["item"]) for i in missing],
        "important_discrepancies": [str(d).replace("conflicting: ", "", 1) for d in discrepancies] + [str(i["item"]) for i in conflicting],
        "aus_status": {"present": "Findings on file", "missing": "Missing", "unknown": "Not checked yet"}[aus_status],
        "income_status": "Reviewed" if income_prep_complete is True else "Needs attention" if income_prep_complete is False else "Not checked yet",
        "asset_status": "Reviewed" if assets_prep_complete is True else "Needs attention" if assets_prep_complete is False else "Not checked yet",
        "orders_status": "Nothing ordered yet" if not workspace.get("orders") else f"{len(workspace.get('orders') or [])} open order{'s' if len(workspace.get('orders') or []) != 1 else ''}",
        "biggest_blocker": (str(conflicting[0]["item"]) if conflicting else str(missing[0]["item"]) if missing else str(discrepancies[0]) if discrepancies else None),
        "best_next_move": "Follow up on the missing items." if missing else "Resolve the conflicting item first." if conflicting else "Ready for the next step." if status == "READY_FOR_NEXT_STEP" else "Review the file details."
    }
    return {
        "report_type": "file_prep_report",
        "workspace_id": workspace.get("workspace_id"),
        "display_name": workspace.get("display_name"),
        "milestone": workspace.get("milestone"),
        "program": workspace.get("program"),
        "aus_findings": aus_status,
        "status": status,
        "score": score,
        "score_components": components,
        "complete": complete,
        "missing": missing,
        "missing_count": len(missing),
        "discrepancies": discrepancies + [f"conflicting: {i['item']}" for i in conflicting],
        "unknown": unknown,
        "income_assets": {
            "income_prep_complete": income_prep_complete,
            "assets_prep_complete": assets_prep_complete,
            "calculation_refs": [],
            "source_refs": list(source_refs or []),
        },
        "risks_questions": open_questions,
        "best_next_move": next_move,
        "ashley_output": ashley_output,
        "is_underwriting_decision": False,
        "disclaimer": DISCLAIMER,
        "generated_by": agent,
        "generated_at": now_iso(),
    }


def _next_move(missing, conflicting, unknown, discrepancies, aus_status, open_questions) -> str:
    if conflicting:
        return f"Resolve the conflicting item first: {conflicting[0]['item']} (ask Flo to engage Sage if it depends on a guideline)."
    if aus_status == "missing":
        return "Confirm AUS findings are present in the file before anything else."
    if missing:
        owner = missing[0].get("owner") or "the owner"
        return f"Only blocker right now: {missing[0]['item']} from {owner}. One clean follow-up."
    if discrepancies:
        return f"Reconcile: {discrepancies[0]}"
    if unknown:
        return f"Confirm the state of: {unknown[0]['item']}."
    if open_questions:
        return f"Get an answer on: {open_questions[0]}"
    return "Checklist is clean. Hand the file back to Flo for the next milestone step."
