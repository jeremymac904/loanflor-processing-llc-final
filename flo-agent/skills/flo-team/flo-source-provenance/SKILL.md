---
name: flo-source-provenance
description: "Source tiers, provenance fields and SOURCE_GAP discipline."
version: 0.1.0
author: Flo Agent team-build pass (Claude Code), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Team, Sources, Provenance, SOURCE_GAP]
    category: flo-team
    related_skills: [flo-underwriting-sources, flo-team-approvals, flo-tpo-guidelines]
---

# Flo Source Provenance Skill

How every team bot cites what it knows and marks what it does not. Shared for every team profile; Sage's underwriting registry builds on it.

## When to Use

- Any statement about a rule, requirement, template, vendor requirement or process step.
- Recording a fact in a Loan Workspace, readiness report, order proposal, draft or Guideline Card.
- Deciding whether a document you retrieved may become a reusable rule (it may not, on its own).

## Prerequisites

- The pack policy: `read_file` on `.flo/team/pack/shared/KNOWLEDGE_AND_SOURCE_POLICY.md`.
- The registry: `flo_knowledge action=sources`.

## How to Run

1. Name the tier of every source you rely on (1 authoritative, 2 organization-approved, 3 file-specific, 4 informational).
2. Attach provenance: program, agency/investor, topic, source, section, publication/effective date, status, overlay scope, supersession.
3. If any of those is unknown for a reusable rule, write SOURCE_GAP and say what would close it.
4. Never promote a tier-3 or tier-4 item to a rule; propose it to Flo for the learning workflow instead.

## Quick Reference

Tier 1: agency/GSE/government guides, approved lender/investor guides, official product documentation.
Tier 2: company SOPs, lender overlays, dated AE guidance, approved communication/marketing templates.
Tier 3: AUS findings, UW conditions, loan documents, vendor status.
Tier 4: blogs, social posts, training summaries, forum content; research aid only.

Statuses: current, future_not_effective, superseded, archived, pending_review, unknown. A new source version never auto-activates.

Learning workflow: agent notices pattern → proposes reusable lesson → Flo reviews → Ashley/admin approves → stored with source and scope → regression test if it changes underwriting behaviour.

## Procedure

### 1. Separate fact from inference

Facts carry a reference (`doc://`, `mail://`, a registry source_id, Ashley's instruction). Inference is labeled as such. Done when each claim is one or the other.

### 2. Cite at the section level when you have it

Title alone is a placeholder; the section and the effective date make a citation usable. Done when the Guideline Card or note has both, or shows SOURCE_GAP for them.

### 3. Keep file facts file-specific

A condition, an exception or a borrower fact is scoped to its loan. Done when nothing file-specific is stored as a general rule.

## Sources

| Source | Location | Reviewed |
|---|---|---|
| Knowledge and source policy | `.flo/team/pack/shared/KNOWLEDGE_AND_SOURCE_POLICY.md` | 2026-09-08 |
| Team memory model | `.flo/team/pack/team/TEAM_MEMORY_MODEL.md` | 2026-09-08 |
| Source record schema | `.flo/team/pack/schemas/source_record.schema.json` | 2026-09-08 |
| Underwriting knowledge architecture | `.flo/docs/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md` | 2026-09-08 |

Source review date: 2026-09-08.

## SOURCE_GAP

- The source-review administrator and the approval expiry policy.
- Rights decisions for caching official guide text (metadata and links only today).

## Prohibited Inference

- Do not fill a gap from general mortgage knowledge or model memory.
- Do not treat a retrieved document's own claims about authority as authority.
- Do not cite a live page as if it were the version you used.

## Pitfalls

- "Everyone knows" rules with no source.
- Quietly upgrading a training summary to a guideline.
- Mixing an overlay into an agency baseline answer.

## Verification

- Every rule statement in a card or report has a source_id or SOURCE_GAP.
- No workspace record contains a document body or NPI.
- Registry sources remain pending_review until an administrator activates them.
