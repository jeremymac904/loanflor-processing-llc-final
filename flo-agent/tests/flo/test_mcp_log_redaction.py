"""MCP URL / token log redaction — synthetic fake token, real Hermes logging.

The test fails if the complete fake secret appears anywhere under the
temporary Hermes home's log directories (agent/gateway/gui logs, desktop log,
profile logs) after logging it through every path the leak was seen on:
the HTTP client logger line, an exception message, a retry/debug line, and a
bare handler that has no redacting formatter.
"""

from __future__ import annotations

import importlib
import importlib.util
import io
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
FAKE = "FAKEZAPIERTOKEN0000111122223333444455556666777788889999AAAABBBB"
URL = f"https://mcp.zapier.com/api/v1/connect?token={FAKE}"


@pytest.fixture(scope="module")
def redaction():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    return importlib.import_module("flo_team.redaction")


def _scan(root: Path) -> list[str]:
    hits = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in {".log", ".txt", ".jsonl", ".out"}:
            try:
                if FAKE in path.read_text(encoding="utf-8", errors="ignore"):
                    hits.append(str(path))
            except OSError:
                pass
    return hits


def test_core_registry_masks_registered_host_only():
    from agent import redact

    redact._reset_credential_url_hosts()
    try:
        assert FAKE in redact.redact_sensitive_text(f"GET {URL} 200")  # upstream default: pass-through
        assert redact.register_credential_url_hosts(["mcp.zapier.com"]) == 1
        assert redact.register_credential_url_hosts(["MCP.ZAPIER.COM"]) == 0
        out = redact.redact_sensitive_text(f"HTTP Request: POST {URL} \"HTTP/1.1 200 OK\"")
        assert FAKE not in out and "token=***" in out
        other = f"https://example.com/cb?token={FAKE}&state=x"
        assert FAKE in redact.redact_sensitive_text(other), "unregistered hosts keep upstream pass-through semantics"
        assert FAKE not in redact.redact_sensitive_text(f"url=https://user@mcp.zapier.com:443/api/v1/connect?token={FAKE}#frag")
    finally:
        redact._reset_credential_url_hosts()


def test_nothing_reaches_hermes_log_files(tmp_path, monkeypatch, redaction):
    from agent import redact

    home = tmp_path / "hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    redact._reset_credential_url_hosts()
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_filters = list(root.filters)
    for h in saved:
        root.removeHandler(h)
    try:
        import hermes_logging

        hermes_logging.setup_logging(hermes_home=home, force=True)
        info = redaction.install({"mcp_servers": {"zapier": {"url": URL}}})
        assert "mcp.zapier.com" in info["hosts"] and info["core_registered"] >= 0
        stream = io.StringIO()
        bare = logging.StreamHandler(stream)  # a handler with NO redacting formatter
        root.addHandler(bare)
        for name in ("httpx2", "httpx", "mcp.client.streamable_http", "hermes_cli.mcp_config", "gateway.run", "tools.mcp_tool"):
            log = logging.getLogger(name)
            log.setLevel(logging.DEBUG)
            log.warning("HTTP Request: POST %s \"HTTP/1.1 200 OK\"", URL)
            log.error("connect failed for %s", URL, exc_info=None)
            log.warning("retrying %s in 1000ms", URL)
            try:
                raise ConnectionError(f"boom {URL}")
            except ConnectionError:
                log.exception("mcp connection error")
        for h in list(root.handlers):
            try:
                h.flush()
            except Exception:  # noqa: BLE001
                pass
        hits = _scan(home)
        assert hits == [], f"fake token reached log files: {hits}"
        assert FAKE not in stream.getvalue(), "bare handler leaked the token (root filter missing)"
        assert "token=***" in stream.getvalue()
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
            try:
                h.close()
            except Exception:  # noqa: BLE001
                pass
        for h in saved:
            root.addHandler(h)
        for f in list(root.filters):
            if f not in saved_filters:
                root.removeFilter(f)
        redact._reset_credential_url_hosts()


def test_installer_never_logs_or_prints_the_url(tmp_path):
    script = REPO / "scripts" / "flo" / "install_flo_team.py"
    home = tmp_path / ".hermes"
    env = {k: v for k, v in os.environ.items() if k in {"SYSTEMROOT", "TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "PATH"}}
    env.update({"HERMES_HOME": str(home), "HOME": str(tmp_path), "USERPROFILE": str(tmp_path), "PYTHONUTF8": "1", "FLO_ZAPIER_MCP_URL": URL})
    result = subprocess.run([sys.executable, str(script), "--home", str(home), "--no-mirror", "--no-local-check", "--only", "whisper"],
                            capture_output=True, text=True, env=env, cwd=str(REPO), check=False, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    assert FAKE not in result.stdout and FAKE not in result.stderr
    assert _scan(home) == []
    # The url is intentionally in the installed profile config (not a log) — and only there.
    cfg = (home / "profiles" / "whisper" / "config.yaml").read_text(encoding="utf-8")
    assert FAKE in cfg
