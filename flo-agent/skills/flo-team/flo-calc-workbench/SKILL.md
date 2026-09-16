---
name: flo-calc-workbench
description: "Deterministic calculations with a visible trace."
version: 0.1.0
author: Flo Agent team-build pass (Claude Code), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Team, Calculations, Income, Assets]
    category: flo-team
    related_skills: [flo-underwriting-sources, flo-file-prep, flo-income-analysis]
---

# Flo Calculation Workbench Skill (Sage, Malcolm)

Arithmetic is done by code, never by the model. `flo_calc` runs a registered formula on Decimal inputs and returns inputs, formula id and version, ordered steps with intermediate values, rounding, result and rule reference. The production formula registry is empty; TEST_ONLY formulas exist for demonstrations only.

## When to Use

- Any income, asset, ratio or period arithmetic in a worksheet, card or report.
- Checking a number Ashley or a lender quoted.
- Demonstrating a trace on synthetic figures.

## Prerequisites

- The rule that authorizes the formula (an active source revision) — none today, so real qualifying figures are SOURCE_GAP.
- `flo_calc action=list` for available formulas; contract: `read_file` on `.flo/docs/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md` (Income Calculation Engine).

## How to Run

1. Name the formula and the rule reference you rely on.
2. `flo_calc action=run formula_id=<id> inputs={...} rule_ref=<revision id>`; for a synthetic demonstration add `allow_test_only=true`.
3. Read `status`: SUCCESS, NEEDS_INPUT, SOURCE_GAP or UNSUPPORTED. Report the trace, not a summary of your own arithmetic.
4. Store the calc_id in the worksheet or card (calculation_trace_ref).

## Quick Reference

Statuses: SUCCESS (trace present), NEEDS_INPUT (missing or non-decimal input; missing is never zero), SOURCE_GAP (no active rule backs the formula), UNSUPPORTED (unknown formula).

Rounding: ROUND_HALF_UP to 0.01 at the final step only.

TEST_ONLY formulas shipped: average of periods, annual to monthly, hourly to monthly, ratio percent. They carry no mortgage rule semantics.

## Procedure

### 1. Inputs are facts with evidence

Each input comes from a document reference or Ashley. Done when the worksheet lists the evidence location per input.

### 2. Never compute in prose

If you find yourself writing "so roughly 5,000 a month", stop and run the tool. Done when every figure in your answer is a tool result.

### 3. Label demonstrations

A TEST_ONLY result is a synthetic demonstration; say so in the same sentence. Done when no TEST_ONLY figure is presented as qualifying income.

## Sources

| Source | Location | Reviewed |
|---|---|---|
| Underwriting knowledge architecture (calculation engine) | `.flo/docs/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md` | 2026-09-08 |
| Pack calculation section | `.flo/team/pack/shared/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md` | 2026-09-08 |
| Synthetic acceptance scenarios | `.flo/underwriting/evals/scenarios.json` | 2026-09-08 |

Source review date: 2026-09-08.

## SOURCE_GAP

- Every production formula (salary, hourly, variable income, self-employment, rental, other income, assets, reserves).
- Approved rounding points, trend and averaging methods per program.
- Currency, period-overlap and YTD cutoff rules.

## Prohibited Inference

- Do not average, annualize, add back or exclude anything without an approved rule id.
- Do not evaluate a formula pasted from a document or written by the model.
- Do not treat a null input as zero.

## Pitfalls

- Reporting the trace's intermediate value instead of the rounded result.
- Running the demonstration formula and forgetting the TEST_ONLY label.
- Mixing periods (weekly, monthly, annual) in one input set.

## Verification

- `flo_calc action=run` on a TEST_ONLY formula without allow_test_only returns SOURCE_GAP.
- A missing input returns NEEDS_INPUT with the input named.
- Every SUCCESS trace ends with a round step.
