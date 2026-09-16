# Flo Team — progress (2026-09-08, Claude Code team-build pass)

Continues `CLAUDE_PROGRESS.md` (bootstrap, owner directives, branding, underwriting architecture). Nothing earlier was discarded; the concurrent writer's files (`AGENTS.md` prefix, `opencode.json`, `.flo/underwriting/*`, `.flo/docs/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md`) were built on, not replaced.

## Done

1. Read the whole `Flo_Team_Agents_Pack` (113 files), upstream `AGENTS.md`, Flo docs, `CLAUDE_PROGRESS.md`, git diff; copied the pack to `.flo/team/pack/`.
2. Mapped Hermes v0.21 Bot Mode primitives in code (profiles, `profile.yaml` ui_meta, `assets/avatar.png`, `message_agent`, group rooms, MCP include/exclude, plugin hooks/tools, cron) — `FLO_TEAM_BUILD.md` §1.
3. Built `plugins/flo-team` (16 modules, 12 tools) and the manifest `team.yaml`.
4. Wrote six SOUL.md files and USER.md seeds; generated the rest of each distribution; installer with credential mirroring, routine seeding, local-model health check and FloWorkspace layout.
5. Nine `skills/flo-team/*` skills (shared: handoff, approvals, provenance; role: file prep, order outs, conditions-to-action, underwriting sources, calc workbench, marketing guardrails). Pass the repo authoring standards.
6. Desktop `flo-team` plugin (Team Floor, Deal Rooms, Approvals, Activity, Pipeline, Knowledge, Health) + data helpers/tests.
7. Integrated the owner-approved visual asset package (portraits, app icon set, brand mark, banner); verified in the running Electron app via screenshots.
8. Installed all six profiles into the real Hermes home (Zapier URL and auth mirrored from `ashley`; routines created; team state root and knowledge registry in place). Bot Mode protocol lists the six teammates.
9. Tests: `tests/flo/test_flo_team.py` (67 cases incl. real installer + real PluginManager), `data.test.ts`; full Flo Python run 1443 passed; desktop typecheck/lint/plugin tests pass (full ui suite + build: see `FLO_TEAM_TEST_RESULTS.md`).
10. Docs: `FLO_TEAM_BUILD.md`, `FLO_TEAM_DECISIONS.md`, `FLO_TEAM_OPEN_QUESTIONS.md`, `FLO_TEAM_SECURITY_REVIEW.md`, `FLO_TEAM_TEST_RESULTS.md`; `CLAUDE.md`, changelog, decision log, open questions updated.

## Environment notes

- Windows 11; Python via `.venv`; Node via winget (PATH must be refreshed per shell); `hermes` CLI = `.venv\Scripts\hermes.exe`.
- The `ashley` profile's mirrored cloud provider (`opencode-free / deepseek-v4-flash-free`, changed since the bootstrap) returned HTTP 400 "Model is unavailable" during the first live handoff attempt; the installer therefore routes local-first roles to Ollama `qwen3-flo:latest` when the health check passes.
- The desktop dev app (Electron, `npm run dev`) was running throughout; HMR picked up the plugins. Renderer screenshots were taken through the dev CDP port.
- Desktop-outside-Electron (plain browser) shows "Desktop IPC bridge is unavailable" — expected; not a defect.

## Blocked / deferred

- Approval Center decisions from the page (needs approval request id exposure; deep-link only).
- Per-LLM-call model routing (would need a `pre_llm_call` implementation).
- Any active underwriting source, production formula, document matrix, vendor directory, template library, brand/compliance sources — all SOURCE_GAP pending owner-supplied material and a rights decision.
- Unsloth Studio endpoint verification (Mac-only in the pack's findings).

## Next (ranked)

See the final report's top-ten list and `FLO_TEAM_OPEN_QUESTIONS.md`.

---

# Golden Loan Path pass (2026-09-08/09)

## Done

1. **Flo personality addendum** applied to `.flo/profile/flo/SOUL.md` and Flo's private `memories/USER.md` only (coffee, SHEIN, gym, family, Jeremy, Lily); specialist profiles untouched; installed.
2. **Fannie source activation**: 12 official Selling Guide sections fetched to a private cache with checksums (`scripts/flo/fetch_fannie_sources.py`), 34 rule records with anchor phrases (`plugins/flo-team/knowledge/fannie/`), lifecycle script (`scripts/flo/activate_fannie_slice.py`), all 12 ACTIVE on this machine (approver `owner`, basis: this directive). `FANNIE_SOURCE_ACTIVATION.md`.
3. **Real Guideline Cards** (`fannie.guideline_card` behind `flo_guideline_card program=fannie`): section-level citations with section date, revision, checksum, official URL; SOURCE_GAP when not active; STALE_SOURCE on cache tampering.
4. **Income calculators**: seven production formulas bound to active sections (`calc.py`); `INCOME_CALCULATOR_STATUS.md`.
5. **Asset workbench** (`assets.py`, `flo_assets`): depository only; `ASSET_WORKBENCH_STATUS.md`.
6. **DU findings** (`du.py`, `flo_du`): verbatim recommendation language, message-vs-file comparison, tolerance check, conflict routing.
7. **File Prep matrix** (`fileprep.py`, `flo_fileprep`): provenance per item, five states.
8. **Golden synthetic loan** fixture with four intentional issues; deterministic whole-team run (`golden_path.py`) covered by `tests/flo/test_golden_loan.py` (23 tests, including a sandbox activation from this machine's cache).
9. **Live model orchestration** on Codex: Flo → Malcolm → Flo and Flo → Sage → Flo completed with model-generated replies; three environment/code defects found and fixed along the way (`LIVE_AGENT_HANDOFF_RESULTS.md`).
10. **Provider discovery** (`providers.py` + `providers.yaml`): endpoint/reachable/model/context/latency/throughput/PII-permission/status per candidate; installer picks per role; `flo_model_health action=discover`.
11. **MCP log redaction** hardened at the core (`agent/redact.py` host registry) + plugin filter + installer; fake-token test scans the log directories (`MCP_LOG_REDACTION_REVIEW.md`).
12. Small upstream patch: `tools/bot_mode_dm.py` delivery cwd fallback (repo path with an apostrophe blocked every delivery).

## Not done / partial (Golden Loan Path pass)

- Whisper's draft step ran deterministically, not as a live model turn (exercised live in the program-expansion pass).
- Announcement-level effective dates per rule; internal LoanFlow document list; property/appraisal; overlays.
- All profiles currently run on a cloud model (see open question #20).

---

# Program expansion pass (2026-09-09)

Checkpoint before the pass: `a8b130c8e776f94d8f35791780c8b9fcaa9af74c` (tag `flo/fannie-golden-loan-path-2026-09-09`); the activated Fannie rules were not modified. Code checkpoint of this pass: `11f98d7197`.

## Done

1. **Program-agnostic source layer** (`plugins/flo-team/sources.py`): cache/checksum/rule records/regression/lifecycle/effective dates/in-force flag/program- and method-scoped matching; `fannie.py` delegates unchanged. `MULTI_PROGRAM_SOURCE_REGISTRY.md`.
2. **Official sources captured** privately: Freddie (Guide JSON API, 21 sections with the Guide's own published/effective dates and versions), FHA (Handbook 4000.1 Update 18 PDF, 8 heading-located slices), VA (Chapter 4 from KnowVA's article API), USDA (HB-1-3555 chapter PDFs, 7 slices). Fetchers in `scripts/flo/`.
3. **Rule records with anchors**: Freddie 36, FHA 31 (`fha.total.*` / `fha.manual.*`), VA 20, USDA 20; every anchor verified against the cached text; activated on this install through the generalized lifecycle (`scripts/flo/activate_sources.py --program …`) with the structured approval identity (`identity.py`); Fannie approval records migrated.
4. **Calculators**: Freddie 6, FHA 9 (4 TOTAL + 5 Manual), VA 4 (residual tables parsed from official text), USDA 4 (annual / adjusted annual / repayment / ratios); program- and method-bound, fail closed on mismatch. `INCOME_CALCULATOR_STATUS.md` remains the Fannie status.
5. **AUS envelope** (`aus.py`, `AUS_NORMALIZATION.md`), **standard Guideline Card** with progressive disclosure (`cards.py`), program-aware **asset workbench** and **File Prep matrix** with `<program>:<section>` provenance, program-aware **golden path**.
6. **Four synthetic golden loans** (Synthetic-Bellamy, -Okafor, -Reyes, -Lindqvist), each with intentional defects from activated rules only; deterministic whole-team runs green (`CROSS_PROGRAM_REGRESSION_RESULTS.md`).
7. **Self-employed and rental** data structures (`income_structures.py`) with SOURCE_GAP calculation entry points; no formulas.
8. **Live validations** per program on Nous Portal (Codex hit its usage limit): `LIVE_AGENT_HANDOFF_RESULTS.md`.
9. Docs: `FREDDIE_GOLDEN_LOAN_PATH.md`, `FHA_GOLDEN_LOAN_PATH.md`, `VA_GOLDEN_LOAN_PATH.md`, `USDA_GOLDEN_LOAN_PATH.md`, `MULTI_PROGRAM_SOURCE_REGISTRY.md`, `AUS_NORMALIZATION.md`, `CROSS_PROGRAM_REGRESSION_RESULTS.md`, `PROGRAM_EXPANSION_PROGRESS.md`.

## Not done / partial

- FHA: only the Update 18 text (effective 11/10/2026) is cached; the currently in-force version is SOURCE_GAP (open question #25). *Resolved in the reliability pass below.*
- Freddie context-only sections (5302.1/.3-.6, 5303.2-.4, 5401.1, 5102.3) and USDA 9.4 have no rule records and stay `pending_review`.
- VA/USDA pay-period conversion, taxes, area income limits and deduction amounts are inputs, not activated rules.
- Non-QM / Jumbo / investor-specific underwriting: not started, by instruction.

# Reliability hardening pass (2026-09-09)

No new program. Summary and completion-standard check: `FLO_RELIABILITY_HARDENING.md`; scenario-by-scenario results: `RELIABILITY_REGRESSION_RESULTS.md`.

## Done

1. FHA Update 17 captured beside Update 18; versioned sections/rules; `resolve_rule` by case number assignment date; cards label CURRENT / FUTURE — NOT YET EFFECTIVE (`FHA_EFFECTIVE_DATE_TESTS.md`).
2. Source-bound Sage prose with a post-generation validator and handoff enforcement (`SOURCE_BOUND_RESPONSE_ARCHITECTURE.md`).
3. Draft and side-effect idempotency through the intent registry (`ACTION_IDEMPOTENCY.md`).
4. Provider state machine, preflight board, stalled-task resume, fail-closed sensitive route (`PROVIDER_FAILOVER.md`).
5. Knowledge Center (CLI + desktop tab), source diff, rule impact, overlays (empty), guidance capture, structured audit identity (`KNOWLEDGE_CENTER.md`, `SOURCE_DIFF_AND_IMPACT.md`).
6. 99 new tests; 309 passed overall; live Flo→Sage FHA run proved build → validate → rewrite → validated close with CURRENT/FUTURE labels.

## Not done / partial

- Failover is between turns (`flo_workflow check/resume`), not inside a running LLM call.
- No approved sensitive-data route exists on this machine (local model too slow, cloud routes `pii_allowed: false`): real borrower files fail closed by design.
- Knowledge Center actions copy administrator commands; execution stays in the terminal with an approver identity.
- The validator is lexical; semantic misuse of a supported number is not detected.
- Non-QM / Jumbo / DSCR / bank-statement / foreign-national / ITIN, full self-employed/rental, and Trusted autonomy: untouched, by instruction.

# Website loan intake (2026-09-09)

lfprocessing.net Loan Submission v2 (website repo, branch `feature/loan-submission-v2`) → `scripts/flo/intake_server.py` → `plugins/flo-team/intake.py` (Deal Room + Malcolm task, idempotent) → Flo dispatch → Malcolm review → Ashley's Pipeline. End-to-end proven locally with two synthetic loans, including the Flo-unavailable retry path. Production still needs: a private tunnel from the website host to Ashley's machine, the intake as a service with `FLO_INTAKE_TOKEN`, a Node host for the site's API, and secure document storage (uploads are UI-only). Details: website repo `FLO_INTAKE_INTEGRATION.md`.

# Ashley UX simplification pass (2026-09-09)

Owner directive mid-phase: make Flo as easy as possible for Ashley; hide, do not remove, the machinery. Details: `ASHLEY_UX_SIMPLIFICATION.md`.

## Done

1. One desktop plugin (`apps/desktop/src/plugins/flo/`): Today (home), Pipeline with a one-summary file view and one-click actions, Approvals with plain cards, Advanced page for admin (not in the sidebar).
2. Plain-English status and Today rules in TS (`ashley.ts`, 12 tests) and Python (`today.py`, 5 tests); `flo_team action=today|file_summary` for Flo's answers to "what next?" and "where are we on X?".
3. Flo SOUL and morning/midday routines updated for the one-assistant experience; synced to the installed profile.

## Deferred (started, not delivered) — the provider/data-classification + Income Lab phase

Investigation only, no code: (a) Bot Chat pinning root cause is `cli.py::_restore_session_model` restoring the session row's model/provider on `-c "Bot Chat"`; the fix belongs in a small core patch that consults a Flo router hook or a config flag. (b) This Windows host has no M1 Max, no NVIDIA GPU and 32 GB RAM; Ollama serves `qwen3:8b` / `qwen3-flo` (TOO_SLOW) and no Unsloth/LM Studio endpoint is up, so the local benchmark must run on the Mac. (c) Cached official text already covers overtime/bonus/commission for Fannie (B3-3.3-02), FHA (II.A.4.c both versions), VA (Chapter 4) and USDA (9-A); Freddie 5303.3 is the temporary-leave section and 5303.4/5303.5 need fetching before Freddie additional-income rules can be anchored. Data classification, provider policy registry, task routing, Income Lab, Ask Sage packet (now the Why? button prompt), coverage matrix and the ten deliverables of that phase are not started.
