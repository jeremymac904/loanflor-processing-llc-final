"""Ashley's Today view and one-file summary — plain English, one source of truth.

The desktop screens (`apps/desktop/src/plugins/flo/ashley.ts`) and Flo's chat
answers ("what should I work on next?", "where are we on Bell?") derive the
same six answers from the same files with the same rules:

    1. what matters right now     -> top three files
    2. what do I need to do       -> best next move per file
    3. what is the team handling  -> quiet hints from activity
    4. what are we waiting on     -> orders out + items owned by other people
    5. is anything at risk        -> Blocked / At Risk files and why
    6. anything to approve        -> pending Approval Center cards + drafts

Status vocabulary is fixed: Done, Needs Ashley, Waiting, Working, At Risk,
Blocked. Internal states (pending_review, handoff_open, provider_degraded,
READY_FOR_NEXT_STEP …) never leave this module.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from .store import JsonDocStore, JsonlLog, now_iso, utcnow

STATUSES = ("Done", "Needs Ashley", "Waiting", "Working", "At Risk", "Blocked")
_OPEN_ORDER = {"requested", "approved", "ordered", "vendor_confirmed", "pending", "overdue"}
_OPEN_TASK = {"proposed", "sent", "received", "in_progress"}
_OTHERS = {"borrower", "lo", "lender", "realtor", "title", "vendor", "ae", "uw", "underwriter"}
ORDER_LABEL = {"title": "Title", "hoi": "Homeowners insurance", "wvoe": "Written VOE", "voe": "VOE", "loe_request": "Letter of explanation", "custom": "Order"}
_ORDER_STATE = {
    "requested": "proposed, needs your approval", "approved": "approved, placing", "ordered": "ordered, waiting on vendor",
    "vendor_confirmed": "ordered, waiting on vendor", "pending": "ordered, waiting on vendor", "overdue": "overdue",
    "received": "received", "reconciled": "done", "cancelled": "cancelled",
}
_CAPABILITY = {
    "email_send": "Send an email", "outbound_message": "Send a message", "email_modify": "Change an email", "drive_upload": "Upload a file",
    "drive_share_external": "Share a file outside the team", "calendar_write": "Update the calendar", "portal_submit": "Submit to a portal",
    "external_status_change": "Update a status",
}
_PRIORITY = {"Blocked": 100, "At Risk": 80, "Needs Ashley": 60, "Working": 20, "Waiting": 10, "Done": 0}


def _name(ws: Dict[str, Any]) -> str:
    return str(ws.get("display_name") or ws.get("workspace_id") or "this file")


def missing_items(ws: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [m for m in ((ws.get("readiness") or {}).get("missing") or []) if isinstance(m, dict) and m.get("item")]


def open_orders(ws: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [o for o in (ws.get("orders") or []) if o.get("state") in _OPEN_ORDER]


def drafts_for_review(ws: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [d for d in (ws.get("drafts") or []) if d.get("status") in ("draft", "proposed")]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _pending_cards(cards: Iterable[Dict[str, Any]], workspace_id: Optional[str] = None, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    now = _aware(now or utcnow())
    out = []
    for c in cards or []:
        if c.get("status") != "pending" or (workspace_id and c.get("workspace_id") != workspace_id):
            continue
        exp = c.get("expires_at")
        try:
            if exp and _aware(datetime.fromisoformat(str(exp))) <= now:
                continue
        except ValueError:
            pass
        out.append(c)
    return sorted(out, key=lambda c: str(c.get("created_at") or ""), reverse=True)


def short(text: Any, limit: int = 140) -> str:
    """First sentence, bounded — Malcolm's reasons can run long; Ashley gets the headline."""
    s = " ".join(str(text or "").split()).rstrip(". ")
    s = re.sub(r"\s*\((?:verified|is_underwriting_decision)=\w+\)", "", s)  # Malcolm's machine flags never reach Ashley
    if not s:
        return ""
    first = re.split(r"(?<=[.;])\s+", s, maxsplit=1)[0].rstrip(". ;")
    if len(first) > limit:
        first = first[: limit - 1].rsplit(" ", 1)[0] + "…"
    return first


def plain_status(ws: Dict[str, Any], approvals: Iterable[Dict[str, Any]] = (), tasks: Iterable[Dict[str, Any]] = (), now: Optional[datetime] = None) -> str:
    """One plain-English state per file; the worst news wins."""
    r = ws.get("readiness") or {}
    if ws.get("blockers") or r.get("status") == "BLOCKED":
        return "Blocked"
    overdue = any(o.get("state") == "overdue" for o in ws.get("orders") or [])
    if overdue or (ws.get("milestone") == "Clear to Close" and (r.get("missing_count") or 0) > 0):
        return "At Risk"
    if _pending_cards(approvals, ws.get("workspace_id"), now) or drafts_for_review(ws):
        return "Needs Ashley"
    if ws.get("milestone") == "Closed" or (r.get("status") == "READY_FOR_NEXT_STEP" and not open_orders(ws)):
        return "Done"
    if any(t.get("workspace_id") == ws.get("workspace_id") and t.get("status") in _OPEN_TASK for t in tasks or []):
        return "Working"
    waiting = open_orders(ws) or any(str(m.get("owner") or "").lower() in _OTHERS for m in missing_items(ws))
    return "Waiting" if waiting else "Working"


def long_date(value: Any) -> str:
    """'2026-09-23' -> 'September 23' (what Ashley reads on a card)."""
    try:
        d = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return str(value or "")
    return f"{d.strftime('%B')} {d.day}"


def new_loan_card(ws: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The NEW LOAN card for a website submission Malcolm has not reviewed yet."""
    sub = ws.get("submission") or {}
    if not sub or ws.get("readiness"):
        return None
    docs = int((ws.get("documents_summary") or {}).get("received") or 0)
    return {
        "workspace_id": ws.get("workspace_id"), "name": _name(ws), "submitted_by": (sub.get("loan_officer") or {}).get("name") or "the loan officer",
        "program": " • ".join(p for p in (sub.get("program_label"), sub.get("transaction_label")) if p),
        "expected_closing": long_date(sub.get("expected_closing_date")) if sub.get("expected_closing_date") else None,
        "documents_received": docs,
        "line": (f"{docs} document{'s' if docs != 1 else ''} received. " if docs else "") + "Malcolm is reviewing it.",
    }


def submission_line(ws: Dict[str, Any]) -> Optional[str]:
    """'Submitted by Matt Combs • FHA • Purchase • Expected closing September 23. Malcolm is reviewing it.' while a website submission awaits review."""
    card = new_loan_card(ws)
    if not card:
        return None
    parts = [f"Submitted by {card['submitted_by']}", card["program"]]
    if card["expected_closing"]:
        parts.append(f"Expected closing {card['expected_closing']}")
    return " • ".join(p for p in parts if p) + ". Malcolm is reviewing it."


def readiness_label(ws: Dict[str, Any]) -> str:
    r = ws.get("readiness")
    if not r:
        return "New submission" if ws.get("submission") else "Not checked yet"
    status = r.get("status")
    if status == "BLOCKED":
        return "Blocked"
    if status == "READY_FOR_NEXT_STEP":
        return "Ready"
    if status == "NOT_STARTED":
        return "Not started"
    missing = r.get("missing_count") if r.get("missing_count") is not None else len(missing_items(ws))
    if missing:
        return f"Needs {missing} item{'s' if missing != 1 else ''}"
    return "Almost ready" if (r.get("score") or 0) >= 50 else "In progress"


def _aus(ws: Dict[str, Any]) -> str:
    if ws.get("aus"):
        return str(ws["aus"])
    return {"present": "Findings on file", "missing": "Missing"}.get(str((ws.get("readiness") or {}).get("aus_findings")), "Not checked yet")


def _prep(flag: Any) -> str:
    return "Reviewed" if flag is True else ("Needs attention" if flag is False else "Not checked yet")


def orders_label(ws: Dict[str, Any]) -> str:
    orders = ws.get("orders") or []
    if not orders:
        return "Nothing ordered yet"
    return " · ".join(f"{ORDER_LABEL.get(str(o.get('order_type')), 'Order')}: {_ORDER_STATE.get(str(o.get('state')), 'not ordered')}" for o in orders)


def risk_line(ws: Dict[str, Any]) -> Optional[str]:
    blockers = ws.get("blockers") or []
    if blockers:
        b = blockers[0]
        return str(b.get("text") if isinstance(b, dict) else b) or "Blocked"
    for o in ws.get("orders") or []:
        if o.get("state") == "overdue":
            return f"{ORDER_LABEL.get(str(o.get('order_type')), 'An order')} is overdue"
    r = ws.get("readiness") or {}
    if ws.get("milestone") == "Clear to Close" and (r.get("missing_count") or 0) > 0:
        return "Clear to Close with items still missing"
    disc = (r.get("discrepancies") or [None])[0]
    if disc:
        text = str(disc)
        return short(text[len("conflicting:"):].strip() if text.lower().startswith("conflicting:") else text)
    return None


def best_next_move(ws: Dict[str, Any]) -> str:
    new = submission_line(ws)
    if new:
        return new
    r = ws.get("readiness") or {}
    conflicting = any(str(d).lower().startswith("conflicting") for d in r.get("discrepancies") or [])
    if missing_items(ws) and not ws.get("blockers") and not conflicting:
        return "Request the missing documents."
    return short(ws.get("next_action") or r.get("best_next_move"), 160) or "Nothing urgent. Flo will flag the next step."


_DOC_CATEGORY_LABEL = {"loan_application": "Application", "credit_report": "Credit", "aus_findings": "AUS", "income": "Income", "assets": "Assets", "purchase_contract": "Contract",
                       "title_property": "Title / Property", "insurance": "Insurance", "identification": "ID", "other": "Other"}
_DOC_CATEGORY_ORDER = list(_DOC_CATEGORY_LABEL)
_MISSING_ROUTES = [  # mirrors ashley.ts MISSING_ROUTES (order matters)
    ("insurance", re.compile(r"insurance|\bhoi\b|hazard|flood", re.I)), ("title_property", re.compile(r"\btitle\b|appraisal|survey", re.I)),
    ("purchase_contract", re.compile(r"contract|purchase agreement", re.I)), ("aus_findings", re.compile(r"\baus\b|\bdu\b|findings|\blpa\b|\btotal\b|\bgus\b", re.I)),
    ("credit_report", re.compile(r"credit", re.I)), ("loan_application", re.compile(r"1003|application", re.I)),
    ("income", re.compile(r"paystub|pay stub|w-?2|1099|tax return|income|k-?1|p&l|profit|award letter|\bvoe\b", re.I)),
    ("assets", re.compile(r"bank|statement|asset|retirement|gift|funds", re.I)), ("identification", re.compile(r"identification|license|passport|\bid\b", re.I)),
]
_WAITING_CATEGORIES = ("insurance", "title_property")
_DOC_ATTENTION = {"needs_review", "missing_pages", "unreadable", "listed"}


def missing_category(item: str) -> str:
    for category, rx in _MISSING_ROUTES:
        if rx.search(item or ""):
            return category
    return "other"


def missing_documents(ws: Dict[str, Any]) -> List[str]:
    """Malcolm's readiness list first; before his review, the intake inventory."""
    items = [str(m.get("item")) for m in missing_items(ws)]
    return items or list((ws.get("documents_summary") or {}).get("missing") or [])


def document_board(ws: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The DOCUMENTS section as Ashley reads it (mirrors ashley.ts `documentBoard`): received docs ✓/⚠ per group,
    missing items inside their group, insurance/title "Waiting" on a website file until something arrives."""
    groups: Dict[str, Dict[str, Any]] = {}

    def group(category: str) -> Dict[str, Any]:
        return groups.setdefault(category, {"category": category, "label": _DOC_CATEGORY_LABEL.get(category, "Other"), "documents": [], "missing": [], "waiting": False})

    for d in ws.get("document_refs") or []:
        status = d.get("status") or "received"
        group(d.get("category") or "other")["documents"].append({"name": d.get("display_name"), "status": status, "attention": status in _DOC_ATTENTION, "note": d.get("note") or ""})
    for item in missing_documents(ws):
        group(missing_category(item))["missing"].append(item)
    if ws.get("submission"):
        for category in _WAITING_CATEGORIES:
            if category not in groups:
                group(category)["waiting"] = True
    order = _DOC_CATEGORY_ORDER + [c for c in groups if c not in _DOC_CATEGORY_ORDER]
    return [groups[c] for c in order if c in groups]


def _docs(n: int) -> str:
    return f"{n} document{'s' if n != 1 else ''}"


def new_loan_line(name: str, documents: int) -> str:
    """Flo's line when a website submission lands (owner wording, 2026-09-09):
    "New loan came in — Johnson.\n\n12 documents came with it.\n\nMalcolm is reviewing everything now. 💚"
    """
    middle = f"{_docs(documents)} came with it." if documents else "No documents came with it."
    return f"New loan came in — {name}.\n\n{middle}\n\nMalcolm is reviewing everything now. 💚"


def review_line(ws: Dict[str, Any]) -> Optional[str]:
    """What Flo says when Malcolm's review of a website submission lands — exactly this shape, nothing more:
    "Johnson is reviewed.\n\n12 documents received.\n\nWe're missing 2 items.\n\nBiggest blocker:\nMost recent paystub.\n\nBest next move:\nRequest the missing docs."
    """
    if not ws.get("submission") or not ws.get("readiness"):
        return None
    docs = int((ws.get("documents_summary") or {}).get("received") or 0)
    missing = missing_items(ws)
    blocker = risk_line(ws) or (short(missing[0].get("item"), 80) if missing else None)
    move = best_next_move(ws)
    if move == "Request the missing documents.":
        move = "Request the missing docs."
    n = len(missing)
    parts = [f"{_name(ws)} is reviewed.", f"{_docs(docs)} received.", "We're not missing anything." if n == 0 else f"We're missing {n} item{'s' if n != 1 else ''}."]
    if blocker:
        parts.append(f"Biggest blocker:\n{blocker.rstrip('.')}.")
    parts.append(f"Best next move:\n{move}")
    return "\n\n".join(parts)


def file_summary(ws: Dict[str, Any], approvals: Iterable[Dict[str, Any]] = (), tasks: Iterable[Dict[str, Any]] = ()) -> Dict[str, Any]:
    """The one clean summary Ashley sees for a file. Never says a loan, income or condition is approved."""
    approvals, tasks = list(approvals), list(tasks)
    r = ws.get("readiness") or {}
    ia = r.get("income_assets") or {}
    open_conditions = [c for c in ws.get("conditions") or [] if (c.get("state") if isinstance(c, dict) else "open") != "cleared"]
    return {
        "workspace_id": ws.get("workspace_id"), "name": _name(ws), "status": plain_status(ws, approvals, tasks), "milestone": ws.get("milestone") or "Intake",
        "readiness": readiness_label(ws), "aus": _aus(ws), "income": _prep(ia.get("income_prep_complete")), "assets": _prep(ia.get("assets_prep_complete")),
        "orders": orders_label(ws), "conditions": "None open" if not open_conditions else f"{len(open_conditions)} open",
        "missing": [{"item": m.get("item"), "owner": m.get("owner")} for m in missing_items(ws)],
        "best_next_move": best_next_move(ws), "risk": risk_line(ws),
        "documents": ws.get("documents_summary") or None,
        "document_board": document_board(ws) if ws.get("document_refs") or ws.get("submission") else [],
        "team_hints": ["Whisper has a draft ready for you."] if drafts_for_review(ws) else [],
        "is_underwriting_decision": False,
        "say_it_like": _say_file(ws, approvals, tasks),
        "review_line": review_line(ws),
    }


def _say_file(ws: Dict[str, Any], approvals, tasks) -> str:
    """One paragraph Flo can say almost verbatim."""
    r = ws.get("readiness") or {}
    ia = r.get("income_assets") or {}
    missing = missing_items(ws)
    parts = [f"{_name(ws)} — {readiness_label(ws).lower()} ({plain_status(ws, approvals, tasks).lower()}, {ws.get('milestone') or 'Intake'})."]
    parts.append(f"AUS: {_aus(ws)}. Income: {_prep(ia.get('income_prep_complete')).lower()}. Assets: {_prep(ia.get('assets_prep_complete')).lower()}.")
    if missing:
        parts.append("We're missing: " + "; ".join(f"{short(m.get('item'), 80)}" + (f" ({m.get('owner')})" if m.get("owner") else "") for m in missing[:4]) + ".")
    orders = orders_label(ws)
    if orders != "Nothing ordered yet":
        parts.append(f"Orders: {orders}.")
    risk = risk_line(ws)
    if risk:
        parts.append(f"Risk: {risk}.")
    if drafts_for_review(ws):
        parts.append("Whisper has the request drafted; you just need to give it the green light.")
    parts.append(f"Best next move: {best_next_move(ws)}")
    return " ".join(parts)


# ── Today ────────────────────────────────────────────────────────────────────


def _score(status: str, ws: Dict[str, Any]) -> int:
    r = ws.get("readiness") or {}
    return _PRIORITY[status] + (15 if r.get("missing_count") == 1 else 0) + (10 if ws.get("milestone") == "Clear to Close" else 0) + (5 if ws.get("next_action") else 0)


def _ts(value: Any) -> float:
    try:
        return datetime.fromisoformat(str(value)).timestamp() if value else 0.0
    except ValueError:
        return 0.0


def approval_what(card: Dict[str, Any]) -> str:
    key = str(card.get("action_type") or "")
    if key in _CAPABILITY:
        if key == "email_send" and str((card.get("payload_preview") or {}).get("audience") or "") == "borrower":
            return "Send borrower email"
        return _CAPABILITY[key]
    if "order" in key:
        return "Place an order"
    if any(w in key for w in ("publish", "post", "newsletter", "social", "gbp")):
        return "Publish a post"
    return key.replace("_", " ").capitalize() or "Take an action"


def team_hints(activity: Iterable[Dict[str, Any]], workspaces: Iterable[Dict[str, Any]], limit: int = 5) -> List[str]:
    """Small contextual hints ("Malcolm checked the file.") — never a raw event feed."""
    names = {w.get("workspace_id"): _name(w) for w in workspaces}
    out: List[str] = []
    for row in sorted(activity or [], key=lambda a: str(a.get("timestamp") or ""), reverse=True):
        file = names.get(row.get("workspace_id"), "a file")
        event = row.get("event")
        line = None
        if event == "readiness.updated":
            line = f"Malcolm checked the {file} file."
        elif event == "draft.added":
            line = f"Whisper drafted a message for {file}."
        elif event == "order.updated":
            line = f"Chadwick is tracking {ORDER_LABEL.get(str(row.get('order_type')), 'an order').lower()} on {file}."
        elif event == "handoff.created":
            line = {"sage": f"Sage is checking a guideline on {file}.", "malcolm": f"Malcolm is reviewing {file}.",
                    "whisper": f"Whisper is drafting for {file}.", "chadwick": f"Chadwick is on the orders for {file}."}.get(str(row.get("to")))
        elif event == "handoff.completed" and row.get("actor") == "sage":
            line = f"Sage verified the guideline on {file}."
        elif event == "approval.proposed":
            line = f"Something on {file} is ready for your okay."
        if line and line not in out:
            out.append(line)
        if len(out) >= limit:
            break
    return out


def greeting(now: Optional[datetime] = None) -> str:
    hour = (now or datetime.now()).hour
    return "Morning Ash ☕" if hour < 12 else ("Afternoon Ash" if hour < 17 else "Evening Ash")


def build(workspaces: List[Dict[str, Any]], approvals: List[Dict[str, Any]], tasks: List[Dict[str, Any]], activity: List[Dict[str, Any]],
          now: Optional[datetime] = None) -> Dict[str, Any]:
    workspaces, approvals, tasks, activity = list(workspaces), list(approvals), list(tasks), list(activity)
    pending = _pending_cards(approvals, None, now)
    rows = [(plain_status(w, approvals, tasks, now), w) for w in workspaces]
    ranked = sorted([r for r in rows if r[0] != "Done"], key=lambda r: (-_score(r[0], r[1]), -_ts(r[1].get("updated_at"))))
    top = [{"workspace_id": w.get("workspace_id"), "name": _name(w), "status": st,
            "line": (risk_line(w) or best_next_move(w)) if st in ("Blocked", "At Risk") else best_next_move(w)} for st, w in ranked[:3]]
    names = {w.get("workspace_id"): _name(w) for w in workspaces}
    fastest = None
    if pending:
        c = pending[0]
        target = f" for {names.get(c.get('workspace_id'), c.get('workspace_id'))}" if c.get("workspace_id") else ""
        fastest = {"line": f"Approve: {approval_what(c)}{target}.", "workspace_id": c.get("workspace_id"), "proposal_id": c.get("proposal_id")}
    else:
        for st, w in rows:
            if st != "Done" and (w.get("readiness") or {}).get("missing_count") == 1:
                item = short((missing_items(w) or [{}])[0].get("item"), 80) or "see the file"
                fastest = {"line": f"{_name(w)}: one item left — {item}.", "workspace_id": w.get("workspace_id")}
                break
    risky = next((r for r in ranked if r[0] in ("Blocked", "At Risk")), None)
    biggest = {"line": f"{_name(risky[1])}: {risk_line(risky[1]) or 'needs a look'}.", "workspace_id": risky[1].get("workspace_id")} if risky else None
    needs_you = len(pending) + sum(len(drafts_for_review(w)) for w in workspaces)
    waiting = sum(len(open_orders(w)) + len([m for m in missing_items(w) if str(m.get("owner") or "").lower() in _OTHERS]) for w in workspaces)
    new_loans = [c for c in (new_loan_card(w) for w in workspaces) if c]
    return {
        "greeting": greeting(now), "new_loans": new_loans, "top": top, "fastest_win": fastest, "biggest_risk": biggest, "needs_you": needs_you, "waiting_on_others": waiting,
        "handling": team_hints(activity, workspaces), "everything_else": "Everything else can wait.", "generated_at": now_iso(),
        "say_it_like": _say_today(top, fastest, biggest, needs_you, waiting, now, new_loans),
    }


def _say_today(top, fastest, biggest, needs_you, waiting, now, new_loans=()) -> str:
    lines = [greeting(now)]
    for c in new_loans:
        lines.append(new_loan_line(c["name"], int(c.get("documents_received") or 0)))
    if not top:
        lines.append("No open files need you right now.")
    else:
        lines.append(f"Best next move: {top[0]['name']} — {top[0]['line']}")
        for i, t in enumerate(top[1:], start=2):
            lines.append(f"{i}. {t['name']} — {t['line']}")
    if fastest:
        lines.append(f"Fastest win: {fastest['line']}")
    lines.append(f"Biggest risk: {biggest['line']}" if biggest else "Biggest risk: none. 💚")
    lines.append(f"Needs you: {needs_you}. Waiting on others: {waiting}. Everything else can wait.")
    return "\n".join(lines)


def from_root(root, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Today from the team root on disk (what `flo_team action=today` and the morning routine use)."""
    from pathlib import Path

    root = Path(root)
    return build(list(JsonDocStore(root / "workspaces").all()), list(JsonDocStore(root / "approvals").all()),
                 list(JsonDocStore(root / "tasks").all()), JsonlLog(root / "activity", "activity").tail(200), now)
