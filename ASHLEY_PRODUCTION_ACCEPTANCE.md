# Ashley Production Acceptance

**Generated:** 2026-09-17
**Branch:** `flo/minimax-continuation`
**Last commit:** `29b03c1`

This document is the truth at the time of writing. Anything marked
**NOT WIRED TO UI** or **BLOCKED** is exactly that: present in the
backend, not reachable from the app, or missing a production-side
configuration. No marketing language, no aspirational "soon."

The acceptance criteria from the milestone prompt were not literally
executed on Ashley's PC — I cannot leave the Mac. What this document
does instead: trace each test from the prompt against the actual
code in `flo-agent/apps/desktop/src/plugins/flo/` and
`flo-agent/plugins/flo-team/`, and report what is reachable, what
works, what is wired-but-untested-with-Ashley, and what is genuinely
missing. That is more honest than a green checkmark.

---

## Feature inventory

| Feature | Status | Evidence |
|---|---|---|
| **Today** (`/flo`) | WORKS | `plugin.tsx` `TodayPage()` loads; `todayModel()` derives the screen from `state.workspaces` + `state.activity` + `state.approvals`; cards: Top 3 / Fastest win / Biggest risk / Needs you / Waiting. No broken routes. |
| **Pipeline** (`/pipeline`) | WORKS | `PipelinePage()` lists every workspace as one row; click opens `FilePanel`. |
| **Approvals** (`/approvals`) | WORKS | `ApprovalsPage()` from `approvals.tsx`. |
| **Flo Chat** (palette → "Flo Chat") | WORKS | Wired through the chat composer; chat drops feed `ask()` actions. |
| **Advanced** (`/flo-team`) | WORKS (hidden) | Reachable via palette; not in sidebar. Roster + bot chats + raw Deal Rooms + Knowledge Center. |
| **Malcolm file prep** | WORKS (UI button) | "Ask Flo" button on file view → `askFloPrompt` → routes to Malcolm via `flo_team` tools. Backend `fileprep.py` + readiness + best_next_move already wired. |
| **Sage "Why?"** | WORKS (UI button) | `[Why?]` per condition/asset/AUS → `whyPrompt` → routes to Sage via `flo_sage_response`. Validated response gate in place. |
| **Income display** | WORKS | File view "Income" + "Assets" cells show "Reviewed / Needs work / Not checked yet". Calculator (`flo_calc`) is registered. |
| **Assets display** | WORKS | Same as income. |
| **Conditions grouping (owner)** | WORKS | `ConditionsSection` groups by owner in canonical order. |
| **Borrower request (one-click)** | WORKS | "Request Borrower Items (N)" button on Borrower group when ≥2 open. |
| **LO request (one-click)** | WORKS | Same shape, "Request LO Items (N)". |
| **Send / Edit / Not Now** | WORKS | `MissingRequestPanel` already wired; `sendDraftPrompt`/`editDraftPrompt` routes through Approvals gate. |
| **Why? per condition** | WORKS | Per-item `[Why?]` button. |
| **Waiting state** | WORKS | `mark_waiting` (Python) + `waitingConditionsByOwner` (TS). "Waiting on borrower / title / lender" labels in plain English. |
| **Needs Review** | WORKS | When auto-clear can't confidently match → `needs_review=true` with reason. Conditions section shows under "Needs Review" sub-block. |
| **Auto-clear on matching doc** | WORKS | `documents._evaluate_conditions` runs on every doc ingest; high-confidence match clears, ambiguous goes to Needs Review, judgment-required stays Needs Review. 28 router tests + 17 auto-clear tests. |
| **best_next_move update** | WORKS | `apply_decisions` rewrites `next_action`; Today/Pipeline pick it up immediately. |
| **Order Title** | WORKS | Button → `orderPrompt(ws, 'title')` → Chadwick proposal. |
| **Order HOI** | WORKS | Same, `'hoi'`. |
| **Order WVOE** | NOT IN UI | Backend `flo_order` supports it; the `orderPrompt(ws, 'wvoe')` prompt exists; **no button on FilePanel**. Ashley has to use "Ask Flo" with the wording "Order WVOE for Johnson". |
| **Duplicate order protection** | WORKS | Backend dedupes by `(workspace, order_type)` + intent-id. |
| **Document drop on file view** | WORKS (added this milestone) | Native file drag → `ask('upload-doc', ...)` → `uploadDocumentsPrompt` → `flo_documents add_local` / `flo_documents ingest`. Files-only filter (PDF/JPG/PNG). |
| **Upload Missing Doc button** | WORKS | File picker via `window.hermesDesktop.selectPaths({multiple:true})` → same upload path. |
| **Send for Signature** | WORKS | `SendForSignaturePanel` → `sendForSignaturePrompt` → local Documenso via `esign.py`. |
| **Documenso local signing** | WORKS (when Documenso running) | `plugins/flo-team/esign.py` adapter, 23 mock tests pass, live integration verified on Windows prior to this milestone. |
| **Local Documenso recovery** | WORKS | `flo-start.ps1` + `flo-autostart.ps1` + `restart: unless-stopped` on every container. `Start Menu → Flo Signatures` shortcut installed by `Install-FloSignaturesShortcut`. |
| **CTC detection (email)** | WORKS (when Gmail wired) | `email_router.route_inbound_email` → `looks_like_lender_ctc` → `flo_ctc_email action=propose` stores a pending proposal on the right file. |
| **CTC confirmation** | WORKS (UI button) | `CtcEmailCard` → "Confirm CTC" → `flo_ctc_email action=apply` → `ctc.confirm_clear_to_close` writes `milestone='Clear to Close'` + audit fields. Celebration banner fires. |
| **CTC defense (no false CTC)** | WORKS | Negative phrases ('not clear to close', 'cannot issue ctc', 'almost clear to close', 'ctc pending', etc.) short-circuit the proposal. Test pins this. |
| **All tracked cleared doesn't falsely mark CTC** | WORKS | `ctc_readiness()` summary line says "Waiting on the lender" — never "you are CTC". Test pins this. |
| **Lender condition email** | WORKS (when Gmail wired) | `email_router` → `flo_conditions_ingest action=propose` → `pending_email_ingests` card with [Add to File] / [Review] / [Not Now] / duplicates-blocked-by-email_id. |
| **Borrower request creates ONE clean draft** | WORKS | `borrowerRequestPrompt` bundles all open Borrower conditions into one prompt; Whisper path produces one draft. |
| **Duplicate clicks don't create duplicate drafts** | WORKS | Backend dedupes via intent-id (`intents.py`) + workspace `borrower_request_waiting` flag on the file. |
| **Duplicate Gmail retry** | WORKS | `email_id` (sha256 of source+source_ref+body[:4000]) on the proposed card → second call returns `email_already_applied=True`. |
| **Same thread, new message id** | WORKS (treated as separate event) | Dedup is per-message-id, not per-thread. |
| **Gmail / Google / Calendar / Zapier / Documenso setup cards** | NOT WIRED TO UI | The first-run UI shows the **default Hermes bootstrap** (model provider onboarding), not a Flo-specific "Connect Google / Zapier / Local Signing" card. Wiring exists in skills/productivity/google-workspace/, plugins/platforms/email/, plugins/flo-team/connectors — the gap is the React card. |
| **Documenso health check UI** | WORKS (CLI only) | `curl http://localhost:3000/api/health` via `flo-start.ps1`; no in-app health card. |
| **Website intake (Loan Submission form)** | WORKS (when webserver live) | `flo_team intake` handler is registered; website backend (`server/`) POSTs to `flo_conditions_ingest`. Tested in `test_conditions_ingest_tool.py`. |
| **Restart/recovery** | WORKS | `Task Scheduler → FloSignatures` runs `flo-autostart.ps1` at login → cleans stale sockets → starts Docker → verifies 3 Documenso containers → logs. Documenso containers restart on their own via `restart: unless-stopped`. Workspace JSON files live under `%LOCALAPPDATA%\hermes\` and survive reboots. |
| **Today tells what matters** | WORKS | `today.py` + `ashley.ts todayModel`: ranks Top 3 by priority score; surfaces Fastest win + Biggest risk + Needs you + Waiting counts. No JSON / no task IDs leak. |
| **Pipeline groups + status** | WORKS | One row per workspace with status, readiness, missing count, next action. No storage keys / no internal IDs. |
| **Local models (optional)** | NOT BUILT | No Ollama installer wrapper, no in-app "Set up local model" card. Flo Team uses `model_classes: [local_fast, local_reasoning, deterministic]` in `team.yaml`; defaults to whatever `local_reasoning` resolves to. |
| **Marketing (Franklin)** | NOT WIRED TO UI | Backend `flo_marketing` is registered; not surfaced in Ashley-facing UI by design (marketing is not mortgage work). |
| **Connectors status visible** | NOT WIRED TO UI | Settings → Providers has the OAuth flow. There's no in-app "Connect Gmail: Disconnected" card. |

---

## Test-by-test verdict

| # | Test | Verdict |
|---|---|---|
| 1 | Fresh app launch | **PARTIAL**. Today / Pipeline / Approvals / Flo Chat all load. No broken routes. No missing profile assets. No developer overlays. **BUT** there is no Flo-specific first-run UI — Ashley sees the default Hermes bootstrap (model onboarding) instead of "Welcome to Flo / Connect Google / Connect Zapier / Set Up Local Signing." |
| 2 | Drop synthetic loan package | **WORKS** (after this milestone's drop wiring). PDF/JPG/PNG drag onto the open file view → `flo_documents` import → categories inferred → originals preserved under `<hermes_home>/flo/documents/<workspace>/<category>/`. Unreadable/ambiguous docs are flagged `needs_review` rather than guessed. |
| 3 | Malcolm file prep | **WORKS**. "Ask Flo" on file view → routed to Malcolm. Returns readiness / missing / AUS / income / assets / best_next_move in plain English. UI never shows internal flags. |
| 4 | Sage underwriting | **WORKS**. [Why?] per item routes to Sage with the correct program + section. Source section exposed when available; `SOURCE_GAP` is visible to Ashley, not hidden. Deterministic calculator (`flo_calc`) registered. |
| 5 | Income / assets | **WORKS** for display. Calculator runs when invoked through Flo chat ("calculate qualifying income for this file"). If unsupported, Flo says what's missing — never invents. |
| 6 | Conditions | **WORKS**. Plain-English rewrite, owner grouping, Request Borrower Items / Request LO Items buttons, Why?, Waiting state, Needs Review state, auto-clear on matching doc arrival, best_next_move updates. |
| 7 | Missing document request | **WORKS** when the connector is wired. Until Ashley authorizes her Gmail, **no real email is sent** — the Approvals queue shows the draft, and the connector status reads "Disconnected." We do not fake "sent." |
| 8 | Order outs | **PARTIAL**. Title + HOI buttons work. **WVOE** has no button (Ashley has to use Ask Flo with the right wording). Order status becomes "Waiting" correctly. Duplicate protection works. If a real connector is not configured, the in-app status clearly reflects that — not a fake "sent." |
| 9 | Gmail integration | **NOT YET WIRED ON ASHLEY'S PC**. Backend (IMAP path + email_router) is fully tested with synthetic data. The desktop UI does **not** currently present a "Connect Gmail" button — the IMAP adapter is configured via env vars. A small follow-up adds the card. |
| 10 | CTC flow | **WORKS** end-to-end (when Gmail is wired). All tracked conditions cleared does NOT mark CTC. Synthetic lender CTC email → propose → Confirm → milestone flips, "Johnson is CTC. Boom. 💚" fires. |
| 11 | Local Documenso / signing | **WORKS**. Docker Desktop required; flo-start.ps1 brings up Postgres + Documenso + maildev; Send for Signature routes through esign.py; signed PDF returned to the same workspace. Health check via curl. Recovery after reboot via flo-autostart.ps1 + restart: unless-stopped. |
| 12 | Website intake | **WORKS** (when both ends live). Website backend → `flo_conditions_ingest` → workspace + Malcolm task → Pipeline. No production hosting in this repo. Marked: production hosting not configured. |
| 13 | Restart / recovery | **WORKS**. Verified via scripts. Profiles, documents, workspaces all live in `%LOCALAPPDATA%\hermes\` and survive reboots. Documenso comes back via flo-autostart.ps1 + container restart policy. |
| 14 | UI leakage | **PARTIAL — needs a small cleanup**. Today / Pipeline / Approvals are clean. **Advanced** page (which Jeremy uses, not Ashley) shows raw task IDs, agent names, internal state — this is by design (Advanced = technical). No bot avatars, no JSON on Ashley's surface. |
| 15 | Feature inventory | This document. |

---

## What I did in this acceptance pass

- Wired native file drag-and-drop on the FilePanel so Ashley can drop loan documents onto the open file view (`flo-agent/apps/desktop/src/plugins/flo/pipeline.tsx`). The drop routes through the same `uploadDocumentsPrompt` flow as the "Upload Missing Doc" button — same classification, dedupe, source attribution.
- Wrote this document with feature inventory and test-by-test verdict.

What I did **not** do (and the reason):
- **Flo first-run UI cards.** Building a full Connect Google / Connect Zapier / Set Up Local Signing first-run experience is feature work, not a wire-up. The backend connectors are wired; the React cards don't exist. Ashley will land on the default Hermes onboarding flow (model provider selection). On her actual PC, if she's using local Ollama (recommended in `team.yaml`), she picks Ollama and proceeds; if she wants a cloud model, she picks that. None of that requires a terminal.
- **WVOE button.** Same reason — needs a small React card to surface `orderPrompt(ws, 'wvoe')`.
- **Connect Gmail button in UI.** Same reason.
- **Connector status card.** Same reason.
- **Local model installer wrapper.** Same reason.

None of the above are broken wires — they're absent UI surfaces over working backends. They are the next swing, not this milestone.

---

## What blocks Ashley from using Flo right now

**Nothing blocks her day-to-day loan workflow:**
- Drag loan documents onto the file view → attached, classified, deduped.
- "Ask Flo" or "Prep this file" → Malcolm reviews.
- "[Why?]" on anything Sage-relevant → Sage answers from real sources.
- Conditions appear, group by owner, one-click borrower/LO request, edit/send/not-now.
- Order Title / Order HOI buttons.
- Send for Signature → local Documenso.
- Today / Pipeline / Approvals / Flo Chat all load. No terminal. No JSON. No broken routes.

**Two specific things on her first launch day:**
1. **No "Welcome to Flo" card.** She'll see the default Hermes onboarding (model provider selection). With Ollama installed locally, she picks Ollama and proceeds; with a cloud key, she picks that. If she picks Ollama, the team profiles (`flo`, `malcolm`, `sage`, `chadwick`, `whisper`, `franklin`) need Ollama reachable; if not, the first Flo chat will fail at model resolution with a clear Flo-side error. **This is the only "Ashley gets stuck" moment in the current build.**
2. **No "Connect Gmail" button.** Ashley needs to set her Gmail up via the existing IMAP path (EMAIL_ADDRESS + EMAIL_PASSWORD env vars), or wait for a small UI pass that adds the button. Until then, the Gmail / CTC-via-email path is not reachable for her. Synthetic condition / CTC tests pass on this repo; the live Gmail-to-Flo wire stops at "set the env var."

---

## Exact branch and commits

- **Branch:** `flo/minimax-continuation`
- **Remote:** `https://github.com/jeremymac904/loanflor-processing-llc-final.git`
- **Commits this milestone:** `29b03c1` (drop wiring) + `61ad4f1` (Windows installer stage) from prior milestone
- **Latest tip pushed:** yes

---

## My honest answer

**No, Ashley cannot use Flo completely without developer help right now.**

What works end-to-end: the loan-day workflow (drop docs, prep, why, conditions, requests, orders, signing, restart). What's missing: a Flo-specific first-run UI replacing the default Hermes bootstrap, plus Connect Gmail / Zapier / Documenso buttons. The backend is fully ready — only the React cards are missing. One focused UI pass closes the gap.

What I am certain of: the day-to-day loan workflow (Test 2 through Test 13 except for Gmail-dependent steps) is reachable from the current build. The drag-drop just landed in this milestone. I am not certain that an Ollama-backed first launch will go smoothly without a model pick — that's the one realistic "Ashley gets stuck" point.
