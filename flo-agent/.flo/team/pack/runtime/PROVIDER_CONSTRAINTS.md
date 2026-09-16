# Provider Constraints

## Runtime abstraction

Profiles should choose logical model classes, not assume a hardcoded endpoint.

Conceptual:
- `local_fast`
- `local_reasoning`
- `cloud_reasoning`
- `deterministic`

## Fallback

If local model unavailable:
- safe read/draft tasks may route to an approved fallback if data policy allows;
- sensitive tasks should fail closed rather than silently send data to an unapproved cloud;
- policy/calculation functions remain deterministic.

## Context

The currently verified Hermes-via-Unsloth path needs >=64K context.

Add a startup health check:
- endpoint reachable;
- model listed;
- context requirement satisfied;
- test completion works;
- model ID mapping valid.

Do not bury provider-name prefix workarounds inside five separate profile configs. Centralize them in the provider adapter.
