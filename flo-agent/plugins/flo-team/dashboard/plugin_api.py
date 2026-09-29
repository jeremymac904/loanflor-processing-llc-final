"""Thin deterministic action door for Ashley's Flo desktop plugin.

The desktop buttons already represent a concrete user intent.  This router
calls the existing Flo Team handlers directly so a small local model does not
have to select a specialist or reconstruct tool arguments.  It deliberately
does not add business logic or a second state store.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

# Lifecycle plugins are loaded under Hermes' isolated import namespace.  Reuse
# that already-loaded module so the dashboard API and model tools share the same
# role/state implementation.
from hermes_plugins.flo_team import tools
from hermes_plugins.flo_team.workspace import WorkspaceStore

router = APIRouter()


def _payload(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Flo action returned invalid data") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=500, detail="Flo action returned an invalid result")
    if value.get("error"):
        raise HTTPException(status_code=400, detail=str(value["error"]))
    return value


def _workspace(workspace_id: str) -> dict[str, Any]:
    if not workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id is required")
    try:
        return WorkspaceStore(tools._root()).get(workspace_id)
    except Exception as exc:  # noqa: BLE001 - convert handler boundary errors to HTTP
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _effective_program(ws: dict[str, Any]) -> str:
    """Translate the workspace product label to a supported specialist slice."""
    program = str(ws.get("program") or "fannie").strip().lower()
    # The intake UI uses "conventional" as the borrower-facing product label;
    # the existing deterministic guideline/file-prep handlers use the Fannie
    # or Freddie rule slices.  A conventional test file without an agency
    # binding uses the Fannie slice, rather than failing before Malcolm/Sage
    # can run.
    if program == "conventional":
        return "fannie"
    return program


def _missing_items(ws: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    readiness = ws.get("readiness") or {}
    for item in readiness.get("checklist") or []:
        state = str(item.get("state") or "").lower()
        if state in {"missing", "unknown", "needs_review", "source_gap"}:
            label = str(item.get("item") or item.get("label") or "document").strip()
            if label and label not in rows:
                rows.append(label)
    for item in (readiness.get("missing") or []) + (readiness.get("unknown") or []):
        label = str(item.get("item") or item.get("label") or "document").strip() if isinstance(item, dict) else str(item).strip()
        if label and label not in rows:
            rows.append(label)
    for label in (ws.get("documents_summary") or {}).get("missing") or []:
        label = str(label).strip()
        if label and label not in rows:
            rows.append(label)
    return rows


def _specialist_documents(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapt persisted document records to the existing specialist envelope."""
    mapped: list[dict[str, Any]] = []
    for record in records:
        doc = dict(record)
        category = str(doc.get("category") or "").lower()
        subtype = str(doc.get("subcategory") or "").lower()
        if not doc.get("type"):
            doc["type"] = subtype or category
        if category == "aus_findings":
            doc["type"] = "aus_findings"
        if category == "income" and subtype:
            doc["type"] = subtype
        if category == "assets" and subtype:
            doc["type"] = subtype
        doc.setdefault("ref", f"doc://{doc.get('document_id')}")
        mapped.append(doc)
    return mapped


def _prep(args: dict[str, Any]) -> dict[str, Any]:
    wid = str(args.get("workspace_id") or "")
    ws = _workspace(wid)
    from hermes_plugins.flo_team.documents import DocumentStore

    docs = _specialist_documents(DocumentStore(tools._root()).list(wid))
    result = _payload(
        tools.handle_flo_fileprep(
            {
                "workspace_id": wid,
                "documents": docs,
                "program": args.get("program") or _effective_program(ws),
                "underwriting_method": args.get("underwriting_method"),
                "transaction_type": ws.get("transaction_type") or "purchase",
                "store_readiness": True,
            }
        )
    )
    readiness = result.get("readiness") or {}
    checklist = list(readiness.get("checklist") or [])
    missing = [str(row.get("item") or row.get("label")) for row in checklist if str(row.get("state") or "").lower() in {"missing", "unknown", "needs_review", "source_gap"}]
    for row in list(readiness.get("missing") or []) + list(readiness.get("unknown") or []):
        label = str(row.get("item") or row.get("label")) if isinstance(row, dict) else str(row)
        if label and label != "None" and label not in missing:
            missing.append(label)
    return {
        "action": "prep",
        "message": "Malcolm checked this file and saved the File Readiness report.",
        "readiness": readiness.get("status") or readiness.get("readiness") or "Needs review",
        "missing_items": [item for item in missing if item and item != "None"],
        "aus": (result.get("aus_review") or {}).get("status") or (result.get("aus_review") or {}).get("result") or "Needs review",
        "income": (result.get("income_review") or {}).get("status") or "Needs review",
        "assets": (result.get("asset_review") or {}).get("status") or "Needs review",
        "discrepancies": list(readiness.get("discrepancies") or []),
        "best_next_move": readiness.get("best_next_move")
        or (readiness.get("ashley_output") or {}).get("best_next_move")
        or "Review the missing items and any discrepancies before submission.",
    }


def _why(args: dict[str, Any]) -> dict[str, Any]:
    wid = str(args.get("workspace_id") or "")
    ws = _workspace(wid)
    topic = str(args.get("subject") or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="subject is required")
    program = _effective_program(ws)
    conditions = [str(row.get("plain_english") or row.get("text") or "") for row in ws.get("conditions") or []]
    card = _payload(
        tools.handle_flo_guideline_card(
            {
                "program": program,
                "topic": topic,
                "workspace_id": wid,
                "file_conditions": [item for item in conditions if item],
                "aus_findings": [],
            }
        )
    )
    rendered = _payload(
        tools.handle_flo_sage_response(
            {
                "action": "build",
                "workspace_id": wid,
                "program": program,
                "cards": [card],
                "file_conditions": [item for item in conditions if item],
            }
        )
    )
    source_refs = card.get("source_refs") or rendered.get("source_refs") or []
    return {
        "action": "why",
        "message": str(rendered.get("rendered") or card.get("conclusion") or card.get("answer") or "SOURCE_GAP: no supported source was found."),
        "program": program,
        "sources": source_refs,
        "section": card.get("section") or card.get("section_ref") or card.get("source_section"),
        "source_gap": bool(card.get("source_gap") or rendered.get("source_gaps")),
    }


def _order(args: dict[str, Any]) -> dict[str, Any]:
    wid = str(args.get("workspace_id") or "")
    ws = _workspace(wid)
    order_type = str(args.get("order_type") or "").lower()
    if order_type not in {"title", "hoi", "wvoe"}:
        raise HTTPException(status_code=400, detail="unsupported order type")
    result = _payload(
        tools.handle_flo_order(
            {
                "action": "propose",
                "workspace_id": wid,
                "order_type": order_type,
                "inputs": {"topic": order_type, "property_ref": ws.get("property_ref") or "synthetic-test"},
                "purpose": f"Order {order_type.upper()} for {ws.get('display_name') or wid}",
                "urgency": "normal",
                "source_ref": "flo-desktop-action",
            }
        )
    )
    return {"action": "order", "message": f"{order_type.upper()} proposal created and is waiting for approval.", "order": result}


def _request_missing(args: dict[str, Any]) -> dict[str, Any]:
    wid = str(args.get("workspace_id") or "")
    ws = _workspace(wid)
    items = _missing_items(ws)
    if not items:
        items = ["the remaining file items"]
    body = "Please send the following items for this file:\n" + "\n".join(f"- {item}" for item in items)
    result = _payload(
        tools.handle_flo_draft(
            {
                "action": "create",
                "workspace_id": wid,
                "audience": "borrower",
                "purpose": "Request missing documents",
                "body": body,
                "needed": "; ".join(items),
                "urgency": "needs attention today",
                "channel": "email",
            }
        )
    )
    return {"action": "request-missing", "message": "Whisper created one grouped missing-document draft for approval.", "draft": result}


def _esign_prepare(args: dict[str, Any]) -> dict[str, Any]:
    wid = str(args.get("workspace_id") or "")
    result = _payload(
        tools.handle_flo_esign(
            {
                "action": "prepare",
                "workspace_id": wid,
                "document_id": str(args.get("document_id") or ""),
                "template_key": str(args.get("template_key") or "loe"),
                "recipients": list(args.get("recipients") or []),
                "message": str(args.get("message") or ""),
            }
        )
    )
    return {"action": "esign-prepare", "message": "The local signature request is prepared for approval.", "request": result}


def _upload_documents(args: dict[str, Any]) -> dict[str, Any]:
    wid = str(args.get("workspace_id") or "")
    _workspace(wid)
    paths = args.get("paths")
    if not isinstance(paths, list) or not paths:
        raise HTTPException(status_code=400, detail="At least one local document path is required")

    from pathlib import Path
    from hermes_plugins.flo_team import documents as documents_mod

    results: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(str(raw_path))
        if not path.is_file():
            raise HTTPException(status_code=400, detail="A selected document is no longer available")
        if path.suffix.lower() not in {".pdf", ".jpg", ".jpeg", ".png"}:
            raise HTTPException(status_code=400, detail="Only PDF and image documents can be added")
        extracted = documents_mod.extract_text(path)
        classification = documents_mod.classify(path.name, extracted.get("text") or "", None, None)
        record = _payload(
            tools.handle_flo_documents(
                {
                    "action": "add",
                    "workspace_id": wid,
                    "path": str(path),
                    "category": classification.get("category") or "other",
                    "subcategory": classification.get("subcategory"),
                }
            )
        )
        results.append(record)

    added = sum(1 for record in results if record.get("status") != "duplicate")
    duplicates = len(results) - added
    prep = _prep({"workspace_id": wid}) if added else None
    summary = f"Added {added} document{'s' if added != 1 else ''} to this file."
    if duplicates:
        summary += f" Skipped {duplicates} duplicate{'s' if duplicates != 1 else ''}."
    if prep:
        summary += " Malcolm refreshed file readiness."
    return {"action": "upload-documents", "message": summary, "documents": results, "prep": prep}


@router.post("/actions/{action}")
async def run_action(action: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    args = dict(body or {})
    try:
        if action == "prep":
            return _prep(args)
        if action == "why":
            return _why(args)
        if action == "order":
            return _order(args)
        if action == "request-missing":
            return _request_missing(args)
        if action == "esign-prepare":
            return _esign_prepare(args)
        if action == "upload-documents":
            return _upload_documents(args)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - keep the desktop action boundary visible
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=404, detail=f"unknown Flo action: {action}")
