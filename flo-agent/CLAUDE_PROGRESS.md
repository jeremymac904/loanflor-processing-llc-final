# Flo bootstrap progress

Two sessions wrote this file on 2026-09-08. Section 1 is the Claude Code (Fable 5.1) engineering pass that
implemented Phases 0–3. Section 2 preserves, verbatim, the notes of an earlier/concurrent session (Codex desktop
app-server, per process inventory) that cloned the repo, created `.flo/`, installed the coding-agent toolchain and
drafted the underwriting architecture. Read both; they describe disjoint work in the same tree.

---

# 1. Claude Code bootstrap pass (Fable 5.1) — 2026-09-08

## 1.1 Upstream baseline

| Item | Value |
|---|---|
| Upstream repo | `https://github.com/NousResearch/hermes-agent.git` (remote `upstream`; no `origin` configured) |
| Tag / commit | `v2026.8.31` = `29112bef099274229cadff79cdff7bf7b99c4b77` ("chore: release v0.21.0 (2026.8.31)") |
| Branch | `flo/0.21-bootstrap` (uncommitted working tree; nothing pushed) |
| Clone depth | Was `--depth 1`; **unshallowed** in this pass (`git fetch --unshallow upstream`, 26,683 commits + tags) so upstream security fixes can be merged later |
| Host | Windows 11 Pro 10.0.26100, Windows PowerShell 5.1 (no `pwsh` on PATH, no WSL) |
| Toolchain installed this pass (winget, user scope) | Git 2.55.0.windows.3, Node 24.19.0 / npm 11.17.0, Python 3.11.9, uv 0.12.10 |
| Python env | `.venv` via `uv sync --extra dev --extra mcp` (Python 3.11.9; `.python-version` = 3.11; `requires-python >=3.11,<3.14`) |
| Node requirement | `engines.node ^22.22.0 || ^24.11.0 || >=26.0.0`; `.nvmrc` = 26; 24.19 satisfies |

### Architecture observed in the checked-out source (not from docs)

- **Desktop** (`apps/desktop`): Electron 40 + React 19 + Vite 8 renderer using `@assistant-ui/react`; main process `electron/main.ts` (~17k lines) plus focused modules. It spawns a headless `hermes serve` Python backend and talks JSON-RPC/WebSocket through `apps/shared` (`@hermes/shared`). Toolsets for desktop sessions resolve as platform **`cli`** in `tui_gateway/server.py` plus `desktop_ui`/`project` added from the session source. No `desktop` platform key exists.
- **Updater**: no electron-updater. `checkUpdates()` (`main.ts`) runs `git ls-remote`/`fetch` against the checkout's `origin` (or the hardcoded official HTTPS URL for official SSH remotes) and the GitHub compare API; `applyUpdates()` hands off to `scripts/desktop-update/windows.ps1|posix.sh` which run `hermes update` (Python `hermes_cli/update_cmd.py`, `git fetch origin <branch>` + `merge --ff-only`, Windows ZIP fallback from `github.com/NousResearch/hermes-agent/archive/...`). First-run bootstrap (`electron/bootstrap-runner.ts`) downloads `scripts/install.{sh,ps1}` from `raw.githubusercontent.com/NousResearch/hermes-agent/<ref>`. `connections:update-all` calls `applyUpdates()` directly, bypassing the IPC handler. **No config key or env var disables updates upstream.**
- **Branding**: literal strings — `package.json` build block, `set-exe-identity.mjs` (rcedit), `APP_NAME` in `main.ts`, four `BrowserWindow` titles, notification fallback, `index.html`, `main.tsx`, `intro.tsx` `WORDMARK`, and ~150 literals in each of five i18n catalogs (`src/i18n/{en,zh,zh-hant,ja,ar}.ts`) with no brand token/interpolation.
- **Deep links**: `hermes://` parsed in `main.ts` (`HERMES_PROTOCOL`, `DEEPLINK_SCHEMES`) and in the renderer resolver `src/lib/hermes-open-target.ts`; internal privileged scheme `hermes-media` is separate.
- **Plugins** (`hermes_cli/plugins.py`): directory plugins with `plugin.yaml` + `register(ctx)`; `pre_tool_call` hook may return `{"action": "block"|"approve"|"modify"}`; `approve` escalates to Hermes' human-approval gate (`tools/approval.py::request_tool_approval`), fail-closed on deny/timeout/error. Bundled plugins under `plugins/` are opt-in via `plugins.enabled`.
- **Profiles** (`hermes_cli/profiles.py`, `profile_distribution.py`): `~/.hermes/profiles/<name>/` with `config.yaml`, `.env`, `SOUL.md` (the only persona slot; loaded from `<HERMES_HOME>/SOUL.md`), `memories/USER.md`, `skills/`, `skins/`. A **profile distribution** (`distribution.yaml`) installs distribution-owned files; `memories/`, `.env`, sessions are user-owned and never copied.
- **Approvals/config**: `approvals.mode` = `manual|smart|off`; `cron_mode/single_query_mode/unattended_mode` default `deny`; dangerous capability is removed by toolset membership (`agent.disabled_toolsets`, `platform_toolsets.<platform>`); there is no `terminal.backend: none`. `send_message` is not an agent-callable tool at this pin.
- **Skills**: `skills/<category>/<name>/SKILL.md`; authoring hardline enforced by `tests/skills/test_authoring_standards.py` (frontmatter fields, ≤60-char description ending in a period, name = dir, related_skills resolve). No skill eval framework exists.
- **Tests**: desktop vitest projects `ui` (jsdom, `src/**`) and `electron` (node, `electron/**`, `scripts/**`); root `tests-js/` workspace; Python via `scripts/run_tests.sh` → `scripts/run_tests_parallel.py` (per-file subprocess isolation, hermetic env).

## 1.2 Commands executed (this pass)

```
winget install Git.Git / OpenJS.NodeJS.LTS / Python.Python.3.11 / astral-sh.uv   (--scope user)
git fetch --unshallow upstream
uv sync --extra dev --extra mcp
cd apps/desktop && npm run typecheck && npm run lint && npm run test:ui && npm run test:desktop:platforms && npm run build
cd apps/desktop && npx vitest run --project electron electron/flo-release-channel.test.ts electron/flo-brand.test.ts
cd apps/desktop && npx vitest run --project ui src/i18n src/lib/hermes-open-target.test.ts src/components/chat
.venv/Scripts/python.exe scripts/run_tests_parallel.py tests/flo tests/skills/test_flo_mortgage_skills.py tests/skills/test_authoring_standards.py tests/plugins/test_flo_policy_plugin.py tests/plugins/test_security_guidance_plugin.py tests/hermes_cli/test_profile_distribution.py tests/hermes_cli/test_plugin_manifest_v2.py tests/hermes_cli/test_plugins.py -q
.venv/Scripts/python.exe -m ruff check plugins/flo-policy scripts/flo tests/flo tests/plugins/test_flo_policy_plugin.py tests/skills/test_flo_mortgage_skills.py
```

`scripts/run_tests.sh` (Git Bash 5.3 from Git for Windows) fails on this host: MSYS does not convert the POSIX-style
`$SCRIPT_DIR` path when `env -i` execs the native `python.exe`, so `run_tests_parallel.py` is looked up under
`C:\c\Users\...`. Workaround used: invoke `scripts/run_tests_parallel.py` directly with the venv interpreter and the
runner's env (`TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 PYTHONUTF8=1`, credential vars cleared).
`tests/conftest.py` still applies the per-test isolation. Not the canonical runner; Codex should fix the wrapper or
document the deviation upstream.

## 1.3 Test / build results

| Check | Stock baseline (before Flo changes) | After Flo changes |
|---|---|---|
| Desktop `npm run typecheck` (3 tsconfigs) | PASS | PASS |
| Desktop `npm run lint` | PASS (pre-existing warnings) | PASS (0 errors) |
| Desktop `npm run build` (vite + esbuild + native staging) | PASS (prior session) | PASS |
| Desktop `test:ui` | 686/687 files, 6803/6804 tests; 1 pre-existing failure `src/plugins/hermes-bots/cron-prompt.test.ts` (expects spawn exit 0, gets null on Windows) | 687/688 files, 6807/6808 tests; same single pre-existing failure (see 1.3.1) |
| Desktop `test:desktop:platforms` | 34 failed / 1943 passed / 6 skipped (prior session, stock) | 36 failed / 1954 passed / 6 skipped. Same 34 stock failures (POSIX/macOS assumptions: ssh-connection, ssh-config, hardening chmod, git-repo-scan darwin, managed-ssh-update POSIX, windows-hermes-path POSIX, stage-native-deps darwin, desktop-installation, git-worktree-ops) + `git-review-ops` (passes in isolation; load-related) + `update-handoff-marker` "PowerShell hand-off" (times out at 5 s: spawns Windows PowerShell 5.1 three times; script unmodified; environment/timing) |
| New: `electron/flo-brand.test.ts`, `electron/flo-release-channel.test.ts` | — | 13/13 PASS |
| New: `src/i18n/flo-rebrand.test.ts` + touched i18n/deep-link/chat tests | — | PASS (32 tests in the targeted run) |
| Python subset via upstream parallel runner (stock) | 3 files fail on native Windows: `tests/hermes_cli/test_profiles.py` (6: symlink privilege, POSIX wrapper/alias), `tests/skills/test_openclaw_migration.py` (7), `tests/skills/test_setup_wizard_generator_skill.py` (1); everything else passed | — |
| Python: `tests/flo`, `tests/skills/test_flo_mortgage_skills.py`, `tests/skills/test_authoring_standards.py` (all 1214 bundled skills incl. the 7 new), `tests/plugins/test_flo_policy_plugin.py`, `tests/plugins/test_security_guidance_plugin.py`, `tests/hermes_cli/test_profile_distribution.py`, `test_plugin_manifest_v2.py`, `test_plugins.py` | — | **8 files, 1483 passed, 0 failed, 3 skipped** |
| `ruff check` on new Python files | — | PASS |
| Stock desktop GUI launch | not performed (prior session) | not performed: no model provider configured; GUI launch is not verifiable non-interactively here. `npm run build` output validated by `assert-dist-built` |
| Playwright e2e | not run | not run (title assertions updated to brand config) |

### 1.3.1 Full `test:ui` after Flo changes

Final run: **687/688 files, 6807/6808 tests**; the single failure is the pre-existing stock
`src/plugins/hermes-bots/cron-prompt.test.ts` case. An intermediate run showed 20 failures, all upstream tests
asserting literal "Hermes" screen text (onboarding, update blockers, gateway settings, thinking indicator); they were
fixed by wrapping the unchanged literals in `rebrandText(...)` (see 1.4). The suite gained four tests (`flo-rebrand`).

## 1.4 Files changed (Claude Code pass)

Tracked files modified (upstream files touched — keep this list short on purpose):

- `apps/desktop/package.json` — visible identity in the electron-builder block (+ top-level `productName`, `description`, `author` placeholder).
- `apps/desktop/electron/main.ts` — imports; `APP_NAME` default; AUMID; About copyright; 4× window `title`; notification title; protocol scheme; Flo update gates in `checkUpdates` and `applyUpdates`.
- `apps/desktop/electron/bootstrap-runner.ts` — refuse upstream install-script download unless a Flo bootstrap source is configured.
- `apps/desktop/scripts/set-exe-identity.mjs` — exe identity from brand config.
- `apps/desktop/index.html`, `src/main.tsx`, `src/components/chat/intro.tsx` — title/wordmark.
- `apps/desktop/src/lib/hermes-open-target.ts` — accept `flo://` (+ `hermes://` alias).
- `apps/desktop/src/i18n/catalog.ts`, `runtime.ts` — rebrand at the resolution boundary; `runtime.test.ts` — two expected literals.
- Five upstream renderer tests whose assertions quote screen text (`src/components/desktop-install-overlay.test.tsx`, `src/app/updates-overlay.blockers.test.tsx`, `src/app/settings/gateway-settings.test.tsx`, `src/components/assistant-ui/thread/streaming.test.tsx`, `status-tail-only.test.tsx`) — 31 assertion lines wrap the unchanged literal in `rebrandText(...)`; no other lines changed.
- `apps/desktop/e2e/boot.spec.ts`, `launch-packaged-app.spec.ts` — title assertions from brand config.
- `apps/desktop/tsconfig.electron.json` (include `flo/` + `flo/brand.config.json`), `tsconfig.e2e.json` (include `flo/brand.ts` + `flo/brand.config.json` only; the release channel pulls an untyped upstream module that the strict e2e project must not compile).
- `CLAUDE.md` (untracked; created by the prior session, expanded here).

New files:

- `apps/desktop/flo/brand.config.json`, `flo/brand.ts`, `flo/release-channel.ts`; `electron/flo-brand.test.ts`, `electron/flo-release-channel.test.ts`; `src/i18n/flo-rebrand.ts`, `src/i18n/flo-rebrand.test.ts`.
- `plugins/flo-policy/{plugin.yaml,__init__.py,policy.py,approvals.py,audit.py,gate.py,connectors.py}`; `tests/plugins/test_flo_policy_plugin.py`.
- `.flo/profile/ashley/{distribution.yaml,SOUL.md,config.yaml,README.md,flo/policy.yaml,skins/flo.yaml,memories/USER.md}`; `scripts/flo/install_ashley_profile.py`; `tests/flo/{__init__.py,test_ashley_profile.py}`.
- `skills/flo-mortgage/{README.md, flo-processing-workflow, flo-milestones, flo-income-analysis, flo-tpo-guidelines, flo-communication, flo-compliance-messaging, flo-notes-and-emails}/SKILL.md`; `tests/skills/test_flo_mortgage_skills.py`.
- `.flo/HERMES_REFERENCE_INVENTORY.md`; appended sections in `.flo/docs/14_DECISION_LOG.md`, `15_OPEN_QUESTIONS.md`, `CHANGELOG_FLO_BOOTSTRAP.md`.

Not touched by this pass but present in the tree (prior session): `AGENTS.md` 3-line prefix, `.gitignore` (`!/opencode.json`), `opencode.json`, `.flo/docs/DEVELOPMENT_AGENT_TOOLCHAIN.md`, `.flo/docs/UNDERWRITING_*`, `.flo/underwriting/**`.
`contributors/emails/agent@Agents-Mac-mini.local` shows modified only because of a case-insensitive filename collision on Windows — **never commit it**.

## 1.5 What is truly implemented

- Visible rebrand of the desktop app (package metadata, exe identity, titles, About, notifications, wordmark, all locale strings, deep-link scheme) with invariant tests; production build succeeds.
- Updater safety: the app cannot check or apply updates while the channel is `disabled`, and never against the upstream remote even when a channel is configured; first-run bootstrap refuses the upstream installer download. Tested.
- Deterministic policy plugin wired into Hermes' real `pre_tool_call` path: read-only tools pass, side effects escalate to the built-in human-approval gate, destructive/policy-disabling/credential-exposing actions are blocked, unknown tools require a human; fail-closed on internal error; per-target approval rule keys; JSONL audit with redaction. Discovery through `PluginManager` is tested end-to-end.
- Approval binding (exact-proposal hash, expiry, single use, source restricted to user/administrator) and an execution gate that consumes approved proposals — tested including prompt-injection and replay cases.
- Ashley profile distribution installable with the stock `hermes profile install` (tested against the real installer in a temp HERMES root), plus the helper that seeds the user-owned USER.md once.
- Seven bundled, source-backed skills passing upstream authoring standards, with tests that pin the source text and forbid fabricated rule vocabulary.

## 1.6 What is only scaffolded

- `plugins/flo-policy/connectors.py`: Google connector **contract** (Protocol + gated actions) with a fake in tests. No OAuth, credential broker, network, or Google API code. Model-facing `flo_*` tool names exist only in the policy table.
- Release channel: policy and config shape exist; there is no Flo release repository, installer, or signing.
- Approval persistence: `ApprovalStore` is in-memory; Hermes' own gate handles the live UI path.
- Audit log: file-based JSONL under `<HERMES_HOME>/flo/audit/`; no viewer/Activity UI.
- Today/Pipeline/Inbox/Conditions/Documents/Activity UI surfaces (Phase 5): not started.
- Routines (Phase 6): not started.
- Icons/avatar: upstream art still shipped.
- Underwriting Knowledge Architecture (prior session): design + inactive scaffolds only.

## 1.7 Security-sensitive decisions

- Policy is enforced in code (plugin hook), not prompt text; SOUL.md restates it for the model but is not the boundary.
- CONFIRM uses Hermes' approval gate, which offers "[a]lways"; Flo scopes the rule key per capability+target digest so an "always" never blankets a tool. Whether to disable "always" entirely for Ashley is an open question.
- Writes to `config.yaml`, `.env`, `flo/policy.yaml`, `flo/audit/*`, `plugins/`, `skills/`, `SOUL.md` are classified `policy_disable` → DENY; reads of `.env`, `*token*.json`, `*credential*.json`, `client_secret*.json`, `auth.json`, `~/.ssh` → `credential_exposure` → DENY.
- A policy file can tighten but not relax confirm/deny floors; malformed files fall back to defaults and log an error.
- Audit records carry metadata and digests only; every string is passed through the redactor (SSN, long digit runs, bearer/authorization headers, OAuth/API-key/JWT shapes, secret key/value pairs).
- No environment variable disables policy or the update gate.
- Ashley profile: no terminal/code execution/browser/computer-use/delegation/cron/kanban; manual approvals; no agent scheduling; skills self-authoring guarded; curator and background review off; only `flo-policy` plugin enabled; no model/provider or keys.
- No credentials, tokens, borrower data, or session DBs were created or committed. Nothing was pushed.

## 1.8 Blockers and environment notes

- Concurrent writer: another agent wrote to this tree during the pass (see decision log). Its work is intact; shared docs were appended, not rewritten.
- `scripts/run_tests.sh` unusable from Git Bash on this host (path conversion); direct runner used.
- 34 stock electron tests and 3 stock Python files fail on native Windows (POSIX/macOS assumptions, symlink privilege). Not Flo regressions; documented, not hidden.
- `update-handoff-marker.test.ts` PowerShell case times out here (5 s budget, three PowerShell 5.1 spawns).
- No `pwsh` on PATH; no WSL; no model provider configured, so no live agent or GUI session was exercised.

## 1.9 Remaining SOURCE_GAP items

All mortgage rules beyond: the six milestone names; "Processing = docs collected", "CTC = ready to close"; "follow agency rules, confirm overlays with AE"; the guide *covers* W2/self-employed/rental; one compliance template; one sample note; Ashley's communication contract. Specifically missing: income formulas/averaging/documentation for every income type; agency and program rules; lender overlays; milestone entry/exit criteria, owners, SLAs, checklists; condition taxonomy; additional compliance templates and signature/disclosure requirements; Ashley's outbound greeting/sign-off/channel preferences; model/provider; Google account details. See `.flo/docs/15_OPEN_QUESTIONS.md`.

## 1.9b Owner directive follow-up (same day): least restrictive for Ashley

The owner directed that Flo be the easiest, least restrictive experience for Ashley. Changes:

- `.flo/profile/ashley/config.yaml` no longer disables anything: full stock toolset (terminal, files, web, browser, cron, subagents, skills), `approvals.mode: smart` (upstream default), agent scheduling on, memory/skill writes without approval. Only Flo skin + `flo-policy` plugin remain.
- `plugins/flo-policy` default table: ALLOW everything, including unknown tools; one-click CONFIRM only for email send, mass send, permanent delete, external share, and writes that would disable policy/audit or expose credentials. No DENY by default; only the three irreversible capabilities keep a CONFIRM floor. `.flo/profile/ashley/flo/policy.yaml` mirrors this.
- `SOUL.md` tells Flo to work freely and not ask for routine things.
- **Flo home page** in the desktop app: bundled plugin `apps/desktop/src/plugins/flo/` (`/flo` route, sidebar entry, palette commands, first-launch landing). Six buttons (Morning brief, File check, Translate conditions, Draft a message, Escalation help, End-of-day recap) each mint a chat session and submit a prompt in Ashley's contract, plus a recent-activity list read from the Flo audit log. Tests: `src/plugins/flo/actions.test.ts`.
- **Routines**: `scripts/flo/install_ashley_profile.py` now creates two Hermes cron jobs in the profile (morning brief 7:30 weekdays, end-of-day recap 17:00 weekdays, `deliver: local`), idempotently. Covered by `tests/flo/test_ashley_profile.py`.
- **Google**: the bundled `google-workspace` skill is used as-is (Ashley authorises once via its setup flow). The least-privilege connector scaffold stays as a future option, not a gate.
- Verified: Python `tests/flo` + `tests/plugins/test_flo_policy_plugin.py` 73/73; desktop typecheck, lint, build PASS; plugin tests PASS.
- **Installed for real** (owner instruction): `%LOCALAPPDATA%\hermes\profiles\ashley` via `scripts/flo/install_ashley_profile.py --alias` (alias `ashley.bat`), both routines active in `hermes -p ashley cron list`, `flo-policy` enabled, all 65 bundled skills (incl. the 7 Flo skills) synced.
- **Provider**: Hermes' own Codex-CLI credential import (`hermes_cli/auth.py::_import_codex_cli_tokens`, the same path `hermes login` offers) applied to the profile: `model.provider: openai-codex`, model pinned to the account's top live model (`gpt-6-astra` at install time; change with `hermes -p ashley model`). Credentials live in the profile's `auth.json`, never in git.
- **Smoke test passed**: `hermes -p ashley -z "..."` answered as Flo and listed the six milestones with the skill cited.
- **Zapier MCP** (owner-supplied connect URL) added to the installed profile as `mcp_servers.zapier` (HTTP). `hermes -p ashley mcp test zapier`: connected, 104 tools (Gmail, Google Drive, Docs, Sheets, Tasks, Contacts, Forms). Live check: Flo listed real Drive spreadsheets through Zapier. The URL embeds an account token, so it is stored only in the local profile config (not in `.flo/profile/ashley`, not in git). Note: `hermes mcp add` hangs non-interactively (discovery prompt); the entry was written directly.
- **Desktop app**: launched in dev mode (`npm run dev`) on the `ashley` profile (sticky default via `hermes profile use ashley`); backend ready, Flo page present.
- **Branding from the owner's sheet** (`.flo/assets/originals/Flo-AI-Assistant-Branding.PNG`, cut by `scripts/flo/build_brand_assets.py`): app icon (`apps/desktop/assets/icon.png/.ico/.icns` = circular Flo badge), window/favicon (`public/apple-touch-icon.png`), BrandMark tile now `public/flo-face.png` (`src/components/brand-mark.tsx`), LoanFlow logo at `public/loanflow-logo.png`, Flo home header shows the badge. Publisher/company/copyright set to **LoanFlow Processing LLC** (app ID still a placeholder). New desktop theme `flo-desktop` (deep green / gold / cream, light + dark, `src/plugins/flo/theme.ts`) registered via `THEMES_AREA` and applied once on first launch; selectable in Appearance. Palette record: `.flo/assets/palette.json`.
- **Local models**: Ollama installed (auto-starts), `qwen3:8b` pulled, 64K-context variant `qwen3-flo` created, `providers.ollama` registered in the profile; verified end-to-end on CPU (slow; default stays the Codex model).

## 1.10 Top five recommended tasks for the Codex pass

1. **Run Flo for real and polish the home page**: install the profile (`python scripts/flo/install_ashley_profile.py --alias`), `hermes -p ashley setup`, launch the desktop dev build, click each of the six Flo buttons, and fix anything rough (session titling, hydration timing, activity list on a remote connection). Consider making `/flo` the persistent landing route.
2. **Keep it frictionless**: review every remaining prompt Ashley could hit (Hermes approval prompts, the four CONFIRM capabilities, first-run) and remove any that is not about an irreversible action. Verify the "smart" approval mode never nags on routine shell/file work.
3. **Windows test hygiene**: root-cause the `update-handoff-marker` PowerShell timeout and the `cron-prompt` spawn null exit; fix or mark the 34 stock POSIX-assumption tests with the upstream OS markers; make `scripts/run_tests.sh` work under Git Bash (path conversion) or add a documented Windows entry point.
4. **Ashley smoke run with a sandbox HERMES root**: `python scripts/flo/install_ashley_profile.py --home <tmp>`, configure a provider locally (never commit), launch `hermes -p ashley` and the desktop dev build; confirm the seven skills load, the Flo skin applies, `terminal` is blocked, and a `write_file` outside protected paths prompts. Record findings in CLAUDE_PROGRESS.md.
5. **Google connector Stage 1 (read + draft only)** behind `plugins/flo-policy/connectors.py`: a real connector with `gmail.readonly`-class scopes owned by a trusted host component, registering `flo_email_search/read/create_draft` tools through `ctx.register_tool`, with tokens never reaching renderer/plugin/model context. Do not add send scopes yet.

## 1.11 Flo Team pass (same day) — pointer

The six-profile Flo Team (Bot Mode) was built on top of everything above without discarding it. Full record in `FLO_TEAM_BUILD.md`, status in `FLO_TEAM_PROGRESS.md`, tests in `FLO_TEAM_TEST_RESULTS.md`, decisions/security/open questions in the matching `FLO_TEAM_*.md` files. Highlights: `plugins/flo-team/` runtime + `team.yaml` manifest; `.flo/profile/{flo,malcolm,chadwick,whisper,sage,franklin}/` distributions (generated + hand-written SOULs); `scripts/flo/{generate_team_profiles,install_flo_team,build_team_avatars,build_team_knowledge_registry}.py`; `skills/flo-team/*`; desktop `src/plugins/flo-team/`; owner-approved artwork in `.flo/assets/team/` (app icon, brand mark and banner replaced). Installed for real on this machine; all six route to the local Ollama model after the health check; the `ashley` profile is untouched.

---

# 2. Prior session notes (preserved verbatim)

## Development Agent Toolchain

2026-09-08: toolchain installed/discovered and shared context prepared. Full inventory, exact executable paths, official sources, auth commands, integration design and loop protection: `.flo/docs/DEVELOPMENT_AGENT_TOOLCHAIN.md`.

- Claude Code 2.1.260: existing official desktop-bundled binary reused and added to user PATH; version/help pass. CLI not authenticated. Run `claude` and sign in; then verify `/context` and perform one read-only architecture request, exit with `/exit`.
- OpenCode 1.18.29: official Windows x64 release ZIP installed, SHA-256 matched official release metadata, user PATH updated. Version/help/run-help/auth-list pass. Zero credentials. Run `opencode auth login` and choose provider; no provider selected automatically. Model comprehension test pending login.
- OpenAI Codex CLI 0.153.4: existing official OpenAI desktop binary reused and added to user PATH. Version/help/exec-help pass. `codex login status`: Logged in using ChatGPT. No key created or auth copied. If login expires, run `codex`, select Sign in with ChatGPT.
- Node v24.19.0 and npm 11.17.0 already installed via WinGet; stale process PATH initially hid npm. No reinstall.
- Integration: design-only; upstream already includes all three CLI skills plus terminal/process, plugin, delegation and MCP/ACP surfaces. Prefer a future optional Flo backend plugin with selectable adapters and existing process lifecycle. No production tools enabled.
- Created `.flo/docs/PROJECT_CONTEXT.md`, `.flo/docs/DEVELOPMENT_AGENT_TOOLCHAIN.md`, thin root `CLAUDE.md`, a short Flo prefix preserving upstream `AGENTS.md`, and `opencode.json` for explicit shared context and initial read-only permissions.
- No paid benchmark, credential transfer, recursive agents, push, deployment or production account connection.

## Phase 0 continuation

Cloned official `https://github.com/NousResearch/hermes-agent.git`, tag `v2026.8.31`, commit `29112bef099274229cadff79cdff7bf7b99c4b77`. Created `flo/0.21-bootstrap`, renamed remote to `upstream`, corrected branch fetch refspec. No origin/push target configured.

Copied original starter docs, config and source material into `.flo/`; canonical downstream edits now live there. Source PDFs were copied as supplied, not used to invent guidelines.

Upstream Windows checkout warning: `contributors/emails/agent@Agents-Mac-mini.local` collides with `contributors/emails/agent@agents-Mac-mini.local`. Git reports one modified contributor file immediately after clone; this is not a Flo edit. Do not commit that collateral diff. Resolve baseline reproducibility on a case-sensitive checkout before release.

Dependency installation, Desktop checks and one safe Codex smoke check finished; results and limitations follow. No rebranding or production runtime claimed.

## CLI smoke-check evidence

- OpenCode `--pure debug config`: canonical `instructions` entry resolved and project permissions parsed. `--pure debug file read .flo/docs/PROJECT_CONTEXT.md` returned base64 text; decoded bytes matched the file on disk. This proves local file visibility, not model comprehension. Commands exited 0.
- Codex single `exec --ignore-user-config --ephemeral --sandbox read-only` run started in the downstream repository, authenticated and exited 0. Its attempted PowerShell `Get-Content` of the two requested Markdown files was rejected: `blocked by policy`. The final response honestly reported neither file could be read. Therefore model comprehension FAILED/UNVERIFIED despite exit 0. No retry or permission bypass. Reported token usage: 11,525; no further inference tests run.
- Codex also warned that PowerShell shell snapshots are unsupported and upstream AGENTS.md exceeded the default 32,768-byte automatic context budget. Flo's reference is prepended; explicit reading is required for the remainder. No global context settings changed.
- Claude model check pending authentication; OpenCode model check pending provider selection/login. Startup/version/help and local configuration checks are not substitutes for those pending checks.

## Baseline commands and results

- `npm install --no-audit --no-fund` from root: PASS, 1,337 packages installed. Deprecation warnings reported. No audit/fix or package upgrades performed. npm peer metadata churn (27 deletions) in package-lock.json was restored to the pinned upstream version.
- `npm run test:desktop:platforms --workspace apps/desktop`: FAIL, 9 failed / 130 passed / 1 skipped test files; 34 failed / 1,943 passed / 6 skipped tests. Stock code, before branding. Failures include POSIX/macOS assumptions on Windows, permissions and path handling; not all have been root-caused. Exact diagnostic log: `%TEMP%/flo-baseline-platforms.log`.
- Available bundled Python: 3.12.14. No repository Python venv yet. Bash/WSL unavailable; canonical `scripts/run_tests.sh` backend suite not run. Do not report Python tests passing or substitute direct pytest for the upstream runner.
- `npm run typecheck --workspace apps/desktop`: PASS (renderer, Electron and e2e TypeScript configurations), exit 0. Log: `%TEMP%/flo-baseline-typecheck.log`.
- `npm run build --workspace apps/desktop`: PASS, exit 0. Renderer, Electron main/preload and Windows native dependencies built/staged; postbuild artifact assertion passed. Dynamic-import/chunk/plugin timing warnings reported. Log: `%TEMP%/flo-baseline-build.log`.
- `git diff --check`: PASS. Upstream AGENTS.md contents preserved after the Flo prefix. `opencode.json` explicitly unignored for version control.

## Current checkpoint and next implementation task

Tool installation/discovery and design documentation are complete; authentication-dependent comprehension checks are pending. Phase 0 resumed with successful dependency install, typecheck and Desktop build, but is not fully accepted. No stock app GUI/backend launch, Python test pass, Flo rebrand, Ashley runtime profile or production permission system is claimed.

Next: triage the 34 stock platform failures (including POSIX assumptions, Windows ACL/path behavior and temporary-directory EPERM), establish the documented isolated Python test environment, resolve case-sensitive baseline reproducibility, and verify stock Desktop against an isolated backend. Then proceed through Phase 1/2 and safe Phase 3. Do not enable coding-agent production tools as a shortcut. No commits or pushes made; the contributor collision diff must stay out of a Flo commit.


## Underwriting Knowledge Engine — architecture checkpoint (2026-09-08)

Added mandatory core product architecture without coupling Hermes core or enabling live rules. Canonical design: `.flo/docs/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md`; owner requirements preserved in `UNDERWRITING_REQUIREMENTS_ORIGINAL.md`.

Deliverables: `.flo/underwriting/source_registry.json` (11 official source/announcement/index records), five independent agency pack manifests, lender/Loan Factory and investor extension directories, 20 synthetic SOURCE_GAP scenarios and 8 future contract specs. Updated architecture decisions, implementation plan, data model, testing plan, open questions, decision log, mortgage skill plan and canonical project context. CLAUDE.md/Codex/OpenCode already point to that shared context.

Research: Fannie September 2, 2026 edition marker and HUD August 12, 2026 publication confirmed on official pages. Freddie guide body unavailable; VA handbook redirects to KnowVA shell; HUD PDF retrieval failed; USDA current chapter set requires Procedure Notice reconciliation. All 11 records PENDING_REVIEW/inactive; null source-byte checksums and retrieval timestamps are intentional. Registry is discovery metadata, not a certified current rule library. No third-party guide PDF/corpus downloaded into the repo. GSE terms reviewed; authorized ingestion/rights review remains required.

Designed deterministic source/date/overlay resolution, income arithmetic/trace, document requirements, Income Analysis UI, conflict escalation and admin-reviewed activation/rollback. No mortgage formulas, tax add-backs, Loan Factory overlays or approval claims invented. Runtime engine and executable mortgage regressions remain staged work; fixture validation is not a passing underwriting calculator test.

Bootstrap continuation: retain the existing Phase 0 checkpoint (Desktop build/typecheck passed, 34 stock platform failures, Python/backend launch unresolved) before rebranding. Underwriting full ingestion is a parallel product track, not a reason to reorder or discard that work. Next remains baseline triage and isolated backend verification, then Phase 1/2 and safe Phase 3. No production account connection, update monitor, deployment or push.

Validation for underwriting artifacts: PASS — JSON parsed; 11 unique inactive source records; five program-isolated packs with resolvable source IDs and empty rule/calculator sets; 28 uniquely identified synthetic acceptance specs; no guide PDFs under underwriting. `git diff --check` passed. These are metadata/consistency checks, not executable underwriting tests. An unrelated untracked `plugins/flo-policy/` appeared during this turn and was left untouched.


## Secure document intake (2026-09-09, Fable 5.1)

LO documents now travel browser -> website API (validated, private storage) -> Flo intake (pulled through the shared token, checksum verified) -> Deal Room (clean names, text sidecars, missing-page and duplicate flags, inventory) -> Malcolm (flo_documents) -> Ashley (Documents section, preview, Upload Missing Doc). New: plugins/flo-team/documents.py, flo_documents tool, tests/flo/test_documents.py; intake.py, today.py, tools.py, Malcolm/Flo SOULs, desktop pipeline.tsx/ashley.ts updated. Verified end-to-end with synthetic files only (8 documents, missing bank page 3 detected, duplicates marked, rejected uploads, Flo offline -> delivered on retry, duplicate submission ignored, preview in the running desktop). Production blockers unchanged plus one: the Supabase project / service-role key for the private bucket (owner decision). Details: site repo DOCUMENT_UPLOAD_IMPLEMENTATION.md, DOCUMENT_STORAGE_SCHEMA.md, DOCUMENT_SECURITY_REVIEW.md, DOCUMENT_INTAKE_TEST_RESULTS.md.

## Electronic signatures via Documenso (2026-09-10, Sonnet 5)

Owner's final product decision: Documenso, self-hosted Community Edition, one approved LOE template to
start. Built and tested against the verified current Envelope API v2 (see FLO_ESIGN.md for the exact
verified-vs-inferred endpoint table). New: plugins/flo-team/esign.py (Documenso adapter, signature-request
store, poll_all catch-up), flo_esign/_send/_remind/_cancel tools reusing the existing Approval Center + tool-
call idempotency (no new approval system), Send for Signature panel inline in the existing Documents section
(apps/desktop/src/plugins/flo/pipeline.tsx), one new website route (POST /api/esign-webhook, Documenso
credentials never touch the website), one new Flo intake endpoint (POST /intake/esign-webhook). Tests: 23
new Python tests against a local mock Documenso server (tests/flo/mock_documenso.py, explicitly not the real
product), full Flo suite 350 passed, website 19 passed, desktop plugin 28 passed, all typecheck/lint clean.
Blocker (reported, not worked around): no Docker/Postgres in this sandbox, so the real send/borrower-signing/
completed-PDF/certificate path was never exercised against a live Documenso instance; installing Docker
Desktop needs WSL2/Hyper-V + a reboot and was not attempted without explicit approval. Not production-ready
until that live run happens — see FLO_ESIGN.md "What could not be verified in this environment" for the
exact next steps.