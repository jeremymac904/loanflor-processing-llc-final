# Provider failover (2026-09-09)

What the live expansion exposed: Codex HTTP 429 (usage limit), Nous `gpt-6-astra` HTTP 402 (credits exhausted mid-run), opencode-free "Model is unavailable" after a passing smoke, the deepseek route eventually finishing. Discovery said "available"; it never said "can finish a five-hop workflow".

## Routing state machine (`plugins/flo-team/provider_state.py`)

Per route (provider × model), persisted under `<team root>/providers/`:

provider, model, kind, health, last_successful_completion, last_failure, latency_ms (EWMA), context_capacity, rate_limit_state, credit_state, data_classification_allowed, workflow_suitability (ready / marginal / unsuitable), cooldown_until, retry_after, failure_count, consecutive_failures, success_count, last_error, transitions[].

States: `HEALTHY DEGRADED RATE_LIMITED OUT_OF_CREDIT MODEL_UNAVAILABLE OFFLINE TOO_SLOW CONTEXT_INSUFFICIENT DATA_POLICY_BLOCKED` (+ `UNKNOWN`).

`classify_error()` maps provider errors: 429 / "usage limit" → RATE_LIMITED (retry-after honoured when present), 402 / "insufficient credits" → OUT_OF_CREDIT, "Model is unavailable" / "has been retired" / 404 model → MODEL_UNAVAILABLE, connection errors → OFFLINE, timeouts → TOO_SLOW, context errors → CONTEXT_INSUFFICIENT. Default cooldowns: 30 min / 6 h / 1 h / 10 min / 1 h / 24 h. Discovery rows (`providers.discover`) fold in through `record_health`; successes reset failure counts and cooldowns.

`select(classification)` returns the best usable route (prefer HEALTHY, fewest consecutive failures, lowest latency) for `synthetic | non_sensitive | sensitive`. Sensitive data only ever selects a route whose `data_classification_allowed` includes `sensitive` (today: the local model class); otherwise `FAIL_CLOSED` with the user-facing message **"AI provider unavailable — your work is saved."**

## Preflight (`workflow.preflight`, `flo_workflow action=preflight`)

Before a complex workflow: estimated specialist turns (per return format), data classification of the Deal Room, a route per role, expected latency class, rough minutes, blockers, and the readiness board:

```
Team AI: Ready | Local Fast: Slow | Local Reasoning: Slow | Cloud Reasoning: Healthy | Fallback: Available | Sensitive-data route: Fails closed (no approved route)
```

If a provider is unusable the route is replaced before starting; if nothing compliant exists the workflow does not start and Flo tells Ashley the fail-closed message.

## Mid-chain failover (`workflow.stalled_tasks` / `resume_task` / `check_and_failover`, `flo_workflow action=check|resume`)

1. task state is preserved (the specialist task stays `received` with objective, Deal Room and source refs);
2. the Deal Room is classified (synthetic / non-sensitive / sensitive);
3. another approved provider is selected from the state machine (failed providers excluded);
4. the unfinished specialist turn is resumed by re-entering that profile's Bot Chat with a continuation message naming the task id and the "do not repeat" instruction (`hermes -p <profile> chat -c "Bot Chat" --provider … --model …`);
5. workspace/source references travel with the task record;
6. the transition is recorded on the task (`result.provider_transitions[]`) and in the activity log (`workflow.failover`);
7. completed external actions are not repeated (intents.py; the continuation instruction says so and the tools enforce it).

`check` also ingests provider errors from each profile's `logs/agent.log` (the lines Hermes writes: provider, model, HTTP status) so the state machine learns about a 402 that killed a turn even though no tool call reported it.

## Tests (`tests/flo/test_provider_failover.py`)

Error classification for the real messages seen live; cooldown and rotation after 429 then 402; sensitive fail-closed with only cloud usable; discovery rows folding in; preflight board and estimates; unusable provider replaced before starting; a 429 between Malcolm and Sage resuming Sage on another provider with Malcolm's work untouched; a 402 handled by `check_and_failover`; model-unavailable and too-slow routes skipped; a sensitive workflow with only cloud fallback failing closed with the task preserved; parsing of a real Hermes log line.

## Limits

The resume path re-enters a Bot Chat through the CLI with explicit provider/model flags; it is exercised with a fake spawner in tests and manually on this machine (the USDA recovery used the same mechanism by hand). There is still no per-LLM-call interception inside a running turn (decision D8's honest limit): a turn that dies mid-way is recovered on the next `check`, not inside the same turn.
