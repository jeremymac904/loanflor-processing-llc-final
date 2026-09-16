# Codex Build Prompt — Flo Team Agents

You are working in the existing Flo downstream fork of Nous Research Hermes Agent.

Claude Code has already been working on the initial Flo/Hermes bootstrap. Do not restart the fork and do not discard Claude's work.

I am giving you a separate `Flo_Team_Agents_Pack` directory.

Your task is to integrate the six-profile Flo Team into the current Flo application using Hermes Agent's actual v0.21 profile/Bot Mode/plugin/gateway architecture.

## First: inspect, don't overwrite

Read:
- the current repository's upstream `AGENTS.md` and scoped instructions;
- `CLAUDE_PROGRESS.md`;
- Flo project docs already present;
- every file in `Flo_Team_Agents_Pack`;
- current git status/diff;
- Hermes v0.21 Bot Mode/profile implementation in the checked-out code.

There may already be pre-existing changes from Claude or another agent. Preserve them unless a concrete correction is required. Document overlap instead of blindly replacing files.

## Team mapping

Build these Hermes profiles:

- Flo — Team Leader
- Malcolm — File Prep & QC
- Chadwick — Order Outs
- Whisper — Processing Assistant / Communications
- Sage — Underwriting
- Franklin — Marketing & Growth

The mapping is canonical in `team/team_manifest.yaml`.

Flo is the Team Leader and default orchestration surface.

Do not turn these into six separate apps.

## Hermes-native implementation

Use Hermes' actual profile primitive.

At the current v0.21 architecture, Bot Mode is a UI over profiles and supports isolated profile config/memory/skills/credentials/chat history, avatars, routines, and bot-to-bot/group-chat behavior.

Prefer:
1. profiles
2. skills
3. profile toolsets
4. backend/Desktop plugins
5. gateway/profile messaging
6. small isolated core patches only when required.

Do not implement a parallel multi-agent framework if Hermes already provides the primitive.

Bot Mode currently has some fresh upstream UI issues. The team must remain functional through profile/CLI/gateway primitives even if a Bots-pane rendering/live-refresh bug appears.

## Create real profile content

For every agent, convert the pack's `SOUL_SEED.md` into a production-quality Hermes `SOUL.md` in the actual profile structure.

Create/configure:
- display name
- title
- description
- avatar
- model/provider policy
- skills
- tool allowlist
- workspace roots
- MCP scopes
- routines
- memory seed
- direct-chat behavior
- delegation/handoff behavior

Keep SOUL files focused. Do not stuff entire underwriting guides into SOUL.md.

Shared knowledge belongs in skills/source libraries.

## Flo orchestration

Flo must be able to delegate:

File Prep -> Malcolm
Order Outs -> Chadwick
Communication -> Whisper
Underwriting -> Sage
Marketing -> Franklin

Implement a structured handoff envelope based on `schemas/handoff.schema.json`.

Flo should:
- decompose multi-part work;
- assign focused tasks;
- collect results;
- resolve conflicts;
- surface one clear answer to Ashley;
- own the approval queue.

Prevent recursive agent loops.

Track:
- parent task
- child task
- origin agent
- delegation depth
- max depth
- cancellation
- status.

Specialists should normally return work to Flo instead of recursively building their own teams.

## Deal Rooms

Implement or scaffold a Deal Room concept around the shared Loan Workspace.

A Deal Room is:
- one structured loan workspace;
- optional Hermes group chat of relevant specialists;
- one activity timeline;
- one approval history.

Default membership:
Flo always.
Malcolm, Chadwick, Whisper, Sage as needed.
Franklin excluded from borrower Deal Rooms.

The structured workspace is the source of truth, not the raw group-chat transcript.

## Ashley Approval Center

Implement or scaffold a unified approval queue for Yellow actions.

Approval cards need:
- proposing agent;
- workspace;
- exact action;
- destination/recipient;
- payload/draft preview;
- attachment/data categories;
- policy result;
- Approve/Edit/Reject.

Bind approval to a payload hash or equivalent immutable proposal identity.

Editing a material action invalidates the old approval.

Do not allow a bot to claim "sent/ordered/published" until the execution tool confirms it.

## Zapier MCP

All team agents may eventually use Zapier MCP, but NOT with one unrestricted global tool catalog.

Use per-agent action scoping or an equivalent second-layer Flo allowlist.

Recommended posture:

Flo:
coordination/read/search + approved workflow actions.

Malcolm:
processing reads/searches; no broad outbound writes.

Chadwick:
approved title/HOI/WVOE/order actions.

Whisper:
approved email/calendar/communication actions.

Sage:
primarily read/search; no external writes.

Franklin:
marketing-only actions; no borrower systems.

Keep MCP endpoint URLs/secrets out of Git and model-visible logs.

Do not expose generic "API by Zapier" arbitrary requests unless explicitly reviewed.

All external side effects still pass Flo deterministic policy even if Zapier permits the action.

## Local folders

Implement role-scoped workspace roots based on `shared/LOCAL_FOLDER_POLICY.md`.

Do not give every bot access to the entire Mac.

Marketing must be structurally denied borrower loan folders.

Protect original borrower documents.

Permanent deletes remain denied.

## Underwriting / Sage

Sage is the authoritative guideline specialist.

Create the knowledge source architecture from:
- `shared/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md`
- `sources/official/underwriting_sources.yaml`

Programs:
- Fannie
- Freddie
- FHA
- VA
- USDA Guaranteed
- Non-QM/Jumbo/specialty only when the actual lender/investor guide exists.

Do not invent Loan Factory overlays.

Do not invent Non-QM rules.

Keep:
agency baseline
lender overlay
investor/program rule
AUS finding
file-specific UW condition

as separate layers.

Create citation-capable Guideline Cards.

Implement deterministic calculation interfaces before pretending an LLM is a calculator.

Arithmetic needs:
inputs
formula
result
source/rule
trace.

Do not expose hidden chain-of-thought.

Use `SOURCE_GAP` whenever authority is missing.

Never have Sage say the loan is approved.

## Malcolm / File Prep

Build Malcolm around:
- initial review
- AUS findings status/source
- minimum docs
- doc consistency
- income/assets prep
- missing items
- pre-submission QC
- readiness report.

Malcolm can use Sage-approved rules but should escalate rule conflicts to Sage.

A File Readiness Score is useful only if transparent and not represented as an underwriting approval.

## Chadwick / Order Outs

Build structured order proposals/tracking for:
- Title
- HOI
- WVOE/VOE
- approved LOE request workflow
- future configurable order types.

External order placement is confirmation-gated initially.

Track:
requested
approved
ordered
vendor confirmed
pending
received
reconciled
overdue.

## Whisper / Processing Assistant

Build:
- inbox triage
- borrower drafts
- LO/lender/realtor drafts
- milestone updates
- condition translation
- escalation drafts
- communication queue.

Whisper uses Ashley's concise, calm voice.

Whisper cannot independently change an underwriting rule.

Draft is never shown as sent.

## Franklin / Marketing

Franklin is structurally separate from borrower data.

Build marketing workspace for:
- social media
- LO email newsletter
- Google Business Profile
- website/blog
- content calendar
- repurposing.

Load current public platform/marketing source registry from the pack.

Publishing/sending is approval-gated.

Do not invent rates, APRs, licensing, savings, eligibility promises, disclosures, or product claims.

## Profile pictures

Generate a production avatar for:
- Flo
- Malcolm
- Chadwick
- Whisper
- Sage
- Franklin

Read:
- `avatars/TEAM_VISUAL_SYSTEM.md`
- each agent's `AVATAR_BRIEF.md`

Use an approved image-generation capability available in the environment.

The six portraits must form one coherent original visual family while being clearly distinguishable at 48px.

Generate:
- 1024x1024 master
- 512
- 256
- 128
- 64

Use PNG and preserve circular-crop safety.

Install the avatars into the actual Flo/Hermes profile locations discovered in code.

If no approved image-generation capability is available:
1. do not use random web images;
2. do not fabricate fake PNGs;
3. create `AVATAR_GENERATION_BLOCKED.md`;
4. preserve exact prompts/asset paths;
5. continue the rest of the profile build.

## Unsloth runtime

Read `runtime/UNSLOTH_HERMES_RUNTIME.md`.

The current Mac has a verified Unsloth local server path and Hermes was tested through it.

Important observed compatibility constraints:
- the tested Hermes path requires >=64K context;
- a provider/model prefix mismatch required a wrapper workaround;
- provider port collisions are possible.

Do not copy the workaround independently into each profile.

Create one provider adapter/configuration layer.

Implement a model-health check before assigning local work:
- endpoint reachable
- model listed
- context sufficient
- model ID mapping valid
- smoke completion works.

Use logical model classes from `runtime/MODEL_ROUTING.yaml`.

Do not hard-code all agents to one local model.

## Model strategy

Initial routing philosophy:

Malcolm:
local fast/local reasoning + deterministic calculators.

Chadwick:
local fast + deterministic policy.

Whisper:
local fast/local reasoning.

Sage:
strongest approved reasoning model + deterministic calculations; local when it passes underwriting evals.

Franklin:
local fast or approved cloud depending task.

Flo:
local reasoning for routine orchestration; approved higher reasoning when needed.

Sensitive data must not silently fall back to an unapproved cloud provider.

## Skills / source libraries

Convert role knowledge into Hermes skills.

Do not make every skill globally available if only one specialist needs it.

Suggested shared skills:
- Ashley operating style
- mortgage milestones
- handoff protocol
- source provenance
- safety/approval

Role skills:
Malcolm:
file prep, doc QC, income/assets prep.

Chadwick:
order types, vendor workflow, follow-ups.

Whisper:
communication, conditions-to-action, templates.

Sage:
Fannie/Freddie/FHA/VA/USDA source packs, calculations, overlay resolution.

Franklin:
brand, social, newsletters, GBP, blog, marketing safeguards.

## Source ingestion

Do not embed stale full guide text in SOUL.md.

Implement the source registry now.

Create a private/versioned knowledge-cache strategy.

New guideline versions must become:
pending_review
-> regression tests
-> human/admin approval
-> active

Do not silently activate a new scraped guide.

## Make it epic, but controlled

Implement/scaffold these product concepts where they fit cleanly:

1. Team Floor
2. Deal Rooms
3. Approval Center
4. File Readiness report
5. Guideline Cards
6. Income/Asset Calculation Workbench
7. Knowledge Freshness monitor
8. Team Activity timeline
9. Model/Agent Health panel
10. Shadow / Assisted / Trusted capability levels
11. Pipeline heat map
12. Synthetic Mortgage Eval Lab
13. Marketing Content Factory

Do not let feature ambition destroy upstream mergeability.

## Tests

Use synthetic data only.

Add tests for:
- correct routing
- out-of-role refusal/handoff
- cross-agent handoff schema
- max delegation depth
- Ashley approval binding
- prompt injection
- source gaps
- underwriting source conflicts
- local-provider health failure
- marketing borrower-folder denial
- draft vs sent
- File Readiness not equal approval
- Zapier action scoping
- role folder boundaries.

## Required deliverables

Create/update:

- `FLO_TEAM_BUILD.md`
- `FLO_TEAM_PROGRESS.md`
- `FLO_TEAM_DECISIONS.md`
- `FLO_TEAM_OPEN_QUESTIONS.md`
- `FLO_TEAM_SECURITY_REVIEW.md`
- `FLO_TEAM_TEST_RESULTS.md`

Document:
- actual profile paths created
- actual Hermes APIs/RPCs/plugins used
- model config per agent
- tool scope per agent
- MCP scope per agent
- avatar paths
- routines
- tests
- source gaps
- blockers
- what is production-ready vs scaffold-only.

## Final response

When finished give me:

1. Team roster and implementation status
2. What each bot can actually do now
3. What each bot cannot yet do
4. Avatars generated/installed status
5. Bot-to-bot handoff test results
6. Zapier MCP scoping status
7. Unsloth/local model status
8. Underwriting source-ingestion status
9. Test summary
10. git status/diff stat
11. The top 10 remaining tasks ranked by business value and risk

Do not claim capabilities that are only scaffolds.
