"""Local folder / MISMO 3.4 intake into the existing Flo Loan Workspace store."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from . import documents
from . import contacts as contacts_mod
from .mismo import parse_file
from .store import now_iso
from .workspace import WorkspaceStore

SUPPORTED = {".xml", ".pdf", ".jpg", ".jpeg", ".png"}
MAX_FILES = 500
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_TOTAL_BYTES = 500 * 1024 * 1024
MAX_DEPTH = 20


class LocalIntakeError(ValueError):
    pass


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _walk(folder: Path) -> tuple[list[Path], list[str]]:
    if not folder.is_dir():
        raise LocalIntakeError("Choose a folder that is available on this PC.")
    files: list[Path] = []
    unsupported: list[str] = []
    total_bytes = 0
    for current, dirs, names in os.walk(folder, followlinks=False):
        base = Path(current)
        depth = len(base.relative_to(folder).parts)
        dirs[:] = [name for name in dirs if not name.startswith((".", "~$")) and not (base / name).is_symlink()]
        if depth >= MAX_DEPTH:
            dirs.clear()
        for name in names:
            path = base / name
            if name.startswith((".", "~$")) or path.is_symlink() or not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in SUPPORTED:
                if len(unsupported) < 20:
                    unsupported.append(path.name)
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_FILE_BYTES:
                unsupported.append(f"{path.name} (over size limit)")
                continue
            total_bytes += size
            if total_bytes > MAX_TOTAL_BYTES:
                raise LocalIntakeError("This folder exceeds the 500 MiB safe intake limit.")
            files.append(path)
            if len(files) > MAX_FILES:
                raise LocalIntakeError("This folder contains more than 500 supported files.")
    return files, unsupported


def _norm(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _borrower_key(parsed: dict[str, Any]) -> str:
    borrowers = parsed.get("borrowers") or []
    vals = next((row.get("values") or {} for row in borrowers if (row.get("values") or {}).get("full_name")), {})
    return _norm(vals.get("full_name"))


def _property_key(parsed: dict[str, Any]) -> str:
    row = next((p.get("values") or {} for p in parsed.get("properties") or [] if p.get("kind") == "subject"), {})
    return _norm(" ".join(str(row.get(k) or "") for k in ("street", "city", "state", "postal_code")))


def _borrower_display_name(parsed: dict[str, Any]) -> str | None:
    for row in parsed.get("borrowers") or []:
        values = row.get("values") or {}
        name = values.get("full_name") or " ".join(
            str(values.get(key) or "").strip() for key in ("first_name", "middle_name", "last_name", "suffix")
        ).strip()
        if name:
            return " ".join(str(name).split())
    return None


def _usable_display_name(value: Any) -> bool:
    name = " ".join(str(value or "").split())
    if not name or any(separator in name for separator in ("/", "\\")) or name.lower().endswith((".xml", ".mismo")):
        return False
    return name.casefold() not in {"downloads", "download", "desktop", "documents", "new loan", "loan file"}


def _persist_parsed_metadata(store: WorkspaceStore, workspace_id: str, parsed: dict[str, Any]) -> dict[str, Any]:
    loan = parsed.get("loan") or {}
    borrower_name = _borrower_display_name(parsed)
    display_name = borrower_name or parsed.get("display_name")
    program_value = str(loan.get("loan_program") or loan.get("loan_type") or "conventional").lower()
    program = next((candidate for candidate in ("fha", "va", "usda", "conventional") if candidate in program_value), "conventional")
    agency = "fannie" if program == "conventional" else None
    loan_officers = parsed.get("loan_officers") or []
    loan_officer = (loan_officers[0].get("values") or {}) if loan_officers else {}
    companies = parsed.get("origination_companies") or []
    lenders = parsed.get("lenders") or []
    executives = parsed.get("account_executives") or []
    company_values = (companies[0].get("values") or {}) if companies else {}
    lender_values = (lenders[0].get("values") or {}) if lenders else {}
    executive_values = (executives[0].get("values") or {}) if executives else {}
    subject = next((item.get("values") for item in parsed.get("properties") or [] if item.get("kind") == "subject"), None)
    source_ref = None
    if parsed.get("source_sha256"):
        source_ref = {
            "ref": f"mismo://{parsed['source_sha256']}", "kind": "mismo_3_4",
            "filename": parsed.get("source_file"), "sha256": parsed["source_sha256"],
            "imported_at": parsed.get("source_imported_at"),
        }

    def update(doc: dict[str, Any]) -> None:
        doc["mismo"] = parsed
        doc["contacts"] = contacts_mod.merge_imported(
            doc.get("contacts") or [], contacts_mod.from_mismo(parsed)
        )
        doc["borrowers"] = parsed.get("borrowers") or []
        if subject is not None:
            doc["property"] = subject
        doc["loan_terms"] = loan
        if loan.get("lender_loan_id"):
            doc["loan_number"] = loan["lender_loan_id"]
        if loan_officer:
            doc["loan_officer"] = loan_officer
        company_name = company_values.get("company") or company_values.get("full_name")
        if company_name:
            doc["origination_company"] = company_name
        lender_name = lender_values.get("company") or lender_values.get("full_name")
        if lender_name:
            doc["lender"] = lender_name
        executive_name = executive_values.get("full_name")
        if executive_name:
            doc["account_executive"] = executive_name
        if loan.get("closing_date"):
            doc["closing_date"] = loan["closing_date"]
        if display_name:
            doc["display_name"] = display_name
        elif not _usable_display_name(doc.get("display_name")):
            doc["display_name"] = str(loan.get("lender_loan_id") or "New Loan")
        doc["program"] = program
        doc["agency"] = agency
        doc["milestone"] = doc.get("milestone") or "Intake"
        doc["status_summary"] = doc.get("status_summary") or "MISMO 3.4 received locally."
        if not doc.get("next_action"):
            doc["next_action"] = "Review the imported application and supporting documents."
        if source_ref:
            doc["source_refs"] = _upsert_source(doc.get("source_refs") or [], source_ref)
        doc["mismo_summary_refreshed_at"] = now_iso()

    store.docs.update(workspace_id, update)
    return store.get(workspace_id)


def refresh_existing_workspace_metadata(team_root: Path, workspace_id: str) -> dict[str, Any]:
    """Refresh saved summary fields from an already-imported local MISMO XML.

    This is a metadata migration only: it does not import documents, create a
    workspace, or rerun Malcolm.
    """
    store = WorkspaceStore(Path(team_root))
    workspace = store.get(workspace_id)
    if workspace.get("mismo_summary_refreshed_at"):
        return {"workspace_id": workspace_id, "updated": False}
    source = next((
        row.get("local_path") for row in documents.DocumentStore(Path(team_root)).list(workspace_id)
        if str(row.get("original_filename") or "").lower().endswith(".xml") and row.get("local_path")
    ), None)
    if not source or not Path(source).is_file():
        return {"workspace_id": workspace_id, "updated": False, "reason": "source_unavailable"}
    parsed = parse_file(source)
    old_mismo = workspace.get("mismo") or {}
    parsed["source_sha256"] = old_mismo.get("source_sha256") or _hash(Path(source))
    parsed["source_imported_at"] = old_mismo.get("source_imported_at") or now_iso()
    parsed["subject_property_key"] = _property_key(parsed)
    parsed["borrower_key"] = _borrower_key(parsed)
    refreshed = _persist_parsed_metadata(store, workspace_id, parsed)
    store._activity(workspace_id, "flo", "workspace.summary_refreshed", {"source": "mismo_3_4"})
    return {"workspace_id": workspace_id, "updated": True, "display_name": refreshed.get("display_name")}


def _match_workspace(store: WorkspaceStore, parsed: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    loan_id = _norm((parsed.get("loan") or {}).get("lender_loan_id"))
    borrower = _borrower_key(parsed)
    prop = _property_key(parsed)
    rows = list(store.docs.all())
    exact = [ws for ws in rows if loan_id and _norm(((ws.get("mismo") or {}).get("loan") or {}).get("lender_loan_id") or ws.get("loan_number")) == loan_id]
    if len(exact) == 1:
        return exact[0], []
    if len(exact) > 1:
        return None, [ws["workspace_id"] for ws in exact]
    strong = []
    for ws in rows:
        current = ws.get("mismo") or {}
        existing_property = current.get("subject_property_key")
        if not existing_property and isinstance(ws.get("property"), dict):
            existing_property = " ".join(str(ws["property"].get(k) or "") for k in ("street", "city", "state", "postal_code"))
        existing_borrower = current.get("borrower_key")
        if not existing_borrower:
            borrower_rows = ws.get("borrowers") or []
            existing_borrower = next((row.get("full_name") or row.get("name") for row in borrower_rows if isinstance(row, dict)), "")
        same_property = bool(prop and _norm(existing_property) == prop)
        same_borrower = bool(borrower and _norm(existing_borrower) == borrower)
        if same_property and same_borrower:
            strong.append(ws)
    if len(strong) == 1:
        return strong[0], []
    if len(strong) > 1:
        return None, [ws["workspace_id"] for ws in strong]
    return None, []


def bind_session(team_root: Path, session_id: str, workspace_id: str) -> dict[str, Any]:
    session_id = str(session_id or "").strip()
    if not session_id or len(session_id) > 200:
        raise LocalIntakeError("A chat session is required before this file can be linked to the chat.")
    store = WorkspaceStore(team_root)
    ws = store.get(workspace_id)
    row = {"session_id": session_id, "workspace_id": workspace_id, "bound_at": now_iso()}
    store.docs.update(workspace_id, lambda d: d.__setitem__("chat_sessions", _upsert_session(d.get("chat_sessions") or [], row)))
    from .store import JsonDocStore
    bindings = JsonDocStore(Path(team_root) / "chat_workspace_bindings")
    bindings.put("sessions", {
        "bindings": {**((bindings.get("sessions") or {}).get("bindings") or {}), session_id: workspace_id}
    })
    store._activity(workspace_id, "flo", "chat.bound", {"session_id": session_id})
    return {"session_id": session_id, "workspace_id": workspace_id, "display_name": ws.get("display_name")}


def _upsert_session(rows: list[dict[str, Any]], row: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in rows if item.get("session_id") != row["session_id"]] + [row]


def intake(team_root: Path, source_path: str | Path, *, additional_paths: list[str | Path] | None = None, session_id: str | None = None, actor: str = "flo") -> dict[str, Any]:
    """Parse locally, create/update the existing workspace, preserve source files, and import supported docs."""
    source = Path(source_path).expanduser().resolve(strict=True)
    if source.is_dir():
        files, unsupported = _walk(source)
    elif source.is_file():
        if source.suffix.lower() not in SUPPORTED:
            raise LocalIntakeError("Choose a MISMO XML, PDF, JPG, JPEG, or PNG file.")
        files, unsupported = [source], []
    else:
        raise LocalIntakeError("The selected file or folder is unavailable.")
    for raw_path in additional_paths or []:
        path = Path(raw_path).expanduser().resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        if path not in files:
            files.append(path)
    xml_files = [path for path in files if path.suffix.lower() == ".xml"]
    if not xml_files:
        raise LocalIntakeError("I found documents, but no MISMO 3.4 XML. Identify an existing Customer File before importing a folder without a loan file.")
    if len(xml_files) > 1:
        raise LocalIntakeError("I found more than one MISMO XML in this folder. Choose a folder with one loan file, or select the intended XML directly.")
    xml_path = xml_files[0]
    parsed = parse_file(xml_path)
    source_digest = _hash(xml_path)
    workspace_store = WorkspaceStore(Path(team_root))
    existing, ambiguous = _match_workspace(workspace_store, parsed)
    if ambiguous:
        raise LocalIntakeError("This loan may match more than one Customer File. Choose the correct file in Pipeline before importing.")
    parsed["source_sha256"] = source_digest
    parsed["source_imported_at"] = now_iso()
    parsed["subject_property_key"] = _property_key(parsed)
    parsed["borrower_key"] = _borrower_key(parsed)
    duplicate_source = next((ws for ws in workspace_store.docs.all() if (ws.get("mismo") or {}).get("source_sha256") == source_digest), None)
    if duplicate_source and (existing is None or duplicate_source["workspace_id"] == existing["workspace_id"]):
        workspace = duplicate_source
        created = False
    else:
        loan = parsed.get("loan") or {}
        program_value = str(loan.get("loan_program") or loan.get("loan_type") or "conventional").lower()
        program = next((candidate for candidate in ("fha", "va", "usda", "conventional") if candidate in program_value), "conventional")
        agency = "fannie" if program == "conventional" else None
        display_name = _borrower_display_name(parsed) or parsed.get("display_name") or loan.get("lender_loan_id") or "New Loan"
        if existing:
            wid = existing["workspace_id"]
            workspace_store.docs.update(wid, lambda d: d.update({"program": program, "agency": agency, "milestone": d.get("milestone") or "Intake"}))
            workspace = workspace_store.get(wid)
            created = False
        else:
            workspace = workspace_store.create(display_name=display_name, program=program, agency=agency, milestone="Intake", actor=actor)
            created = True
        wid = workspace["workspace_id"]
        if not duplicate_source:
            workspace_store._activity(wid, actor, "client_folder.imported", {"file_count": len(files), "mismo_sha256": source_digest})
    wid = workspace["workspace_id"]
    _persist_parsed_metadata(workspace_store, wid, parsed)

    existing_docs = documents.DocumentStore(team_root).list(wid)
    existing_hashes = {row.get("sha256") for row in existing_docs if row.get("sha256")}
    imported = []
    for path in files:
        digest = _hash(path)
        if digest in existing_hashes:
            continue
        extracted = documents.extract_text(path)
        classification = documents.classify(path.name, extracted.get("text") or "", None, None)
        category = "loan_application" if path.suffix.lower() == ".xml" else classification.get("category") or "other"
        record = documents.add_local(team_root, wid, str(path), category=category, subcategory=None, by=actor)
        imported.append({"document_id": record.get("document_id"), "filename": record.get("original_filename"), "category": record.get("category"), "status": record.get("status"), "sha256": record.get("sha256")})
        existing_hashes.add(digest)
    if imported:
        workspace_store._activity(wid, actor, "documents.added", {"count": len(imported)})
    if session_id:
        bind_session(Path(team_root), session_id, wid)
    return {
        "workspace_id": wid, "display_name": workspace_store.get(wid).get("display_name"), "created": created,
        "updated": not created, "duplicate_source": bool(duplicate_source), "program": workspace_store.get(wid).get("program"),
        "milestone": workspace_store.get(wid).get("milestone"), "borrower_count": len(parsed.get("borrowers") or []),
        "document_count": len(imported), "documents": imported, "unsupported": unsupported,
        "needs_review": parsed.get("needs_review") or [], "source_sha256": source_digest,
    }


def _upsert_source(rows: list[dict[str, Any]], row: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in rows if item.get("sha256") != row["sha256"]] + [row]
