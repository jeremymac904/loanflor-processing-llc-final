# MiniMax Continuation Plan

This is what I (MiniMax, acting as the Flo continuation engineer) plan to work on
next, in priority order. It is consistent with `MAC_HANDOFF.md` §"What should
be worked on next" and `ASHLEY_UX_SIMPLIFICATION.md`.

## Ranking method

Per the rules in the handoff:

1. Direct benefit to Ashley
2. Frequency of use
3. Amount of manual work removed
4. Reliability impact
5. Complexity

Technical novelty is **not** a criterion. Cloud infrastructure is not a
criterion. None of this should expose MCP, model providers, Docker, source
registries, rule activation, Bot Mode internals, Documenso envelopes, or any
other technical plumbing to Ashley.

## Priority 1 — Mac-side completion of the existing handoff

These are items already called out in `MAC_HANDOFF.md` that are simply not yet
done on Mac because of environment blockers I hit on first pass.

### 1a. Mac equivalent of the Windows Flo Signatures launcher
- **Effort:** Small.
- **What exists on Windows:** `flo-start.ps1`, `flo-autostart.ps1`, Task Scheduler entry, "Flo Signatures" Edge app-mode shortcut. `MAC_SETUP.md` §15 says "there is no Mac equivalent yet".
- **Mac version:** a `Flo Signatures.app` (Electron app-mode is the cleanest
  path — it reuses the existing Electron app already at `apps/desktop/`, just
  pointed at the Documenso signing URL with a custom icon). Or, simpler still,
  a `.command` file in `~/Applications` that runs the existing Electron app
  with the Documenso URL. The custom `.app` is the right answer because Ashley
  should not see a Terminal window. Use the existing Flo icon
  (`.flo/assets/`).
- **Blocker:** needs Docker Desktop running (priority 1c).
- **Files:** new — likely `apps/desktop/flo-signatures/` or a thin wrapper
  using Electron's `BrowserWindow` config that auto-opens the Documenso URL.

### 1b. Mac `npm run lint` regression test in CI
- **Effort:** Trivial.
- **Why:** the `eslint` / `brace-expansion` overrides fix needs to stay fixed.
  Add `npm run lint` to whatever local pre-commit / verification script
  exists. (There's no CI config in this repo yet; this is just a local check.)

### 1c. Mac Documenso local stack
- **Effort:** Medium. Mostly waiting on Docker Desktop install (an admin step
  Jeremy has to do — not me).
- **What:** `cd flo-agent/deploy/documenso && cp .env.example .env.flo && docker compose up -d`. Then re-run the live integration test from `FLO_ESIGN.md` against a Mac-hosted Documenso v2.18.0. Confirm the 21-check list still passes on Mac.

## Priority 2 — Ashley's core missing-document workflow

This is the owner-directed next milestone. It is **already mostly built**;
what's missing is the end-to-end wiring that takes it from "Ashley clicks
**Request Missing Documents**" to "Whisper has a draft" to "Ashley approves
it" to "the loan's Documents section now shows `Requested from borrower`."

### 2a. Malcolm's plain-English readiness output contract
- **Effort:** Small.
- **Already there:** `plugins/flo-team/readiness.py`, the `missing_items()`,
  `biggest_blocker()`, `best_next_move()` helpers in `today.py`, and the same
  helpers in `apps/desktop/src/plugins/flo/ashley.ts`. Both have tests
  (`tests/flo/test_today.py`, `apps/desktop/src/plugins/flo/ashley.test.ts`).
- **What to lock down:** the exact JSON shape that leaves Malcolm. Per
  `MAC_HANDOFF.md`: `status`, `missing_items`, `important_discrepancies`,
  `aus_status`, `income_status`, `asset_status`, `orders_status`,
  `biggest_blocker`, `best_next_move`. Make sure none of the internal flags
  (`pending_review`, `handoff_open`, `provider_degraded`,
  `READY_FOR_NEXT_STEP`) ever leak into that shape. Add a test that
  asserts the shape end-to-end.

### 2b. The one-click Request Missing Documents button
- **Effort:** Medium.
- **Where:** `apps/desktop/src/plugins/flo/pipeline.tsx` — inside the File
  view. There's already a `SendForSignaturePanel`. The new component is a
  `RequestMissingPanel` (or similar) that:
  1. Shows the missing-items list in plain English.
  2. On click, calls `flo_draft` (the existing Whisper tool, idempotent
     via `intents.py`).
  3. Lands the draft in `approvals` queue with `Approve / Edit / Not Now`.
  4. After send, the loan's Documents section shows `Requested from
     borrower: <items>, status: Waiting` — not "still missing".

### 2c. Today-screen card wording after a request goes out
- **Effort:** Small.
- **Why:** Today currently says "Needs N items". After Whisper has sent the
  request, it should say "Waiting on borrower: <items>" or "Waiting for N
  items" — not "Needs N items" again. The card rules in `ashley.ts` already
  know about `_OTHERS = {borrower, lo, lender, ...}` — the gap is just that
  the post-send state is currently derived from a different field than
  pre-send. Wire it through.

## Priority 3 — Order Outs and Conditions

### 3a. **Order Title / Order HOI / Order WVOE** buttons in the File view
- **Effort:** Medium.
- **What exists:** `plugins/flo-team/orders.py` (Chadwick's tool), `Order`
  tool already idempotent, `flo_order` action with intent IDs. The
  Approvals queue already knows how to render order proposals.
- **Missing:** the File view buttons. Each button only shows when the
  corresponding order is `not_yet_ordered`. Click → one chat opens with
  Flo, one Approvals card shows up.
- **Tests:** add a flow test (synthesize a workspace, run the bot, assert the
  Approvals queue has one card with the right action).

### 3b. Conditions / work-conditions workflow
- **Effort:** Medium-large. Conditions are a real mortgage concept — UW
  conditions, prior-to-doc conditions, prior-to-funding conditions.
- **What exists:** `plugins/flo-team/readiness.py` already treats conditions
  as first-class (`ws["conditions"]`). The Today screen mentions
  "Conditions: None open". The File view has a `▸ Conditions` collapsed row.
- **Missing:** the workflow to mark a condition cleared when an updated
  document comes in, and to re-render Today with the cleared condition. The
  existing `documents.py` already calls `update_status` when an updated doc
  arrives — what needs adding is a "this satisfied condition X" hook so the
  condition clears and the loan's `best_next_move` recomputes.

## Priority 4 — Underwriting explanation via "Why?"

- **Effort:** Small once Sage's response validation gate is in place.
- **Where:** File view's `[Why?]` on missing items, conditions, AUS
  findings, income/asset lines.
- **Already exists:** `plugins/flo-team/sources.py`, `sage_response.py`,
  `flo_sage_response build → validate` gate per `FLO_RELIABILITY_HARDENING.md`.
- **What's missing:** the desktop-side click handler that calls Sage with
  the validated question and shows the source-bound answer. `ashley.ts`
  has `whyPrompt` placeholder; the wiring needs the prompt to be sent
  through the right gateway method and the response rendered as
  `Source: <section> — <plain-English answer>`.

## Priority 5 — CTC / end-of-file workflow

- **Effort:** Medium. Real-world CTC handling is messy.
- **What to defer until priorities 1–4 are done.** Owner has not asked for
  this yet.

## Priority 6 — Marketing (Franklin)

- **Effort:** Small once triggered.
- **What exists:** Franklin's profile, Zapier scoping excludes him from
  borrower data, marketing tool is wired.
- **When:** only after priorities 1–4 are stable. Per `MAC_HANDOFF.md`:
  "marketing only after core processing is solid."

## What I am **not** going to do

- Move anything to cloud / VPS / Kubernetes.
- Replace the six-agent system.
- Rewrite Hermes.
- Add a dashboard.
- Activate mortgage rules without sources.
- Push secrets.
- Use real borrower data.
- Add MCP/model-provider/Docker/Postgres concepts to Ashley's UI.
- Touch upstream Hermes code unless absolutely necessary; everything stays in
  the additive Flo surface (profile, plugin, skill, Desktop plugin, theme).

## Open questions for Jeremy (no business answer required to start
priorities 1–4 — these are informational)

1. Is the existing Flo icon (`apps/desktop/src/plugins/flo/flo-badge.png`)
   the one to use for the Mac `Flo Signatures.app` icon, or do you want
   a separate mark for the signing launcher?
2. When a borrower signs in Documenso's local signing UI and the signed PDF
   comes back into the deal room, should the existing `documents.ashley_documents`
   section show it as `Signed (auto-filed)` or `Signed (just received)` —
   wording only, no behavior change.
3. Do you want the `npm run lint` step added to the website too, or only
   desktop? The website's `package.json` currently has no `lint` script.
