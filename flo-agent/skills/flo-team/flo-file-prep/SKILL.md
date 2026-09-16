---
name: flo-file-prep
description: "Malcolm's file review, checklist and readiness report."
version: 0.1.0
author: Flo Agent team-build pass (Claude Code), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Team, FilePrep, QC, Readiness]
    category: flo-team
    related_skills: [flo-processing-workflow, flo-milestones, flo-income-analysis, flo-calc-workbench, flo-team-handoff]
---

# Flo File Prep Skill (Malcolm)

Initial review, minimum-document checklist, AUS findings presence, consistency checks, income/asset prep, missing items, pre-submission QC and the File Readiness report. The report shape is the pack's FILE_PREP_REPORT; the score is computed by `flo_readiness` from visible counts.

## When to Use

- A handoff from Flo asks for file prep, a readiness check, or a missing-document list.
- A file moves into Intake, Application or Processing.
- Before submission (pre-submission QC).

## Prerequisites

- The Loan Workspace exists (`flo_workspace action=get`).
- A checklist from the handoff or Ashley. No approved minimum-document matrix is loaded: do not invent one (see SOURCE_GAP). Read the template with `read_file` on `.flo/team/pack/templates/FILE_PREP_REPORT.md`.
- Loan folder access: intake/ (read-only originals), aus/, income/, assets/, conditions/, exports/ (your worksheets).

## How to Run

1. Collect facts: milestone, program, AUS findings present or not, documents present (references only).
2. Mark each checklist item complete / missing / expired / conflicting / unknown with its owner.
3. `flo_readiness workspace_id=<id> checklist=[...] aus_status=<present|missing|unknown> discrepancies=[...] open_questions=[...]`.
4. Return the report to Flo with `flo_handoff action=complete` (return_format `file_prep_report`).

## Quick Reference

Status vocabulary: NOT_STARTED, IN_PROGRESS, BLOCKED, READY_FOR_NEXT_STEP. None of these is an approval.

Score components (shown in the report): checklist completion 50, AUS present 15, no discrepancies 15, income prep 10, assets prep 10, minus 4 per open question (max 20).

Best next move: the single missing item or discrepancy that unblocks the file, with its owner.

## Procedure

### 1. Confirm AUS findings exist and what status the source shows

Report the status shown; do not interpret it as an approval. Done when aus_status is one of present/missing/unknown with a reference.

### 2. Reconcile documents against the application

Name mismatches, date gaps, amounts that disagree between documents. Done when each discrepancy names the two references that disagree.

### 3. Prepare income and asset worksheets

Classify documents, extract facts with evidence location, run arithmetic only through `flo_calc`. Write worksheets to exports/. Done when nothing in prose is a computed qualifying amount.

### 4. Escalate rule questions

Anything program-specific, conflicting or overlay-dependent goes back to Flo for Sage. Done when the open_questions list holds them verbatim.

## Sources

| Source | Location | Reviewed |
|---|---|---|
| Malcolm role | `.flo/team/pack/agents/malcolm/ROLE.md` | 2026-09-08 |
| File Prep Report template | `.flo/team/pack/templates/FILE_PREP_REPORT.md` | 2026-09-08 |
| Local folder policy | `.flo/team/pack/shared/LOCAL_FOLDER_POLICY.md` | 2026-09-08 |
| Processing workflow (owner source) | `.flo/source_material/distilled/01_LoanFlow_OS_Processing_Workflow.md` | 2026-09-08 |

Source review date: 2026-09-08.

## SOURCE_GAP

- Approved minimum-document matrix per program.
- Document taxonomy and age/expiration rules.
- Lender-specific prep overlays.
- AUS findings interpretation boundaries beyond "present / status shown".

## Prohibited Inference

- Do not present the readiness score as underwriting approval or as a probability of approval.
- Do not invent a required document from general knowledge; mark SOURCE_GAP and ask.
- Do not rewrite, rename or move original borrower documents.

## Pitfalls

- Marking an item complete because a document with the right name exists, without checking its content reference.
- Averaging or annualizing income in prose.
- Sending a borrower a document request yourself (that is Whisper's draft and Ashley's send).

## Verification

- The report's `is_underwriting_decision` is always false.
- A conflicting item forces BLOCKED and names the item in best_next_move.
- Writing to loans/*/intake/ is refused by policy.
