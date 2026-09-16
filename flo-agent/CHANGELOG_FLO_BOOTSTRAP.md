# Flo bootstrap change log

## 2026-09-10 — Electronic signatures via Documenso (Sonnet 5)

Owner decision: Documenso, self-hosted Community Edition. Ashley's flow stays in Flo: open loan → select
document → **Send for Signature** (`apps/desktop/src/plugins/flo/pipeline.tsx` `SendForSignaturePanel`,
inline in the existing Documents section, no new dashboard) → review recipients/message → confirm; the
actual send is a normal Yellow tool call (`flo_esign_send`, `roles.EXTERNAL_TOOLS`) that stops at Ashley's
existing native approval prompt, bound to the exact document/recipients/message (`approvals_center.py`
`MATERIAL_ARG_KEYS` extended by three keys) and protected from double-sends by the *existing* tool-call
`IntentRegistry` — no new approval system. `plugins/flo-team/esign.py` (new): a thin adapter to Documenso's
current Envelope API v2 (`/template/use`, `/api/v2/envelope/distribute|{id}|item/{id}/download`), a
signature-request store, and status/retrieve/remind/cancel/poll_all/webhook-reconcile logic; completed PDFs
+ evidence are filed into the *existing* `documents.DocumentStore` (no new storage). `flo_esign` /
`flo_esign_send` / `flo_esign_remind` / `flo_esign_cancel` tools, Franklin excluded like every other loan
tool. `scripts/flo/intake_server.py` gained `POST /intake/esign-webhook` and a startup + periodic catch-up
sweep so a borrower who signs while Flo is closed still gets filed. Website (`loanflow-site`) gained
`POST /api/esign-webhook` (verifies Documenso's `X-Documenso-Secret`, dedupes, forwards only the envelope id
over the existing private Flo channel — Documenso API credentials never touch the website). Tests:
`tests/flo/test_esign.py` (23) against `tests/flo/mock_documenso.py` (a local stand-in for Documenso's API,
clearly not the real product), `test_intake.py` webhook-endpoint cases, `server/esignWebhook.test.js` (7),
`ashley.test.ts` esign cases (6) — 350 Flo Python / 19 website / 28 desktop-plugin tests all green. **Not
verified against a live Documenso instance**: this sandbox has no Docker/Postgres, and installing Docker
Desktop needs WSL2/Hyper-V + a reboot (a system-level change requiring explicit approval, not attempted
autonomously). See `FLO_ESIGN.md` for the full verified-vs-inferred API breakdown and what a follow-up
session with Docker available should do to finish proving this live.

## 2026-09-09 — Secure document intake (Fable 5.1)

- `plugins/flo-team/documents.py` (new): pulls every website document through the authenticated connector at intake, keeps a private copy under `<hermes root>/flo/documents/<workspace>/<category>/[borrower]/<clean name>` (sha256 verified, original bytes untouched), extracts the PDF text layer to a sidecar, flags `Page N of M` gaps (`missing_pages`), marks checksum duplicates (kept, never deleted), fills blank subtypes by keyword (LO choice never overridden), and builds the inventory: *required* only behind an ACTIVE source rule, otherwise a clarification with `SOURCE_GAP`.
- `intake.py`: `receive` ingests `documentRefs[].fetchUrl` (token `FLO_INTAKE_TOKEN`), writes `document_refs` + `documents_summary`, adds the inventory to Malcolm's facts; `ashley_line` "New loan came in — Johnson. / 12 documents came with it. / Malcolm is reviewing everything now. 💚". Sensitive-data scan no longer trips on hex ids / storage keys.
- `flo_documents` tool (list · get bounded text · update metadata/status · inventory · add from Ashley's machine · refetch); borrower-data roles only. Malcolm/Flo SOULs: document review behaviour and the after-review line "Johnson is reviewed. / 12 documents received. / We're missing 2 items. / Biggest blocker: Most recent paystub. / Best next move: Request the missing docs.".
- Desktop: NEW LOAN card shows the document count; file view **Documents** section (grouped ✓/⚠, missing list, Upload Missing Doc, Request From Borrower, View Documents) and a per-document preview (PDF/image, Open / Download / Mark Not Needed / Reclassify) — no storage keys or ids shown.
- Tests: `tests/flo/test_documents.py` (5), intake tests updated; desktop `ashley.test.ts` documents case. End-to-end evidence in the website repo's `DOCUMENT_INTAKE_TEST_RESULTS.md`.

## 2026-09-09 — Website loan intake (Fable 5.1)

- `plugins/flo-team/intake.py` + `flo_intake` tool + `scripts/flo/intake_server.py`: lfprocessing.net submissions (schema 1.0) become a Deal Room (milestone Intake, `submission` block, listed document refs) and one Malcolm file-prep task, idempotent per submission id, NPI refused; Flo dispatches the packet and tells Ashley "NEW LOAN — …". Malcolm's readiness report marks the submission reviewed and replaces the placeholder next step.
- Today/Pipeline: "NEW LOAN" pill and "New loan from <LO> • Purchase • FHA • Expected close … Malcolm is reviewing the file." until the review lands (TS + Python).
- Tests: `tests/flo/test_intake.py` (7); end-to-end run documented in the website repo's `LOAN_SUBMISSION_TEST_RESULTS.md`.

## 2026-09-09 — Ashley UX simplification pass (Fable 5.1)

- Desktop: the `flo` and `flo-team` plugins merged into one `apps/desktop/src/plugins/flo/` plugin. Sidebar reduced to Today (home: Top 3, fastest win, biggest risk, needs you, waiting on others, team hints, three primary actions), Pipeline (plain rows → one file summary with Request From Borrower / Order Title / Order HOI / Ask Flo / Why? and expandable Documents, Income & Assets, Conditions, Orders, Communication) and Approvals (what will happen / to / Flo proposes / preview / Approve / Edit / Not Now). Team Floor, Deal Rooms (raw), Activity, Sources, Knowledge Center and Providers moved to an Advanced page that is not in the sidebar.
- Plain-English status vocabulary (Done / Needs Ashley / Waiting / Working / At Risk / Blocked) and the Today rules implemented twice on purpose — `ashley.ts` for the screens and `plugins/flo-team/today.py` for Flo's chat (`flo_team action=today|file_summary`) — with matching tests.
- Flo SOUL: one assistant; Ashley never names a bot; Why? → Sage silently; Request/Order are buttons; no internal machinery in her view. Morning/midday routines call `flo_team action=today`.
- `ASHLEY_UX_SIMPLIFICATION.md` documents what was removed, combined and hidden, and what still feels complicated.

## 2026-09-09 — Reliability hardening pass (Fable 5.1)

- FHA Handbook 4000.1 Update 17 (in force) captured beside Update 18 (mandatory 11/10/2026); version-qualified section keys and rule records; deterministic `resolve_rule` by case number assignment date with CURRENT / FUTURE — NOT YET EFFECTIVE / SUPERSEDED / early-implementation labels on cards.
- Source-bound Sage responses (`sage_response.py`, `flo_sage_response`): retrieval → bound object → validator → rewrite; guideline_card handoffs close only with a validated response id.
- Idempotency: intent registry (`intents.py`) for drafts, orders, marketing content and every CONFIRM-gated external tool call; duplicate executed payloads are blocked at the executor gate.
- Provider routing state machine (`provider_state.py`), workflow preflight/readiness board, stalled-task detection and mid-chain resume on another approved provider (`workflow.py`, `flo_workflow`); sensitive files fail closed with "AI provider unavailable — your work is saved."
- Knowledge Center (`knowledge_center.py`, CLI, desktop tab), source diff (`sourcediff.py`; fetchers snapshot before re-recording), rule impact analysis (`impact.py`), overlay architecture (`overlays.py`, empty by design), human guidance capture (`guidance.py`, `flo_guidance`), structured audit identity on every approval record.
- Tests: `test_fha_effective_dates.py`, `test_source_bound_response.py`, `test_idempotency.py`, `test_provider_failover.py`, `test_reliability_regression.py`; Flo suites 309 passed; desktop typecheck/lint/vitest green. Live Flo→Sage FHA run validated on Nous/Codex. Docs: `FLO_RELIABILITY_HARDENING.md` and the seven deliverables it lists.

## 2026-09-09 — Program expansion pass (Fable 5.1)

- Program-agnostic source layer (`plugins/flo-team/sources.py`); Fannie delegates unchanged; Freddie/FHA/VA/USDA official sources captured to the private cache with checksums, rule records with verified anchors, structured approval identity (`identity.py`), generalized activation (`scripts/flo/activate_sources.py`).
- Program- and method-bound calculators (`freddie.*`, `fha.total.*`, `fha.manual.*`, `va.*` with residual income tables read from the official text, `usda.*` with annual/adjusted/repayment income kept distinct); fail closed on program mismatch.
- AUS envelope (`aus.py`), standard Guideline Card (`cards.py`), program-aware asset workbench, File Prep matrix and golden path; self-employed/rental data structures (`income_structures.py`, formulas SOURCE_GAP).
- Four synthetic golden loans, `tests/flo/test_program_expansion.py` (47), all Flo suites green; docs: `PROGRAM_EXPANSION_PROGRESS.md`, `MULTI_PROGRAM_SOURCE_REGISTRY.md`, `AUS_NORMALIZATION.md`, `CROSS_PROGRAM_REGRESSION_RESULTS.md`, four `*_GOLDEN_LOAN_PATH.md`.
- Live validations routed through Nous Portal after Codex hit its usage limit; `nous_portal` added to provider discovery.
## 2026-09-08

- Established downstream branch at official Hermes v2026.8.31; preserved upstream runtime, branding and license.
- Copied starter documentation/config/source references to canonical `.flo/` context.
- Added shared project context and Development Agent Toolchain design, thin CLAUDE.md and Flo AGENTS.md prefix.
- Added versioned OpenCode configuration with explicit canonical instructions and analysis-only initial permissions; .gitignore exception permits this reviewed config only.
- Installed official stable OpenCode; reused existing official Codex and Claude binaries; made user PATH entries available for fresh terminals.
- Started stock Desktop baseline installation/checks. No coding-agent runtime adapters, production capabilities, credentials, pushes or deployments added.

## 2026-09-08 — Claude Code bootstrap pass (Fable 5.1)

### Phase 0
- Installed Git 2.55, Node 24.19 (winget), Python 3.11.9, uv 0.12.10; created `.venv` with `uv sync --extra dev --extra mcp`; unshallowed the clone (full upstream history and tags for future merges).
- Re-verified baseline on stock code: desktop typecheck PASS, `test:ui` 6803/6804 (1 pre-existing Windows failure), Python subset run with the upstream per-file runner (3 stock files fail on native Windows: symlink privilege / POSIX-only wrapper tests).

### Phase 1 — thin distribution
- `apps/desktop/flo/brand.config.json` + `flo/brand.ts`: single source of truth for visible identity; `flo/release-channel.ts`: updater policy (disabled by default, upstream remote always refused).
- Rebranded package metadata, exe identity, window titles, About panel, notification title, wordmark, deep-link scheme (`flo://`), and every locale string via a boundary transform (`src/i18n/flo-rebrand.ts`) — upstream catalogs untouched.
- Gated `checkUpdates`, `applyUpdates` and the bootstrap install-script download; added invariant tests (`electron/flo-brand.test.ts`, `electron/flo-release-channel.test.ts`, `src/i18n/flo-rebrand.test.ts`).
- `.flo/HERMES_REFERENCE_INVENTORY.md`: classified inventory of remaining Hermes references.

### Phase 2 — Ashley + Flo
- `.flo/profile/ashley/` profile distribution: Flo `SOUL.md`, safe `config.yaml` (no shell/browser/computer-use/delegation/cron, manual approvals, Flo policy plugin on), `flo/policy.yaml`, `skins/flo.yaml`, `memories/USER.md` seed; installer `scripts/flo/install_ashley_profile.py`; tests `tests/flo/`.
- Seven source-backed skills under `skills/flo-mortgage/` with provenance, review date, SOURCE_GAP and prohibited-inference sections; tests `tests/skills/test_flo_mortgage_skills.py`.

### Phase 3 — policy / audit contracts
- `plugins/flo-policy/`: capability classification, allow/confirm/deny table with floors, `pre_tool_call` enforcement through Hermes' human-approval gate, approval binding (single-use, expiring, exact-proposal hash), execution gate, redacting JSONL audit log, Google connector contract scaffold; tests `tests/plugins/test_flo_policy_plugin.py`.
- Root `CLAUDE.md` expanded with Flo facts, locations and working rules; decision log and open questions updated.

## 2026-09-08 — owner directive: least restrictive for Ashley
- Ashley profile: full stock toolset, `approvals.mode: smart`, no lock-downs; Flo policy is audit + one click before irreversible actions only.
- New desktop plugin `apps/desktop/src/plugins/flo/` (Flo home page: six work-mode buttons, recent activity, sidebar + palette entries, first-launch landing).
- Installer creates the morning-brief and end-of-day-recap routines (Hermes cron) in the profile.
- Stock `google-workspace` skill is the Google path.

## 2026-09-08 — branding, local models, Zapier
- Owner branding sheet cut into app assets (`scripts/flo/build_brand_assets.py`): Flo badge app icon (png/ico/icns), Flo face brand mark, LoanFlow logo; publisher = LoanFlow Processing LLC.
- `flo-desktop` theme (green/gold/cream, light+dark) registered by the Flo plugin, applied on first launch; Flo home header shows the badge.
- Zapier MCP added to the installed profile (104 tools); Ollama + `qwen3-flo` (64K ctx) as a local provider.

## 2026-09-09 — Golden Loan Path (Fannie vertical slice)

- Flo personality addendum (Flo SOUL + private USER.md only).
- Official Fannie Selling Guide sections (12) fetched to a private cache with checksums; rule records with regression anchors; lifecycle script; all active on this machine under the owner's directive. Section-level Guideline Cards, seven production income/asset/DU formulas, asset workbench, DU review, File Prep matrix, golden synthetic loan, deterministic whole-team run and tests.
- Provider discovery/routing (`providers.py/.yaml`), throughput-aware local health; all six profiles on Codex here.
- Core patches: `agent/redact.py` credential-URL host registry (+ plugin filter, fake-token log-scan test); `tools/bot_mode_dm.py` delivery cwd fallback.
- Live Flo→Malcolm→Flo and Flo→Sage→Flo model runs passed. Reports: `FLO_GOLDEN_LOAN_PATH.md`, `FANNIE_SOURCE_ACTIVATION.md`, `INCOME_CALCULATOR_STATUS.md`, `ASSET_WORKBENCH_STATUS.md`, `LIVE_AGENT_HANDOFF_RESULTS.md`, `MCP_LOG_REDACTION_REVIEW.md`, `FULL_TEST_RERUN.md`.

## 2026-09-08 — Flo Team (six Bot Mode profiles)

- `plugins/flo-team/`: team manifest, role-policy `pre_tool_call`/`post_tool_call` overlay (folders, Franklin exclusion, Zapier scope, delegation, Shadow/Assisted/Trusted), Approval Center queue, structured handoffs with depth-1 recursion protection, Loan Workspaces/Deal Rooms, File Readiness, order/draft/marketing state machines, citation-capable Guideline Cards over a metadata-only source registry, deterministic Calculation Workbench (TEST_ONLY formulas), local-model adapter with five-check health probe and fail-closed routing; twelve `flo_*` tools.
- Six profile distributions `.flo/profile/{flo,malcolm,chadwick,whisper,sage,franklin}/` (SOUL.md, Bot Mode `profile.yaml`, config with per-role skills/toolsets/Zapier filter, policy, routines, avatar); generator + installer scripts; nine `skills/flo-team/*` skills.
- Desktop `flo-team` plugin: Team Floor, Deal Rooms, Approval Center, Activity, Pipeline heat map, Knowledge freshness, Health.
- Owner-approved visual assets integrated: six portraits (circular crops), app icon (png/ico/icns), brand mark, Flo home badge, team banner. Replaces the interim generated portraits.
- Tests: `tests/flo/test_flo_team.py` (67), `apps/desktop/src/plugins/flo-team/data.test.ts`. Reports: `FLO_TEAM_*.md`.

## 2026-09-08 — underwriting architecture

- Added first-class Underwriting Knowledge Architecture and preserved original owner requirements.
- Established five inactive agency packs, 11 official discovery records, lender/investor extension structure and 28 synthetic acceptance specifications.
- Updated architecture, implementation, data model, testing, source rights/gaps, canonical context and Claude/Codex handoff.
- No active underwriting rules, formulas, guideline corpus, runtime tools or production side effects introduced.
