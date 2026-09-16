---
name: flo-underwriting-sources
description: "Sage's source registry, layers and Guideline Cards."
version: 0.1.0
author: Flo Agent team-build pass (Claude Code), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Team, Underwriting, Guidelines, Citations]
    category: flo-team
    related_skills: [flo-source-provenance, flo-calc-workbench, flo-tpo-guidelines, flo-income-analysis]
---

# Flo Underwriting Sources Skill (Sage)

Program-aware, source-backed guideline answers for Fannie Mae, Freddie Mac, FHA, VA and USDA Guaranteed, with Non-QM/Jumbo/specialty only from an actual lender/investor guide. Output is a Guideline Card from `flo_guideline_card`; sources and freshness come from `flo_knowledge`.

## When to Use

- Flo (or Malcolm via Flo) asks a guideline, income-rule, asset, credit or property question.
- Two sources or two teammates disagree.
- The weekly source freshness check.

## Prerequisites

- Registry: `flo_knowledge action=sources program=<fannie|freddie|fha|va|usda>`.
- Architecture: `read_file` on `.flo/docs/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md`; card template: `.flo/team/pack/templates/GUIDELINE_CARD.md`.
- Activation is per install: `flo_knowledge action=sources` reports `active_by_program` (section-level, with published/effective dates and revision ids) and `not_yet_in_force` (sections captured ahead of their effective date, e.g. FHA Handbook 4000.1 Update 18 sections effective 11/10/2026). Anything not listed as active is SOURCE_GAP.
- FHA questions need `underwriting_method=total|manual`; TOTAL (II.A.4) and Manual (II.A.5) rules are separate records and are never mixed on one file. Rule namespaces: `fannie.*`, `freddie.*`, `fha.total.*`, `fha.manual.*`, `va.*`, `usda.*` — a Freddie question is never answered from a Fannie rule ("conventional" is not a program).
- Calculations: `flo_calc program=<...> [underwriting_method=...]`; a formula from another program's namespace is refused (fail closed), never adapted.

## How to Run

1. Identify program, agency/investor, AUS or manual path, lender, and the file facts (AUS findings, conditions).
2. `flo_guideline_card program=<...> topic=<...> lender=<...> aus_path=<DU|LPA|TOTAL|GUS|manual> aus_findings=[...] file_conditions=[...]` (Non-QM/Jumbo: add `investor_source_id`).
3. Read the card's layers; if the conclusion is SOURCE_GAP, give Ashley the official link and the exact thing an AE/UW must confirm.
4. Return the card to Flo with `flo_handoff action=complete` (return_format `guideline_card`).

## Quick Reference

Resolution order: program → AUS/manual → effective official source → lender overlay → investor/product overlay → AUS findings → UW conditions → if conflict remains, AE/UW confirmation.

Layers, always separate: agency_baseline, lender_overlay, investor_program, aus_finding, file_condition.

Overlay states: NOT_LOADED, LOADED, NOT_APPLICABLE_WITH_EVIDENCE, CONFLICT. "None loaded" never means "no overlays exist".

Lifecycle: detected → pending_review → regression → approval → active → archived. Bots may detect; only an administrator approves or activates.

Wording: "guideline-supported assessment", "based on the documents currently available", "potential issue to confirm with UW", "Overlay not loaded, confirm with AE".

## Procedure

### 1. Pin the program before the topic

A question without program and path has no answer. Done when the card header is filled.

### 2. Cite the revision, not the site

Title, section, publication and effective dates, lifecycle. Done when the card shows them or SOURCE_GAP for each.

### 3. Keep file facts out of the rule layer

AUS findings and conditions are evidence for this file only. Done when nothing file-specific appears under agency_baseline.

### 4. Escalate unresolved conflicts

Preserve both positions, name the missing authority, recommend AE/UW confirmation. Done when the card's caution list says so.

## Sources

| Source | Location | Reviewed |
|---|---|---|
| Sage role | `.flo/team/pack/agents/sage/ROLE.md` | 2026-09-08 |
| Underwriting knowledge architecture (pack) | `.flo/team/pack/shared/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md` | 2026-09-08 |
| Underwriting knowledge architecture (repo) | `.flo/docs/UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md` | 2026-09-08 |
| Official source registry | `.flo/team/pack/sources/official/underwriting_sources.yaml` | 2026-09-08 |
| Discovery registry | `.flo/underwriting/source_registry.json` | 2026-09-08 |

Source review date: 2026-09-08.

## SOURCE_GAP

- Sections outside the activated Golden Loan Path slices (self-employment, rental, gifts, retirement assets, credit, property) for every program.
- The currently in-force FHA text for sections whose Update 18 version (effective 11/10/2026) is the one captured.
- USDA area income limits and the 7 CFR 3555.152(c) deduction amounts (lender worksheet inputs, not cached text).
- Loan Factory overlays (supplied TPO source only says follow agency rules and confirm overlays with AE).
- Any Non-QM, Jumbo, DSCR, bank-statement, asset-depletion, foreign-national or ITIN guide.
- Section-level effective-date review for the discovered editions.

## Prohibited Inference

- Do not recite guideline content from memory as if it were the registry.
- Do not infer overlays or Non-QM rules from agency guides.
- Do not turn a file condition into a general rule.
- Never say a loan, income or condition is approved.

## Pitfalls

- Answering the topic without the program.
- Treating "current" on a website as an active revision.
- Letting a fetched PDF's text change what the registry says is active.

## Verification

- A card for a topic outside the activated slice concludes SOURCE_GAP with the pending sections listed; a card inside it cites the section, published/effective dates and revision id.
- `flo_calc formula_id=fannie.base_income.monthly program=freddie` returns UNSUPPORTED (program mismatch); `fha.total.*` with `underwriting_method=manual` likewise.
- A Non-QM card without investor_source_id concludes SOURCE_GAP.
- `flo_knowledge action=advance state=active` is refused for a bot.
