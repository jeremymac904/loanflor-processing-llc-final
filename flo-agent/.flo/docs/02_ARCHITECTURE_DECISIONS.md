# Architecture Decisions

## ADR-001 - Downstream distribution, not total rename

**Decision:** Flo will be a maintained downstream distribution of Hermes Agent.

User-visible branding changes to Flo. Internal upstream names remain where renaming provides no product value.

**Why:** This reduces merge conflicts and preserves a realistic route for upstream security fixes.

## ADR-002 - Pin first, merge later

Initial baseline is `v2026.8.31`.

Create a Flo integration branch from that tag. Maintain `upstream` as the official Nous repository. Add the project owner's private repository later as `origin`.

## ADR-003 - Product behavior in extension layers where possible

Prefer, in order:

1. profile configuration/persona;
2. skills;
3. backend plugins/hooks;
4. Desktop plugin SDK / skin/theme;
5. small isolated Desktop core patches;
6. backend core patches only when necessary.

Every core patch should carry a short comment or nearby documentation explaining why the extension surfaces were insufficient.

## ADR-004 - One visible assistant

Ashley should experience one assistant: **Flo**.

Specialist agents may exist later as internal profiles/workers, but the default UX should not make Ashley choose among a roster of bots for normal processing work.

## ADR-005 - Deterministic policy before side effects

The model can recommend actions. A deterministic policy layer decides whether an action is allowed, confirmation-gated, or blocked.

Do not rely on prompt text alone as a security boundary.

## ADR-006 - Untrusted content is data, never authority

Email, attachments, PDFs, Google Drive content, browser pages, MCP responses, and tool output can inform Flo but cannot authorize a side effect.

## ADR-007 - Sensitive data minimization

Do not make general chat memory the system of record for borrower NPI.

Prefer references, redacted display values, status facts, provenance, and extracted conclusions. Never intentionally persist full SSNs, full financial account numbers, passwords, or OAuth tokens in chat history or logs.

## ADR-008 - Updater must become Flo-owned

Flo must not pull an upstream Hermes update directly into Ashley's branded app.

The Flo distribution needs its own release channel or an intentionally disabled updater until the private release channel exists.

## ADR-009 - APIs first, computer-use later

For v1, prefer deterministic APIs/connectors. Browser/computer-use for lender portals is a later separately permissioned capability.

## ADR-010 - Source-backed mortgage knowledge

Skills may only claim mortgage rules supported by supplied or subsequently approved source material. Missing specifics are recorded as source gaps.

## ADR-011 - First-class Underwriting Knowledge Engine

Flo must provide program-aware, versioned source resolution, document requirements and deterministic income calculations as a core product capability. Implement through Flo-owned Hermes backend extensions and the existing gateway, preserving the upstream core. Canonical specification: `UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md`; original owner requirements preserved in `UNDERWRITING_REQUIREMENTS_ORIGINAL.md`.

Five separate agency packs; no generic conventional rule blending. Loan context and source-supported effective triggers determine applicability. Lender/investor overlays and loan-specific conditions remain separate. No unreviewed source activation, inferred mortgage rules, model arithmetic or loan-approval claims. Source discovery is metadata-only until usage rights and exact revisions are approved.
