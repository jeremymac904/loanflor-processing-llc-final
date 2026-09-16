---
name: flo-milestones
description: "Apply supplied milestone definitions; invent none."
version: 0.1.0
author: Flo Agent bootstrap (Claude Code pass), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Mortgage, Milestones, Definitions, Status]
    category: flo-mortgage
    related_skills: [flo-processing-workflow, flo-communication]
---

# Flo Milestones Skill

Holds the only two milestone definitions the owner has supplied and makes Flo say so when asked about any other. It exists so status language stays consistent and so Flo never manufactures a definition.

## When to Use

- Ashley or a draft needs the meaning of "Processing" or "CTC".
- A status update, borrower message, or recap uses a milestone term.
- Someone asks what a milestone "means" or "requires".

## Prerequisites

- `.flo/source_material/distilled/04_Milestone_Definitions.md` (read with `read_file` for provenance).
- `flo-processing-workflow` for the ordered milestone list.

## How to Run

1. Match the term to the table in Quick Reference.
2. If it is defined, use the definition verbatim or in a plain-language paraphrase that adds nothing.
3. If it is not defined, report SOURCE_GAP and, when useful, ask Ashley for the working definition she uses.

## Quick Reference

Source-backed definitions (Milestone Definitions, supplied 2026-09-08):

| Milestone | Supplied definition |
|---|---|
| Processing | Docs collected |
| CTC | Ready to close |

"CTC" is the abbreviation the source uses; the workflow source spells it "Clear to Close".

Milestones that exist in the workflow but have **no supplied definition**: Intake, Application, Conditional Approval, Closed.

## Procedure

### 1. Resolve the term

Normalise capitalisation and the CTC/Clear to Close abbreviation. Done when the term maps to one of the six milestone names.

### 2. Answer from the table only

For Processing and CTC, use the supplied definition. For the other four, say the supplied source has no definition (SOURCE_GAP). Done when no definition is stated without a source.

### 3. Keep the communication milestone-based

The communication style source asks for "clear, simple, milestone-based communication"; use the milestone name in borrower- or LO-facing drafts. Done when the draft names the milestone rather than internal jargon.

## Sources

| Source | Location | Reviewed |
|---|---|---|
| Milestone Definitions (owner-supplied PDF) | `.flo/source_material/originals/04_Milestone_Definitions.pdf` | 2026-09-08 |
| Distilled copy | `.flo/source_material/distilled/04_Milestone_Definitions.md` | 2026-09-08 |
| Communication Style Guide | `.flo/source_material/distilled/05_Communication_Style_Guide.md` | 2026-09-08 |

Source review date: 2026-09-08.

## SOURCE_GAP

- Definitions for Intake, Application, Conditional Approval, and Closed.
- Any sub-status, entry/exit criteria, or "what triggers the transition".
- Whether "docs collected" means all initial documents or a defined checklist.

## Prohibited Inference

- Do not expand "Docs collected" into a document list.
- Do not define "Conditional Approval" or "Closed" from general mortgage knowledge, even if it seems obvious.
- Do not treat a lender portal label as a Flo milestone definition without Ashley's mapping.

## Pitfalls

- Silently substituting an industry definition for a missing one.
- Using "CTC" and "Clear to Close" as if they were different milestones.

## Verification

- Only two definitions are ever stated as fact, and they match the source text.
- Every other milestone question yields an explicit SOURCE_GAP statement.
