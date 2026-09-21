# Codex UI polish

This pass keeps the existing Flo/Hermes routes and backend contracts intact.

## Ashley-facing changes

- Today keeps a quiet, three-column-feeling hierarchy: greeting, Top 3, then the four decision cards and three primary actions.
- The greeting now defaults to “Morning Ash ☕” while preserving the backend-provided greeting when available.
- Flo cards share a single rounded surface treatment and section-label rhythm.
- Top-3 file rows have more breathing room and a clearer action edge.
- File View already exposes contextual Title, HOI, WVOE, missing-document, and Ask Flo actions; no mortgage workflow logic was changed.
- Existing Approvals, onboarding, chat, document drop, CTC, and order flows remain the source of truth.

## Deliberate boundaries

No underwriting, conditions, intake, routing, provider, approval, signing, or workspace architecture was redesigned. Voice remains optional and the normal text composer remains complete.
