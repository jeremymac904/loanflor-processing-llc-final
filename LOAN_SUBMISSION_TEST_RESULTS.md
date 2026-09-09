# Loan Submission — test results (2026-09-09, synthetic data only)

## Automated

| Suite | Command | Result |
|---|---|---|
| Website server + shared contract | `npm test` (`node --test server/loanSubmissions.test.js`) | **8 / 8 passed** |
| Website typecheck / build | `npm run typecheck`, `npm run build` | pass |
| Flo intake (deterministic Deal Room + Malcolm task, idempotency, NPI refusal, token-protected endpoint) | Flo repo `tests/flo/test_intake.py` | **7 / 7 passed** |
| Flo full suite (regression) | Flo repo `tests/flo` + policy + skills | pass (exit 0) |
| Flo desktop plugin (NEW LOAN row, new-submission line) | `apps/desktop` typecheck / lint / vitest | pass, 21 tests |

What the server tests cover: purchase and refinance normalization; borrower-only and co-borrower; FHA and Conventional (Fannie/Freddie agency); non-borrowing title party required fields; lender fee buyout Yes (notes carried) / No; HOA + condo questionnaire conditional; funds-to-close rows; multiple income streams; omitted-debt explanation required; full SSN / full account number refused, last-4 and phone-in-notes allowed; double submit and retry after timeout → one record, one delivery; Flo unavailable → 202 "received", `pending_delivery`, retry worker delivers later, resubmit still a duplicate; honeypot; bad ids; origin check; rate limit; connector auth headers and status handling (201/200/409 delivered, 5xx retryable, 4xx not).

## Manual, in the browser (Vite dev + API + real Flo intake, all local)

Filled the form as a loan officer would (typed, not injected), with a co-borrower, FHA purchase, TOTAL, brokered/lender-paid, LP comp 2.75, credit report 152, processing 995, lender buyout **No**, appraisal prior to inspection, PMI yes, lock/escrow/sub no, two contact preferences, non-occupant **No**, **Non-borrowing spouse / individual on title = applies** (name, on title Yes, email, phone), W-2 income stream with LO-stated $7,842/mo, bank funds with account reference "checking 1234", borrower credit as-per-pull, co-borrower **tradeline omitted** (validation blocked Next until an explanation was typed), title company selected, insurance not selected, HOA yes (condo questionnaire hidden for single-family), listing/buyer agents (purchase), notes via the "Rush closing" chip, no documents, review screen, **double-click** on Submit.

Observed:

* phone fields auto-format, money/percent fields format on blur, the date defaults to today, the stepper marks steps done and links to errors;
* review screen listed the recommended-but-missing items (documents, insurance) without blocking;
* one request reached the API despite the double click; confirmation showed borrower, "Today at 5:24 PM", expected closing 9/23/2026, confirmation ID `sub_0694e236a2c5d51a5fe30301`;
* draft autosave restored the in-progress form after a reload earlier in the session.

## End-to-end (Website → LoanFlow backend → Flo intake → Deal Room → Malcolm task → Pipeline)

| Step | Evidence |
|---|---|
| Website submit | `POST /api/loan-submissions` → 200 `delivered` |
| LoanFlow backend | record `sub_0694e236a2c5d51a5fe30301` status `delivered`, attempts 1 |
| Flo intake | `201 accepted → loan_1707eb2c9ed8 task task_52a72c665837` |
| Deal Room | `Justinvil-Synthetic`, milestone Intake, program fha, AUS TOTAL, `submission` block, LO contact refs, status summary "New submission from Matt Combs (Synthetic Mortgage Group). Purchase • FHA. Expected close 2026-09-23." |
| Flo turn | `flo_intake dispatch` → `message_agent` to Malcolm (status sent) → Ashley line "NEW LOAN — Justinvil-Synthetic. Submitted by Matt Combs. Purchase • FHA. Expected close 2026-09-23. Malcolm is reviewing the file." |
| Malcolm | task `completed`; File Readiness report written to the workspace (score 0, 10 missing items: income docs, bank statement for the stated asset, TOTAL findings report, credit report, signed 1003, …); flagged LO-stated income as unverified |
| Ashley's Pipeline (rules used by the desktop plugin) | before review: **NEW LOAN · Working · New submission · "New loan from Matt Combs • Purchase • FHA • Expected close 2026-09-23. Malcolm is reviewing the file."**; after review: **Waiting · In progress · "Only blocker right now: Income docs - borrower (paystubs, W-2) verified from borrower"**, Missing: 10 items, Request From Borrower available |

## Flo temporarily unavailable

Stopped the intake server, submitted a second synthetic loan (`sub_31d694aad9a770096ea82a5f`, borrower "Devon Synthetic-Retry") through the API: **202 received**, record `pending_delivery`, attempt 1 error "Flo intake unreachable", next attempt scheduled +60 s; an immediate resubmit with the same id answered `duplicate: true` and did not create a second record. Restarted the intake: the worker delivered on **attempt 2** (`loan_27eb587249a6`, `task_8aebd85ee24d`), Flo dispatched to Malcolm, Malcolm completed the review (6 missing items). Two submissions → exactly two Deal Rooms, two tasks.

## Second pass (same day): Flo wording, Today card, live Flo screenshots

After tightening the Ashley-facing copy: Flo's message is now exactly *"New loan came in — Johnson. Malcolm is reviewing it now. 💚"* (verified in Flo's Bot Chat for `sub_3e2a9dbeb6e4a0c4f480a5f6`, Deal Room `loan_ba6867ba7a25`, Malcolm task `task_bf272d49d85d`, delivered on attempt 1); Today shows a **NEW LOAN** card (borrower, submitted by, program • transaction, expected closing in words, "Malcolm is reviewing it.", Open File) until Malcolm's report lands; afterwards the file reads *Needs N items*, AUS, Income *Reviewed* / Assets *Needs attention*, the missing list and *Request the missing documents.* Internal delivery statuses are now `received` → `delivered` | `pending_delivery` | `failed_retrying`.

Screenshots taken from the **running Flo desktop app** (dev build, real team state on this machine): `docs/screenshots/flo-today-new-loan.png` (Today with the NEW LOAN card), `flo-pipeline-new-loan.png` (the Johnson file right after Malcolm's review: Needs 6 items, Request From Borrower), `flo-file-after-review.png` (the first end-to-end loan, Needs 10 items), `flo-pipeline-list.png`.

Totals for the day: 5 synthetic submissions → 5 Deal Rooms, 5 Malcolm tasks, 0 duplicates (two deliberate duplicate requests were answered `duplicate: true`).

## Responsive layout

Screenshots in `docs/screenshots/` (headless Chrome, synthetic data): desktop 1440 px (loan officer, borrowers, program, income & assets, documents, review, confirmation) and mobile 390 px (loan officer, program, review, confirmation). On mobile the pills wrap, the grid collapses to one column, and Next/Back stack.

## Not tested / known gaps

* Real file upload (UI only; see `FLO_INTAKE_INTEGRATION.md`).
* Production hosting of the Express API, the private tunnel and the token rollout.
* Google Sheet summary row (credentials not configured locally; the call is best-effort and skipped).
* The live site (lfprocessing.net) still serves the old form until this branch is deployed.
