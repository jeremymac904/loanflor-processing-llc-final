"""The packaged Flo bootstrap must provision MiniMax's SDK in active envs."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")


def test_anthropic_transport_is_a_declared_versioned_extra():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '[project.optional-dependencies]' in pyproject
    assert 'anthropic = ["anthropic==0.87.0"]' in pyproject


def test_windows_bootstrap_installs_anthropic_in_base_and_pm_generations():
    assert "sync --extra all --extra anthropic --locked" in INSTALLER
    assert 'Spec = ".[all,anthropic]"' in INSTALLER
    assert 'Spec = ".[$safeAll,anthropic]"' in INSTALLER
    assert "& $venvPython -m hermes_cli.main pm install --extra anthropic" in INSTALLER


def test_windows_bootstrap_probes_the_pm_selected_environment():
    assert "Remove-Item Env:UV_PROJECT_ENVIRONMENT" in INSTALLER
    assert "activate_dependencies(root)" in INSTALLER
    assert "import anthropic" in INSTALLER
    assert "site_packages(selected_venv(root))" in INSTALLER
    assert "FLO_PM_ANTHROPIC_OK" in INSTALLER
