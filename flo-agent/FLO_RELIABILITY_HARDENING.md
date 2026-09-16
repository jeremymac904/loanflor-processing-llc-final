# Flo reliability hardening (2026-09-09)

Objective: make the existing Fannie / Freddie / FHA / VA / USDA implementation trustworthy — correctness, source boundaries, idempotency, provider resilience and review tooling — without adding a program. Non-QM, Jumbo, DSCR, bank-statement, foreign-national and ITIN were not touched; self-employed and rental income stay data structures; no capability was promoted to Trusted.

| # | Priority | Delivered | Where |
|---|---|---|---|
| 1 | FHA current-vs-future rule resolution | Handbook 4000.1 Update 17 (in force) captured next to Update 18 (mandatory 11/10/2026, early implementation permitted); version-qualified sections and rule records; deterministic `resolve_rule` by case number assignment date; cards labelled CURRENT / FUTURE — NOT YET EFFECTIVE / SUPERSEDED / early implementation | `sources.py`, `cards.py`, `knowledge/fha/*`, `FHA_EFFECTIVE_DATE_TESTS.md` |
| 2 | Source-bound prose | `sage_response.py` (build → allowed facts → validate → rewrite), `flo_sage_response` tool, guideline_card tasks close only with a validated response id, Sage SOUL updated | `SOURCE_BOUND_RESPONSE_ARCHITECTURE.md` |
| 3 | Draft idempotency | `draft_intent_id` / `idempotency_key` from workspace, audience, purpose, requested items, source task; one active draft per intent; explicit behaviour for sent / rejected / edited | `drafts.py`, `intents.py`, `ACTION_IDEMPOTENCY.md` |
| 4 | Side-effect idempotency | intent registry for drafts, orders, marketing content and every CONFIRM-gated tool call; duplicate executed payloads blocked at the executor gate | `intents.py`, `__init__.py` hooks |
| 5 | Provider routing state machine | `provider_state.py` (nine health states, cooldowns, retry-after, credit/rate-limit state, data classification, suitability); error classification for the failures seen live | `PROVIDER_FAILOVER.md` |
| 6 | Mid-chain failover | `workflow.py`: stalled-task detection, resume on another approved provider with task/Deal Room/source refs preserved and the transition recorded; sensitive files fail closed with "AI provider unavailable — your work is saved." | `flo_workflow action=check|resume` |
| 7 | Workflow budget preflight | readiness board (Team AI / Local Fast / Local Reasoning / Cloud Reasoning / Fallback / Sensitive-data route), turn and latency estimate, route replacement before starting | `flo_workflow action=preflight` |
| 8 | Knowledge review console | `knowledge_center.py` + `scripts/flo/knowledge_center.py --build` + desktop "Knowledge Center" tab (program, source, version, published, effective, status, checksum, rules, regression, human approval, supersedes, pending update, impact, actions) | `KNOWLEDGE_CENTER.md` |
| 9 | Source diff | `sourcediff.py`: new/removed/changed sections, normalized-text diff, re-anchor list, affected calculators/tests; versioned text copies kept by the cache | `SOURCE_DIFF_AND_IMPACT.md` |
| 10 | Rule impact analysis | `impact.py`: rule → calculators → File Prep/asset bindings → cards → synthetic evals → tests; one-line summaries | same |
| 11 | Overlay architecture | `overlays.py`: overlay records (source, section, effective date, program, product, exception, proposed/approved by, AE confirmation) layered on the agency baseline; conflicts flagged, never resolved; store ships empty (no Loan Factory overlay invented) | `cards.py` lender_overlay layer |
| 12 | Human guidance capture | `guidance.py` + `flo_guidance`: AE/UW clarifications become pending knowledge items with scope and communication reference; loan-specific items reach Sage only for that Deal Room; promotion is an administrator command | `KNOWLEDGE_CENTER.md` |
| 13 | Audit identity | structured approval/activation records (schema 2) everywhere: sections, guidance decisions, overlay activation; local/admin identity abstraction; no e-mail | `identity.py` |
| 14 | Reliability eval | 14 scenarios covered by `test_fha_effective_dates.py`, `test_source_bound_response.py`, `test_idempotency.py`, `test_provider_failover.py`, `test_reliability_regression.py` | `RELIABILITY_REGRESSION_RESULTS.md` |

## Completion standard check

* FHA current/future selection proven: 13 tests, both versions active on this install, whole-team FHA path cites only Update 17 for a case number assigned 2026-08-25 and carries the FUTURE caution.
* Sage cannot materially overstate activated rules without validation catching it: validator + handoff enforcement + tests (USDA $960 case reproduced and caught).
* Duplicate drafts/actions prevented: intent registry across drafts, orders, marketing and executor gate; tests for repeated handoff, wording retry, duplicate delivery, task resubmission, title-order retry, executed-send retry.
* Team workflows survive an approved provider failure mid-chain: state machine + resume + check, tested with 429/402/model-unavailable/too-slow; the same mechanism recovered the USDA run by hand.
* Sensitive workflows fail closed: `select(classification="sensitive")` and `resume_task` both return "AI provider unavailable — your work is saved." when only unapproved routes are usable; preflight board says "Fails closed (no approved route)" on this install (the only sensitive-approved route is the too-slow local model).
* Source changes have visible impact analysis: diff + impact on the CLI, the tool surface and the Knowledge Center.
* Source approval has a durable identity: every active revision on this install carries a schema-2 approval record (test asserts it).
* Knowledge Center reviews the lifecycle: built from the real install (57 revisions), desktop tab with lifecycle-aware actions.
* All reliability regression scenarios pass (see results).

## Remaining production blockers (honest)

1. Sensitive-data route: no approved provider is fast enough (local Ollama is TOO_SLOW; every cloud route is `pii_allowed: false`). Real borrower files therefore fail closed by design until a GPU-backed local endpoint or an approved cloud agreement exists (open questions #6, #20, #27).
2. Failover is a between-turns recovery (`check`/`resume`), not a per-LLM-call interception inside a running turn.
3. Preflight without a live completion probe (`discover=true` without cloud smoke) can still report a cloud route HEALTHY that will 429 on the first real turn; the installer's smoke or `record_failure` from logs closes that gap, and the state machine remembers it.
4. The Knowledge Center's Approve/Activate buttons copy the administrator command; execution stays in the terminal with the approver identity until the desktop exposes authenticated user ids.
5. The source-bound validator is lexical (numbers, periods, ratios, modal sentences); it does not judge semantic misuse of a supported number.
