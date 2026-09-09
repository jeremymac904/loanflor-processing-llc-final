# Flo intake integration

How a website submission becomes a new loan in Flo, what runs where, and what production still needs.

## Components

**Website backend (this repo, Express)** — the only thing the browser talks to.
`POST /api/loan-submissions` validates, persists (`server/data/submissions/<id>.json`), and calls the connector `server/services/floIntake.js`:

```
POST {FLO_INTAKE_URL}/intake/loan-submissions
Authorization: Bearer {FLO_INTAKE_TOKEN}
Idempotency-Key: <submissionId>
X-LoanFlow-Source: lfprocessing.net
Content-Type: application/json            body = the v1.0 payload
```
201 `{ok, submissionId, workspaceId, taskId, status:"accepted"}` · 200 `status:"duplicate"` (same id again) · 400 payload rejected (not retried) · 401 bad token · 5xx / timeout / unreachable → kept as `pending_delivery` and retried by `server/services/deliveryQueue.js`.

**Flo intake endpoint (Flo repo, `scripts/flo/intake_server.py`)** — runs on Ashley's machine next to Hermes:

```
FLO_INTAKE_TOKEN=<24+ char shared secret> python scripts/flo/intake_server.py --host 127.0.0.1 --port 8787
```
Refuses to start without a token. Binds to localhost by default. Body limit 1 MB. Logs ids only. On an accepted submission it calls `plugins/flo-team/intake.py: receive()`:

1. validates the payload (schema version, required fields, sensitive-data scan);
2. **idempotent** on `submissionId` (`<team root>/intake/<id>.json`) — a redelivery returns the existing workspace and task;
3. creates the Loan Workspace / Deal Room (`milestone: Intake`, program/agency, AUS, `submission` block, document references, LO contact refs, status summary "New submission from Matt Combs (…). Purchase • FHA. Expected close 2026-09-23.");
4. creates ONE Malcolm task through the normal handoff registry: *"Review this new submission and tell Ashley what is missing."* (`file_prep_report`, urgency from the expected closing, facts = the plain-English summary of the submission, constraints: LO-stated figures are claims, documents are listed not received, use `flo_readiness`, ask Flo for guideline questions);
5. stores the exact `message_agent` packet;
6. starts one Flo turn in her Bot Chat (`hermes -p flo chat -c "Bot Chat" -Q --oneshot …`) unless `--no-spawn`.

**Flo (`flo_intake` tool)** — `pending` lists submissions whose packet has not been sent; `dispatch submission_id=…` returns `send_with` (target Malcolm + message) and marks it dispatched (a second dispatch says "already dispatched; do not send again"); `get` shows the record. Flo sends the packet with `message_agent` and tells Ashley one line: *"New loan came in — Johnson. Malcolm is reviewing it now. 💚"*

**Malcolm** receives the handoff like any other, runs `flo_readiness` (the workspace then shows readiness, missing items, best next move) and reports back to Flo. Sage is only involved if Malcolm asks Flo a guideline question.

**Ashley's screens** (Flo desktop plugin): Today shows a **NEW LOAN** card — *Johnson · Submitted by Matt Combs · FHA • Purchase · Expected closing September 23 · Malcolm is reviewing it. [Open File]* — and the Pipeline row reads **NEW LOAN · Working · Intake · New submission**. After Malcolm's readiness report the file shows *Needs 3 items*, AUS *Findings on file*, Income *Reviewed* / Assets *Needs attention*, the missing list, best next move *Request the missing documents.* and **Request From Borrower**. Nothing technical (ids, tokens, JSON, delivery states) is shown.

## Environment

Website server (`.env`, never committed):

```
FLO_INTAKE_URL=https://<private host or tunnel>      # e.g. http://100.x.y.z:8787 over Tailscale
FLO_INTAKE_TOKEN=<shared secret, 24+ chars>
SUBMISSIONS_DIR=/var/lib/loanflow/submissions        # persistent, writable
CORS_ORIGIN=https://lfprocessing.net
NODE_ENV=production
```

Flo machine:

```
FLO_INTAKE_TOKEN=<same secret>
FLO_INTAKE_HOST=127.0.0.1   FLO_INTAKE_PORT=8787
```

## What production still needs

1. **A private path from the website host to Ashley's machine** — Tailscale (simplest), Cloudflare Tunnel with access policy, or a VPN. The intake must not be reachable from the public internet; the Hermes gateway itself is never exposed.
2. **Run the intake server as a service** on Ashley's machine (Task Scheduler / launchd) with the token in the environment, and keep Hermes' Flo profile installed (the spawn uses the `flo` Bot Chat).
3. **Host the Express API** for lfprocessing.net. The current site is static hosting (hcdn); `server/index.js` needs a Node host (Railway/Render/Fly or the same VPS as the tunnel) with `SUBMISSIONS_DIR` on persistent disk, and the site's `/api` proxied to it (Vite proxies in dev only).
4. **Secure document upload** (currently UI-only). Needed: object storage with server-side encryption (S3/GCS/Drive via the existing Google service account), presigned or server-mediated uploads with type/size validation and virus scanning, a retention policy, and on the Flo side a `document_refs` status change to `received` with the storage reference. Until then the LO gets a secure upload link from processing.
5. **Optional**: Google Sheet summary row (set the three `GOOGLE_*` vars); the full submission never goes to the sheet.
6. **Monitoring**: `GET /api/health` reports `pendingDelivery`; the intake reports `pendingDispatch` at `GET /intake/health`.

## Local run (what the end-to-end test used)

```
# Flo repo
FLO_INTAKE_TOKEN=local-e2e-token-0123456789abcdef python scripts/flo/intake_server.py --port 8787
# website repo (.env: FLO_INTAKE_URL=http://127.0.0.1:8787, same token)
npm run start        # API on :3001
npm run dev          # site on :3000, /api proxied
```
