# Project map

## Loan intake → processing

```
website (Loan Submission form)
  → server/routes/loanSubmission.js (validate, persist, idempotency)
  → POST to Flo's intake connector (flo-agent/scripts/flo/intake_server.py)
  → flo-agent/plugins/flo-team/intake.py
      creates a Deal Room + one Malcolm task (deterministic, idempotent per submissionId)
  → Flo (the assistant Ashley talks to) message_agent's Malcolm
  → Malcolm reviews the file, pulls documents, checks readiness
  → Flo tells Ashley in plain English what's missing
  → Ashley clicks "Request Missing Documents" → Whisper drafts one message → Ashley approves → sent
```

## Documents → signing

```
document uploaded/pulled at intake
  → flo-agent/plugins/flo-team/documents.py (DocumentStore: hash, text-extract, classify)
  → filed under the loan's Documents section (Pipeline → file → Documents)
  → if it needs a signature: Send for Signature
  → flo-agent/plugins/flo-team/esign.py (Documenso adapter, local-only)
  → borrower signs on Documenso's own local signing page
  → signed PDF comes back into the same Documents section (DocumentStore, same category)
```

## Who does what (Flo Team, all behind the scenes for Ashley)

| Name | Role |
|---|---|
| **Flo** | The one assistant Ashley talks to. Delegates everything below. |
| **Malcolm** | File prep, readiness review, document inventory. |
| **Sage** | Guideline / underwriting-rule answers (source-bound, never fabricated). |
| **Whisper** | Drafts borrower-facing messages (missing-document requests, etc.). |
| **Chadwick** | Marketing content. |
| **Franklin** | Structurally excluded from borrower data — never sees it. |

## Where Ashley's UI lives

- **Today** — one card per loan, plain English, no bot names, no tool status.
- **Pipeline** — the loan list and each loan's Documents section.
- **Approvals** — the human-approval gate every outbound/irreversible action stops at.
- **Advanced** — everything technical (team roster, individual bot chats, sources, logs) — not part of the
  three screens above.

Desktop plugin code: `flo-agent/apps/desktop/src/plugins/flo/` (`ashley.ts`, `pipeline.tsx`, `state.ts`).
