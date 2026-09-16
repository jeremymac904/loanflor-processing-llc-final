---
name: flo-income-analysis
description: "Scope income review to sources; refuse unsupplied formulas."
version: 0.1.0
author: Flo Agent bootstrap (Claude Code pass), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Mortgage, Income, W2, Self-employed, Rental]
    category: flo-mortgage
    related_skills: [flo-tpo-guidelines, flo-processing-workflow]
---

# Flo Income Analysis Skill

A deliberately empty shell. The supplied Mortgage Income Calculation Guide states only that it *covers* W2, self-employed, and rental income evaluation; it contains no formulas, averaging periods, documentation standards, or agency rules. This skill makes Flo say exactly that instead of calculating from general knowledge. Never imply Flo approved income.

## When to Use

- Ashley asks how to calculate, average, or qualify any income type.
- A lender condition mentions income documentation and Ashley wants it translated.
- Any draft that would state a qualifying income figure.

## Prerequisites

- `.flo/source_material/distilled/02_Mortgage_Income_Calculation_Guide.md` (read with `read_file`).
- An approved, versioned income guideline with issuer, program, and effective date. **None is on file yet.**

## How to Run

1. Identify the income type and the question (calculation, documentation, eligibility).
2. Check whether an approved source covers it. Today the answer is always: the source names the area but supplies no rule.
3. Reply with the SOURCE_GAP statement in Quick Reference, plus the cleanest next move (usually: confirm with the AE or underwriter, or supply the guideline so Flo can be updated).

## Quick Reference

Source-backed content (Mortgage Income Calculation Guide, supplied 2026-09-08):

- The guide "covers W2, self-employed, and rental income evaluation."

That is the entire supplied content.

Standard SOURCE_GAP reply:

> The approved Flo income source only states that W2, self-employed, and rental income are covered. It does not supply the calculation method, averaging period, documentation standard, or agency rule for this question, so I will not estimate it. Cleanest next move: confirm with the AE/underwriter, or add the guideline to Flo's sources so this can be answered with a citation.

## Procedure

### 1. Classify the request

Label it W2, self-employed, rental, or other, and note whether Ashley wants a number, a document list, or an eligibility view. Done when the request is one line.

### 2. Check the source register

Look for an approved source that covers the exact question. Done when you can name the source or state that none exists.

### 3. Respond without inference

If no source covers it, use the standard reply above. Never produce a figure, ratio, look-back period, or document list. Done when the response contains zero unsupported rules.

### 4. Route the gap

Offer to record the question in the open-questions list so the missing guideline can be supplied. Done when Ashley knows what would close the gap.

## Sources

| Source | Location | Reviewed |
|---|---|---|
| Mortgage Income Calculation Guide (owner-supplied PDF) | `.flo/source_material/originals/02_Mortgage_Income_Calculation_Guide.pdf` | 2026-09-08 |
| Distilled copy | `.flo/source_material/distilled/02_Mortgage_Income_Calculation_Guide.md` | 2026-09-08 |

Source review date: 2026-09-08. This skill must be rewritten, not patched, when authoritative income guidance arrives (see `.flo/docs/09_MORTGAGE_SKILLS_PLAN.md`, "Future source onboarding").

## SOURCE_GAP

Missing for every income type:

- calculation method and formula;
- averaging or look-back period;
- treatment of trends, declines, adjustments, losses, or one-time items;
- documentation standards and forms;
- agency and program distinctions;
- lender overlays;
- worked examples.

## Prohibited Inference

- No formulas, percentages, month or year counts, tax-form names, or document lists from general mortgage knowledge.
- No "typical" or "usually" language that smuggles in a rule.
- No qualifying income figure, even as an estimate or range.
- Never state or imply that income is "approved", "acceptable", or "qualifies".

## Pitfalls

- Answering a confident-sounding lender email as if it were an approved source.
- Filling the gap because the borrower is waiting; the gap is the answer.

## Verification

- A request for a W2, self-employed, or rental formula returns the SOURCE_GAP reply and no numbers.
- The reply names what would close the gap.
- Tests in `tests/skills/test_flo_mortgage_skills.py` assert this file contains no formula vocabulary.
