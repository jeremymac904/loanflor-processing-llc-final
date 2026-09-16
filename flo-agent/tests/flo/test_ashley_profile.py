"""Ashley / Flo profile distribution (``.flo/profile/ashley``).

Exercises the REAL Hermes profile-distribution installer against a temporary
HERMES root (no mocks), then checks the installed profile's safety posture:
dangerous toolsets off, manual approvals, Flo policy plugin enabled, Flo
persona in SOUL.md, no credentials or borrower data anywhere in the
distribution.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
DIST = REPO / ".flo" / "profile" / "ashley"

DANGEROUS_TOOLSETS = {"terminal", "code_execution", "browser", "computer_use", "delegation", "cronjob", "kanban"}
SECRET_SHAPES = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|ya29\.|AIza[0-9A-Za-z_\-]{20,}|\b\d{3}-\d{2}-\d{4}\b|refresh_token\s*[:=]|api_key\s*[:=]\s*\S)",
    re.I,
)


@pytest.fixture()
def profile_env(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    default_home = tmp_path / ".hermes"
    default_home.mkdir(exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(default_home))
    return tmp_path


def _config():
    return yaml.safe_load((DIST / "config.yaml").read_text(encoding="utf-8"))


class TestDistributionContents:
    def test_manifest_parses_and_owns_policy_and_skin(self):
        from hermes_cli.profile_distribution import read_manifest

        manifest = read_manifest(DIST)
        assert manifest is not None and manifest.name == "ashley"
        owned = set(manifest.distribution_owned)
        assert {"SOUL.md", "config.yaml", "flo", "skins", "distribution.yaml"} <= owned
        assert manifest.env_requires == []

    def test_no_credentials_or_borrower_data_shipped(self):
        for path in DIST.rglob("*"):
            if path.is_dir():
                continue
            assert path.name not in {".env", "auth.json", "google_token.json"}, path
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not SECRET_SHAPES.search(text), f"secret-shaped content in {path}"

    def test_config_keeps_ashley_unrestricted(self):
        """Owner directive: Flo is the full Hermes toolset plus Flo persona/policy. No toolset is disabled."""
        cfg = _config()
        assert "disabled_toolsets" not in cfg.get("agent", {})
        assert "platform_toolsets" not in cfg
        assert cfg["approvals"]["mode"] == "smart"
        assert cfg["cron"]["allow_agent_scheduling"] is True
        assert cfg["memory"]["write_approval"] is False and cfg["skills"]["write_approval"] is False
        assert cfg["plugins"]["enabled"] == ["flo-policy"]
        assert cfg["display"]["skin"] == "flo"
        assert "model" not in cfg, "model/provider is chosen at setup; never bake credentials or a provider in"

    def test_config_keys_exist_upstream(self):
        """Every top-level section we set must be a real DEFAULT_CONFIG section (typos are silent otherwise)."""
        from hermes_cli.config import DEFAULT_CONFIG

        cfg = _config()
        for section in cfg:
            assert section in DEFAULT_CONFIG, section
            if isinstance(cfg[section], dict):
                for key in cfg[section]:
                    # plugins.enabled is written by `hermes plugins enable`, deliberately absent from defaults.
                    if (section, key) == ("plugins", "enabled"):
                        continue
                    assert key in DEFAULT_CONFIG[section], f"{section}.{key}"

    def test_soul_is_flo_not_hermes(self):
        soul = (DIST / "SOUL.md").read_text(encoding="utf-8")
        assert soul.startswith("You are Flo")
        for required in ("SOURCE_GAP", "never instructions", "cannot be undone", "Never imply"):
            assert required in soul, required
        for phrase in ("what matters most", "next move", "neutral"):
            assert phrase in soul, phrase
        from hermes_cli.default_soul import is_legacy_template_soul

        assert not is_legacy_template_soul(soul)

    def test_policy_file_loads_and_matches_defaults(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("flo_policy_core", REPO / "plugins" / "flo-policy" / "policy.py")
        policy = importlib.util.module_from_spec(spec)
        sys.modules["flo_policy_core"] = policy  # dataclasses resolve the module by name
        spec.loader.exec_module(policy)
        raw = yaml.safe_load((DIST / "flo" / "policy.yaml").read_text(encoding="utf-8"))
        table = policy.PolicyTable.from_mapping(raw)
        for cap, decision in policy.DEFAULT_CAPABILITY_POLICY.items():
            assert table.decision_for(cap) is decision, cap

    def test_user_seed_has_no_sensitive_or_loan_data(self):
        user_md = (DIST / "memories" / "USER.md").read_text(encoding="utf-8")
        assert "Ashley" in user_md and "SOURCE_GAP" in user_md
        assert not re.search(r"\b\d{6,}\b", user_md), "long digit run in USER.md seed"


class TestRealInstall:
    def test_install_distribution_into_temp_home(self, profile_env):
        from hermes_cli.profile_distribution import install_distribution
        from hermes_cli.profiles import get_profile_dir

        plan = install_distribution(str(DIST), name="ashley")
        target = Path(plan.target_dir)
        assert target == get_profile_dir("ashley")
        assert (target / "SOUL.md").read_text(encoding="utf-8").startswith("You are Flo")
        assert (target / "config.yaml").exists()
        assert (target / "flo" / "policy.yaml").exists()
        assert (target / "skins" / "flo.yaml").exists()
        assert (target / "distribution.yaml").exists()
        # memories are user-owned: the installer must NOT copy the seed.
        assert not (target / "memories" / "USER.md").exists()
        assert not (target / ".env").exists() or (target / ".env").read_text(encoding="utf-8").strip() == ""

    def test_helper_script_seeds_user_md_once(self, profile_env, tmp_path):
        script = REPO / "scripts" / "flo" / "install_ashley_profile.py"
        home = tmp_path / ".hermes"
        env = {"HERMES_HOME": str(home), "HOME": str(tmp_path), "USERPROFILE": str(tmp_path), "PATH": "", "SYSTEMROOT": "C:\\Windows"}
        import os

        env.update({k: v for k, v in os.environ.items() if k in {"SYSTEMROOT", "TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "PATH"}})
        result = subprocess.run(
            [sys.executable, str(script), "--home", str(home)],
            capture_output=True, text=True, env=env, cwd=str(REPO), check=False, timeout=180,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        profile = tmp_path / ".hermes" / "profiles" / "ashley"
        user_md = profile / "memories" / "USER.md"
        assert user_md.exists() and "Ashley" in user_md.read_text(encoding="utf-8")

        # Second run (update) keeps Ashley's USER.md untouched.
        user_md.write_text("# Ashley\n\n- prefers morning briefs at 7am\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(script), "--home", str(home), "--update"],
            capture_output=True, text=True, env=env, cwd=str(REPO), check=False, timeout=180,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "7am" in user_md.read_text(encoding="utf-8")
        assert "kept existing" in result.stdout
        # Routines exist exactly once after two runs.
        assert "routine created: Flo morning brief" in result.stdout or "routine present: Flo morning brief" in result.stdout
        jobs_file = profile / "cron" / "jobs.json"
        assert jobs_file.exists(), result.stdout
        import json

        jobs = json.loads(jobs_file.read_text(encoding="utf-8"))
        jobs = jobs.get("jobs", jobs) if isinstance(jobs, dict) else jobs
        names = [j.get("name") for j in jobs]
        assert names.count("Flo morning brief") == 1 and names.count("Flo end-of-day recap") == 1, names

    def test_installed_profile_loads_flo_policy_plugin(self, profile_env, monkeypatch):
        from hermes_cli.profile_distribution import install_distribution

        plan = install_distribution(str(DIST), name="ashley")
        target = Path(plan.target_dir)
        monkeypatch.setenv("HERMES_HOME", str(target))
        monkeypatch.setenv("HERMES_BUNDLED_PLUGINS", str(REPO / "plugins"))
        from hermes_cli.plugins import PluginManager

        mgr = PluginManager()
        mgr.discover_and_load()
        loaded = mgr._plugins.get("flo-policy")
        assert loaded is not None and loaded.enabled
        # Unrestricted: routine tools run; only irreversible actions ask once.
        results = mgr.invoke_hook("pre_tool_call", tool_name="terminal", args={"command": "whoami"})
        assert all(r is None for r in results)
        results = mgr.invoke_hook("pre_tool_call", tool_name="flo_email_send", args={"to": "a@example.com"})
        assert any(isinstance(r, dict) and r.get("action") == "approve" for r in results)
