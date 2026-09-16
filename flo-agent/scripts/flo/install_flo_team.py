#!/usr/bin/env python3
"""Install (or refresh) the six Flo Team profiles from ``.flo/profile/<name>``.

    python scripts/flo/install_flo_team.py                     # install/refresh all six
    python scripts/flo/install_flo_team.py --home <dir>        # sandboxed HERMES root (tests)
    python scripts/flo/install_flo_team.py --only flo sage     # a subset
    python scripts/flo/install_flo_team.py --mirror-from ashley  (default) credentials/model source
    python scripts/flo/install_flo_team.py --no-mirror         # leave model/Zapier for `hermes -p <name> setup`
    python scripts/flo/install_flo_team.py --workspace <dir>   # create the FloWorkspace folder layout

For every profile it:

1. runs Hermes' own profile-distribution installer (``install_distribution`` /
   ``update_distribution``) for the distribution-owned files: SOUL.md,
   config.yaml, profile.yaml (Bot Mode ui_meta), assets/avatar.png, flo/,
   skins/, routines.yaml;
2. seeds the user-owned ``memories/USER.md`` exactly once;
3. mirrors runtime credentials that must never live in git from the mirror
   profile (default ``ashley``): ``auth.json``, ``.env``, the ``model:`` block,
   ``providers.*`` and the Zapier MCP url — or from ``FLO_ZAPIER_MCP_URL`` /
   ``FLO_LOCAL_BASE_URL`` / ``FLO_LOCAL_MODEL`` env vars. Only the url is
   copied into ``mcp_servers.zapier``; the profile's own ``tools.include`` /
   ``exclude`` filter (role scope) is kept;
4. applies model-class preferences: when the local provider passes the health
   check (reachable, model listed, context >= 64K, id mapping, smoke
   completion) and the role prefers a local class, the profile's ``model:``
   points at it; otherwise the mirrored (cloud) model is used and the reason
   is printed. The runtime ``flo_model_health`` tool re-checks on demand and
   fails closed for sensitive work;
5. creates the role's routines (Hermes cron jobs in that profile) if missing;
6. copies the team knowledge registry into ``<root>/flo/team/knowledge-registry.json``
   and creates the shared team state root ``<root>/flo/team/``.

Nothing is printed that contains a token; the Zapier url is reported only as
"mirrored" / "not available".
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO_ROOT / ".flo" / "profile"
PLUGIN_DIR = REPO_ROOT / "plugins" / "flo-team"
TEAM_NAMES = ("flo", "malcolm", "chadwick", "whisper", "sage", "franklin")
LOCAL_PREFERRING_CLASSES = ("local_fast", "local_reasoning")
_DISCOVERY: Dict = {}  # provider discovery runs once per install


def _configure_home(home: Optional[str]) -> None:
    if home:
        root = Path(home).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        os.environ["HERMES_HOME"] = str(root)
        os.environ["HOME"] = str(root.parent)
        os.environ["USERPROFILE"] = str(root.parent)


def _load_team():
    import importlib.util

    spec = importlib.util.spec_from_file_location("flo_team", PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["flo_team"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    import importlib

    importlib.import_module("flo_team.models")
    importlib.import_module("flo_team.providers")
    return sys.modules["flo_team.manifest"], sys.modules["flo_team.models"]


def _read_yaml(path: Path) -> Dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(path: Path, data: Dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _mirror_source(mirror_from: Optional[str]) -> Dict:
    """Runtime values from the mirror profile (never printed)."""
    out: Dict = {"model": None, "providers": {}, "zapier_url": None, "auth_json": None, "env_file": None}
    env_url = os.environ.get("FLO_ZAPIER_MCP_URL", "").strip()
    if env_url:
        out["zapier_url"] = env_url
    if mirror_from:
        try:
            from hermes_cli.profiles import get_profile_dir

            src = get_profile_dir(mirror_from)
        except Exception:
            src = None
        if src and src.is_dir():
            cfg = _read_yaml(src / "config.yaml")
            if isinstance(cfg.get("model"), dict) and cfg["model"]:
                out["model"] = dict(cfg["model"])
            if isinstance(cfg.get("providers"), dict):
                out["providers"] = dict(cfg["providers"])
            zap = (cfg.get("mcp_servers") or {}).get("zapier") if isinstance(cfg.get("mcp_servers"), dict) else None
            if isinstance(zap, dict) and zap.get("url") and not out["zapier_url"]:
                out["zapier_url"] = str(zap["url"])
            if (src / "auth.json").is_file():
                out["auth_json"] = src / "auth.json"
            if (src / ".env").is_file():
                out["env_file"] = src / ".env"
    local_url = os.environ.get("FLO_LOCAL_BASE_URL", "").strip()
    local_model = os.environ.get("FLO_LOCAL_MODEL", "").strip()
    flo_local = dict(out["providers"].get("flo_local") or {})
    if not flo_local and out["providers"].get("ollama", {}).get("base_url"):
        flo_local = {"base_url": out["providers"]["ollama"]["base_url"], "model": local_model or "qwen3-flo", "context_length": 65536, "api": "openai"}
    if local_url:
        flo_local["base_url"] = local_url
    if local_model:
        flo_local["model"] = local_model
    if flo_local:
        out["providers"]["flo_local"] = flo_local
    return out


def _apply_runtime(profile_dir: Path, role, team, mirror: Dict, models_mod, *, check_local: bool) -> List[str]:
    notes: List[str] = []
    cfg_path = profile_dir / "config.yaml"
    cfg = _read_yaml(cfg_path)

    # Zapier url (secret) — only into the installed config, keep the role filter.
    zap = (cfg.setdefault("mcp_servers", {}) or {}).get("zapier") or {}
    if mirror.get("zapier_url"):
        zap["url"] = mirror["zapier_url"]
        cfg["mcp_servers"]["zapier"] = zap
        notes.append("zapier: url mirrored (scoped by tools.include/exclude)")
    else:
        cfg["mcp_servers"].pop("zapier", None)
        if not cfg["mcp_servers"]:
            cfg.pop("mcp_servers")
        notes.append("zapier: not available (set FLO_ZAPIER_MCP_URL or add it to the mirror profile); role scope still enforced by flo-team")

    # Providers + model.
    providers = dict(cfg.get("providers") or {})
    for name, block in (mirror.get("providers") or {}).items():
        providers.setdefault(name, block)
    if providers:
        cfg["providers"] = providers
    cloud = mirror.get("model")
    chosen = None
    # Credential files first (user-owned; copied only when absent) so discovery can see them.
    for key, dest_name in (("auth_json", "auth.json"), ("env_file", ".env")):
        src = mirror.get(key)
        dest = profile_dir / dest_name
        if src and not dest.exists():
            shutil.copyfile(src, dest)
            try:
                os.chmod(dest, 0o600)
            except OSError:
                pass
            notes.append(f"{dest_name}: mirrored")
    # Provider discovery (plugins/flo-team/providers.py): probe local candidates, check cloud
    # credentials with a real one-line completion, then pick per role from its model-class
    # preferences. Profiles never carry machine-specific endpoints in git; the choice is
    # written here, at install time, and re-checkable with `flo_model_health action=discover`.
    rows = _DISCOVERY.get("rows")
    if rows is None:
        import importlib

        prov = importlib.import_module("flo_team.providers")
        previous_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = str(profile_dir)  # auth store of the profile being installed
        try:
            if check_local:
                rows = prov.discover(config={"providers": providers}, smoke=True, cloud_smoke=lambda p, m: _cloud_smoke(profile_dir, p, m))
            else:
                rows = prov.discover(config={"providers": providers}, smoke=False,
                                     health_check=lambda *a, **k: models_mod.HealthReport(provider="flo_local", base_url=a[0], model=a[1]))
        finally:
            if previous_home is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous_home
        _DISCOVERY["rows"] = rows
        _DISCOVERY["prov"] = prov
        for row in rows:
            notes.append(f"provider {row.provider_id}: {row.status}" + (f" ({row.latency_ms} ms, ctx {row.context_capability})" if row.latency_ms is not None else "") + (f" — {row.error}" if row.error else ""))
    prov = _DISCOVERY["prov"]
    # The processing bots handle borrower documents: prefer a provider with sensitive-data
    # permission; if none is fast enough, fall back to an approved cloud provider only when the
    # owner has not forbidden it (FLO_TEAM_ALLOW_CLOUD=0 forbids) and say so loudly.
    choice = prov.choose(role, rows, sensitive=True, team=team, allow_slow=False)
    if choice.status != "OK":
        slow = prov.choose(role, rows, sensitive=True, team=team, allow_slow=True)
        cloud_ok = os.environ.get("FLO_TEAM_ALLOW_CLOUD", "1").strip() not in ("0", "false", "no")
        any_cloud = prov.choose(role, rows, sensitive=False, team=team, allow_slow=False, allow_any_cloud=True)
        if any_cloud.status == "OK" and cloud_ok:
            choice = any_cloud
            notes.append("model: no fast local provider with sensitive-data permission; using an approved cloud provider for this profile (owner directive: best working provider; synthetic data only until FLO_TEAM_OPEN_QUESTIONS #6 is answered)")
        elif slow.status == "OK":
            choice = slow
            notes.append("model: only a slow local provider is available; using it (sensitive-data safe, but expect long turns)")
    if choice.status == "OK" and choice.hermes_provider != "code":
        chosen = {"provider": choice.hermes_provider, "default": choice.model}
        if choice.base_url:
            chosen["base_url"] = choice.base_url
        notes.append(f"model: {choice.provider_id} -> {choice.model} via {choice.hermes_provider} [{choice.model_class}] ({choice.reason})")
    elif cloud:
        chosen = dict(cloud)
        notes.append(f"model: discovery found nothing usable; mirrored provider {cloud.get('provider')} kept")
    if chosen:
        cfg["model"] = chosen
    else:
        notes.append("model: none configured — run `hermes -p %s setup`" % role.name)
    _write_yaml(cfg_path, cfg)
    return notes


def _cloud_smoke(profile_dir: Path, provider: str, model: str) -> Dict:
    """One-line completion through the Hermes CLI in this profile (real round trip, timed)."""
    import subprocess
    import tempfile
    import time

    exe = Path(sys.executable).with_name("hermes.exe") if os.name == "nt" else Path(sys.executable).with_name("hermes")
    if not exe.exists():
        return {"ok": False, "error": "hermes CLI not found next to the interpreter"}
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write("Reply with exactly: OK")
        query = fh.name
    env = dict(os.environ)
    env["HERMES_HOME"] = str(profile_dir)
    env["PYTHONUTF8"] = "1"
    started = time.monotonic()
    try:
        result = subprocess.run([str(exe), "chat", "--provider", provider, "--model", model, "-Q", "--query-file", query],
                                capture_output=True, text=True, env=env, timeout=120, check=False)
        latency = int((time.monotonic() - started) * 1000)
        out = (result.stdout or "") + (result.stderr or "")
        ok = result.returncode == 0 and "OK" in out and "Error from provider" not in out and "HTTP 4" not in out
        return {"ok": ok, "latency_ms": latency, "error": None if ok else (out.strip().splitlines()[-1][:160] if out.strip() else f"exit {result.returncode}")}
    except subprocess.TimeoutExpired:
        return {"ok": False, "latency_ms": int((time.monotonic() - started) * 1000), "error": "timed out after 120s"}
    finally:
        try:
            os.unlink(query)
        except OSError:
            pass


def seed_routines(profile_dir: Path) -> List[str]:
    routines = (_read_yaml(profile_dir / "routines.yaml") or {}).get("routines") or []
    if not routines:
        return ["routines: none declared"]
    previous = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(profile_dir)
    notes = []
    try:
        from cron import jobs as cron_jobs

        existing = {j.get("name") for j in cron_jobs.list_jobs(include_disabled=True)}
        for routine in routines:
            if routine["name"] in existing:
                notes.append(f"routine present: {routine['name']}")
                continue
            try:
                cron_jobs.create_job(prompt=routine["prompt"], schedule=routine["schedule"], name=routine["name"],
                                     skills=routine.get("skills") or [], deliver="local")
                notes.append(f"routine created: {routine['name']} ({routine['schedule']})")
            except Exception as exc:  # noqa: BLE001
                notes.append(f"routine failed: {routine['name']}: {exc}")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"routines skipped: {exc}")
    finally:
        if previous is not None:
            os.environ["HERMES_HOME"] = previous
    return notes


def make_workspace(root: Path, team) -> None:
    for sub in team.workspace.get("other_roots") or []:
        (root / str(sub)).mkdir(parents=True, exist_ok=True)
    (root / "loans").mkdir(parents=True, exist_ok=True)
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(
            "# FloWorkspace\n\nRole-scoped working folders for the Flo Team (see plugins/flo-team/team.yaml).\n\n"
            "loans/<opaque-loan-id>/{" + ",".join(team.workspace.get("loan_subfolders") or []) + "}/ — one folder per file; "
            "intake/ holds original borrower documents (read-only for bots).\nmarketing/ — Franklin only. templates/, sources/, team/ — shared.\n"
            "Never use SSNs or account numbers in folder names.\n", encoding="utf-8")


def install(*, home: Optional[str], update: bool, only: Optional[List[str]], mirror_from: Optional[str],
            check_local: bool, workspace: Optional[str]) -> Dict[str, List[str]]:
    _configure_home(home)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from hermes_cli.profile_distribution import DistributionError, install_distribution, update_distribution
    from hermes_cli.profiles import get_profile_dir

    manifest_mod, models_mod = _load_team()
    team = manifest_mod.manifest()
    mirror = _mirror_source(mirror_from)
    # Never let the mirrored MCP url reach a log line from this process either.
    try:
        import importlib

        importlib.import_module("flo_team.redaction").install(None, extra_hosts=[urlparse(mirror["zapier_url"]).hostname] if mirror.get("zapier_url") else [])
    except Exception:  # noqa: BLE001
        pass
    results: Dict[str, List[str]] = {}
    names = [n for n in TEAM_NAMES if not only or n in only]
    root = None
    for name in names:
        role = team.role(name)
        dist_dir = PROFILES_DIR / name
        target = get_profile_dir(name)
        notes: List[str] = []
        try:
            if (target / "distribution.yaml").exists():
                update_distribution(name, force_config=True)
                notes.append("distribution updated")
            else:
                install_distribution(str(dist_dir), name=name, force=update, create_alias=False)
                notes.append("distribution installed")
        except DistributionError as exc:
            results[name] = [f"install failed: {exc}"]
            continue
        target = get_profile_dir(name)
        user_md = target / "memories" / "USER.md"
        if not user_md.exists():
            user_md.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(dist_dir / "memories" / "USER.md", user_md)
            notes.append("USER.md seeded")
        else:
            notes.append("USER.md kept")
        notes += _apply_runtime(target, role, team, mirror, models_mod, check_local=check_local)
        notes += seed_routines(target)
        results[name] = notes
        root = manifest_mod.hermes_root(target)
    if root is not None:
        state = root / "flo" / "team"
        state.mkdir(parents=True, exist_ok=True)
        registry = PLUGIN_DIR / "knowledge" / "registry.json"
        if registry.exists():
            shutil.copyfile(registry, state / "knowledge-registry.json")
    if workspace:
        make_workspace(Path(workspace).expanduser(), team)
    return results


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", help="HERMES root to install into (default: the real hermes home)")
    parser.add_argument("--update", action="store_true", help="re-apply distribution-owned files over existing profiles")
    parser.add_argument("--only", nargs="*", help="subset of profiles")
    parser.add_argument("--mirror-from", default="ashley", help="profile whose model/providers/Zapier url/auth are mirrored (default ashley)")
    parser.add_argument("--no-mirror", action="store_true", help="do not mirror anything")
    parser.add_argument("--no-local-check", action="store_true", help="skip the local model health check")
    parser.add_argument("--workspace", help="create the FloWorkspace folder layout at this path")
    args = parser.parse_args(argv)
    results = install(home=args.home, update=args.update, only=args.only, mirror_from=None if args.no_mirror else args.mirror_from,
                      check_local=not args.no_local_check, workspace=args.workspace)
    for name, notes in results.items():
        print(f"[{name}]")
        for note in notes:
            print(f"  - {note}")
    print("Flo Team ready. Open the desktop Bots pane (or `hermes -p flo`) — Flo is pinned; Bot Chats can message teammates.")
    return 0 if all(not n or not n[0].startswith("install failed") for n in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
