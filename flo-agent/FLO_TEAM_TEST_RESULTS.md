# Flo Team — test results (2026-09-08, Windows 11, Python 3.11 venv, Node 24)

All data synthetic. Commands run from the repository root unless noted; PowerShell needs the user PATH refreshed for `npm`/`node`, and Python suites run with `TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTHONUTF8=1`.

## Python

| Suite | Command | Result |
|---|---|---|
| Flo Team | `pytest tests/flo/test_flo_team.py` | **67 passed** |
| Flo Team + Ashley profile + Flo policy + Flo mortgage skills + repo-wide skill authoring standards | `pytest tests/flo tests/plugins/test_flo_policy_plugin.py tests/skills/test_flo_mortgage_skills.py tests/skills/test_authoring_standards.py` | **1443 passed, 0 failed** (164 s) |

Coverage map for the build prompt's list (all in `tests/flo/test_flo_team.py`):

| Requirement | Test(s) |
|---|---|
| Correct routing / delegation edges | `TestManifest::test_delegation_edges`, `test_six_profiles_match_pack_manifest` |
| Out-of-role refusal / handoff | `TestHandoff::test_specialist_to_specialist_is_refused`, `TestSpecialistTools::test_franklin_cannot_use_workspace_tools`, `handle_flo_marketing` role check |
| Cross-agent handoff schema | `test_flo_to_specialist_packet_validates_against_schema` (pack `handoff.schema.json` required keys) |
| Max delegation depth | `test_max_delegation_depth`, `test_cancel_tree_and_status` |
| Ashley approval binding | `TestApprovalCenter::test_binding_and_material_edit_invalidates`, `test_only_humans_decide`, `test_close_only_from_execution` |
| Prompt injection | `test_prompt_injection_in_facts_changes_nothing`, approval source rejection |
| Source gaps | `test_guideline_card_source_gap_and_layers`, `test_calc_deterministic_trace` (TEST_ONLY → SOURCE_GAP) |
| Underwriting source conflicts | `test_source_conflict_recorded_not_resolved`, `test_active_source_yields_citation` |
| Local-provider health failure | `TestModels::test_health_check_fails_on_context`, `test_health_check_unreachable`, `test_sensitive_never_falls_back_to_cloud` |
| Marketing borrower-folder denial | `TestRolePolicy::test_franklin_structurally_denied_borrower_folders`, `TestWorkspace::test_membership_and_franklin_exclusion`, `test_franklin_never_receives_a_workspace`, real-manager test |
| Draft vs sent | `test_draft_is_never_sent_without_execution_ref`, `test_result_cannot_claim_sent_without_execution_ref`, orders `ordered` needs execution_ref, marketing `published` needs execution_ref |
| File Readiness ≠ approval | `test_readiness_is_not_approval` |
| Zapier action scoping | `test_zapier_scopes`, `test_zapier_availability_does_not_override_policy`, `test_zapier_filters_match_manifest` |
| Role folder boundaries | `test_folder_boundaries`, `test_role_decisions` (intake write denied, delete denied) |
| Non-QM without source | `test_non_qm_requires_investor_source` |
| Citations | `test_active_source_yields_citation` (section + effective date), card layers |
| Knowledge lifecycle (bot cannot activate) | `test_knowledge_lifecycle_bot_cannot_activate` |
| Autonomy levels | `test_autonomy_levels` (shadow deny, assisted confirm, trusted allow-listed) |
| Distributions: no secrets, Bot Mode meta, avatar < 2MB, generated files in sync, config keys exist upstream | `TestProfiles::*` |
| Real installer + real `PluginManager` load and enforcement | `TestRealInstall::*` (installs into a temp HERMES root, Bot Mode probe lists all teammates, second run idempotent) |
| Hooks end-to-end | `TestHooks::*` (card filed on CONFIRM, closed on result, inert outside team profiles, fail-closed) |

## Desktop (`apps/desktop`)

| Check | Result |
|---|---|
| `npm run typecheck` (renderer, electron, e2e tsconfigs) | PASS |
| `npx eslint src/plugins/flo-team src/plugins/flo` | 0 errors, 0 warnings after fixes; repo-wide `npm run lint`: 0 errors (127 pre-existing warnings elsewhere) |
| `npx prettier --check src/plugins/flo-team src/plugins/flo` | PASS |
| `npx vitest run --project ui src/plugins/flo-team src/plugins/flo` | 3 files, 11 tests passed |
| `npx vitest run --project electron electron/flo-brand.test.ts electron/flo-release-channel.test.ts` | 2 files, 13 tests passed |
| Full `npx vitest run --project ui` | see "Full desktop suite" below |
| `npm run build` | see "Full desktop suite" below |

## Live checks (real install on this machine)

- `python scripts/flo/install_flo_team.py --workspace %USERPROFILE%\FloWorkspace`: six profiles installed/updated; Zapier URL mirrored (scoped); `auth.json` mirrored; 14 routines created; FloWorkspace created; knowledge registry copied.
- Local model health (all six): `reachable; model listed as qwen3-flo:latest; context 65536 >= 65536; smoke completion ok` → every role's first class is local, so all six profiles were pointed at Ollama `qwen3-flo:latest`.
- Hermes Bot Mode probe on the installed home: `is_bot_mode_managed` = True; the protocol roster lists `@flo @malcolm @chadwick @whisper @sage @franklin` with their titles.
- Real `PluginManager` in the installed Sage profile: `flo-policy` and `flo-team` load; `flo_*` tools registered; `mcp__zapier__gmail_send_email` → block (out of scope for Sage); `write_file` into `loans/*/intake` → block; reads in `loans/*/income` → allowed.
- Desktop (Electron dev build, screenshots via the dev CDP port): Bots pane shows the six profiles with the approved avatars and a "Flo Team" group of 6; `/flo-team` shows banner, roster with circular portraits, tabs; `/flo` shows the new Flo face.
- Live bot-to-bot handoff (Flo Bot Chat → `flo_workspace` → `flo_handoff` → `message_agent` → Malcolm): see "Live handoff" below.

## Full desktop suite

- `npm run lint` (repo-wide): 0 errors, 127 pre-existing warnings (none in `src/plugins/flo*`).
- `npm run build` (renderer + electron bundle + native deps staging): **PASS** (`assert-dist-built` OK).
- `npx vitest run --project ui` (full, 691 files / 6819 tests): ran while the CPU-only local model was mid-inference (see "Live handoff"); result **6782 passed, 20 failed, 17 skipped, 637 s** with environment/setup time ~5× normal. Re-running the reported failing files in isolation: `src/app/skills/index.test.tsx` **8/8 passed**; `src/plugins/hermes-bots/cron-prompt.test.ts` 1 failed — the pre-existing Windows `cron-prompt` failure recorded at baseline (`CLAUDE_PROGRESS.md` §1.3). The remaining load-induced failures were not re-run individually; the same tree passed 6810/6811 earlier today before the team plugin was added, and the team plugin's own 6 tests pass. Treat the 20 as environmental until a quiet-CPU rerun (top-ten item).
- `npx vitest run --project electron electron/flo-*.test.ts`: 13/13 passed. The stock electron project still has the 34 documented Windows POSIX-assumption failures; not re-run.

## Live handoff

**Model-driven run: not completed.** `hermes -p flo chat -c "Bot Chat" -Q --query-file …` (Flo asked to create a synthetic workspace, build a handoff with `flo_handoff`, and send it to Malcolm with `message_agent`):

- Attempt 1 on the mirrored cloud provider (`opencode-free / deepseek-v4-flash-free`, as currently configured on the `ashley` profile): `HTTP 400: Model is unavailable`.
- Attempt 2 on the local Ollama model (`qwen3-flo:latest`, CPU only, no GPU on this machine): the first turn (system prompt + 21 visible tools + Zapier MCP catalog, ~20K tokens) did not return within 20 minutes; run stopped. Bot-to-bot delivery therefore was **not observed end to end** in this session.

**Deterministic transport verification (real installed profiles, no model):**

- Bot Mode gate: `is_bot_mode_managed(<flo profile>)` = True; `message_agent` tool present with local-target syntax accepting `malcolm`; each profile's Bot Chat prompt lists the other five teammates with roles.
- As `flo` through the real `PluginManager`-registered tools: `flo_workspace create` → `loan_0b3fc921a841`, members `[flo, whisper]`, excluded `[franklin]`; `flo_handoff create to=malcolm` → `task_3a2c98f61f51`, depth 1, returns `send_with: {tool: message_agent, target: malcolm, message: <packet>}`; `to=franklin` with a workspace → refused ("structurally excluded").
- As `malcolm`: `flo_handoff receive` parsed the packet (status `sent`, reminder that the packet grants nothing); `flo_handoff complete` with `external_action_status: sent` and no `execution_ref` was stored as `proposed`.
- The records appear on the desktop Team page (Deal Rooms / Activity) from the shared team root.

What remains unproven live: the `message_agent` delivery itself (upstream's `hermes -p malcolm chat -c "Bot Chat" … -Q` spawn) and a specialist's own reply, both of which need a responsive model. Top-ten item 1.

## Golden Loan Path pass (2026-09-08/09)

| Suite | Result |
|---|---|
| `tests/flo/test_golden_loan.py` (sources/rules, calculators, assets, DU, matrix, sandbox-activated whole-team run, cache tampering, providers) | **23 passed** (the two sandbox tests copy this machine's private cache; they skip elsewhere) |
| `tests/flo/test_mcp_log_redaction.py` (fake token: core registry, real Hermes logging into a temp home + log-dir scan, installer) | **3 passed** |
| `tests/flo/test_bot_mode_delivery_workdir.py` | 2 passed |
| `tests/flo/test_flo_team.py` (updated calc test) | 67 passed |
| Everything Flo + skill standards + upstream redaction tests (`tests/agent/test_redact.py`, `tests/test_redaction_registry.py`, `tests/hermes_cli/test_redact_config_bridge.py`) | **1592 passed, 0 failed** (59 s) |
| Live model runs | see `LIVE_AGENT_HANDOFF_RESULTS.md` (Flo→Malcolm→Flo, Flo→Sage→Flo passed with model replies) |
| Clean desktop rerun | see `FULL_TEST_RERUN.md` |

## Program expansion pass (2026-09-09)

| Suite | Result |
|---|---|
| `tests/flo/test_program_expansion.py` (registry/rules per program, Freddie/FHA/VA/USDA calculators, cross-program isolation matrix, AUS envelope, standard card, identity, income structures, sandbox-activated whole-team runs for Freddie, FHA, VA, USDA) | **47 passed** |
| `tests/flo/test_golden_loan.py` (Fannie, unchanged behaviour behind the refactor) | 23 passed |
| `tests/flo` in full | **152 passed** |
| `tests/plugins` + `tests/skills` | 3629 passed, 23 failed — all environmental on this Windows host in untouched plugins (see the baseline note in `CROSS_PROGRAM_REGRESSION_RESULTS.md`) |
| Rule anchors vs cached official text (`activate_sources.py --review`) | Freddie 12/12 rule-bearing sections, FHA 8/8, VA 1/1, USDA 6/6 green |
| Live model runs per program | see `LIVE_AGENT_HANDOFF_RESULTS.md` §§ Freddie, FHA, VA, USDA |

## Known pre-existing failures (unchanged, not Flo regressions)

- Stock Windows failures documented in `CLAUDE_PROGRESS.md` §1.3 (34 electron POSIX-assumption tests, 1 ui `cron-prompt` spawn test, 3 Python files needing symlink privilege / POSIX wrappers).
