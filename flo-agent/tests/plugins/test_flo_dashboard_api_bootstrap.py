"""The Flo dashboard API must load before the profile plugin manager does."""

from __future__ import annotations

import importlib.util
import asyncio
import sys
from pathlib import Path

import pytest

def test_flo_api_import_bootstraps_lifecycle_namespace(monkeypatch):
    plugin_root = Path(__file__).resolve().parents[2] / "plugins" / "flo-team"
    api_file = plugin_root / "dashboard" / "plugin_api.py"

    # A fresh Hermes profile web server imports dashboard APIs before loading
    # lifecycle plugins. Recreate that ordering even if another test imported
    # the team plugin earlier in this process.
    for name in [name for name in sys.modules if name == "hermes_plugins" or name.startswith("hermes_plugins.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)

    module_name = "hermes_dashboard_plugin_flo_bootstrap_test"
    spec = importlib.util.spec_from_file_location(module_name, api_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)

    assert any(route.path == "/intake/local" and "POST" in route.methods for route in module.router.routes)
    assert any(route.path == "/intake/bind-session" and "POST" in route.methods for route in module.router.routes)
    assert any(route.path == "/context/turn" and "POST" in route.methods for route in module.router.routes)
    assert any(route.path == "/actions/{action}" and "POST" in route.methods for route in module.router.routes)
    assert "hermes_plugins.flo_team" in sys.modules


def test_file_detail_action_updates_only_owner_editable_summary_fields(monkeypatch, tmp_path):
    plugin_root = Path(__file__).resolve().parents[2] / "plugins" / "flo-team"
    api_file = plugin_root / "dashboard" / "plugin_api.py"
    module_name = "hermes_dashboard_plugin_flo_summary_test"
    spec = importlib.util.spec_from_file_location(module_name, api_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    team_root = tmp_path / "team"
    workspace = module.WorkspaceStore(team_root).create(display_name="River")
    monkeypatch.setattr(module.tools, "_root", lambda: team_root)

    result = asyncio.run(module.run_action("file-details", {
        "workspace_id": workspace["workspace_id"],
        "account_executive": "Jordan Lee",
        "closing_date": "2026-10-28",
    }))

    saved = module.WorkspaceStore(team_root).get(workspace["workspace_id"])
    assert result["action"] == "file-details"
    assert saved["account_executive"] == "Jordan Lee"
    assert saved["closing_date"] == "2026-10-28"
    assert saved["milestone"] == "Intake"
    with pytest.raises(Exception) as invalid_date:
        asyncio.run(module.run_action("file-details", {
            "workspace_id": workspace["workspace_id"], "closing_date": "not-a-date"
        }))
    assert invalid_date.value.status_code == 400


def test_customer_file_contacts_save_resolve_and_ambiguity(monkeypatch, tmp_path):
    plugin_root = Path(__file__).resolve().parents[2] / "plugins" / "flo-team"
    api_file = plugin_root / "dashboard" / "plugin_api.py"
    module_name = "hermes_dashboard_plugin_flo_contacts_test"
    spec = importlib.util.spec_from_file_location(module_name, api_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    team_root = tmp_path / "team"
    workspace = module.WorkspaceStore(team_root).create(display_name="River")
    monkeypatch.setattr(module.tools, "_root", lambda: team_root)
    wid = workspace["workspace_id"]

    saved = asyncio.run(module.run_action("contacts-save", {
        "workspace_id": wid,
        "contacts": [
            {"contact_id": "lo-1", "role": "loan_officer", "name": "Jordan Lee", "email": "jordan@example.test"},
            {"contact_id": "lo-2", "role": "loan_officer", "name": "Morgan Ray", "email": "morgan@example.test"},
        ],
    }))
    assert len(saved["contacts"]) == 2
    assert len(module.WorkspaceStore(team_root).get(wid)["contacts"]) == 2

    resolved = asyncio.run(module.run_action("contacts-resolve", {"workspace_id": wid, "role": "LO", "contact_id": "lo-2"}))
    assert resolved["status"] == "resolved"
    assert resolved["contact"]["email"] == "morgan@example.test"
    ambiguous = asyncio.run(module.run_action("contacts-resolve", {"workspace_id": wid, "role": "loan_officer"}))
    assert ambiguous["status"] == "ambiguous"


def test_legacy_mismo_workspace_contacts_are_seeded_on_read(monkeypatch, tmp_path):
    plugin_root = Path(__file__).resolve().parents[2] / "plugins" / "flo-team"
    api_file = plugin_root / "dashboard" / "plugin_api.py"
    module_name = "hermes_dashboard_plugin_flo_contacts_seed_test"
    spec = importlib.util.spec_from_file_location(module_name, api_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    team_root = tmp_path / "team"
    workspace = module.WorkspaceStore(team_root).create(display_name="River")
    module.WorkspaceStore(team_root).docs.update(workspace["workspace_id"], lambda doc: doc.update({
        "mismo": {
            "source_file": "synthetic.xml",
            "borrowers": [{"borrower_id": "b1", "role": "borrower", "values": {"full_name": "Avery River", "email": "avery@example.test"}}],
        }
    }))
    monkeypatch.setattr(module.tools, "_root", lambda: team_root)

    first = asyncio.run(module.run_action("contacts-get", {"workspace_id": workspace["workspace_id"]}))
    second = asyncio.run(module.run_action("contacts-get", {"workspace_id": workspace["workspace_id"]}))
    assert first["seeded"] is True
    assert first["contacts"][0]["name"] == "Avery River"
    assert second["seeded"] is False
    assert len(module.WorkspaceStore(team_root).get(workspace["workspace_id"])["contacts"]) == 1


def test_turn_context_endpoint_returns_active_file_from_local_workspace(monkeypatch, tmp_path):
    plugin_root = Path(__file__).resolve().parents[2] / "plugins" / "flo-team"
    api_file = plugin_root / "dashboard" / "plugin_api.py"
    module_name = "hermes_dashboard_plugin_flo_turn_context_test"
    spec = importlib.util.spec_from_file_location(module_name, api_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    team_root = tmp_path / "team"
    workspace = module.WorkspaceStore(team_root).create(display_name="Avery River", workspace_id="loan-avery")
    module.WorkspaceStore(team_root).docs.update(workspace["workspace_id"], lambda doc: doc.update({
        "mismo": {"borrowers": [{"role": "borrower", "values": {"full_name": "Avery River", "phone": "555-0102"}}]}
    }))
    monkeypatch.setattr(module.tools, "_root", lambda: team_root)

    result = asyncio.run(module.customer_file_turn_context({
        "session_id": "session-avery", "active_workspace_id": "loan-avery", "query": "What is Avery's phone number?"
    }))

    assert result["status"] == "resolved"
    assert result["workspace_id"] == "loan-avery"
    assert result["bound"] is True
    assert '"phone":"555-0102"' in result["context"]
