# Codex Handoff

The Codex pass begins after Claude has produced `CLAUDE_PROGRESS.md`.

## Codex responsibilities

1. Read all Flo context and upstream instructions.
2. Review Claude's diff against the pinned upstream commit.
3. Identify changes that unnecessarily increase merge conflicts.
4. Refactor Flo customizations toward extension/plugin/profile surfaces where practical.
5. Polish UI consistency, copy, spacing, accessibility, keyboard flow, loading/empty/error states.
6. Search for incomplete Hermes user-facing branding.
7. Tighten policy/audit tests.
8. Review secrets, OAuth, logging, persistence, updater, and installer paths.
9. Remove dead scaffolding and ambiguous TODOs.
10. Produce a release-candidate checklist rather than enabling risky capabilities prematurely.

## Required review questions

- Can we pull a future upstream security fix without redoing the fork?
- Is any user-visible Hermes branding accidental?
- Did any broad internal rename add no user value?
- Can untrusted retrieved content authorize an action?
- Can a tool bypass confirmation?
- Are credentials accessible to renderer/plugin/model context?
- Is any borrower-sensitive payload written to logs or general memory unnecessarily?
- Could Flo update itself from Nous and overwrite downstream changes?
- Does the app help Ashley prioritize, or does it reproduce a generic agent dashboard?
- Are unsupported mortgage rules clearly marked as source gaps?

## Output

Codex should create:
- `CODEX_REVIEW.md`;
- `CODEX_CHANGES.md`;
- updated tests;
- updated decision/open-question logs;
- a prioritized remaining-work list.

## Underwriting architecture handoff — 2026-09-08

Read `UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md` and `../underwriting/source_registry.json` before income/underwriting implementation. Five inactive packs and synthetic acceptance specs exist. Do not mistake source discovery for approved current rules. Preserve exact program/method/effective triggers, source revision citations, separate overlays/conditions and deterministic math. Rights/access gaps are in `15_OPEN_QUESTIONS.md`; no guide corpus is bundled. Bootstrap baseline/rebrand sequencing is unchanged.
