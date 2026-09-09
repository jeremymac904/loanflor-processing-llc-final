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
3. creates the Loan Workspace / Deal Room (`milestone: Intake`, program/agency, AUS, `submission` block, LO contact refs, status summary "New submission from Matt Combs (…). Purchase • FHA. Expected close 2026-09-23.");
3b. **pulls every document** (`documentRefs[].fetchUrl`, same bearer token) into a private copy under `<hermes root>/flo/documents/<workspace>/…`, verifies the checksum, extracts the PDF text layer, flags `Page N of M` gaps and duplicates, classifies blanks, and writes `document_refs` + `documents_summary` on the workspace (`plugins/flo-team/documents.py`; see `DOCUMENT_UPLOAD_IMPLEMENTATION.md`);
4. creates ONE Malcolm task through the normal handoff registry: *"Review this new submission and tell Ashley what is missing."* (`file_prep_report`, urgency from the expected closing, facts = the plain-English summary of the submission **plus the document inventory**, constraints: LO-stated figures are claims, use `flo_documents` to read/reclassify/inventory, only ACTIVE source rules make a document required, use `flo_readiness`, ask Flo for guideline questions, finish with received / missing / biggest blocker / best next move);
5. stores the exact `message_agent` packet;
6. starts one Flo turn in her Bot Chat (`hermes -p flo chat -c "Bot Chat" -Q --oneshot …`) unless `--no-spawn`.

**Flo (`flo_intake` tool)** — `pending` lists submissions whose packet has not been sent; `dispatch submission_id=…` returns `send_with` (target Malcolm + message) and marks it dispatched (a second dispatch says "already dispatched; do not send again"); `get` shows the record. Flo sends the packet with `message_agent` and tells Ashley one line: *"New loan came in — Johnson. 12 documents received. Malcolm is reviewing the file now. 💚"*

**Malcolm** receives the handoff like any other: `flo_documents list / inventory`, reads extracted text with `get`, reclassifies or sets statuses with `update` (received, needs_review, reviewed, missing_pages, unreadable, duplicate, not_needed — the file itself is never altered), runs `flo_readiness` (the workspace then shows readiness, missing items, best next move) and reports back to Flo: received count, missing items, biggest blocker, best next move. Flo relays: *"Johnson is reviewed. Received: 12 documents. Missing: 2 items. Biggest blocker: Most recent paystub. Best next move: Request the missing documents."* Sage is only involved if Malcolm asks Flo a guideline question.

**Ashley's screens** (Flo desktop plugin): Today shows a **NEW LOAN** card — *Johnson · Submitted by Matt Combs · FHA • Purchase · Expected closing September 23 · 12 documents received. Malcolm is reviewing it. [Open File]* — and the Pipeline row reads **NEW LOAN · Working · Intake · New submission · 12 documents**. The file's **Documents** section groups Application / Credit / AUS / Income / Assets / Contract / … with ✓ or ⚠ and a plain status, lists what is missing, and offers **Upload Missing Doc** (file picker → Flo files it), **Request From Borrower**, **View Documents**; clicking a document opens a preview (PDF/image, name, category, received, status, borrower) with Open / Download / Mark Not Needed / Reclassify. After Malcolm's readiness report the file shows *Needs 3 items*, AUS *Findings on file*, Income *Reviewed* / Assets *Needs attention*, the missing list and best next move *Request the missing documents.* Nothing technical (ids, storage keys, tokens, JSON, delivery states) is shown.

## Environment

Website server (`.env`, never committed):

```
FLO_INTAKE_URL=https://<private host or tunnel>      # e.g. http://100.x.y.z:8787 over Tailscale
FLO_INTAKE_TOKEN=<shared secret, 24+ chars>
SUBMISSIONS_DIR=/var/lib/loanflow/submissions        # persistent, writable
DOCUMENTS_META_DIR=/var/lib/loanflow/documents-meta  # persistent, writable (document records)
PUBLIC_API_BASE_URL=https://<api host Flo can reach>  # used in the document fetch URLs Flo calls back on
SUPABASE_URL=https://<project>.supabase.co           # private bucket "loan-documents"; service-role key server-side only
SUPABASE_SERVICE_ROLE_KEY=<service role key>
SUPABASE_STORAGE_BUCKET=loan-documents
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
4. **Document storage credentials** — the upload path is built (`DOCUMENT_UPLOAD_IMPLEMENTATION.md`); production needs the Supabase project that owns the private `loan-documents` bucket plus its service-role key in the API host's environment, and `PUBLIC_API_BASE_URL` pointing at an address Flo can reach through the same private path as item 1. Antivirus scanning and the retention/cleanup job are documented follow-ups (`DOCUMENT_SECURITY_REVIEW.md`).
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
