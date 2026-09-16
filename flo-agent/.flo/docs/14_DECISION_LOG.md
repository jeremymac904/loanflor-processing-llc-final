# Decision Log

## 2026-09-08 - Baseline
Pinned Hermes Agent v0.21.0 / tag `v2026.8.31`.

## 2026-09-08 - Distribution model
Flo is a maintained downstream distribution rather than a total internal rename.

## 2026-09-08 - User experience
Flo is the single default visible assistant. Specialist workers may remain internal.

## 2026-09-08 - Action safety
External side effects require deterministic policy. Consequential writes require Ashley confirmation in the initial product.

## 2026-09-08 - Google integration
Create a Flo-specific, least-privilege Google connector rather than treating the stock broad Google Workspace configuration as production-ready for Ashley.

## 2026-09-08 - Portal automation
General browser/computer-use is deferred from the initial production scope.

## 2026-09-08 - Mortgage knowledge
Do not infer unsupported mortgage rules. Use explicit source gaps.

## 2026-09-08 - Development coding agents

Reuse existing official Codex/Claude desktop CLIs; install stable official OpenCode 1.18.29. Keep `.flo/docs/PROJECT_CONTEXT.md` canonical, thin tool entrypoints, and a versioned OpenCode analysis-only config. Upstream AGENTS.md content remains intact. No production runtime registration. Future invocation belongs in an optional Flo backend plugin reusing Hermes process/environment and delegation concepts, with per-call deterministic authorization and bounded leaf workers. See DEVELOPMENT_AGENT_TOOLCHAIN.md.

## 2026-09-08 - Baseline environment

Native Windows checkout matches existing desktop tools; WSL is absent. Tag v2026.8.31 resolves to 29112bef099274229cadff79cdff7bf7b99c4b77. Case-colliding contributor files and stock Windows test failures must be understood before rebranding. npm install succeeded; its peer-metadata-only lockfile churn was reverted to preserve the pin.

## 2026-09-08 - Rebrand at the i18n boundary (Claude Code pass)

User-visible product identity is rebranded through one config file (`apps/desktop/flo/brand.config.json`) and one transform applied where translations are resolved (`src/i18n/flo-rebrand.ts`, `runtime.ts`), instead of editing ~150 literals in each of five upstream locale files. Upstream catalogs stay byte-identical, future upstream strings are covered automatically, and internal identifiers (`hermes serve`, `HERMES_*`, paths, URLs) are untouched because the match is case-sensitive on the capitalised product name. "Hermes Cloud", "Hermes Skills Hub" and "Nous Hermes" are preserved as third-party product names. Trade-off: two upstream test literals (`runtime.test.ts`) and two e2e title assertions were updated.

## 2026-09-08 - Deep-link scheme

The OS-registered scheme is `flo://` (`flo-dev://` in dev). The renderer resolver additionally accepts `hermes://` as an internal alias so upstream plugin docs, notification payloads and existing tests keep working. Upstream constant names (`HERMES_PROTOCOL`, `DEEPLINK_SCHEMES`) are kept; only their values come from brand config.

## 2026-09-08 - Updater: disabled release channel (ADR-008 implemented)

`apps/desktop/flo/release-channel.ts` is the single updater policy. Mode `disabled` ships; `flo-release` requires a Flo-owned git source and is rejected if the source canonicalises to NousResearch/hermes-agent. `checkUpdates` and `applyUpdates` (including the `connections:update-all` path that bypasses the IPC handler) consult it before any git/network traffic; `bootstrap-runner.ts` refuses to download the upstream install script unless a Flo bootstrap source is configured. No environment override exists by design. The Python `hermes update` CLI is not gated (developer surface; Ashley's profile has no shell). Invariant tests: `electron/flo-release-channel.test.ts`, `electron/flo-brand.test.ts`.

## 2026-09-08 - Policy as a bundled plugin using the upstream approval gate

Deterministic policy lives in `plugins/flo-policy` (isolated directory, no core edits). It uses Hermes' documented `pre_tool_call` contract: `block` for DENY, `approve` for CONFIRM — which escalates to the existing human-approval UI (`tools.approval.request_tool_approval`, fail-closed on deny/timeout/error). Approval binding (`approvals.py`), the execution gate (`gate.py`), audit with redaction (`audit.py`) and the connector contract (`connectors.py`) are pure Python so the future Google connector reuses them without the agent runtime. Policy files may tighten but never relax confirm/deny floors. The rule key passed to Hermes' "[a]lways" allowlist is per capability+target, never per tool.

## 2026-09-08 - Ashley profile as a Hermes profile distribution

`.flo/profile/ashley/` uses the real `distribution.yaml` format so it installs with `hermes profile install` and can be versioned. SOUL.md is the only persona slot Hermes reads (`<HERMES_HOME>/SOUL.md`); USER.md lives in `memories/`, which distributions never copy, so `scripts/flo/install_ashley_profile.py` seeds it once. Dangerous capability is removed by toolset membership (`agent.disabled_toolsets`, `platform_toolsets.cli`) because Hermes has no `terminal.backend: none`; approvals are `manual`. Model/provider is intentionally absent.

## 2026-09-08 - Mortgage skills are bundled, source-backed shells

The seven `skills/flo-mortgage/*` skills follow upstream authoring standards (frontmatter, ≤60-char descriptions, section order) and add Sources, SOURCE_GAP and Prohibited Inference sections. Tests assert the milestone list and the two definitions verbatim, the single compliance template verbatim, and the absence of formula/agency vocabulary in the income and TPO skills. Bundled placement means every profile receives them through Hermes' normal skill sync; the Underwriting Knowledge Architecture (ADR-011) remains the future home for actual rules.

## 2026-09-08 - Owner directive: least restrictive for Ashley (supersedes the lock-down defaults)

The project owner directed that Flo be the easiest, least restrictive experience for Ashley. Applied: the Ashley profile no longer disables any toolset (terminal, browser, files, web, cron, subagents, skills all on, as in stock Hermes); approvals use upstream's default `smart` mode; the Flo policy plugin's default table is ALLOW for everything except a one-click CONFIRM before irreversible actions (email send, mass send, permanent delete, external share) and before writes that would disable Flo policy/audit or expose stored credentials. Nothing is denied by default; only the three irreversible capabilities keep a CONFIRM floor. The stock Google Workspace skill is used as-is (Ashley authorises it once through its normal setup). The earlier "Action safety" and "Security and permissions" lock-down defaults in this log and in `07_SECURITY_AND_PERMISSIONS.md` are superseded for the Ashley profile; the mechanisms remain available for a stricter profile later.

## 2026-09-08 - Concurrent writer observed

A second coding agent (Codex desktop app-server, per process inventory) wrote to this working tree during the Claude Code pass (16:18–16:41 local): the clone itself, `.flo/`, `opencode.json`, the AGENTS.md prefix, the underwriting architecture and the first progress/changelog entries. Claude Code kept its edits to disjoint files, re-read shared docs before appending, and did not revert any of that work. Decision: one writer per tree going forward (already stated in PROJECT_CONTEXT.md); use worktrees for parallel agents.

## 2026-09-08 - Underwriting Knowledge Engine

Accepted as required Flo product architecture (ADR-011). Added canonical design, five inactive source-backed pack scaffolds, official discovery metadata and synthetic acceptance specs. Calculations must be deterministic and source/version/program aware; overlays and conditions remain separate. All discovered sources remain pending/inactive, with source bytes/checksums absent until authorized ingestion. Manual approval governs activation. Bootstrap/rebrand phase ordering remains unchanged.

## 2026-09-08 - Flo Team on Hermes Bot Mode (Claude Code team-build pass)
Six Hermes profile distributions (flo, malcolm, chadwick, whisper, sage, franklin) with Bot Mode `ui_meta` and upstream `message_agent` as the only bot-to-bot transport; one manifest (`plugins/flo-team/team.yaml`) drives generated profile files, role policy, Zapier scopes and model classes; `flo-team` plugin adds the role overlay on `pre_tool_call` next to `flo-policy` and a durable Approval Center queue closed only by tool results. Owner-approved artwork supersedes interim generated portraits. Full rationale: `FLO_TEAM_DECISIONS.md`.

## 2026-09-09 - Reliability hardening (Claude Code pass)
FHA Handbook versions are kept side by side and resolved deterministically by case number assignment date; a card never blends versions and always labels CURRENT / FUTURE - NOT YET EFFECTIVE / SUPERSEDED. Sage's guideline answers pass through a source-bound object and a post-generation validator, and a guideline_card handoff only closes with a validated response id. External side effects and drafts carry intent ids so a provider retry can never send, order or publish twice. Provider routing is a persisted state machine with preflight and between-turn failover; sensitive files fail closed ("AI provider unavailable - your work is saved.") rather than reaching an unapproved provider. Source lifecycle review moves to a Knowledge Center with diff and impact analysis; overlays and human guidance are separate, human-promoted layers; every approval carries a structured identity without e-mail. Full rationale: `FLO_RELIABILITY_HARDENING.md`.
