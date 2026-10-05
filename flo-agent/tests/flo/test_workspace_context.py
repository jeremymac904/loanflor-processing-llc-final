"""Fresh, local Customer File context is resolved before each Flo turn."""

from __future__ import annotations

import importlib
import importlib.util
import hashlib
import json
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "flo-team"
if "flo_team" not in sys.modules:
    spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["flo_team"] = module
    spec.loader.exec_module(module)
for _name in ("store", "workspace", "contacts", "documents", "local_intake", "workspace_context"):
    importlib.import_module(f"flo_team.{_name}")

from flo_team.contacts import save_workspace_contacts
from flo_team.documents import DocumentStore, documents_root
from flo_team.store import JsonDocStore
from flo_team.workspace import WorkspaceStore
from flo_team.workspace_context import resolve_turn_context, resolve_workspace_query


def _workspace(root, *, wid="loan-jason-synthetic", name="Jason Lathrop"):
    store = WorkspaceStore(root)
    row = store.create(display_name=name, workspace_id=wid)
    store.docs.update(wid, lambda doc: doc.update({
        "loan_number": "1000000012345",
        "program": "Conventional",
        "loan_terms": {"total_loan_amount": 185500},
        "property": {"street": "10 Synthetic Way", "city": "Sampletown", "state": "FL", "postal_code": "32000"},
        "milestone": "Processing",
        "readiness": {"status": "Needs attention", "best_next_move": "Review AUS findings"},
        "conditions": [{"condition_id": "condition-1", "plain_english": "Provide current bank statement", "state": "open"}],
        "orders": [],
        "mismo": {
            "source_file": "Jason_3.4.xml",
            "source_sha256": "a" * 64,
            "source_imported_at": "2026-01-02T00:00:00Z",
            "loan": {"lender_loan_id": "1000000012345", "total_loan_amount": 185500},
            "borrowers": [{"role": "borrower", "values": {"full_name": name, "phone": "555-0101"},
                            "provenance": {"full_name": "/MISMO/LOAN/PARTY/FULLNAME", "phone": "/MISMO/LOAN/PARTY/PHONE"}}],
            "properties": [{"kind": "subject", "values": {"street": "10 Synthetic Way", "city": "Sampletown", "state": "FL", "postal_code": "32000"}}],
        },
    }))
    save_workspace_contacts(store, wid, [{"role": "borrower", "name": name, "phone": "555-0101", "email": "jason@example.invalid"}])
    return store


def _add_original_xml(root, wid="loan-jason-synthetic"):
    path = documents_root(root) / wid / "application" / "Jason_3.4.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    original_bytes = b"<synthetic-original/>\n"
    path.write_bytes(original_bytes)
    digest = hashlib.sha256(original_bytes).hexdigest()
    WorkspaceStore(root).docs.update(wid, lambda doc: doc["mismo"].update(source_sha256=digest))
    DocumentStore(root).add(wid, {
        "document_id": "doc-mismo-original", "original_filename": "Jason_3.4.xml",
        "display_name": "Jason_3.4.xml", "category": "loan_application", "status": "received",
        "sha256": digest, "local_path": str(path), "text_path": None, "text_chars": 0,
        "received_at": "2026-01-02T00:00:00Z",
    })


def test_active_file_new_chat_gets_current_structured_context_and_binds(tmp_path):
    root = tmp_path / "flo"
    _workspace(root)
    _add_original_xml(root)

    result = resolve_turn_context(root, session_id="session-new", active_workspace_id="loan-jason-synthetic", query="What is Jason's phone number?")

    assert result["status"] == "resolved"
    assert result["bound"] is True
    assert '"phone":"555-0101"' in result["context"]
    assert '"email":"jason@example.invalid"' in result["context"]
    assert '"document_id":"doc-mismo-original"' in result["context"]
    assert '"preserved_in_customer_file":true' in result["context"]
    assert '"total_loan_amount":185500' in result["context"]
    binding = JsonDocStore(root / "chat_workspace_bindings").get("sessions")
    assert binding["bindings"]["session-new"] == "loan-jason-synthetic"


def test_bound_session_loads_latest_workspace_state_on_every_turn(tmp_path):
    root = tmp_path / "flo"
    store = _workspace(root)
    resolve_turn_context(root, session_id="session-bound", active_workspace_id="loan-jason-synthetic", query="hello")

    store.docs.update("loan-jason-synthetic", lambda doc: doc.update({
        "best_next_move": "Request the updated bank statement",
        "milestone": "Conditional Approval",
    }))
    second = resolve_turn_context(root, session_id="session-bound", active_workspace_id=None, query="What are we missing?")

    assert second["workspace_id"] == "loan-jason-synthetic"
    assert second["bound"] is True
    assert "Request the updated bank statement" in second["context"]
    assert '"milestone":"Conditional Approval"' in second["context"]


def test_unbound_general_chat_resolves_unique_borrower_and_missing_facts_stay_missing(tmp_path):
    root = tmp_path / "flo"
    store = _workspace(root)
    store.docs.update("loan-jason-synthetic", lambda doc: (
        doc["mismo"]["borrowers"][0]["values"].pop("email", None),
        doc["contacts"][0].update(email=None),
    ))

    result = resolve_turn_context(root, session_id="session-general", active_workspace_id=None, query="What's going on with Jason Lathrop?")

    assert result["workspace_id"] == "loan-jason-synthetic"
    assert result["bound"] is True
    assert '"phone":"555-0101"' in result["context"]
    assert '"email":null' in result["context"]
    assert '"values":{"full_name":"Jason Lathrop","phone":"555-0101"}' in result["context"]
    assert "Missing fields are absent, not permission to guess" in result["context"]


def test_ambiguous_borrower_query_does_not_choose_a_customer_file(tmp_path):
    root = tmp_path / "flo"
    store = _workspace(root, wid="loan-alex-one", name="Alex Morgan")
    _workspace(root, wid="loan-alex-two", name="Alex Morgan")

    result = resolve_workspace_query(store.docs.all(), "What is Alex Morgan's phone number?")

    assert result["status"] == "ambiguous"
    assert {item["workspace_id"] for item in result["candidates"]} == {"loan-alex-one", "loan-alex-two"}


def test_existing_mismo_source_is_retrievable_without_reupload_or_reparse(tmp_path):
    root = tmp_path / "flo"
    _workspace(root)
    _add_original_xml(root)

    result = resolve_turn_context(root, session_id="session-source", active_workspace_id="loan-jason-synthetic", query="Check the original Fannie Mae 3.4 and tell me the loan amount")

    assert '"filename":"Jason_3.4.xml"' in result["context"]
    assert '"source_available"' not in result["context"]
    assert '"preserved_in_customer_file":true' in result["context"]
    assert '"total_loan_amount":185500' in result["context"]
    assert "do not ask Ashley to re-upload" in result["context"]
    source = documents_root(root) / "loan-jason-synthetic" / "application" / "Jason_3.4.xml"
    assert source.read_bytes() == b"<synthetic-original/>\n"


def test_document_get_returns_saved_mismo_parse_and_preserved_source_metadata(tmp_path, monkeypatch):
    root = tmp_path / "flo"
    _workspace(root)
    _add_original_xml(root)
    tools = importlib.import_module("flo_team.tools")
    monkeypatch.setattr(tools, "_STATE_ROOT_OVERRIDE", root)
    monkeypatch.setenv("HERMES_PROFILE_NAME", "flo")

    result = json.loads(tools.handle_flo_documents({
        "action": "get", "workspace_id": "loan-jason-synthetic", "document_id": "doc-mismo-original"
    }))

    assert result["source_available"] is True
    assert result["structured_mismo"]["loan"]["total_loan_amount"] == 185500
    assert result["structured_mismo"]["source_file"] == "Jason_3.4.xml"
    assert result["source_sha256"] == DocumentStore(root).get("loan-jason-synthetic", "doc-mismo-original")["sha256"]
