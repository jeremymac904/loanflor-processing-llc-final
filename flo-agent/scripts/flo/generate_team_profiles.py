#!/usr/bin/env python3
"""Generate the derivable files of the six Flo Team profile distributions.

    python scripts/flo/generate_team_profiles.py          # write
    python scripts/flo/generate_team_profiles.py --check  # verify in sync (CI/test)

Source of truth: ``plugins/flo-team/team.yaml``. For each profile under
``.flo/profile/<name>/`` this writes:

    distribution.yaml   Hermes profile-distribution manifest
    config.yaml         profile config (skin, approvals, plugins, per-role skill
                        and toolset scoping, Zapier tool filter — NO url/secret)
    profile.yaml        display_name, description, ui_meta['hermes-bots']
                        (title, color, group, pinned) — the block that makes the
                        install Bot-Mode-managed and unlocks message_agent
    flo/policy.yaml     Flo capability policy overrides for the role
    flo/team-role.yaml  the role's manifest slice (folders, Zapier scope,
                        model classes, autonomy) for humans and the desktop page
    routines.yaml       the role's cron routines (created by the installer)
    skins/flo.yaml      the Flo CLI skin (copied from the Ashley profile)
    README.md

Hand-written files are never touched: ``SOUL.md``, ``memories/USER.md``,
``assets/avatar.png``.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
sys.path.insert(0, str(PLUGIN.parent))

PROFILES_DIR = REPO / ".flo" / "profile"
ASHLEY_SKIN = PROFILES_DIR / "ashley" / "skins" / "flo.yaml"
GENERATED = ("distribution.yaml", "config.yaml", "profile.yaml", "flo/policy.yaml", "flo/team-role.yaml", "routines.yaml", "skins/flo.yaml", "README.md")

# Bundled Flo skills (skills/flo-mortgage + skills/flo-team) each role should carry.
# Everything not listed for a role is disabled in that profile (skills.disabled).
ALL_FLO_SKILLS = [
    "flo-processing-workflow", "flo-milestones", "flo-income-analysis", "flo-tpo-guidelines", "flo-communication",
    "flo-compliance-messaging", "flo-notes-and-emails",
    "flo-team-handoff", "flo-team-approvals", "flo-source-provenance",
    "flo-file-prep", "flo-order-outs", "flo-conditions-to-action", "flo-underwriting-sources", "flo-calc-workbench",
    "flo-marketing-guardrails",
]
ROLE_SKILLS = {
    "flo": ["flo-processing-workflow", "flo-milestones", "flo-communication", "flo-compliance-messaging", "flo-notes-and-emails",
            "flo-team-handoff", "flo-team-approvals", "flo-source-provenance", "flo-tpo-guidelines"],
    "malcolm": ["flo-processing-workflow", "flo-milestones", "flo-income-analysis", "flo-tpo-guidelines", "flo-communication",
                "flo-team-handoff", "flo-team-approvals", "flo-source-provenance", "flo-file-prep", "flo-calc-workbench"],
    "chadwick": ["flo-processing-workflow", "flo-milestones", "flo-communication", "flo-notes-and-emails",
                 "flo-team-handoff", "flo-team-approvals", "flo-source-provenance", "flo-order-outs"],
    "whisper": ["flo-processing-workflow", "flo-milestones", "flo-communication", "flo-compliance-messaging", "flo-notes-and-emails",
                "flo-team-handoff", "flo-team-approvals", "flo-source-provenance", "flo-conditions-to-action"],
    "sage": ["flo-processing-workflow", "flo-income-analysis", "flo-tpo-guidelines", "flo-communication",
             "flo-team-handoff", "flo-team-approvals", "flo-source-provenance", "flo-underwriting-sources", "flo-calc-workbench"],
    "franklin": ["flo-communication", "flo-team-handoff", "flo-team-approvals", "flo-source-provenance", "flo-marketing-guardrails"],
}

# Stock Hermes toolsets a role does not need. Kept deliberately light (owner
# directive: no friction); role boundaries are enforced by plugins/flo-team.
DISABLED_TOOLSETS = {
    "flo": [],
    "malcolm": ["delegation", "computer_use", "browser"],
    "chadwick": ["delegation", "computer_use", "browser"],
    "whisper": ["delegation", "computer_use", "browser"],
    "sage": ["delegation", "computer_use"],
    "franklin": ["delegation", "computer_use"],
}

# Routines from the pack's ROUTINE_CATALOG / per-agent ROUTINES.md. All are
# read/analysis + proposal only; external side effects still stop at approval.
ROUTINES = {
    "flo": [
        {"name": "Flo morning command brief", "schedule": "30 7 * * 1-5", "skills": ["flo-communication", "flo-team-handoff"],
         "prompt": "Morning command brief for Ashley: call flo_team action=today (top three, fastest win, biggest risk, needs you, waiting on others), check reachable email/calendar, then give it to her in her words: greeting, Top 3, Fastest win, Biggest risk, Needs you, Waiting on others, 'everything else can wait'. Delegate focused follow-ups with flo_handoff only where a specialist is clearly needed, and mention teammates only as small hints."},
        {"name": "Flo midday risk sweep", "schedule": "0 12 * * 1-5", "skills": ["flo-communication"],
         "prompt": "Midday risk sweep: call flo_team action=today. One quick heads-up only if the biggest risk or 'needs you' changed: what, urgent now or urgent tomorrow. Stay silent-short if nothing moved."},
        {"name": "Flo approval queue sweep", "schedule": "0 10,15 * * 1-5", "skills": ["flo-team-approvals"],
         "prompt": "Approval queue sweep: call flo_approvals action=list status=pending. If anything is waiting, summarize each card in one line (bot, action, destination, why) so Ashley can decide. Never decide for her."},
        {"name": "Flo end-of-day team recap", "schedule": "0 17 * * 1-5", "skills": ["flo-communication"],
         "prompt": "End-of-day team recap: call flo_team action=activity limit=60 and action=floor. What moved, what cleared, what is open and on whom, main carryover for tomorrow. Clean summary."},
    ],
    "malcolm": [
        {"name": "Malcolm new-file prep sweep", "schedule": "0 8 * * 1-5", "skills": ["flo-file-prep"],
         "prompt": "New-file prep sweep: call flo_workspace action=list. For any workspace at Intake/Application without a readiness report, prepare a File Prep Report skeleton from the facts present and list what Ashley must supply. Propose only; do not contact anyone."},
        {"name": "Malcolm missing-document refresh", "schedule": "0 13 * * 1-5", "skills": ["flo-file-prep"],
         "prompt": "Missing-document refresh: for each workspace with a readiness report, re-list the missing items and who owns them. Hand the list to Flo with flo_handoff (return_format status_note)."},
    ],
    "chadwick": [
        {"name": "Chadwick outstanding orders sweep", "schedule": "30 8 * * 1-5", "skills": ["flo-order-outs"],
         "prompt": "Outstanding orders sweep: for each workspace, call flo_order action=tracker. Flag anything ordered/pending past its expected turn time as overdue via flo_order transition, and propose the cleanest vendor follow-up as a draft. Never send."},
        {"name": "Chadwick vendor follow-up queue", "schedule": "0 14 * * 1-5", "skills": ["flo-order-outs"],
         "prompt": "Vendor follow-up queue: list overdue orders and prepare one follow-up proposal per vendor for Ashley's approval."},
    ],
    "whisper": [
        {"name": "Whisper inbox action sweep", "schedule": "45 7 * * 1-5", "skills": ["flo-communication", "flo-notes-and-emails"],
         "prompt": "Inbox action sweep: read recent email if reachable (Zapier Gmail find/search only), group what needs a reply by file, and create drafts with flo_draft. Drafting is not sending."},
        {"name": "Whisper milestone update queue", "schedule": "0 11 * * 1-5", "skills": ["flo-compliance-messaging"],
         "prompt": "Milestone update queue: for workspaces whose milestone changed today, prepare borrower-facing drafts using only the approved template wording, and LO/realtor updates in Ashley's voice. Queue them; do not send."},
    ],
    "sage": [
        {"name": "Sage source freshness check", "schedule": "0 7 * * 1", "skills": ["flo-underwriting-sources"],
         "prompt": "Weekly source freshness check: call flo_knowledge action=freshness. Report which official sources are UNKNOWN/STALE_SOURCE and any pending revisions. Never activate anything; recommend the admin review step."},
        {"name": "Sage underwriting question queue", "schedule": "30 9 * * 1-5", "skills": ["flo-underwriting-sources"],
         "prompt": "Underwriting question queue: call flo_handoff action=status. For each open question produce a Guideline Card with flo_guideline_card; SOURCE_GAP is a valid answer. Return results to Flo."},
    ],
    "franklin": [
        {"name": "Franklin weekly content plan", "schedule": "0 9 * * 1", "skills": ["flo-marketing-guardrails"],
         "prompt": "Weekly content plan: call flo_marketing action=calendar, propose this week's social, newsletter, GBP and blog items as ideas/drafts with flo_marketing action=create. Flag every claim that needs an approved source. Nothing publishes without approval."},
        {"name": "Franklin GBP draft queue", "schedule": "0 10 * * 2,4", "skills": ["flo-marketing-guardrails"],
         "prompt": "GBP draft queue: draft one Google Business Profile post from approved educational topics only. No rates, APRs, guarantees, licensing claims or borrower stories. Queue for review."},
    ],
}

POLICY_OVERRIDES = {
    # Capability-policy tightening per role (flo/policy.yaml). Floors stay confirm.
    "malcolm": {"email_send": "deny", "outbound_message": "confirm", "portal_submit": "deny", "drive_share_external": "deny"},
    "sage": {"email_send": "deny", "outbound_message": "confirm", "portal_submit": "deny", "drive_upload": "confirm", "drive_share_external": "deny"},
    "chadwick": {"email_send": "confirm", "outbound_message": "confirm", "portal_submit": "confirm", "calendar_write": "confirm"},
    "whisper": {"email_send": "confirm", "outbound_message": "confirm", "calendar_write": "confirm", "portal_submit": "deny"},
    "franklin": {"email_send": "confirm", "outbound_message": "confirm", "portal_submit": "deny", "drive_upload": "confirm", "drive_share_external": "deny"},
    "flo": {"email_send": "confirm", "outbound_message": "confirm", "portal_submit": "confirm", "external_status_change": "confirm"},
}


def _dump(data) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def render(name: str, spec, team) -> dict[str, str]:
    files: dict[str, str] = {}
    files["distribution.yaml"] = (
        f"# Flo Team profile distribution: {spec.display_name} — {spec.title}.\n"
        f"# Generated by scripts/flo/generate_team_profiles.py from plugins/flo-team/team.yaml; do not edit by hand.\n"
        f"# Install all six with: python scripts/flo/install_flo_team.py\n"
        + _dump({
            "name": name, "version": "0.1.0",
            "description": f"{spec.display_name} — {spec.title}. {spec.description}",
            "hermes_requires": ">=0.21.0", "author": "LoanFlow Processing LLC / Flo Agent team-build pass (2026-09-08)", "license": "MIT",
            "env_requires": [],
            "distribution_owned": ["SOUL.md", "config.yaml", "distribution.yaml", "profile.yaml", "assets", "flo", "skins", "routines.yaml"],
        })
    )
    config = {
        "display": {"personality": "", "skin": "flo", "language": "en"},
        "approvals": {"mode": "smart"},
        "cron": {"allow_agent_scheduling": name == "flo"},
        "memory": {"memory_enabled": True, "user_profile_enabled": True, "write_approval": False},
        "skills": {"write_approval": False, "disabled": sorted(set(ALL_FLO_SKILLS) - set(ROLE_SKILLS[name]))},
        "plugins": {"enabled": ["flo-policy", "flo-team"]},
        "agent": {"disabled_toolsets": DISABLED_TOOLSETS[name], "bot_mode_protocol": True},
        "delegation": {"max_spawn_depth": 1},
        # Zapier: the URL (which carries the token) is injected by the installer
        # from the mirror profile or FLO_ZAPIER_MCP_URL — never stored in git.
        "mcp_servers": {"zapier": {"connect_timeout": 90, "tools": {"include": list(spec.zapier_include), "exclude": sorted(set(spec.zapier_exclude) | {"*api_request*", "*raw_request*", "*webhook_by_zapier*"})}}},
    }
    files["config.yaml"] = (
        f"# {spec.display_name} ({spec.title}) — Flo Team profile config. Generated from plugins/flo-team/team.yaml.\n"
        "# Model/provider and the Zapier MCP url are written by the installer (mirrored from the Ashley profile or env);\n"
        "# they never live in git. Role boundaries (folders, Zapier scope, Franklin's loan-workspace exclusion,\n"
        "# Shadow/Assisted/Trusted) are enforced by plugins/flo-team; this file only pre-filters what the bot sees.\n"
        + _dump(config)
    )
    role_line = spec.description if spec.description.lower().startswith(spec.title.lower()) else f"{spec.title}: {spec.description}"
    files["profile.yaml"] = _dump({
        "display_name": spec.display_name,
        "description": role_line,
        "description_auto": False,
        "ui_meta": {"hermes-bots": {"title": spec.display_name, "description": role_line, "color": spec.color,
                                    "group": team.team_name, "groups": [team.team_name], "pinned": name == team.leader, "custom": True, "imageKind": "photo"}},
    })
    files["flo/policy.yaml"] = (
        f"# Flo capability policy for {spec.display_name}. Loaded by plugins/flo-policy from <HERMES_HOME>/flo/policy.yaml.\n"
        "# Only tightens; irreversible actions can never drop below confirm.\n"
        + _dump({"version": 1, "mass_outbound_threshold": 10, "capabilities": {
            "mass_outbound": "confirm", "drive_share_external": "confirm", "drive_delete_permanent": "confirm",
            "policy_disable": "confirm", "credential_exposure": "confirm", **POLICY_OVERRIDES[name]}})
    )
    files["flo/team-role.yaml"] = (
        f"# {spec.display_name}'s slice of plugins/flo-team/team.yaml (informational copy; the plugin reads the manifest).\n"
        + _dump({
            "name": name, "display_name": spec.display_name, "title": spec.title, "role": spec.role, "reports_to": spec.reports_to,
            "delegates_to": list(spec.delegates_to), "loan_workspace": spec.loan_workspace, "deal_rooms": spec.deal_rooms,
            "folders": {"loans": list(spec.loan_folders), "other": list(spec.other_folders)},
            "zapier": {"include": list(spec.zapier_include), "exclude": list(spec.zapier_exclude)},
            "model_classes": list(spec.model_classes), "external_writes": spec.external_writes,
            "team_autonomy_level": team.autonomy_level, "max_delegation_depth": team.max_delegation_depth,
        })
    )
    files["routines.yaml"] = (
        f"# {spec.display_name}'s routines (Hermes cron jobs in this profile). Created once by the installer; edit in the Cron page.\n"
        "# Every routine is read/analysis + proposal only. External side effects still stop at Ashley's approval.\n"
        + _dump({"routines": ROUTINES[name]})
    )
    files["README.md"] = (
        f"# {spec.display_name} — {spec.title}\n\n{spec.description}\n\n"
        f"Hermes profile distribution for the Flo Team (see `plugins/flo-team/team.yaml`, `FLO_TEAM_BUILD.md`).\n\n"
        "| File | Owner | Purpose |\n|---|---|---|\n"
        "| `SOUL.md` | hand-written | persona (production SOUL from the pack's SOUL_SEED) |\n"
        "| `profile.yaml` | generated | display name, description, Bot Mode `ui_meta` (title/color/group) |\n"
        "| `config.yaml` | generated | skin, approvals, plugins, per-role skills/toolsets, Zapier tool filter (no url) |\n"
        "| `flo/policy.yaml` | generated | Flo capability policy tightening |\n"
        "| `flo/team-role.yaml` | generated | role slice of the team manifest |\n"
        "| `routines.yaml` | generated | cron routines seeded by the installer |\n"
        "| `assets/avatar.png` | generated from `.flo/assets/team/` | Bot Mode avatar (`profiles.get_asset`) |\n"
        "| `memories/USER.md` | hand-written seed, user-owned after install | Ashley profile seed |\n\n"
        f"Reports to: {spec.reports_to or '— (team leader)'}. Delegates to: {', '.join(spec.delegates_to) or '— (returns work to Flo)'}.\n"
    )
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="verify generated files match; exit 1 if not")
    args = parser.parse_args()

    import importlib.util

    spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["flo_team"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    manifest_mod = sys.modules["flo_team.manifest"]
    team = manifest_mod.manifest()

    drift = []
    for name, role in team.profiles.items():
        target = PROFILES_DIR / name
        files = render(name, role, team)
        files["skins/flo.yaml"] = ASHLEY_SKIN.read_text(encoding="utf-8")
        for rel, content in files.items():
            path = target / rel
            if args.check:
                if not path.exists() or path.read_text(encoding="utf-8") != content:
                    drift.append(str(path.relative_to(REPO)))
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        for required in ("SOUL.md", "memories/USER.md", "assets/avatar.png"):
            if not (target / required).exists():
                drift.append(f"{target.relative_to(REPO)}/{required} (hand-written file missing)")
    if args.check:
        if drift:
            print("out of sync:\n  " + "\n  ".join(drift))
            return 1
        print("team profiles in sync")
        return 0
    print(f"generated {len(GENERATED)} files for {len(team.profiles)} profiles under {PROFILES_DIR}")
    if drift:
        print("still missing (hand-written):\n  " + "\n  ".join(drift))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
