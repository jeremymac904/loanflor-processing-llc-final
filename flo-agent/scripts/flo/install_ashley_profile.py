#!/usr/bin/env python3
"""Install (or refresh) the Ashley/Flo profile from ``.flo/profile/ashley``.

Uses Hermes' own profile-distribution installer for the distribution-owned
files (SOUL.md, config.yaml, flo/policy.yaml, skins/), then seeds the
user-owned ``memories/USER.md`` exactly once (never overwrites an existing
one — that file is Ashley's).

    python scripts/flo/install_ashley_profile.py
    python scripts/flo/install_ashley_profile.py --home <dir>   # sandboxed HERMES root
    python scripts/flo/install_ashley_profile.py --update       # re-apply distribution files

No credentials are read or written. The model/provider block in config.yaml
is left for the operator (see .flo/docs/15_OPEN_QUESTIONS.md).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / ".flo" / "profile" / "ashley"
PROFILE_NAME = "ashley"


def _configure_home(home: str | None) -> None:
    if home:
        root = Path(home).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        os.environ["HERMES_HOME"] = str(root)
        # Profiles are HOME-anchored (~/.hermes/profiles); sandbox that too.
        os.environ["HOME"] = str(root.parent)
        os.environ["USERPROFILE"] = str(root.parent)


def install(home: str | None = None, update: bool = False, alias: bool = False) -> Path:
    _configure_home(home)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from hermes_cli.profile_distribution import (  # noqa: WPS433 - runtime import after sys.path
        DistributionError,
        install_distribution,
        update_distribution,
    )
    from hermes_cli.profiles import get_profile_dir

    target = get_profile_dir(PROFILE_NAME)
    try:
        if update and (target / "distribution.yaml").exists():
            plan = update_distribution(PROFILE_NAME, force_config=True)
        else:
            plan = install_distribution(str(DIST_DIR), name=PROFILE_NAME, force=update, create_alias=alias)
    except DistributionError as exc:
        print(f"install failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    target = Path(plan.target_dir)
    user_md = target / "memories" / "USER.md"
    if not user_md.exists():
        user_md.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DIST_DIR / "memories" / "USER.md", user_md)
        print(f"seeded {user_md}")
    else:
        print(f"kept existing {user_md}")

    seed_routines(target)

    print(f"Flo profile '{PROFILE_NAME}' ready at {target}")
    print("Next: `hermes -p ashley setup` once for model/provider, then `hermes -p ashley` (or the Flo desktop app).")
    return target


# Flo routines (Hermes cron jobs). Created once per profile; Ashley can edit,
# pause or remove them from the Cron page or `hermes -p ashley cron`.
ROUTINES = [
    {
        "name": "Flo morning brief",
        "schedule": "30 7 * * 1-5",
        "skills": ["flo-communication", "flo-processing-workflow"],
        "prompt": (
            "Good morning Ashley. Give the morning command brief: top three moves for today, "
            "biggest risk, fastest win. Check recent email, calendar and notes if reachable "
            "(google-workspace skill); say in one line if a source is not reachable. Short and plain."
        ),
    },
    {
        "name": "Flo end-of-day recap",
        "schedule": "0 17 * * 1-5",
        "skills": ["flo-communication"],
        "prompt": (
            "End-of-day wrap-up for Ashley: what moved forward, what got cleared, what is still open "
            "and on whom, main carryover for tomorrow. Acknowledge real wins. Clean summary only."
        ),
    },
]


def seed_routines(profile_dir: Path) -> None:
    """Create the two Flo routines in this profile's cron store if they are missing."""
    os.environ["HERMES_HOME"] = str(profile_dir)
    try:
        from cron import jobs as cron_jobs
    except Exception as exc:  # pragma: no cover - cron is a core dependency
        print(f"routines skipped: {exc}")
        return
    existing = {j.get("name") for j in cron_jobs.list_jobs(include_disabled=True)}
    for routine in ROUTINES:
        if routine["name"] in existing:
            print(f"routine present: {routine['name']}")
            continue
        try:
            cron_jobs.create_job(
                prompt=routine["prompt"],
                schedule=routine["schedule"],
                name=routine["name"],
                skills=routine["skills"],
                deliver="local",
            )
            print(f"routine created: {routine['name']} ({routine['schedule']})")
        except Exception as exc:  # noqa: BLE001 - report, don't abort the install
            print(f"routine failed: {routine['name']}: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", help="HERMES root to install into (default: the real ~/.hermes)")
    parser.add_argument("--update", action="store_true", help="re-apply distribution-owned files over an existing profile")
    parser.add_argument("--alias", action="store_true", help="create the `ashley` wrapper alias")
    args = parser.parse_args(argv)
    install(args.home, update=args.update, alias=args.alias)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
