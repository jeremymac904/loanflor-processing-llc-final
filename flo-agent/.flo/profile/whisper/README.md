# Whisper — Processing Assistant

Processing Assistant: inbox triage, borrower/LO/lender drafts, milestone updates, condition translation.

Hermes profile distribution for the Flo Team (see `plugins/flo-team/team.yaml`, `FLO_TEAM_BUILD.md`).

| File | Owner | Purpose |
|---|---|---|
| `SOUL.md` | hand-written | persona (production SOUL from the pack's SOUL_SEED) |
| `profile.yaml` | generated | display name, description, Bot Mode `ui_meta` (title/color/group) |
| `config.yaml` | generated | skin, approvals, plugins, per-role skills/toolsets, Zapier tool filter (no url) |
| `flo/policy.yaml` | generated | Flo capability policy tightening |
| `flo/team-role.yaml` | generated | role slice of the team manifest |
| `routines.yaml` | generated | cron routines seeded by the installer |
| `assets/avatar.png` | generated from `.flo/assets/team/` | Bot Mode avatar (`profiles.get_asset`) |
| `memories/USER.md` | hand-written seed, user-owned after install | Ashley profile seed |

Reports to: flo. Delegates to: — (returns work to Flo).
