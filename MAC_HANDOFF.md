# Mac handoff

Written for continuing this project with Claude Code / Codex on a Mac, without depending on the original
Windows dev machine. Read `PROJECT_MAP.md` first for how the pieces fit together, then this file for status.

## Repo state at handoff

- **Branch:** `flo/full-project-migration`
- **Base:** `feature/loan-submission-v2` (website), which is a clean superset of `origin/main`
- **flo-agent Flo branch at time of migration:** `flo/0.21-bootstrap` @ `9b032fa5686256eb0f53dd67c9ba98da320fec23`

## Permanent product rules (do not relitigate these)

1. **Build local.** No VPS, no cloud infrastructure, unless the owner explicitly asks.
2. Use normal Hermes connectors when an external service is genuinely required — never a bespoke tunnel.
3. Keep Ashley's UI extremely simple: Today / Pipeline / Approvals only; everything technical is under
   Advanced.
4. Flo is Ashley's one primary assistant — she never talks to Malcolm/Sage/Whisper/Chadwick/Franklin
   directly in normal use.
5. Specialist bots work behind the scenes.
6. Never expose technical plumbing to Ashley (no Docker, no "envelope", no API terms, no bot names unless
   genuinely helpful).
7. Do not invent mortgage guidelines. No active source = no production underwriting formula; mark
   `SOURCE_GAP` instead.
8. Keep borrower data local whenever possible.
9. Never commit real secrets, tokens, certificates, Docker volumes, or borrower data.
10. One writer per working tree — check `git status` and recent mtimes before editing shared docs.

## What's currently working (verified, not just written)

- **Local Documenso signing.** Single-signer flow verified live end-to-end through Documenso's own browser
  signing page (create → distribute → sign → retrieve signed PDF). Health check + auto-recovery in
  `flo-agent/plugins/flo-team/esign.py`. All 10 Documenso API endpoints the adapter uses are confirmed
  against a live v2.18.0 instance. See `flo-agent/FLO_ESIGN.md`.
- **Website → Flo intake.** 13-step Loan Submission form, duplicate protection, document upload, intake
  delivery with retry. See `LOAN_SUBMISSION_V2.md`, `FLO_INTAKE_INTEGRATION.md`.
- **Multi-program source-bound rules.** Fannie/Freddie/FHA (TOTAL + Manual)/VA/USDA, all gated on ACTIVE
  source sections — never a generic "conventional" rule.

## Known limitations (intentionally deferred, not bugs to chase)

- **Two-signer borrower signing is not a completed live end-to-end test.** It's validated by the mock
  integration test (`test_two_signers_partial_then_complete`) plus live API confirmation that per-recipient
  `signingStatus` is reported correctly — not by an actual two-borrower browser signing session.
- **Remote borrower signing is not production-ready**, by owner directive: Flo Signatures runs locally, and
  an outside borrower cannot reach `localhost`. This is intentionally deferred, not something to solve
  proactively — do not propose Cloudflare Tunnel, ngrok, a VPS, or any other external-access method unless
  the owner explicitly asks.
- Production SMTP and a CA-issued signing certificate are still open (business/legal decisions, not code
  changes).

## What should be worked on next

Per the owner's most recent direction: **stop expanding signing infrastructure — it's good enough for now.**
The next milestone is Ashley's core workflow:

```
NEW LOAN → Malcolm preps it → Flo tells Ashley what's missing → Ashley clicks one button to request it
```

Concretely:

1. A clean, plain-English output contract from Malcolm (`status`, `missing_items`,
   `important_discrepancies`, `aus_status`, `income_status`, `asset_status`, `orders_status`,
   `biggest_blocker`, `best_next_move`) — no internal flags or machine-style readiness prose reaching
   Ashley.
2. A one-click **Request Missing Documents** button inside a loan that hands the missing-item list to
   Whisper, shows Ashley one drafted borrower message, and lets her Send / Edit / Not Now — no navigating to
   Whisper, no re-selecting the same items twice.
3. After send, the loan shows "Requested from borrower: <items>, status: Waiting" — not left looking like
   unrequested missing items.
4. Today screen cards stay simple: loan name, "Needs N items", what it's waiting on, the next move — no
   team handoff details, no tool status.
5. Signing UI stays as-is (`Send for Signature` / `Ready to send` / `Waiting for signature` / `Signed` /
   `Needs attention`) — no new dashboard.

## Tests currently passing

See `MIGRATION_TEST_RESULTS.md` for what was actually run on the Windows machine before this migration, and
the exact output.

## Source activation status

Fannie: ACTIVE (Golden Loan Path). Freddie/FHA/VA/USDA: source registry + fetchers exist; activation is a
per-install, human-approved step (`flo-agent/scripts/flo/activate_sources.py --program <p>`) — check current
status with `flo-agent/scripts/flo/knowledge_center.py` on the machine you're setting up, since activation
state is local (source caches are never committed — see `MAC_SETUP.md` §12).
