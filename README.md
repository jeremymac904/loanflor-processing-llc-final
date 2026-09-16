# Flo / LoanFlow Processing

This is the single source of truth for LoanFlow Processing LLC's website **and** Flo, Ashley's mortgage-
processing assistant. It's a monorepo: the website lives at the repository root (its existing deployment
expects that), and everything Flo/Hermes-related lives in `flo-agent/`.

New to this repo? Read `PROJECT_MAP.md` for how the pieces connect, and `MAC_HANDOFF.md` for exactly what's
working, what's deferred, and what's next.

## 1. Website

Marketing site + the **Loan Submission** form that delivers new loans straight into Ashley's Flo.

```
npm install
cp .env.example .env        # fill FLO_INTAKE_URL / FLO_INTAKE_TOKEN for real delivery (optional locally)
npm run start                # API on :3001  (POST /api/loan-submissions, GET /api/health)
npm run dev                  # site on :3000, /api proxied to :3001
npm test                     # server + shared-contract tests
npm run typecheck && npm run build
```

Without `FLO_INTAKE_URL` the API still accepts submissions and keeps them as pending delivery
(`server/data/submissions`, git-ignored) until Flo is configured. Dev demo of the form with synthetic data:
`http://localhost:3000/?lfDemo=1&lfStep=review`.

Docs: `LOAN_SUBMISSION_V2.md`, `LOAN_SUBMISSION_SCHEMA.md`, `FLO_INTAKE_INTEGRATION.md`,
`LOAN_SUBMISSION_TEST_RESULTS.md`, `DOCUMENT_UPLOAD_IMPLEMENTATION.md` / `DOCUMENT_STORAGE_SCHEMA.md` /
`DOCUMENT_SECURITY_REVIEW.md` / `DOCUMENT_INTAKE_TEST_RESULTS.md`.

## 2. Flo Desktop

The Electron desktop app Ashley runs day to day — a downstream distribution of Hermes Agent (Nous Research,
MIT). Lives in `flo-agent/apps/desktop/`. Ashley's sidebar is deliberately just **Today**, **Pipeline**,
**Approvals** — everything technical lives under Advanced. See `flo-agent/CLAUDE.md` for the full map of
where each concern lives, and `flo-agent/UPSTREAM_HERMES.md` for the Hermes lineage.

## 3. Flo Team

Six Bot Mode profiles behind the scenes: **Flo** (the one assistant Ashley talks to), **Malcolm** (file prep
and readiness), **Sage** (guideline answers), **Whisper** (borrower-facing drafts), **Chadwick** (marketing),
**Franklin** (structurally excluded from borrower data). Manifest: `flo-agent/plugins/flo-team/team.yaml`.
Runtime: `flo-agent/plugins/flo-team/`. See `flo-agent/FLO_TEAM_BUILD.md`.

## 4. Mortgage knowledge

Program packs (Fannie, Freddie, FHA TOTAL/Manual, VA, USDA) built on source-bound rules with provenance —
never fabricated guidelines. A rule is either backed by an ACTIVE source section or it's `SOURCE_GAP`.
See `flo-agent/.flo/docs/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md` and `flo-agent/MULTI_PROGRAM_SOURCE_REGISTRY.md`.

## 5. Loan Submission

The website's 13-step form → `POST /api/loan-submissions` → Flo's intake connector
(`flo-agent/scripts/flo/intake_server.py`) → a Deal Room + Malcolm task, created deterministically and
idempotently per `submissionId`. Schema shared between both sides: `shared/loanSubmission.js`.

## 6. Documents

Each uploaded document is pulled at intake, hashed, text-extracted, and classified — a document is only
*required* when an ACTIVE source rule backs it. Ashley's Documents section (upload, preview, missing-item
requests) lives in `flo-agent/apps/desktop/src/plugins/flo/pipeline.tsx`.

## 7. Local e-signing

Documenso, self-hosted Community Edition, running **entirely locally** via Docker Desktop — this is a
deliberate, explicit owner decision (see `flo-agent/FLO_ESIGN.md`). Remote/borrower-facing signing is
**intentionally not enabled**; Flo Signatures only works on the machine it runs on today.

## 8. Local services

Documenso (Postgres + Documenso + maildev) via `flo-agent/deploy/documenso/docker-compose.yml`. Recovery
and auto-start scripts: `flo-agent/flo-start.ps1`, `flo-agent/flo-autostart.ps1`,
`flo-agent/FLO_RECOVERY.md`.

## 9. Development

One writer per working tree at a time — check `git status` before editing shared docs. Run the checks for
whatever you touch:

```
# Website
npm test && npm run typecheck && npm run build

# Flo (Python)
cd flo-agent && scripts/run_tests.sh <paths>

# Flo Desktop
cd flo-agent/apps/desktop && npm run typecheck && npm run lint && npm run test:ui
```

## 10. Mac setup

See `MAC_SETUP.md` and `scripts/setup-mac.sh`.

## 11. Security / secrets

Nothing above needs a real secret to explore the code. `.env.example` files exist at the root, in
`flo-agent/`, and in `flo-agent/deploy/documenso/` — copy them to `.env` and fill in your own values.
Real secrets, tokens, certificates, Docker volumes, and borrower data are never committed; see the root
`.gitignore` and `flo-agent/.gitignore`. If you find a credential in this repo that looks real, stop and
report it rather than committing around it.

## 12. Current status

See `MAC_HANDOFF.md` for the living list of what works, what's deferred, and what's next. Short version:
local signing milestone is accepted and local-only by owner directive; the next priority is Ashley's core
missing-document workflow (Malcolm → clean summary → one-click request → Whisper draft → send).
