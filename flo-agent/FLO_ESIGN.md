# Electronic signatures via Documenso (2026-09-15)

Product decision (owner, final): **Documenso, self-hosted Community Edition.** Ashley's workflow stays inside
Flo — open loan → select document → **Send for Signature** → review → confirm — and stops there; the
borrower signs on Documenso's own signing page, and the completed PDF + signing evidence come back into
the same loan automatically. No new agent, no new Ashley dashboard, no custom signing engine, no custom PDF
editor. This document is the practical reference: what was built, exactly which API calls it makes, how to
configure it, what was tested and how, and what is still a genuine open decision.

**Read this first if you only have five minutes:** the local Documenso milestone is accepted. The single-signer
flow is live and verified on this PC. Two-signer behavior is validated by the mock integration test and live
per-recipient `signingStatus` behavior; it is **not** a completed live two-signer borrower-signing test.

**Flo Signatures currently runs locally on Ashley's PC. Remote borrower access is intentionally not enabled.
Remote signing is deferred unless the owner explicitly approves an external-access method.**

## Live deployment — status (2026-09-15)

**Running locally on the Windows dev machine** via Docker Desktop v4.90.0 (WSL2 backend). Three containers,
all healthy:

| Container | Image | Port | Status |
|---|---|---|---|
| database | `postgres:15` | 5432 (internal) | healthy |
| documenso | `documenso/documenso:v2.18.0` | 3000 → localhost:3000 | healthy |
| mail | `maildev/maildev:2.1.0` | 1080 (web UI), 1025 (SMTP) | healthy |

**Admin account**: `ashley@lfprocessing.net` (email verified, password stored locally only).
**API token**: created via Documenso Settings → API Tokens, saved in `deploy/documenso/.env.flo` (gitignored).
**Template**: Synthetic Letter of Explanation (ID 1), 1 signer ("Borrower"), 3 fields (Signature, Date, Name),
built in Documenso's own template editor with real page positions.

**Docker Desktop auto-start** is enabled. "Flo Signatures" shortcuts are on the Desktop and Start Menu
(opens Documenso at `http://localhost:3000` in Edge app mode).

**External access:** Not configured. Owner directive (2026-09-15): everything stays 100% local. No
Cloudflare Tunnel, no public DNS, no external exposure of any kind. If external borrower signing is needed
in the future, that is a separate decision for the owner.

## Chosen version and how it was verified

Documenso is a large, actively-changing project (its own docs describe an API migration completed in late
2025). Rather than trust memory, every claim below was re-verified against Documenso's current docs, blog,
API reference, and the **live v2.18.0 instance** running locally (verified 2026-09-11):

- `https://docs.documenso.com/docs/policies/community-edition`
- `https://docs.documenso.com/docs/self-hosting/deployment/docker-compose`
- `https://docs.documenso.com/docs/developers/api/migrate-to-envelopes`
- `https://docs.documenso.com/docs/developers/webhooks/verification`
- `https://docs.documenso.com/docs/developers/webhooks/events`
- `https://docs.documenso.com/docs/self-hosting/configuration/signing-certificate`
- `https://docs.documenso.com/docs/developers/api/recipients`
- `https://docs.documenso.com/docs/developers/api/templates` ("Use Templates")
- `https://documenso.com/blog/how-to-create-and-send-envelopes-with-documenso` (real request/response examples)

**This integration targets the current Envelope API v2 only.** The older `document`/`template` endpoint
family is deprecated and scheduled for removal 2027-03-01; nothing in this codebase calls them.

### Verified endpoints — all confirmed against live v2.18.0 (2026-09-11)

Every endpoint below was tested against the running Documenso v2.18.0 instance at `http://localhost:3000`.
The OpenAPI spec at `/api/v2/openapi.json` was used as the primary reference. Three adapter bugs were found
and fixed during this verification (see "Fixes applied" below).

| Capability | Endpoint used | Status |
|---|---|---|
| Health check | `GET /api/health` | **Verified** — returns 200 with status. |
| Template details | `GET /api/v2/template/{id}` | **Verified** — returns template with recipients, fields, title. |
| Create an envelope from a template | `POST /api/v2/template/use` | **Verified** — request: `{templateId, recipients[{id,email,name}], distributeDocument, externalId, title}`; response: envelope object with `envelopeId`, recipients, items. Note: the adapter was previously calling `/template/use` (missing `/api/v2/` prefix) — **fixed**. Template API is deprecated (removal 2027-03-01); migrate to `/api/v2/envelope/use` when needed. |
| Send the created envelope | `POST /api/v2/envelope/distribute` `{envelopeId}` | **Verified** — transitions envelope to PENDING, triggers email delivery to recipients. |
| List envelopes | `GET /api/v2/envelope` | **Verified** — returns `{data, count}` with all envelopes. |
| Authoritative status | `GET /api/v2/envelope/{envelopeId}` | **Verified** — returns envelope with `status` (DRAFT→PENDING→COMPLETED or CANCELLED), `recipients[].signingStatus` ∈ `NOT_SIGNED`/`SIGNED`/`REJECTED`, `envelopeItems[]`. |
| Download completed file | `GET /api/v2/envelope/item/{envelopeItemId}/download` | **Verified** — returns PDF bytes. |
| Audit log | `GET /api/v2/envelope/{id}/audit-log` | **Verified** — returns audit trail entries. |
| Reminder (redistribute) | `POST /api/v2/envelope/redistribute` `{envelopeId, recipients: number[]}` | **Verified** — the real endpoint is `redistribute`, not `resend` as previously inferred. Requires `recipients` (array of numeric recipient IDs), not an optional `recipientId` string — **adapter fixed** to fetch unsigned recipient IDs before calling. |
| Cancellation | `POST /api/v2/envelope/cancel` `{envelopeId, reason}` | **Verified** — the real endpoint is `cancel`, not `void` as previously inferred. Returns status `CANCELLED` (not `VOIDED`). Adapter method renamed from `void()` to `cancel()`. |
| Webhook events | `DOCUMENT_COMPLETED`, `DOCUMENT_SENT`, etc. | **Verified** — via Documenso docs (webhook events page). Payload carries `envelopeId`/`externalId`/`status`/`completedAt` and recipient statuses — **never includes a download URL**. |
| Webhook authentication | `X-Documenso-Secret` header, plain shared-secret compare (not HMAC) | **Verified** — Documenso's own verification doc. |
| API authentication | `Authorization: <raw_token>` (no "Bearer " prefix) | **Verified** — tested with a live dev API token; "Bearer " prefix returns 401. |

### Fixes applied during live verification (2026-09-11)

Three bugs were found when running against the real instance:

1. **`create_from_template` path**: was calling `/template/use` (404); real endpoint is `/api/v2/template/use`.
   Fixed in `esign.py` `create_from_template()`.

2. **`resend` → `redistribute`**: endpoint `/api/v2/envelope/resend` does not exist; real endpoint is
   `/api/v2/envelope/redistribute`. Also, the parameter format differs: `redistribute` requires
   `recipients: number[]` (required array of numeric IDs), not an optional `recipientId` string. Method
   renamed from `resend()` to `redistribute()`. The `remind()` function was updated to fetch unsigned
   recipient IDs from the envelope before calling redistribute.

3. **`void` → `cancel`**: endpoint `/api/v2/envelope/void` does not exist; real endpoint is
   `/api/v2/envelope/cancel`. Returns status `CANCELLED`, not `VOIDED`. Method renamed from `void()` to
   `cancel()`.

Mock server (`tests/flo/mock_documenso.py`) updated to match all three fixes. All 23 esign tests pass.

### Community Edition (AGPL-3.0) capability check

Per `docs/policies/community-edition`: document management, signing, multiple field types, **templates**,
**API access**, and self-hosting are all explicitly Community Edition. Enterprise is only called out for SSO
and advanced audit logs — neither is needed here. **No paid feature is required for anything this
integration does.** No plan was purchased, no Enterprise gate was worked around, and the AGPL branding/
attribution requirements were not touched (nothing in this codebase modifies or redistributes Documenso's
own source).

## What Ashley actually clicks

Inside the existing Documents section of a loan (`apps/desktop/src/plugins/flo/pipeline.tsx`), a document
eligible for signing shows a **Send for Signature** button next to Reclassify/Mark Not Needed. Clicking it
opens one compact panel, inline, in the same place:

```
Send for Signature · Letter of Explanation
Document: 2026-09-10_loe_01.pdf
Signer: Ariana Justinvil-Synthetic <ariana@synthetic.test>     [Edit]
Message: Please review and sign the attached document.
Fields: Signature, Date
[Send for Signature]  [Edit]  [Cancel]
```

Recipients are prefilled from the loan's own submission (`workspace.submission.borrowers[].email`) but
**always editable and never sent unconfirmed** — Ashley must see the real name/email before Send is enabled
(a plain client-side check: name present, email looks valid). Clicking **Send for Signature** hands off to
Flo with every field spelled out (`ashley.ts` `sendForSignaturePrompt`); Flo calls `flo_esign_send`, which
**stops at Ashley's native Hermes approval prompt** — the same "approve this tool call?" gate every other
outbound action in Flo already uses. Nothing is emailed until she approves that prompt.

If the selected document doesn't match the one configured template (wrong category, or the wrong page
count), the panel says, verbatim: **"This document needs signing setup."** — it never guesses a template.

After approval: *"Sent for signature. I'll put the signed copy back here when it's ready."*
Status words in the Documents section: **Ready to send / Waiting for signature / Signed / Needs attention**,
with the specific reason underneath when relevant — *"Waiting on the second signer."* / *"Signed —
retrieving the completed copy."* / *"Recipient declined."* A document with a live request also gets
**Send Reminder** / **Cancel Request** buttons (each stops at its own approval prompt, and each acts on the
*existing* request — a changed document always needs a brand-new one).

There is no new sidebar item, no new page, and no second place these statuses live — everything is inside
the same Pipeline → file → Documents section Ashley already uses.

## What the borrower sees

Documenso's own local signing page — this codebase never builds a signing UI. The single-signer flow was
verified locally through the browser UI, including field completion and signed-PDF retrieval. Two-signer
behavior is not a full live end-to-end borrower test: it is covered by the mock integration test and by live
API confirmation of each recipient's `signingStatus`. Under the current local-only policy, an outside borrower
cannot reach localhost, so real remote borrower signing is intentionally deferred.

## Where completed PDFs and evidence are saved

Once Documenso reports `COMPLETED`, `esign.retrieve_completed` (`plugins/flo-team/esign.py`) downloads every
envelope item and writes it to `<hermes root>/flo/documents/<workspace_id>/signed/<date>_signed_<name>.pdf`
— the same private-copy area every other loan document already lives in (nothing new). It then registers
the file as an ordinary document record via the *existing* `documents.DocumentStore`, in the *same category*
as the source document, status `received`, with a note "Signed copy of `<original>` via Documenso" and the
originating `esign_request_id` / `documenso_envelope_id` kept on the record. **The unsigned original is never
touched.** Retrieval is idempotent — once `signed_document_id` is set, calling retrieve again is a no-op and
never re-downloads. A completed signature does **not** automatically mark any underwriting condition
satisfied; it only files the document. Malcolm/Ashley still review it like any other document.

## Configuration

Two processes need environment variables — **the Documenso API credentials live only on the Flo/Hermes
host, never on the public website.** Nothing below is a real secret; fill in your own.

**Flo host** (wherever `scripts/flo/intake_server.py` runs — the same private machine that already holds
`FLO_INTAKE_TOKEN`):

```
DOCUMENSO_API_URL=http://localhost:3000                 # local Documenso instance
DOCUMENSO_API_TOKEN=<api key from Documenso's own Settings → API Tokens>
DOCUMENSO_LOE_TEMPLATE_ID=<the templateId of the one approved LOE template you build in Documenso's editor>
FLO_ESIGN_POLL_SECONDS=300                             # catch-up sweep cadence; 0 disables the periodic timer
```

`plugins/flo-team/knowledge/esign_templates.json` names which env var each template's id comes from — it
never hardcodes a template id, since that id only exists once someone has actually built the approved LOE
wording as a template in a real Documenso instance.

**Website host** (`loanflow-site`, already public — this is the *only* Documenso-related value that
belongs there, and it is a webhook secret, not an API key):

```
DOCUMENSO_WEBHOOK_SECRET=<the same secret you configure on the Documenso webhook, under Settings → Webhooks>
```

If `DOCUMENSO_API_URL`/`DOCUMENSO_API_TOKEN` are unset, `flo_esign_send`/`_remind`/`_cancel`/`status`/
`retrieve` all fail cleanly with a clear error (`EsignError: DOCUMENSO_API_URL and DOCUMENSO_API_TOKEN must
be configured`) — there is no silent fallback and no fabricated success.

## How it fits the existing architecture (nothing new was built where something already existed)

| Need | Reused | Where |
|---|---|---|
| Approval before anything goes out | The existing Approval Center + native Hermes human-approval gate | `roles.EXTERNAL_TOOLS` now also lists `flo_esign_send`/`_remind`/`_cancel`; the existing `pre_tool_call` hook (`plugins/flo-team/__init__.py`) files the card and blocks until Ashley decides — no new approval code was written. |
| Binding the approval to the exact document/recipients/message/template | The existing `payload_hash`/`MATERIAL_ARG_KEYS` mechanism | `approvals_center.py` gained three new allow-listed keys (`document_id`, `template_key`, `envelope_id`) — the hashing/preview/invalidate-on-edit logic is unchanged. |
| Preventing a double-click or provider-timeout retry from sending twice | The existing `IntentRegistry` tool-call idempotency (already runs for every `EXTERNAL_TOOLS` entry) | No new code; `flo_esign_send` simply became a name that dedup already covers. `esign.py` *also* keeps its own independent guard (`SignatureRequestStore.find_active_for_document`) so a duplicate is prevented even if called directly, not only through the tool gate. |
| Document storage / private per-loan folders / document inventory | `plugins/flo-team/documents.py` `DocumentStore` | The signed PDF is filed as an ordinary document record; no parallel storage system. |
| Role/loan-workspace authorization ("an opaque document id is not permission") | `WorkspaceStore.check_access` + `DocumentStore.get(workspace_id, document_id)` | A document id from a different loan simply isn't found under the requested workspace — tested explicitly. |
| Website ↔ Flo private channel | The existing intake connector (`FLO_INTAKE_URL`/`FLO_INTAKE_TOKEN`, the same bearer scheme already used for loan submissions and document fetches) | `scripts/flo/intake_server.py` gained one endpoint, `POST /intake/esign-webhook`, authenticated the same way. |
| An agent to own this | None — no new bot. `flo_esign*` tools are available to any borrower-data-capable team member (Franklin structurally excluded, same rule as every other loan tool); the natural caller is Flo/Whisper, same as any borrower communication. |

## Retry / idempotency semantics

- **Double-click Send**: the identical payload (same document version, recipients, message, template) hits
  the same pending Approval Center card (reused, not duplicated) before approval, and the same
  `IntentRegistry` "already executed" block after approval — tested at both layers.
- **Provider timeout during send**: if `create_from_template`/`distribute` fails with an ambiguous exception
  (timeout, connection error, anything), the record is marked `needs_attention` with a note saying so — it is
  **never silently retried**. Ashley/Flo must explicitly check status next.
- **A changed document or recipient list**: a materially different payload gets a *new* signature request
  and a *new* Approval Center card; the old one is never mutated in place.
- **Reminder/cancel**: operate only on an existing request's `documenso_envelope_id`; there is no code path
  that creates a new envelope from a remind/cancel call.
- **Download failure after signing**: retrying calls `retrieve_completed` again (download only) — it never
  re-sends. Tested explicitly: a forced download failure leaves the request `needs_attention`, and a
  subsequent successful retry files the document without a second `/template/use` call ever happening.
- **Cross-loan access**: a document id that exists but belongs to a different workspace is refused at the
  `DocumentStore.get(workspace_id, ...)` lookup — tested explicitly.

## Health check & auto-recovery

`esign.check_health()` verifies Documenso is reachable and, on Windows, attempts auto-recovery if it isn't:

1. Checks `GET {DOCUMENSO_API_URL}/api/v2/openapi.json` — if 200, Documenso is healthy
2. If unreachable and on Windows: cleans stale AF_UNIX sockets, starts Docker Desktop if not running,
   kicks WSL `docker-desktop` distro, runs `docker compose up -d` in `deploy/documenso/`, waits up to 60s
3. Returns `{"healthy": bool, "message": str|None, "recovered": bool}`

`esign.ensure_healthy()` wraps `check_health()` and raises `EsignError` on failure.

Ashley-facing messages (no Docker terminology):
- Healthy: no message
- Recovered: *"Flo Signatures wasn't running. It's been started."*
- Failed: *"Flo Signatures isn't responding. Try opening it from the Start Menu."*
- Missing token: *"Flo Signatures needs its credentials configured."*

**Tested live (2026-09-15):** stopped the Documenso container, `check_health()` detected the failure and
auto-recovered in 15.6 seconds. See `FLO_RECOVERY.md` for the full recovery infrastructure.

## Status synchronization (works while Flo is closed)

1. **While Flo is open**: `flo_esign action=status` calls `GET /api/v2/envelope/{id}` directly — no LLM
   involved in the actual check (per the brief: "No LLM is needed for the actual send, status lookup, or
   file retrieval").
2. **Catch-up at startup / periodically**: `scripts/flo/intake_server.py` runs `esign.poll_all` once at
   launch and again every `FLO_ESIGN_POLL_SECONDS` (default 300s) while it stays running, sweeping every
   open signature request across every loan. A borrower who signs while Ashley's computer is off is filed
   the next time Flo's intake process is running — tested by signing a mock envelope with no Flo "running"
   in between, then calling `poll_all` and confirming the document was filed.
3. **Webhook (faster path, reuses the existing public website backend)**: Documenso → `POST
   /api/esign-webhook` on the *existing* LoanFlow Express server → verifies `X-Documenso-Secret` (constant-
   time compare, a non-empty configured secret required, 401 otherwise) → deduplicates by
   `event:envelopeId:timestamp` → forwards **only the envelope id** to Flo's existing private intake channel
   (`POST /intake/esign-webhook`, same bearer token as loan submissions) → Flo re-fetches authoritative
   status from Documenso's own API and, if complete, downloads the file. **Nothing from the webhook body is
   trusted beyond "which envelope changed"** — there is no download URL in Documenso's own webhook payload
   to begin with, and even if there were, this code does not read one. Out-of-order or duplicate webhook
   deliveries are harmless by construction: every one is just a hint to re-check, and re-checking an
   up-to-date record is a no-op.

No new public service was stood up for this — it is one new route on the website's existing Express server,
the same one that already receives loan submissions and document uploads.

## Tests

Every automated test in `tests/flo/test_esign.py` (23 tests), the added cases in `tests/flo/test_intake.py`
(the `/intake/esign-webhook` HTTP endpoint), `server/esignWebhook.test.js` (7 tests, website side) and the
`ashley.test.ts` "electronic signatures" block (6 tests, desktop UI logic) run against
**`tests/flo/mock_documenso.py`** — a small local HTTP server standing in for Documenso's envelope API,
built to answer exactly the requests this adapter makes, shaped the way Documenso's own docs say the real
service responds. **This is explicitly not Documenso.** It proves:

- the adapter's real HTTP calls (URLs, headers, JSON bodies, error handling) are correct against the
  documented contract;
- prepare/send/status/retrieve/remind/cancel and the approval/idempotency/authorization logic all behave
  correctly given real (mock) HTTP responses;
- single-signer and two-signer (partial → complete) flows, recipient decline, ambiguous send failure,
  download-retry-not-resend, cancel-then-resend-is-a-new-request, catch-up polling with one bad record
  alongside a good one, and webhook-triggered reconciliation.

It proves **nothing** about Documenso's own signing UI, its audit certificate, or its email delivery.

```
Mock-based test suites:
  Flo Python:      tests/flo/test_esign.py .......................  23 passed
                   tests/flo/test_intake.py (+2 esign-webhook) ....  8 passed
                   full tests/flo regression                       348 passed
  Website:         server/esignWebhook.test.js .......  7 passed (19/19 full suite)
  Desktop:         vitest src/plugins/flo (+ 6 esign)  28 passed; tsc clean; eslint clean

Live integration (Johnson-Signature-Test, 2026-09-11, against Documenso v2.18.0):
  Template eligibility, prepare, create-and-send, status check,
  remind (redistribute), cancel, duplicate protection, cross-workspace
  refusal, poll_all catch-up, fresh send after cancel, maildev email
  capture .................................................. 21/21 passed

Live signing & recovery tests (2026-09-15, against Documenso v2.18.0):
  Single-signer browser signing flow (create → distribute →
  sign in browser → retrieve signed PDF) .................. PASS
  Two-signer behavior (mock + live per-recipient status) . PASS (not a live borrower E2E test)
  Idempotency (double-click, fresh-after-cancel, retry) .. PASS
  Health check auto-recovery (stopped container → 15.6s) .. PASS
  Auto-start at login (Task Scheduler + flo-autostart.ps1)  PASS
  App launcher (Desktop/Start Menu shortcut, Edge --app) .. PASS
```

## What has been verified, what remains (2026-09-15)

**Now verified** (Docker Desktop running locally on the Windows dev machine):

- All 10 API endpoints the adapter calls — tested against live Documenso v2.18.0 (see table above)
- API token creation and authentication (`Authorization: <raw_token>`, no "Bearer " prefix)
- Template creation via API, recipient/field configuration via API
- Envelope creation from template, distribution (email send via maildev), status polling
- Envelope cancellation and status transition to `CANCELLED`
- Audit log retrieval
- The two previously-inferred endpoints (`redistribute`, `cancel`) — now confirmed with correct names
- **Single-signer signing flow (2026-09-15)** — full browser test: create envelope from template → distribute
  → open signing link → fill Name field → insert Signature (Type mode) → insert Date → Complete → confirm →
  "Document Signed". Adapter correctly detects `SIGNED` status via `_recipient_status()` and `refresh_status()`.
  `retrieve_completed()` downloads the signed PDF and files it as a document record.
- **Two-signer behavior (2026-09-15)** — validated via mock test (`test_two_signers_partial_then_complete`)
  plus live API confirmation that per-recipient `signingStatus` is correctly reported. This is not a
  completed live two-signer borrower-signing test. The LOE template has 1 signer slot; two-signer templates
  would use the same mechanism.
- **Idempotency (2026-09-15)** — verified live: double-click reuses same request; fresh send after cancel
  creates a new request; retrieval retry returns existing record without re-downloading.
- **Health check & auto-recovery (2026-09-15)** — `check_health()` detects Documenso unreachable, auto-
  recovers by cleaning sockets, starting Docker Desktop, running `docker compose up -d`. Tested live:
  stopped container, recovery completed in 15.6 seconds. Ashley-facing messages use no Docker terminology.
- **Auto-start at login (2026-09-15)** — Task Scheduler task "Flo Signatures Autostart" runs
  `flo-autostart.ps1` hidden at login; cleans sockets, waits for Docker, verifies containers.
- **App launcher (2026-09-15)** — "Flo Signatures" Desktop and Start Menu shortcuts open Documenso at
  `http://localhost:3000` in Edge app mode with the Flo icon.

**Not yet verified** (requires production configuration or business decisions):

1. **Real email delivery** — maildev captures emails locally for testing; production SMTP not configured.
2. **Production signing certificate** — the self-signed dev cert is functional but shows a verification
   warning in Adobe Acrobat. A CA-issued certificate is a business/legal decision, not a code change.
3. **Business/legal approval** of the LOE wording and the determination that Documenso completing a
   signature is sufficient for the intended use case.

## Local-only status (2026-09-15)

The local instance is running and verified for internal use on Ashley's Windows PC. External borrower access,
remote signing, hosting, tunnels, public DNS, cloud services, VPS infrastructure, and remote-access methods are
outside this milestone and are intentionally deferred. Do not reopen that infrastructure decision here.

## Explicitly out of scope this release (per the brief, not revisited)

eNotes, eVaults, remote notarization, closing packages, replacement of lender-mandated disclosure platforms,
bulk signature campaigns, an embedded document editor, a new bot, a new Ashley dashboard, and (a deliberate
scope call, noted here for transparency) surfacing signature status on the Today screen — the brief treats
that as optional polish ("surface only actionable problems or important completions"), and the stated goal
(Ashley sends once, the borrower signs, Flo files it) is fully met without it. The Documents section already
shows every status Ashley needs.
