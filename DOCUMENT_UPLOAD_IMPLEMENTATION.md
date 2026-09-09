# Document upload — implementation (2026-09-09)

When a loan officer submits a new loan on lfprocessing.net, the documents arrive securely, are organized automatically, and show up inside Flo ready for Malcolm to review. This document says what was built, where each piece runs, and what production still needs. Schema: `DOCUMENT_STORAGE_SCHEMA.md`. Security: `DOCUMENT_SECURITY_REVIEW.md`. Evidence: `DOCUMENT_INTAKE_TEST_RESULTS.md`.

## Flow

```
Browser (Documents step)
   │  PUT /api/loan-submissions/:id/documents?category&subcategory&borrower&filename   (raw bytes, one file per request)
   ▼
Website API (Express, server/routes/documents.js)
   │  validateUpload: extension allow-list, size ≤ 25 MB, magic bytes match the extension, HTML/script sniff,
   │  filename must not carry an SSN / account number; sha256 → duplicate detection
   │  documentStore.register: opaque doc id, clean display name, generated storage key
   ▼
Private storage (server/services/documentStorage.js)
   │  Supabase Storage private bucket (production)  ·  local disk under server/data/documents (dev)
   │  no public URLs, credentials only in the server environment
   ▼
POST /api/loan-submissions  (the LO clicks Submit)
   │  the server REPLACES the browser's document list with its own records (documentRefsFromRecords)
   │  each ref carries a fetchUrl: {PUBLIC_API_BASE_URL}/api/internal/documents/<submission>/<doc>
   ▼
Flo intake (Flo repo, scripts/flo/intake_server.py → plugins/flo-team/intake.py)
   │  documents.ingest: GET fetchUrl with the shared bearer token, verify sha256, write the private copy,
   │  extract the PDF text layer, detect "Page N of M" gaps, classify blanks, mark duplicates
   ▼
Deal Room (workspace.document_refs + documents_summary) → Malcolm task (facts include the inventory)
   │  Malcolm: flo_documents list / get / update / inventory → flo_readiness → File Prep summary to Flo
   ▼
Ashley: Today "8 documents received" · Pipeline file DOCUMENTS section (✓ / ⚠, missing, preview) · Flo's one-line updates
```

The browser never talks to storage or to Hermes. Hermes never talks to the browser. The only cross-system call is the website API → Flo intake POST (existing), and Flo → website API `GET /api/internal/documents/...` with the same shared token (new).

## Storage provider decision

**Supabase Storage, private bucket `loan-documents`.** It is already part of this stack (the site's Login goes to a Supabase-backed app and a Supabase connector is attached to the workspace), so no new cloud account; it gives a private bucket with no public URLs, signed URLs when we want them, per-object metadata, and simple deletion. Uploads go **browser → this server → bucket** with the service-role key (never a presigned browser upload, so the browser never sees storage credentials and every byte passes the server-side validator). The driver is `SupabaseStorage` in `server/services/documentStorage.js` (Storage REST: `POST/GET/HEAD/DELETE /storage/v1/object/<bucket>/<key>`, `x-upsert: false`, `POST .../object/sign/...` for signed URLs), covered by tests with a fake fetch.

`LocalDiskStorage` (`DOCUMENTS_DIR`, default `server/data/documents`, git-ignored, files written `0600` via a temp file + rename) is the development / single-host fallback and what the end-to-end run used. The API picks Supabase automatically when `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set; `GET /api/health` reports `documentStorage: supabase | local`.

**Production status:** driver implemented and unit-tested; **not yet pointed at a production project**. The Supabase projects visible to this workspace are LegendsOS (another product, active) and two inactive projects; the service-role key is not exposed through the connector. Decision needed from the owner: which Supabase project owns the `loan-documents` bucket (a new "LoanFlow" project is the clean choice), then provide `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` to the API host's environment and create the private bucket (dashboard → Storage → New bucket → *Public: off*, file size limit 25 MB, allowed MIME types optional).

## Website pieces

| File | What it does |
|---|---|
| `shared/loanSubmission.js` | `OPTIONS.documentCategory / incomeSubtype / assetSubtype / documentBorrower`, `DOCUMENT_STATUS`, `DOCUMENT_UPLOAD` (25 MB, 60 files, extension → MIME), `subtypeOptionsFor`, `submissionReference` (`LF-…`), validation refuses a submission while a file is `uploading` or `failed`, `documentRefsFromRecords` (server-side authoritative refs) |
| `server/services/documentStore.js` | `validateUpload` (ext allow-list, magic bytes, HTML/script sniff, SSN/account-number filenames refused, size), `createDocumentStore` (records per submission, `register` with sha256 dedupe → `duplicate` status sharing the stored object, clean display name `<date>_<slug>_<nn>.<ext>`, storage key `submissions/<sid>/<folder>/<display>`, `remove`, `markSubmitted`), `publicDocument` (no storage key / hash to the browser) |
| `server/services/documentStorage.js` | `assertSafeKey`, `LocalDiskStorage`, `SupabaseStorage`, `createDocumentStorage(env)` |
| `server/routes/documents.js` | `PUT /api/loan-submissions/:id/documents` · `GET …/documents` · `DELETE …/documents/:docId` (record marked removed; object kept for cleanup) · `GET /api/internal/documents/:id/:docId` (Bearer `FLO_INTAKE_TOKEN`, timing-safe compare, streams the bytes with `X-Document-Sha256`); uploads refused (409) once the submission is sent |
| `server/routes/loanSubmissions.js` | on submit: swaps in the server's document records with `fetchUrl`s, `meta.documentsReceived`, `documents.markSubmitted`; `publicStatus` returns `documentsReceived` |
| `components/loan-submission/steps.tsx` `DocumentsStep` | category → optional type (Paystub, W-2, 1099, Tax return, P&L, K-1 / Bank statement, Retirement statement, Gift documentation) → whose (when there is a co-borrower); drag/drop or pick; **each file uploads immediately** with Uploading… / Received / Duplicate / *failed + Retry*; Remove; multiple files per category; counts |
| `components/LoanSubmission.tsx` | draft autosave keeps received document records (a refresh does not lose uploads; the bytes are already stored); confirmation shows **Documents received: N** and **Submission ID: LF-XXXXXXXXXX** |

Retry semantics: one failed file shows *failed* with **Retry** (the `File` object is kept in memory for the session); nothing else on the page is affected and the LO never restarts the form. Submit is blocked only while a file is still uploading or failed (the message says which). If the API is unreachable the LO's answers stay in the browser draft.

## Flo pieces (Flo repo)

| File | What it does |
|---|---|
| `plugins/flo-team/documents.py` | `ingest` (pull through the connector, sha256 verify, private copy under `<hermes root>/flo/documents/<workspace>/<folder>/[borrower1|borrower2|joint]/<display>`, `.txt` sidecar with the extracted text, page count, `Page N of M` gap detection → `missing_pages`, duplicate by checksum, no text layer → `needs_review`, transfer failure → `needs_review` + `refetch`), `classify` (keeps the LO's choice, fills blank subtypes from filename/text keywords, suggests a category when the text disagrees — never overrides), `DocumentStore` (records + history, editable fields only), `add_local` (Ashley's Upload Missing Doc), `expected_documents` / `inventory` (required only when an ACTIVE source rule backs it, otherwise a clarification with `SOURCE_GAP`), `ashley_documents` (grouped plain view) |
| `plugins/flo-team/intake.py` | `receive` ingests every `documentRef` with a `fetchUrl` (token from `FLO_INTAKE_TOKEN`), writes `document_refs` + `documents_summary` on the workspace, adds the inventory to Malcolm's facts, constraints tell Malcolm to use `flo_documents`, `ashley_line` = "New loan came in — Johnson. 12 documents received. Malcolm is reviewing the file now. 💚" |
| `plugins/flo-team/tools.py` `flo_documents` | `list · get (bounded text) · update (category/subcategory/borrower_ref/status/display_name/notes) · inventory · add · refetch`; borrower-data roles only (Franklin refused) |
| `.flo/profile/malcolm/SOUL.md`, `.flo/profile/flo/SOUL.md` | Malcolm's document-review behaviour and the File Prep summary shape; Flo's intake line and the after-review line "Johnson is reviewed. Received: 12 documents. Missing: 2 items. Biggest blocker: … Best next move: Request the missing documents." |
| `plugins/flo-team/today.py`, `apps/desktop/src/plugins/flo/ashley.ts` | NEW LOAN card with the document count; `documentGroups`, `missingDocuments`, `documentsReceived` (rule-for-rule with Python) |
| `apps/desktop/src/plugins/flo/pipeline.tsx` | DOCUMENTS section grouped Application / Credit / AUS / Income / Assets / Contract / …, ✓ or ⚠ per document with the plain status and note, Missing list with Why?, **Upload Missing Doc** (native file picker → Flo adds it), **Request From Borrower**, **View Documents**; click a document → preview (PDF in an iframe / image inline from the private copy, name, category, received date, status, borrower) with **Open**, **Download**, **Mark Not Needed**, **Reclassify** (the last two go through Flo) — no storage keys or internal ids anywhere |

Text extraction is the PDF text layer via `pypdf` (already installed). Images and office files are stored and listed with a note "no text extraction on this install"; OCR is intentionally not added yet (no tooling decision made) and a document without a text layer lands as *Needs review* rather than being guessed at. Model-based classification is not used: the deterministic keyword pass plus the LO's category was enough for the acceptance set, and Malcolm reads the extracted text himself for anything unclear.

## Production checklist (what is verified vs. what needs an owner decision)

| Item | Status |
|---|---|
| Storage driver (Supabase private bucket) | implemented + tested against a fake Storage API; **needs the project/bucket + service-role key** (owner decision) |
| Upload endpoint, validation, dedupe, internal fetch | implemented, tested, exercised end-to-end locally |
| Website deployment | unchanged blocker from the submission phase: lfprocessing.net is static hosting; the Express API needs a Node host with persistent disk (`SUBMISSIONS_DIR`, `DOCUMENTS_META_DIR`) and `/api` proxied — owner decision on host |
| Flo connector for documents | implemented (`fetchUrl` + bearer token); needs `PUBLIC_API_BASE_URL` set on the API host and the same private tunnel the intake already needs |
| Retry worker | existing delivery worker also carries the documents (verified: Flo offline → delivered on attempt 2 with the 3 files pulled) |
| Preview from Ashley's machine | verified in the running Flo desktop (private copy read through the existing preload `readFileDataUrl`; **Open** hands the file to the OS) |
| Deletion path | `DELETE …/documents/:docId` marks the record removed before submit; after submit nothing is deleted from the API (records are the audit trail) — a retention/cleanup job is documented in the schema doc, not built |
