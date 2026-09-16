"""Chadwick's order proposals and tracking (ORDER_PROPOSAL template + state machine).

States: requested → approved → ordered → vendor_confirmed → pending → received
→ reconciled, plus overdue (from pending/ordered) and cancelled. The only
transition a bot may make on its own is *requested* (a proposal). ``approved``
requires an Approval Center card id; ``ordered`` / ``vendor_confirmed``
require an execution reference from the tool that placed the order — a bot
cannot mark an order placed by saying so.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .store import new_id, now_iso

ORDER_TYPES = ("title", "hoi", "wvoe", "voe", "loe_request", "custom")
STATES = ("requested", "approved", "ordered", "vendor_confirmed", "pending", "received", "reconciled", "overdue", "cancelled")
_TRANSITIONS = {
    "requested": {"approved", "cancelled"},
    "approved": {"ordered", "cancelled"},
    "ordered": {"vendor_confirmed", "pending", "overdue", "cancelled"},
    "vendor_confirmed": {"pending", "received", "overdue"},
    "pending": {"received", "overdue", "cancelled"},
    "overdue": {"received", "pending", "cancelled"},
    "received": {"reconciled"},
    "reconciled": set(),
    "cancelled": set(),
}
REQUIRED_INPUTS = {
    # Structural inputs only — vendor requirements beyond these are SOURCE_GAP.
    "title": ["property_ref", "borrower_ref", "vendor"],
    "hoi": ["property_ref", "borrower_ref", "agent_or_carrier_ref"],
    "wvoe": ["employer_ref", "borrower_ref", "authorization_ref"],
    "voe": ["employer_ref", "borrower_ref", "authorization_ref"],
    "loe_request": ["borrower_ref", "topic", "draft_ref"],
    "custom": ["vendor", "purpose"],
}


class OrderError(ValueError):
    pass


def propose(*, workspace_id: str, order_type: str, inputs: Dict[str, Any], purpose: str,
            urgency: Optional[str] = None, source_ref: Optional[str] = None, agent: str = "chadwick") -> Dict[str, Any]:
    order_type = (order_type or "").lower()
    if order_type not in ORDER_TYPES:
        raise OrderError(f"order_type must be one of {ORDER_TYPES}")
    inputs = {str(k): v for k, v in (inputs or {}).items()}
    required = REQUIRED_INPUTS[order_type]
    present = [k for k in required if str(inputs.get(k) or "").strip()]
    missing = [k for k in required if k not in present]
    return {
        "order_id": new_id("ord"),
        "workspace_id": workspace_id,
        "order_type": order_type,
        "vendor_or_destination": str(inputs.get("vendor") or inputs.get("agent_or_carrier_ref") or inputs.get("employer_ref") or "SOURCE_GAP: vendor not supplied")[:200],
        "purpose": str(purpose or "")[:400],
        "required_inputs_present": present,
        "missing_inputs": missing,
        "inputs_ref": {k: str(v)[:200] for k, v in inputs.items()},
        "source_or_trigger": source_ref,
        "urgency": urgency,
        "approval_required": True,
        "state": "requested",
        "approval_id": None,
        "execution_ref": None,
        "vendor_requirements": "SOURCE_GAP: no approved vendor requirement list loaded; confirm with the vendor/AE",
        "history": [{"at": now_iso(), "state": "requested", "by": agent}],
        "created_at": now_iso(),
    }


def transition(order: Dict[str, Any], new_state: str, *, by: str, approval_id: Optional[str] = None,
               execution_ref: Optional[str] = None, note: str = "") -> Dict[str, Any]:
    current = order.get("state", "requested")
    if new_state not in STATES:
        raise OrderError(f"unknown state {new_state!r}")
    if new_state not in _TRANSITIONS.get(current, set()):
        raise OrderError(f"cannot move order from {current} to {new_state}")
    if new_state == "approved" and not approval_id:
        raise OrderError("approved requires an Approval Center approval_id (Ashley's decision)")
    if new_state in ("ordered", "vendor_confirmed") and not execution_ref:
        raise OrderError(f"{new_state} requires an execution_ref from the tool that placed/confirmed the order; a bot cannot declare an order placed")
    order = dict(order)
    order["state"] = new_state
    if approval_id:
        order["approval_id"] = approval_id
    if execution_ref:
        order["execution_ref"] = execution_ref
    order.setdefault("history", []).append({"at": now_iso(), "state": new_state, "by": by, **({"note": note} if note else {})})
    return order


def tracker(orders: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {s: [] for s in STATES}
    for order in orders or []:
        out.setdefault(order.get("state", "requested"), []).append(
            {k: order.get(k) for k in ("order_id", "workspace_id", "order_type", "vendor_or_destination", "state", "urgency", "missing_inputs")})
    return out
