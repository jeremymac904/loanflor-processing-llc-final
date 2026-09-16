# Flo Team — decisions (2026-09-08, Claude Code team-build pass)

Each entry: decision, why, what it rules out. Earlier decisions in `.flo/docs/14_DECISION_LOG.md` still stand.

## D1. Six Hermes profiles, no second framework

Flo, Malcolm, Chadwick, Whisper, Sage and Franklin are plain Hermes v0.21 profile distributions under `.flo/profile/<name>/`. Bot Mode is enabled the way upstream does it: a `profile.yaml` carrying `ui_meta['hermes-bots']`. Bot-to-bot transport is upstream's `message_agent` tool inside each profile's canonical "Bot Chat". Rules out: a custom message bus, six apps, `delegate_task` sub-agents for team work (denied for specialists).

## D2. One manifest, generated profile files

`plugins/flo-team/team.yaml` is the single source of truth for names, titles, delegation edges, folder roots, Zapier scopes, model-class preferences and the autonomy level (a copy of the pack lives at `.flo/team/pack/` for provenance). `scripts/flo/generate_team_profiles.py` renders the derivable profile files; a test fails if they drift. Only `SOUL.md`, `memories/USER.md` and the avatar are hand-placed.

## D3. Two plugins, one gate

`flo-policy` (capability policy, unchanged contract) and the new `flo-team` (role overlay: folders, Franklin exclusion, Zapier scope, delegation, Shadow/Assisted/Trusted) both hook `pre_tool_call`; Hermes takes the first block/approve directive, so each layer can only tighten. CONFIRM goes through upstream's own human approval gate, so the click Ashley makes is the native one. Rules out: a parallel approval transport.

## D4. Approval Center = durable queue + native prompt

Cards are written by the `flo-team` hook at CONFIRM time (payload hash of the material arguments, preview, session id) and closed by `post_tool_call` from the tool result only. The desktop Approval Center lists them and deep-links to the proposing bot's chat, where the native prompt is answered. Approve/reject buttons on the page itself are deferred until the approval request id is exposed to plugins (see open questions). Material edits invalidate via hash mismatch and a re-proposal.

## D5. Handoff = pack envelope + tracking fields, depth 1

`flo_handoff` builds the pack schema envelope plus parent_task_id, origin_agent, depth, max_depth, status, cancel_reason; only Flo→specialist and specialist→Flo edges exist; depth > 1 is refused; Franklin never receives a workspace_id; `permission.external_actions` is a request, never a grant; results claiming sent/placed/published without an execution_ref are downgraded to proposed.

## D6. Loan truth in files, not chat

Workspaces, tasks, approvals, activity and the knowledge registry are JSON/JSONL documents under `<hermes root>/flo/team/` (atomic writes, references only, NPI shapes rejected). The desktop reads them through the existing preview-read IPC; no new RPC. Rules out: a database in this pass.

## D7. Zapier scoping in two layers, secret outside git

Layer 1: each profile's `mcp_servers.zapier.tools.include/exclude` (upstream fnmatch filter on raw tool names). Layer 2: the same globs re-checked per call by `flo-team`, generic API-by-Zapier excluded for every role, read-shaped actions allowed, write-shaped actions CONFIRM/DENY by role. The Zapier URL (token) is injected by the installer from the mirror profile or `FLO_ZAPIER_MCP_URL` and never stored in the repository; audit rows never carry it.

## D8. Local model adapter, fail closed for sensitive work

One `providers.flo_local` block; `plugins/flo-team/models.py` does the five-check health probe and `route()` refuses to move a PII task from a local class to a cloud class. The installer picks the local model for local-first roles only when the check passes; today the Ollama `qwen3-flo` model is used when listed (tag-aware id mapping). Honest limit: Hermes chooses the model per profile config at session start; the fail-closed rule is applied at install/route time and reported by `flo_model_health`, not intercepted per LLM call.

## D9. Sage's knowledge: metadata only, nothing active

The registry merges the prior discovery registry and the pack's official list. All revisions are `pending_review`; Guideline Cards conclude SOURCE_GAP with candidates and the official link; Non-QM/Jumbo require an investor source id; overlays are `NOT_LOADED` ("confirm with AE"). Bots may detect revisions; only a human can approve/activate. Calculators ship only TEST_ONLY formulas.

## D10. Readiness, orders, drafts, marketing carry their own invariants in code

Readiness is never an approval (`is_underwriting_decision: false`, disclaimer); orders need an approval_id to be approved and an execution_ref to be ordered; drafts become sent only with an execution_ref; marketing items with unresolved claim flags cannot be approved and cannot be published without an execution_ref; Franklin cannot open workspaces or loan folders at all.

## D11. Avatars: owner-approved package supersedes generated portraits

Six portraits were generated mid-session with the owner-connected image tool; the owner then delivered an approved package with a different direction (warm wood skin, brown eyes). The approved masters are the only shipped artwork; derivatives are centered circular crops; the app icon set and banner are integrated; signing settings untouched.

## D13. One source layer for every program; Fannie delegates, nothing generic (2026-09-09)

`plugins/flo-team/sources.py` is the only code path for official sources (cache, checksum, rule records with anchors, regression receipts, lifecycle, effective/in-force dates, program- and method-scoped rule matching). `fannie.py` keeps its public API and delegates with `program="fannie"`; the activated Fannie rules were not modified. There is no `conventional` program: Freddie rules are `freddie.*` bound to Guide sections, Fannie rules are `fannie.*` bound to Selling Guide sections, and a question for one is never answered from the other. Rules out: a merged conventional rule set, per-program copies of the lifecycle code.

## D14. FHA is two rule sets, and "not yet in force" is a first-class state

FHA records carry `underwriting_method: total | manual` (II.A.4 vs II.A.5) and are duplicated where the Handbook repeats itself so each cites its own section; differences are preserved (manual paystub coverage 30/28 consecutive Days). The captured Update 18 sections are effective 11/10/2026: they are activated, flagged `in_force: false`, and every card/trace carries the caution; the pre-Update-18 text is a recorded SOURCE_GAP rather than an assumption.

## D15. Program- and method-bound calculators that refuse mismatches

`calc.Formula` carries `program` (and `underwriting_method` for FHA). `run(program=…)` returns `UNSUPPORTED` on a mismatch and `NEEDS_INPUT["underwriting_method"]` when an FHA formula is called without a method — never re-binding. VA residual income tables are parsed from the cached Chapter 4 text at run time; USDA annual/adjusted/repayment income are separate formulas and fields. Self-employment and rental income are data structures only (`income_structures.py`) with SOURCE_GAP entry points.

## D16. AUS envelope preserves wording; approval identity is structured

`aus.py` normalizes DU/LPA/TOTAL/VA-AUS/GUS findings into one envelope with the result exactly as printed and a program/system mismatch flag; no universal "approved". Approval and activation records (`identity.py`, schema 2) carry a stable user id, display name, reason, revision id, environment and identity source; no e-mail is required. Until auth provides ids the local development identity (or `FLO_APPROVER_ID/NAME`, or an explicit name on the command line) is used and labelled as such; legacy Fannie records were migrated in place.

## D17. Provider route for the live validations: Nous Portal

The Codex credential hit its usage limit (HTTP 429, reset several hours out) and the opencode-free model answered "Model is unavailable" during the program-expansion live runs. The authenticated Nous Portal provider (`nous`, curated `openai/gpt-6-astra`; `deepseek/deepseek-v4-flash-0731` as the faster alternative) passed a one-line smoke and was used for all six profiles; it is now a discovery candidate (`nous_portal`, cloud, `pii_allowed: false`). The Codex config is kept as `config.yaml.codex-2026-09-09.bak` in each profile. Synthetic data only; the sensitive-data route still fails closed. Mid-way through the USDA run Nous returned HTTP 402 (insufficient credits for a gpt-6-astra request); the profiles were moved to `deepseek/deepseek-v4-flash-0731` on the same provider to finish the loop, and the model per hop is recorded in `LIVE_AGENT_HANDOFF_RESULTS.md`.

## D12. The `ashley` profile stays

The earlier single-assistant profile keeps working unchanged (its Flo persona, full toolset, credentials). The team leader is the new `flo` profile; the installer mirrors model/providers/Zapier/auth from `ashley` so nothing has to be re-entered. Whether to retire `ashley` is an open question for the owner.
