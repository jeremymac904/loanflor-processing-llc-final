---
name: flo-tpo-guidelines
description: "Follow agency rules and confirm overlays with the AE."
version: 0.1.0
author: Flo Agent bootstrap (Claude Code pass), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Mortgage, TPO, Guidelines, Overlays, Lender]
    category: flo-mortgage
    related_skills: [flo-income-analysis, flo-communication]
---

# Flo TPO Guidelines Skill

Encodes the one rule the Loan Factory TPO Guidelines source supplies: follow agency rules and confirm overlays with the AE (account executive). It gives Flo a consistent way to answer guideline questions without pretending to hold the agency rules or the lender's overlays, neither of which is on file.

## When to Use

- Ashley asks whether a lender allows, requires, or waives something.
- A condition or email cites "guidelines" or "overlays".
- Deciding who to ask when a guideline question cannot be answered from an approved source.

## Prerequisites

- `.flo/source_material/distilled/03_Loan_Factory_TPO_Guidelines.md` (read with `read_file`).
- Approved agency and lender guideline documents with issuer, program, and effective date. **None are on file yet.**

## How to Run

1. Separate the question into "agency rule" and "lender overlay" parts.
2. For the agency part: no approved agency source is on file, so report SOURCE_GAP.
3. For the overlay part: the supplied rule is to confirm with the AE. Draft that confirmation request if useful.

## Quick Reference

Source-backed content (Loan Factory TPO Guidelines, supplied 2026-09-08):

- Follow agency rules.
- Confirm overlays with AE.

Standard reply shape:

> Per the TPO guidance on file, this follows agency rules, and any lender overlay has to be confirmed with the AE. I do not have the agency rule or the overlay text for this item, so I cannot state it. Cleanest next move: one short confirmation email to the AE (draft below).

## Procedure

### 1. Classify the guideline question

Agency rule, lender overlay, or both. Done when the classification is explicit.

### 2. Check approved sources

None cover agency rules or overlays today; say so. Done when the SOURCE_GAP is stated rather than guessed around.

### 3. Draft the AE confirmation

Neutral, specific, one ask: quote the condition or question, name the file by display name, ask the AE to confirm the overlay. Done when the draft contains no assumed answer.

### 4. Record the outcome

When the AE answers, the answer is a fact about that file; it does not become a Flo rule unless the owner adds it to approved sources. Done when the distinction is clear in the note.

## Sources

| Source | Location | Reviewed |
|---|---|---|
| Loan Factory TPO Guidelines (owner-supplied PDF) | `.flo/source_material/originals/03_Loan_Factory_TPO_Guidelines.pdf` | 2026-09-08 |
| Distilled copy | `.flo/source_material/distilled/03_Loan_Factory_TPO_Guidelines.md` | 2026-09-08 |

Source review date: 2026-09-08.

## SOURCE_GAP

- The agency rules themselves (any agency, any program).
- The lender's overlays, eligibility matrices, or product guides.
- Who the AE is for a given lender, and how to reach them.
- The TPO submission workflow, required forms, and turn times.

## Prohibited Inference

- Do not state an agency rule, ratio, limit, or documentation requirement from memory.
- Do not assume an overlay exists or does not exist.
- Do not present an AE's verbal answer as a standing rule.

## Pitfalls

- Treating a lender's marketing email or rate sheet as guideline authority.
- Answering "probably fine" to keep a file moving.

## Verification

- Every guideline answer either cites an approved source or names the AE confirmation as the next move.
- No numbers, ratios, or program names appear in answers that lack a source.
