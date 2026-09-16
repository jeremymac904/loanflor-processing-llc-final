# Action idempotency (2026-09-09)

Why: Whisper created the same borrower draft three times in one USDA turn (model retries). The same failure class would send an e-mail, place a title order or publish a post twice after a provider retry or a duplicate `message_agent` delivery.

## Intent identity (`plugins/flo-team/intents.py`)

```
intent_id = sha256(kind | workspace_id | target | purpose | material_hash)[:16]
```

* `kind`: draft, order, send_email, title_order, hoi_request, wvoe, calendar_event, upload, publish_gbp, publish_newsletter, publish_blog, publish_social, marketing_content, tool_call
* `material`: the relevant payload only — for a draft the audience, channel, purpose category and the normalized, order-insensitive list of requested items (first eight content words each); for an order the order type and property/borrower/vendor/employer/authorization refs; for a tool call the material argument keys the Approval Center already hashes (recipients, subject, body, attachments, amounts, destinations). Wording changes do not change the identity; a material change does.
* Registry: `<team root>/intents/<intent_id>.json` with `record_id` (draft_id / order_id / proposal_id), state and history; every claim and transition is in the activity log.

## Decision before acting

`IntentRegistry.check()` → `return_existing` when an intent is active (pending / proposed / approved) **or** was executed/sent/ordered/published within 30 days; `create_new` when no intent exists or the previous one is rejected / cancelled / expired / invalidated (or executed more than 30 days ago).

| Surface | Behaviour |
|---|---|
| `flo_draft create` | `draft_intent_id` + `idempotency_key` on the record; an active draft with the same intent in the Deal Room is returned (`decision: return_existing`, `deduplicated: true`) — no new draft. `mark` moves the intent to proposed / sent / rejected. |
| `flo_order propose` | same identity on `order_type` + refs; returns the existing open order, and after `ordered` (execution_ref) still returns it ("already ordered … a retry must not repeat it"). |
| `flo_marketing create` | channel + normalized title while unpublished → the same item. |
| Approval Center + executor (`pre_tool_call` hook) | a CONFIRM-gated tool call claims a `tool_call` intent keyed on the material payload; `post_tool_call` marks it executed with the execution ref; a later call with the same payload is **blocked**: "DUPLICATE side effect prevented … nothing was sent, ordered or published twice." A materially edited payload is a new intent (and a new approval card). |

Explicit behaviours: materially edited → new intent; rejected/expired → fresh intent allowed; sent/executed → returned as done (never re-run) for 30 days.

## Tests (`tests/flo/test_idempotency.py`)

Repeated identical handoff; retry with different wording (still one draft); duplicate `message_agent` delivery and Flo resubmitting the task (one draft across three attempts); materially different request (second draft); rejected draft allows a fresh one; duplicate title-order retry (one order, then "already ordered" after placement); executed e-mail send blocked on retry through the real hook, edited payload allowed; marketing content deduplicated until published.

## Trusted autonomy

Still not granted. Action-level idempotency is now in place for every proposal path and the executor gate, which was the stated precondition; the autonomy level stays Assisted (every external action confirms).
