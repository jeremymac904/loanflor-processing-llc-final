"""Team manifest loader + profile/role resolution.

The manifest (``team.yaml`` next to this file) is the single source of truth
for the six Flo Team profiles: names, titles, delegation edges, folder roots,
Zapier scopes, model-class preferences and the team autonomy level.

Everything here is pure (no Hermes imports at module load) so it can be unit
tested and reused by the installer and the desktop page.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "team.yaml"

AUTONOMY_LEVELS = ("shadow", "assisted", "trusted")


@dataclass(frozen=True)
class RoleSpec:
    name: str
    display_name: str
    title: str
    role: str
    description: str
    color: str
    reports_to: Optional[str]
    delegates_to: Tuple[str, ...]
    loan_workspace: str              # read_write | read | deny
    deal_rooms: str                  # always | throughout | when_needed | never
    loan_folders: Tuple[str, ...]
    other_folders: Tuple[str, ...]
    zapier_include: Tuple[str, ...]
    zapier_exclude: Tuple[str, ...]
    model_classes: Tuple[str, ...]
    external_writes: str             # confirm | deny

    @property
    def is_leader(self) -> bool:
        return self.reports_to is None

    @property
    def borrower_data_allowed(self) -> bool:
        return self.loan_workspace != "deny"


@dataclass(frozen=True)
class TeamManifest:
    version: int
    team_name: str
    leader: str
    max_delegation_depth: int
    autonomy_level: str
    profiles: Mapping[str, RoleSpec]
    workspace: Mapping[str, object]
    model_classes: Mapping[str, Mapping[str, object]]
    trusted_capabilities: Tuple[str, ...] = field(default_factory=tuple)

    def role(self, name: str) -> RoleSpec:
        key = (name or "").strip().lower()
        if key not in self.profiles:
            raise KeyError(f"unknown Flo Team profile: {name!r}")
        return self.profiles[key]

    def names(self) -> List[str]:
        return list(self.profiles.keys())

    def may_delegate(self, sender: str, recipient: str) -> Tuple[bool, str]:
        """Deterministic delegation edge check (specialists return to Flo)."""
        try:
            src = self.role(sender)
            dst = self.role(recipient)
        except KeyError as exc:
            return False, str(exc)
        if src.name == dst.name:
            return False, "an agent cannot hand off to itself"
        if dst.name in src.delegates_to:
            return True, "leader delegation"
        if src.reports_to == dst.name:
            return True, "return to leader"
        return False, f"{src.display_name} may not hand off directly to {dst.display_name}; return the work to {self.role(self.leader).display_name}"


def _tuple(value) -> Tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def load_manifest(path: Optional[Path] = None) -> TeamManifest:
    import yaml  # local import: keep module import cheap

    raw = yaml.safe_load((path or MANIFEST_PATH).read_text(encoding="utf-8")) or {}
    profiles: Dict[str, RoleSpec] = {}
    for name, spec in (raw.get("profiles") or {}).items():
        spec = spec or {}
        folders = spec.get("folders") or {}
        zapier = spec.get("zapier") or {}
        profiles[str(name)] = RoleSpec(
            name=str(name),
            display_name=str(spec.get("display_name") or name).strip(),
            title=str(spec.get("title") or "").strip(),
            role=str(spec.get("role") or "").strip(),
            description=str(spec.get("description") or "").strip(),
            color=str(spec.get("color") or "#1f5a2d"),
            reports_to=(str(spec["reports_to"]) if spec.get("reports_to") else None),
            delegates_to=_tuple(spec.get("delegates_to")),
            loan_workspace=str(spec.get("loan_workspace") or "deny"),
            deal_rooms=str(spec.get("deal_rooms") or "never"),
            loan_folders=_tuple(folders.get("loans")),
            other_folders=_tuple(folders.get("other")),
            zapier_include=_tuple(zapier.get("include")),
            zapier_exclude=_tuple(zapier.get("exclude")),
            model_classes=_tuple(spec.get("model_classes")),
            external_writes=str(spec.get("external_writes") or "confirm"),
        )
    autonomy = str(raw.get("autonomy_level") or "assisted").lower()
    if autonomy not in AUTONOMY_LEVELS:
        raise ValueError(f"autonomy_level must be one of {AUTONOMY_LEVELS}, got {autonomy!r}")
    depth = int(raw.get("max_delegation_depth", 1))
    if depth < 1:
        raise ValueError("max_delegation_depth must be >= 1")
    manifest = TeamManifest(
        version=int(raw.get("version", 1)),
        team_name=str(raw.get("team_name") or "Flo Team"),
        leader=str(raw.get("leader") or "flo"),
        max_delegation_depth=depth,
        autonomy_level=autonomy,
        profiles=profiles,
        workspace=dict(raw.get("workspace") or {}),
        model_classes=dict(raw.get("model_classes") or {}),
        trusted_capabilities=_tuple(raw.get("trusted_capabilities")),
    )
    if manifest.leader not in profiles:
        raise ValueError(f"leader {manifest.leader!r} is not a profile")
    return manifest


_MANIFEST: Optional[TeamManifest] = None


def manifest() -> TeamManifest:
    global _MANIFEST
    if _MANIFEST is None:
        _MANIFEST = load_manifest()
    return _MANIFEST


# ---------------------------------------------------------------------------
# Which profile is this process?
# ---------------------------------------------------------------------------

def hermes_home() -> Optional[Path]:
    try:
        from hermes_constants import get_hermes_home  # type: ignore

        return Path(get_hermes_home())
    except Exception:
        raw = os.environ.get("HERMES_HOME")
        return Path(raw) if raw else None


def hermes_root(home: Optional[Path] = None) -> Optional[Path]:
    """Root ~/.hermes for both the default profile and named profiles."""
    home = home or hermes_home()
    if home is None:
        return None
    if home.parent.name == "profiles":
        return home.parent.parent
    return home


def current_profile_name(home: Optional[Path] = None) -> str:
    """Resolve the active profile: env → HERMES_HOME layout → active_profile → 'default'."""
    for var in ("HERMES_PROFILE_NAME", "HERMES_PROFILE"):
        value = os.environ.get(var, "").strip()
        if value:
            return value.lower()
    home = home or hermes_home()
    if home is not None and home.parent.name == "profiles":
        return home.name.lower()
    try:
        from hermes_cli.profiles import get_active_profile_name  # type: ignore

        name = get_active_profile_name()
        if name:
            return str(name).lower()
    except Exception:
        pass
    return "default"


def current_role(home: Optional[Path] = None) -> Optional[RoleSpec]:
    """The RoleSpec for this process, or None when the profile is not a team member."""
    name = current_profile_name(home)
    try:
        return manifest().role(name)
    except KeyError:
        return None


def team_state_root(home: Optional[Path] = None) -> Optional[Path]:
    """Shared team state (workspaces, tasks, approval queue) — one per install, not per profile."""
    root = hermes_root(home)
    return (root / "flo" / "team") if root else None
