# Implementation Plan

## Phase 0 - Baseline and repository hygiene

1. Clone official Hermes Agent at `v2026.8.31`.
2. Rename clone remote to `upstream`.
3. Create branch `flo/0.21-bootstrap`.
4. Record exact commit SHA.
5. Read upstream contributor/Desktop instructions.
6. Install dependencies exactly as upstream documents.
7. Run relevant Python/JS checks and Desktop tests.
8. Launch stock Desktop if environment permits.
9. Record baseline in `CLAUDE_PROGRESS.md`.

**Gate:** Do not rebrand until baseline is understood.

## Phase 1 - Thin Flo distribution foundation

1. Create a `.flo/` project-context directory in the downstream repo.
2. Copy this kit's docs/source material into it.
3. Add/merge a root `CLAUDE.md` without deleting upstream instructions.
4. Add a Flo-specific change log and decision log.
5. Implement visible package identity:
   - Flo product/executable/artifact naming;
   - `flo://` deep link;
   - Flo metadata and permission strings;
   - app icon placeholders or generated assets when available.
6. Find and categorize user-visible Hermes strings.
7. Disable or redirect upstream self-update behavior until Flo's update source exists.
8. Keep internal backend/RPC naming unchanged unless needed.

**Gate:** Flo launches as Flo while the backend remains upstream-compatible.

## Phase 2 - Ashley profile + domain scaffolding

1. Create Ashley/Flo profile seed:
   - `SOUL.md`;
   - `USER.md` seed;
   - safe default config.
2. Create the initial Flo skill directories from `docs/09_MORTGAGE_SKILLS_PLAN.md`.
3. Include source provenance and `SOURCE_GAP` markers.
4. Implement a minimal Today/Pipeline domain model or scaffold without inventing loan data.
5. Ensure product copy follows Ashley's communication contract.
6. Add tests for persona/skill loading where the upstream architecture supports it.

**Gate:** Flo's behavior is recognizably Ashley-specific without external accounts connected.

## Phase 3 - Policy and audit contracts

First Claude pass should at least scaffold/test contracts for:

- `allow`;
- `confirm`;
- `deny`;
- action proposal;
- approval;
- audit event;
- prompt-injection separation.

Do not connect production credentials just to prove the interface.

**Gate:** side effects cannot bypass the policy contract.

## Phase 4 - Google Workspace

Later phase.

Build the Flo credential broker and connector with staged scopes.

Start read-only.

Then add confirmed sends.

Do not ship broad write permissions by default.

## Phase 5 - Ashley workflow UI

Implement:
- Today;
- Pipeline;
- Inbox;
- Conditions;
- Documents;
- Flo;
- Activity.

Favor progressive disclosure.

## Phase 6 - Routines

Add:
- morning brief;
- email/request sweep;
- risk check;
- condition sweep;
- end-of-day recap.

Routines may prepare work but should not silently send externally in v1.

## Phase 7 - Packaging/release

- macOS signing/notarization;
- Windows signing;
- Flo-owned update channel;
- installer testing;
- migration/backups;
- release checklist.

## Phase 8 - Later automation

Only after explicit review:
- lender portals;
- browser/computer-use;
- external LOS mutations;
- more autonomous workflows.

## Underwriting capability track (required; preserves bootstrap sequence)

This track does not replace Phases 0–3 or authorize production connections. See `UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md`.

- Now, alongside bootstrap context: five inactive agency pack manifests, official discovery registry, rights/access gaps, canonical architecture and synthetic acceptance specs. Completed 2026-09-08; no live rules activated.
- After Phase 0 baseline and alongside Phase 2 scaffolding: implement immutable source/rule schema and repository, loan-context applicability resolver, layered conflicts and SOURCE_GAP responses through Flo-owned Hermes extensions. Prove contracts with TEST_ONLY sources before ingesting real guidelines.
- With Phase 3 policy/audit: admin staging/review/activation, checksum-bound approvals, atomic ruleset snapshots, rollback, freshness and historical replay. Production activation requires successful regressions and admin approval; source retrieval alone is insufficient.
- Subsequent narrow slices: rights-approved agency section ingestion, independently verified calculators and document requirements, one program/income type at a time. All five packs remain explicit coverage targets, not interchangeable fallbacks.
- Phase 5 extension: Income Analysis worksheet and Conditions/File Progress integration; progressive citation/trace disclosure, user-initiated save/export. External sends/uploads retain existing policy gates.
- Later: source-backed tax-return adjustments, lender/investor specialty guides, licensed update monitoring. No universal specialty formulas, automatic AE-email-to-rule promotion or unattended production updates.

Gates: rights approved; exact revision and effective trigger verified; no unresolved controlling conflict; Decimal math independently tested; missing documentation/citations/overlays surfaced; no approval language. Existing rebrand work continues independently of completing full guide ingestion.
