"""Bot Mode delivery runner cwd — repo paths with shell-unsafe characters.

Upstream's terminal_tool rejects a workdir containing characters such as an
apostrophe; a checkout under ``.../Ashley's Pipeline/...`` therefore blocked
every ``message_agent`` delivery. ``tools.bot_mode_dm._delivery_workdir``
falls back to a valid directory instead of failing.
"""

from __future__ import annotations

from pathlib import Path

from tools import bot_mode_dm
from tools.terminal_tool import _validate_workdir


def test_delivery_workdir_is_always_valid():
    workdir = bot_mode_dm._delivery_workdir()
    assert _validate_workdir(workdir) is None, workdir
    assert Path(workdir).is_dir()


def test_falls_back_when_repo_path_is_unsafe(monkeypatch, tmp_path):
    unsafe = tmp_path / "Ashley's Pipeline" / "repo" / "tools"
    unsafe.mkdir(parents=True)
    monkeypatch.setattr(bot_mode_dm, "__file__", str(unsafe / "bot_mode_dm.py"))
    workdir = bot_mode_dm._delivery_workdir()
    assert "'" not in workdir and _validate_workdir(workdir) is None
