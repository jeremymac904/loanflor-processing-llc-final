# LoanFlow Processing LLC — website

Marketing site + the **Loan Submission** form that delivers new loans straight into Ashley's Flo (`#submit`).

## Run locally

```
npm install
cp .env.example .env        # fill FLO_INTAKE_URL / FLO_INTAKE_TOKEN for real delivery (optional locally)
npm run start               # API on :3001  (POST /api/loan-submissions, GET /api/health)
npm run dev                 # site on :3000, /api proxied to :3001
npm test                    # server + shared-contract tests
npm run typecheck && npm run build
```

Without `FLO_INTAKE_URL` the API still accepts submissions and keeps them as pending delivery (`server/data/submissions`, git-ignored) until Flo is configured.

Dev demo of the form with synthetic data: `http://localhost:3000/?lfDemo=1&lfStep=review` (`lfStep` = lo | borrowers | loan | program | fees | setup | income | credit | title | agents | notes | documents | review | done).

## Docs

* `LOAN_SUBMISSION_V2.md` — the form, changes from the paper sheet, duplicate protection, failure/retry, security
* `LOAN_SUBMISSION_SCHEMA.md` — the v1.0 payload contract and validation rules
* `FLO_INTAKE_INTEGRATION.md` — how it reaches Flo, environment, what production still needs
* `LOAN_SUBMISSION_TEST_RESULTS.md` — automated + manual + end-to-end results
* `DOCUMENT_UPLOAD_IMPLEMENTATION.md` / `DOCUMENT_STORAGE_SCHEMA.md` / `DOCUMENT_SECURITY_REVIEW.md` / `DOCUMENT_INTAKE_TEST_RESULTS.md` — secure document upload → private storage → Flo Deal Room → Malcolm

Documents: `PUT /api/loan-submissions/:id/documents` stores files in a private Supabase bucket (`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`, server-side only) or on local disk when those are blank (`server/data/documents`, git-ignored); Flo pulls them back through `GET /api/internal/documents/:id/:docId` with the intake token.

Electronic signatures: `POST /api/esign-webhook` receives Documenso's webhook (verifies `X-Documenso-Secret`, a shared secret — `DOCUMENSO_WEBHOOK_SECRET`), then forwards only the envelope id to Flo's existing private intake channel. This website never holds a Documenso API key — only that webhook secret. See `FLO_ESIGN.md` in the Flo repository for the full design, what's verified vs. inferred, and what's still an open decision.

The AI chat assistant uses `GEMINI_API_KEY` (see `services/geminiService.ts`).
