# Flo Team — build record (2026-09-08, Claude Code team-build pass)

The six-profile Flo Team (Flo, Malcolm, Chadwick, Whisper, Sage, Franklin) integrated into the existing Flo downstream of Hermes Agent v0.21 (`v2026.8.31`), using Hermes' own profile / Bot Mode / plugin primitives. Companion documents: `FLO_TEAM_PROGRESS.md`, `FLO_TEAM_DECISIONS.md`, `FLO_TEAM_OPEN_QUESTIONS.md`, `FLO_TEAM_SECURITY_REVIEW.md`, `FLO_TEAM_TEST_RESULTS.md`. Source pack copied to `.flo/team/pack/`.

## 1. Hermes primitives used (verified in the checked-out code)

| Need | Hermes surface | Where |
|---|---|---|
| A bot | profile distribution (`hermes profile install`, `install_distribution` / `update_distribution`) | `hermes_cli/profile_distribution.py` |
| Bot Mode identity (title, color, group, pinned) | `profile.yaml` → `ui_meta['hermes-bots']`; presence of that block makes the install Bot-Mode-managed | `hermes_cli/profiles.py`, `tools/bot_mode_probe.py` |
| Avatar | `<profile>/assets/avatar.png` (PNG/JPEG/WebP < 2MB), RPC `profiles.get_asset` / `has_avatar` in `profiles.list` | `tui_gateway/methods_profiles.py` |
| Bot-to-bot messaging | `message_agent` tool, injected only into each profile's canonical "Bot Chat"; roster and protocol injected at prompt build | `tools/bot_mode_dm.py`, `tools/bot_mode_probe.py` |
| Group chat | desktop-driven `Group: <roomId>` sessions (hermes-bots plugin) / gateway `groups.*` hosted rooms — used as-is, optional | `apps/desktop/src/plugins/hermes-bots/group-*.ts`, `tui_gateway/methods_groups.py` |
| Per-profile tool scoping | `agent.disabled_toolsets`, `delegation.max_spawn_depth`, `skills.disabled`, `mcp_servers.<name>.tools.include/exclude` (fnmatch on raw MCP tool names; MCP tools are `mcp__<server>__<tool>`) | `tools/mcp_tool.py`, `hermes_cli/config*.py` |
| Deterministic policy | plugin `pre_tool_call` returning `approve` (→ `tools.approval.request_tool_approval`, the human gate) or `block`; `post_tool_call` | `hermes_cli/plugins.py`, `tools/approval.py` |
| Plugin tools | `ctx.register_tool` via `tools.py::register_tools` + `provides_tools` in `plugin.yaml` | `hermes_cli/plugins.py` |
| Routines | per-profile cron store, `cron.jobs.create_job` | `cron/jobs.py` |
| Desktop pages | bundled plugin `src/plugins/<id>/plugin.tsx` with `ROUTES_AREA`, `SIDEBAR_NAV_AREA`, `PALETTE_AREA`; `host.request('profiles.list')`, `host.newChat(profile)`, preview-read IPC | `apps/desktop/src/sdk/index.ts` |

No core Python or Electron file was modified for the team. Two upstream-owned files changed earlier in the bootstrap (`electron/main.ts` gates, i18n boundary) are unchanged by this pass.

## 2. Profiles created (actual paths)

Repository distributions: `.flo/profile/<name>/` — `SOUL.md` (hand-written from the pack's SOUL_SEED), `profile.yaml`, `config.yaml`, `distribution.yaml`, `flo/policy.yaml`, `flo/team-role.yaml`, `routines.yaml`, `skins/flo.yaml`, `assets/avatar.png`, `memories/USER.md`, `README.md`. Generated files come from `scripts/flo/generate_team_profiles.py` (source: `plugins/flo-team/team.yaml`); `--check` is enforced by a test.

Installed (this machine): `%LOCALAPPDATA%\hermes\profiles\{flo,malcolm,chadwick,whisper,sage,franklin}\` via `python scripts/flo/install_flo_team.py --workspace %USERPROFILE%\FloWorkspace`. The installer mirrors from the `ashley` profile what must never be in git: `model:` block, `providers.*`, the Zapier MCP URL, `auth.json`, `.env`. Shared team state root: `%LOCALAPPDATA%\hermes\flo\team\` (workspaces/, tasks/, approvals/, activity/, knowledge/, marketing/, knowledge-registry.json). Workspace folders: `%USERPROFILE%\FloWorkspace\{loans,marketing,templates,sources,team}`.

| Profile | Title | Reports to | Loan workspace | Deal Rooms | Folders (loans/*/…) | Zapier scope (layer 1 + 2) | External writes | Model classes |
|---|---|---|---|---|---|---|---|---|
| flo | Team Leader | — | read/write | always | all subfolders; templates, sources, team | find/search/get/list/retrieve + task/row create/update; no delete/API-request | confirm | local_reasoning → cloud_reasoning |
| malcolm | File Prep & QC | flo | read/write | when needed | intake(ro), aus, income, assets, conditions, exports; templates, sources | read/search only | deny | local_fast → local_reasoning → deterministic |
| chadwick | Order Outs | flo | read/write | when needed | title, insurance, correspondence, exports; templates | read/search + gmail send/draft, calendar/task/row create | confirm | local_fast → deterministic |
| whisper | Processing Assistant | flo | read | throughout | correspondence, conditions, exports; templates | gmail_*, google_calendar_*, read/search; no delete/trash | confirm | local_fast → local_reasoning |
| sage | Underwriting | flo | read | when needed | aus, income, assets, conditions; sources | read/search only | deny | local_reasoning → cloud_reasoning → deterministic |
| franklin | Marketing & Growth | flo | **deny** | **never** | marketing only | marketing systems only; gmail/drive/calendar excluded | confirm | local_fast → cloud_reasoning |

Per-profile config also sets: `plugins.enabled: [flo-policy, flo-team]`, `agent.disabled_toolsets` (specialists: delegation, computer_use, browser for the processing roles), `delegation.max_spawn_depth: 1`, `skills.disabled` (role-irrelevant Flo skills), `approvals.mode: smart`, `display.skin: flo`, `cron.allow_agent_scheduling` (Flo only).

Model config per agent after install on this machine: local-first roles use Ollama `qwen3-flo:latest` (64K ctx) when the health check passes; Flo and Sage prefer local reasoning too and get the same local model; the mirrored cloud provider (`opencode-free`) is the fallback for non-sensitive work. See §7.

## 3. Runtime: `plugins/flo-team/`

| Module | What it does | Status |
|---|---|---|
| `team.yaml`, `manifest.py` | team manifest, RoleSpec, delegation edges, current profile resolution, shared state root | real |
| `__init__.py` | `pre_tool_call` role overlay → allow / `approve` (+ Approval Center card) / `block`; `post_tool_call` closes cards from tool results; fail-closed | real |
| `roles.py` | folder boundaries, loan-workspace exclusion, Zapier scope, external-write rule (Shadow/Assisted/Trusted), specialist `delegate_task` denial | real |
| `folders.py` | role-scoped `~/FloWorkspace` roots; `intake/` originals read-only; permanent delete denied for all | real |
| `zapier.py` | second-layer scope on raw tool names; generic API-by-Zapier excluded; read vs write shape; config filter generator | real |
| `approvals_center.py` | durable cards, payload hash binding, human-only decisions, edit → invalidate + re-propose, close from execution only | real |
| `handoff.py` | pack envelope + parent/child/origin/depth/max_depth/status/cancel; edge and depth checks; message render/parse; task registry | real |
| `workspace.py` | Loan Workspace / Deal Room store, membership (Franklin excluded), activity, heat map | real |
| `readiness.py` | File Readiness report with transparent score; never an approval | real (checklist supplied by handoff/Ashley — no doc matrix: SOURCE_GAP) |
| `orders.py` | order proposals + state machine (approved needs approval_id; ordered needs execution_ref) | real (vendor requirements SOURCE_GAP) |
| `drafts.py` | communication queue (draft ≠ sent), condition translation with `needs_sage` | real |
| `knowledge.py` | source registry (12 official sources, all pending_review), lifecycle detected→…→active (admin only), Guideline Cards with five separate layers | real, but **no active source**: every real guideline answer is SOURCE_GAP by design |
| `calc.py` | deterministic Decimal workbench with trace | real engine; **only TEST_ONLY formulas** (production registry empty) |
| `marketing.py` | content factory with claim/NPI flags and publish gate | real |
| `models.py` | one local-provider adapter, five-check health probe, tag/prefix id mapping, fail-closed routing | real (install-time and on-demand; not per-LLM-call) |
| `tools.py` | 12 tools: `flo_team`, `flo_handoff`, `flo_workspace`, `flo_approvals`, `flo_readiness`, `flo_order`, `flo_draft`, `flo_guideline_card`, `flo_knowledge`, `flo_calc`, `flo_marketing`, `flo_model_health` | real |

The earlier `plugins/flo-policy` (capability policy, approvals binding, redacting audit) is unchanged except that audit rows now carry the acting profile name.

## 4. Handoff and recursion protection

`flo_handoff action=create` → validates recipient against the manifest (Flo→specialist, specialist→Flo only), computes depth from the parent task, refuses depth > `max_delegation_depth` (1), refuses a workspace for Franklin, records the task, and returns the exact packet (`send_with.message`) to send with `message_agent`. Receiving bot: `action=receive` (parse + mark received), does the work under its own policy, `action=complete` with a structured result (claims of sent/placed/published without `execution_ref` are downgraded to `proposed`), then messages Flo. `action=cancel` cancels a tree; `action=status` lists open tasks. Transport is Hermes' `message_agent` (fire-and-forget, replies arrive as completion notifications).

## 5. Deal Rooms and Approval Center

Deal Room = a Loan Workspace document (schema fields from the pack + members, excluded_members, activity, readiness, orders, drafts, approvals) with Flo always a member, processing specialists invited as needed, Franklin structurally excluded (invite refused, handoffs refused, tools blocked). The optional Hermes group chat is upstream's; the document is the source of truth.

Approval Center = `<root>/flo/team/approvals/*.json`. A card is filed whenever the role overlay returns CONFIRM (proposing bot, workspace, action, destination, payload preview, data categories, policy result, payload hash, expiry, session). Ashley decides in the bot's native approval prompt; the desktop Approval Center lists cards and opens that chat. Cards close from the tool result (executed / blocked / failed). Material edits produce a new card.

## 6. Zapier MCP scoping

Layer 1: `mcp_servers.zapier.tools.include/exclude` per profile (generated from the manifest; `*api_request*`, `*raw_request*`, `*webhook_by_zapier*` always excluded). Layer 2: `roles.py` re-checks every `mcp__zapier__*` call against the same globs and applies the external-write rule. The URL is injected by the installer and lives only in installed profile configs. Verified against the connected Zapier MCP earlier in the session (104 tools); per-role action availability on the live account is not yet reviewed (open question).

## 7. Local models (Unsloth / Ollama)

`providers.flo_local` is the one adapter block (mirrored from `providers.ollama` on this machine: `http://localhost:11434/v1`, `qwen3-flo`, 65536). `models.health_check` verifies reachable, model listed (with `unsloth/` prefix and Ollama `:latest` tag mapping), context ≥ 64K (listing metadata, declared `context_length`, or Ollama `/api/show`), and a one-token smoke completion. `models.route` picks the first healthy class from the role's preferences and returns FAIL_CLOSED for sensitive work when no PII-approved class is healthy. The Mac's Unsloth Studio endpoint (`127.0.0.1:8888/v1`) is not present on this Windows machine; the adapter targets it by configuration only.

## 8. Underwriting knowledge (Sage)

Registry: `plugins/flo-team/knowledge/registry.json`, built by `scripts/flo/build_team_knowledge_registry.py` from the prior discovery registry (`.flo/underwriting/source_registry.json`) and the pack's `underwriting_sources.yaml`: 12 official sources (Fannie, Freddie, FHA ×4, VA ×2, USDA ×3), Loan Factory overlay `NOT_LOADED`, seven specialty products `source_required`. Lifecycle is per install under `<root>/flo/team/knowledge/`. Guideline Cards keep agency baseline / lender overlay / investor program / AUS finding / file condition apart and cite title, section, dates, lifecycle. Nothing is active; no guide text is cached; no rights decision was taken.

## 9. Desktop

`apps/desktop/src/plugins/flo-team/` — sidebar "Team", route `/flo-team`: Team Floor (roster from `profiles.list`, open handoffs, chat buttons, approved portraits), Deal Rooms, Approvals, Activity, Pipeline heat map, Knowledge freshness, Health (configured provider per bot). Read-only over shared state; no new IPC. The upstream Bots pane shows the six profiles with avatars and the "Flo Team" group; Bot Chats carry the messaging protocol.

## 10. Visual assets

Owner-approved package integrated (see `.flo/assets/team/README.md`): masters + sizes, centered circular crops for profile avatars and Team page, app icon (`assets/icon.png/.ico/.icns`, `apple-touch-icon.png`, `flo-badge.png`), brand mark `flo-face.png`, team banner. Verified rendering in the running Electron app (Bots pane, Team page, Flo home). Signing config untouched.

## 11. What is real vs scaffold

Real and tested: manifest, profiles, installer, role overlay, Approval Center queue + binding, handoffs + depth, workspaces/Deal Rooms, readiness, orders, drafts, condition translation, Guideline Cards (SOURCE_GAP path and active-source path), knowledge lifecycle, calc engine, marketing factory, model health/routing, Team page, avatars.

Scaffold / partial: Approval Center decisions from the page (deep-link only); per-LLM-call model routing (install-time + on-demand only); Health tab (config view; live check runs inside a chat); Synthetic Eval Lab and Marketing Content Factory UI (state exists via tools; no dedicated page); Post-UW feedback loop (not started); production formulas, document matrix, vendor directory, templates, brand/compliance sources (all SOURCE_GAP).

Not production-ready claims: none of the scaffolds above should be described as complete; no underwriting rule is loaded; live bot-to-bot behaviour depends on the configured model (see `FLO_TEAM_TEST_RESULTS.md`).
