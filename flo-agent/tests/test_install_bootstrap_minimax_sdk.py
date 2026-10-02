"""The packaged Flo bootstrap must install MiniMax's declared protocol SDK."""

from pathlib import Path


def test_windows_bootstrap_installs_anthropic_extra_in_locked_and_fallback_tiers():
    install_ps1 = (Path(__file__).resolve().parents[1] / "scripts" / "install.ps1").read_text(encoding="utf-8")

    assert "sync --extra all --extra anthropic --locked" in install_ps1
    assert 'Spec = ".[all,anthropic]"' in install_ps1
    assert 'Spec = ".[$safeAll,anthropic]"' in install_ps1
