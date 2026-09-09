# Loan Submission v2 — lfprocessing.net → Flo

A Loan Officer fills out one form on the LoanFlow website, clicks **Submit Loan to Processing**, and the structured submission lands in Ashley's Flo as a **new loan** with Malcolm's review already started. No more re-typing emailed submission sheets.

```
Website form (React, 13 steps)
    ↓  POST /api/loan-submissions            (browser talks ONLY to the website backend)
LoanFlow server (Express)                    validate · dedupe · persist · rate-limit
    ↓  Authenticated Flo intake connector    Bearer token, Idempotency-Key, private URL
Flo intake endpoint (scripts/flo/intake_server.py, on Ashley's machine)
    ↓  deterministic                          Deal Room (milestone Intake) + one Malcolm task
Flo (one Bot Chat turn)                       sends Malcolm the packet, tells Ashley "NEW LOAN — …"
    ↓
Malcolm                                       File Readiness report → Ashley's Pipeline / Today
```

## Where it lives

| Piece | Path |
|---|---|
| Form (13 steps, autosave, review, confirmation) | `components/LoanSubmission.tsx`, `components/loan-submission/{fields,steps}.tsx`, `components/loan-submission/sample.ts` (dev demo data) |
| Shared contract (options, validation, payload) | `shared/loanSubmission.js` — one module for browser and server; see `LOAN_SUBMISSION_SCHEMA.md` |
| API route | `server/routes/loanSubmissions.js` — `POST /api/loan-submissions`, `GET /api/loan-submissions/:id` |
| Persistence + idempotency + pending queue | `server/services/submissionStore.js` (one JSON file per submission under `server/data/submissions`, git-ignored) |
| Flo connector | `server/services/floIntake.js` (`FLO_INTAKE_URL`, `FLO_INTAKE_TOKEN`) |
| Retry worker | `server/services/deliveryQueue.js` (1 min → 15 min backoff, runs inside the API process) |
| Optional legacy Google Sheet row | `server/services/googleSheets.js` (summary only, best effort, skipped when unconfigured) |
| Flo side | Flo repo: `plugins/flo-team/intake.py`, `scripts/flo/intake_server.py`, `flo_intake` tool; see `FLO_INTAKE_INTEGRATION.md` |
| Tests | `server/loanSubmissions.test.js` (`npm test`), Flo repo `tests/flo/test_intake.py` |
| Screenshots | `docs/screenshots/` (desktop + mobile, synthetic data) |

## The form

Sections (a stepper with progress, clickable step chips, Back/Next, Enter advances):

1. **Loan Officer** — name, company/brokerage, email, phone (auto-formatted), NMLS #, date submitted (defaults to today)
2. **Borrowers** — borrower name / **email / phone**; "Does this loan have a co-borrower?" → co-borrower name / **email / phone**
3. **Loan Details** — investor/lender, property address, loan amount ($), expected closing date, interest rate (%), LTV / CLTV (%), occupancy (Primary / Second home / Investment)
4. **Program & Transaction** — Purchase / Refi rate & term / Refi cash-out; Conventional (→ Fannie / Freddie / Not sure), FHA, VA, USDA, Jumbo, Non-QM, Other (→ text); AUS limited to what applies to the program (FHA shows TOTAL first, USDA shows GUS, VA shows VA AUS…); refinance type only for refinances (FHA Streamline / VA IRRRL / Standard / Other — HARP dropped); home type (Single family, Condo, PUD, 2–4 unit, Manufactured, Other)
5. **Fees & Processing** — Brokered / Correspondent (→ Lender paid / Borrower paid), LP comp %, Box 1 $, discount points %, credits $, credit report fee $, processing fee $, **Is the lender buying out the fee?** Yes/No → buyout details
6. **Appraisal & Loan Setup** — order PRIOR / AFTER inspection (with the sheet's helper text), appraisal notes; PMI (Yes/No/N/A), subordination (Yes → "Attach or provide the second mortgage information if available."), loan locked, escrow waiver; processor may communicate with (multi-select: Realtor voice / Realtor email CC LO / Borrower voice / Borrower email CC LO); non-occupant co-borrower; **Non-Borrowing Spouse / Individual on Title** with helper "We must have this information when applicable." → full name, will be on title, email, phone
7. **Income & Assets** — repeatable **LO-stated qualifying income** streams (W-2, 1099, self-employed, rental, retirement/pension, Social Security, military, other; employer/source; LO-stated monthly income labelled "Your estimate; not validated here."; calculation basis; supporting documents checklist; notes; borrower vs co-borrower); repeatable funds-to-close sources (gift, bank account, retirement withdrawal, lender credits, other) with **Account reference / last 4** — full account numbers are rejected
8. **Credit** — per borrower: as per credit pull / rescore or supplement / tradeline omitted / other issue, plus "Omitted debts / credit notes" (required when a tradeline is omitted: "If any debts are omitted, please explain.")
9. **Title / Insurance / HOA** — title and insurance company (or "Not selected yet"), HOA Yes/No/Unknown → company, contact, phone, email, condo questionnaire status (hidden for single-family)
10. **Agents** — listing and buyer's agent (name, license #, phone, email, brokerage, brokerage license #); hidden for refinances
11. **Special Instructions** — "What else does processing need to know about this file?" with one-tap example prompts
12. **Documents** — pick a category (Loan Application / 1003, Credit Report, AUS Findings, Income Documents → Paystub / W-2 / 1099 / Tax return / P&L / K-1 / Other, Asset Documents → Bank statement / Retirement statement / Gift documentation / Other, Purchase Contract, Title / Property, Insurance, Identification, Other), whose document when there is a co-borrower, then drag/drop or choose files; **each file uploads immediately** to LoanFlow's private storage (Uploading… → Received / Duplicate, or failed with **Retry**); multiple files per category; see Upload status
13. **Review & Submit** — grouped summary (Borrowers, Loan, Program, Income, Assets, Orders, Title/Insurance, Agents, Credit, Notes, Documents), blocking errors linked to their step, **recommended-but-missing** fields highlighted in copper, **Back & Edit** / **Submit Loan to Processing**

Then the confirmation: "Loan Submitted Successfully", borrower, submitted time, **Documents received: N**, expected closing, **Submission ID: LF-XXXXXXXXXX**, **Print / Save Confirmation**, Submit Another Loan. It says LoanFlow *received* the submission — never that Ashley reviewed it.

Autosave: the draft is saved to the browser's localStorage on every change (received document records included — the bytes are already in private storage; a file still uploading or failed is dropped and picked again) and restored after a refresh with a "Start over" option. Dev demo: `?lfDemo=1&lfStep=<step id|done>` renders the form alone with synthetic data.

## Changes from the PDF (Justinvil sub sheet)

1. Borrower **phone number** added; co-borrower **email and phone** added (co-borrower fields appear only when there is one).
2. "Non-Borrowing Spouse OR Individual on title (if applicable) *On a primary refi, we MUST have this info*" → **"Non-Borrowing Spouse / Individual on Title"** with helper **"We must have this information when applicable."** The phrase "On a primary refi" does not appear anywhere (asserted by a test).
3. **"Is the lender buying out the fee?"** Yes/No added to the fee section, with optional buyout details.
4. `Acct#` fields → **Account reference / last 4**; anything that looks like a full account number or SSN is refused client- and server-side.
5. Underwriting options expanded from DU/LP to DU, LPA/LP, TOTAL, GUS, VA AUS, Manual, Other/Not sure, filtered by program. HARP removed from refinance types. Home types expanded (2–4 unit, Manufactured, Other).
6. Qualifying income is per-stream with a calculation basis and document checklist, labelled **LO-stated** (Flo/Malcolm/Sage verify later; the payload carries `verified: false`).
7. Credit and funds-to-close are structured (checklists, repeatable rows) instead of free text on lines.
8. HOA gets a Yes/No/Unknown gate; condo-questionnaire status only when relevant.

## Upload status

Documents upload **from the browser to this site's API only** (`PUT /api/loan-submissions/:id/documents`, one file per request, validated server-side: extension allow-list, magic bytes, HTML/script sniff, 25 MB, filenames without SSN/account numbers) and land in private storage (Supabase private bucket in production, local disk in dev). Duplicates (same checksum) are kept once and shown as *Duplicate*. When the LO submits, the server attaches its own document records to the payload and Flo pulls each file through the authenticated connector into the Deal Room, where it is named cleanly, text-extracted, checked for missing pages and ready for Malcolm. Details: `DOCUMENT_UPLOAD_IMPLEMENTATION.md`, `DOCUMENT_STORAGE_SCHEMA.md`, `DOCUMENT_SECURITY_REVIEW.md`, `DOCUMENT_INTAKE_TEST_RESULTS.md`.

## Duplicate protection

`submissionId` (`sub_<24 hex>`) is minted when the draft starts and kept in the autosaved draft. The Submit button is disabled while a request is in flight (double click = one request). The server creates the record once per id; any repeat — double click, retry after a timeout, browser retry — returns the same record (`duplicate: true`) and never delivers twice. The Flo intake is idempotent on the same id too (`Idempotency-Key` header; 200 `duplicate` instead of a second Deal Room).

## Failure / retry behaviour

The record is written **before** any delivery attempt with `submissionId`, `receivedAt` (created_at) and an internal `status`: `received` → `delivered`, or `pending_delivery` (Flo connector not configured yet) / `failed_retrying` (Flo unreachable or erroring) → `delivered`. The LO never sees those states: whenever the record is saved they see **"Loan Submitted Successfully"** with a confirmation ID (HTTP 202 while delivery is still pending) — never an error asking them to redo the form. A worker in the API process retries every minute with exponential backoff (1 → 15 min cap), records attempts and the last error on the record, and flips it to `delivered` when Flo accepts. A 4xx from Flo other than 409 is flagged `needsAttention` and kept at the 15-minute retry cadence so a human notices it in `GET /api/health` (`pendingDelivery` count).

## Security summary

Server-side validation with the shared contract · HTTPS redirect in production · origin check in production · per-IP rate limit (12 / hour) · honeypot · 512 KB body limit · no secrets in the browser (Flo URL/token only in server env) · no full SSNs or account numbers accepted · logs carry ids and statuses only · Flo/Hermes never exposed publicly (private intake endpoint behind a tunnel, bearer token, localhost bind by default).
