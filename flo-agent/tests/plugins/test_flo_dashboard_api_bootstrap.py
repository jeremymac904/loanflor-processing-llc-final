"""The Flo dashboard API must load before the profile plugin manager does."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


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
    assert "hermes_plugins.flo_team" in sys.modules
