"""The packaged Flo bootstrap must provision MiniMax's SDK in active envs."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")


def test_anthropic_transport_is_in_the_default_runtime_and_optional_extra():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '[project.optional-dependencies]' in pyproject
    assert 'anthropic = ["anthropic==0.87.0"]' in pyproject
    # The runtime activates a separate PM-selected environment, so an SDK
    # required by MiniMax transport must also be part of its default closure.
    assert '"anthropic==0.87.0"' in pyproject.split("[project.optional-dependencies]", 1)[0]
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    project = lock.split('name = "hermes-agent"', 1)[1].split("[[package]]", 1)[0]
    assert '{ name = "anthropic" }' in project


def test_windows_bootstrap_installs_anthropic_in_locked_and_fallback_tiers():
    assert "sync --extra all --extra anthropic --locked" in INSTALLER
    assert 'Spec = ".[all,anthropic]"' in INSTALLER
    assert 'Spec = ".[$safeAll,anthropic]"' in INSTALLER
