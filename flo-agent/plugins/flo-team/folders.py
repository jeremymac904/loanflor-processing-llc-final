"""Role-scoped local folders (shared/LOCAL_FOLDER_POLICY.md).

Layout under the workspace root (``FLO_WORKSPACE_ROOT``, default
``~/FloWorkspace``)::

    loans/<opaque-loan-id>/{intake,aus,income,assets,title,insurance,conditions,correspondence,exports}/
    marketing/  templates/  sources/  team/

Rules, all deterministic and checked on the *resolved* path:

* a bot may only read/write inside its manifest folder roots;
* ``loans/**`` is denied outright to profiles with ``loan_workspace: deny``
  (Franklin) — structurally, not by prompt;
* ``intake/`` holds original borrower-provided documents: writes, renames and
  moves there are denied for every bot (edits go to ``exports/``);
* permanent deletion is denied for every bot everywhere in the workspace;
* paths outside the workspace root are not this module's business (Hermes'
  own tool policy and the Flo capability policy apply) — except that the
  installed Flo Team profiles run with ``FLO_TEAM_CONFINE_FILES=1`` which
  turns "outside the workspace" into a deny for file tools.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .manifest import RoleSpec, TeamManifest, manifest as _manifest

WRITE_TOOLS = {"write_file", "patch", "flo_drive_upload", "flo_drive_move", "flo_drive_rename"}
READ_TOOLS = {"read_file", "search_files", "vision_analyze", "video_analyze"}
DELETE_MARKERS = ("delete", "remove", "rm ", "rmdir", "unlink", "trash")


@dataclass(frozen=True)
class FolderDecision:
    allowed: bool
    reason: str
    zone: str  # loans | marketing | templates | sources | team | outside


def workspace_root(team: Optional[TeamManifest] = None) -> Path:
    team = team or _manifest()
    env = str(team.workspace.get("root_env") or "FLO_WORKSPACE_ROOT")
    raw = os.environ.get(env) or str(team.workspace.get("default_root") or "~/FloWorkspace")
    return Path(raw).expanduser().resolve(strict=False)


def _relative(path: str, root: Path) -> Optional[Tuple[str, ...]]:
    try:
        resolved = Path(path).expanduser().resolve(strict=False)
        return resolved.relative_to(root).parts
    except (ValueError, OSError):
        return None


def check_path(role: RoleSpec, path: str, *, mode: str, team: Optional[TeamManifest] = None,
               root: Optional[Path] = None) -> FolderDecision:
    """``mode`` is read | write | delete."""
    team = team or _manifest()
    root = root or workspace_root(team)
    parts = _relative(path, root)
    if parts is None:
        confine = os.environ.get("FLO_TEAM_CONFINE_FILES", "").strip() in ("1", "true", "yes")
        if confine:
            return FolderDecision(False, f"{role.display_name} may only use files under {root}", "outside")
        return FolderDecision(True, "outside the Flo workspace: not folder-policy scoped", "outside")
    if not parts:
        return FolderDecision(mode == "read", "workspace root: listing only", "root")
    top = parts[0]
    if mode == "delete":
        return FolderDecision(False, "permanent deletion is disabled for every Flo Team bot", top)

    if top == "loans":
        if not role.borrower_data_allowed:
            return FolderDecision(False, f"{role.display_name} is structurally denied borrower loan folders", "loans")
        if len(parts) < 3:
            return FolderDecision(mode == "read", "loan folder listing", "loans")
        sub = parts[2]
        protected = tuple(team.workspace.get("protected_subfolders") or ("intake",))
        if sub not in role.loan_folders:
            return FolderDecision(False, f"{role.display_name} has no access to loans/*/{sub}", "loans")
        if mode == "write" and sub in protected:
            return FolderDecision(False, f"loans/*/{sub} holds original borrower documents; write your worksheet to exports/ instead", "loans")
        return FolderDecision(True, f"{mode} allowed in loans/*/{sub}", "loans")

    if top in role.other_folders:
        return FolderDecision(True, f"{mode} allowed in {top}/", top)
    return FolderDecision(False, f"{role.display_name} has no access to {top}/", top)


def classify_file_tool(tool_name: str, args: dict) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(mode, path)`` for file-shaped tool calls, else ``(None, None)``."""
    name = (tool_name or "").strip()
    args = args if isinstance(args, dict) else {}
    path = None
    for key in ("path", "file_path", "target", "source", "dest", "destination", "directory", "dir"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            path = value.strip()
            break
    if name in WRITE_TOOLS:
        return "write", path
    if name in READ_TOOLS:
        return "read", path
    if name == "terminal":
        command = str(args.get("command") or "")
        lowered = command.lower()
        if any(marker in lowered for marker in DELETE_MARKERS):
            return "delete", path or _first_path_token(command)
        return None, None
    return None, None


def _first_path_token(command: str) -> Optional[str]:
    for token in command.split():
        if "/" in token or "\\" in token:
            return token.strip("'\"")
    return None
