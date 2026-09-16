---
name: flo-processing-workflow
description: "Track a loan file through the six LoanFlow milestones."
version: 0.1.0
author: Flo Agent bootstrap (Claude Code pass), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Mortgage, Processing, Workflow, Milestones]
    category: flo-mortgage
    related_skills: [flo-milestones, flo-communication, flo-notes-and-emails]
---

# Flo Processing Workflow Skill

Gives Flo the approved, source-backed picture of how a loan file moves from intake to closing so it can report where a file is and what the next milestone is. It does not define entry or exit criteria, owners, SLAs, or document checklists; those are not in the supplied source and are marked SOURCE_GAP below.

## When to Use

- "Where is the Johnson file?" / "What stage is this loan in?"
- Building a File Progress update (current milestone, what is complete, what is waiting, next move).
- Morning brief or end-of-day recap that groups files by milestone.

Do not use it to decide whether a file *qualifies* to advance; that is a lender/underwriter decision.

## Prerequisites

- Approved source material under `.flo/source_material/` (read with `read_file` when provenance must be shown).
- Loan status facts come from Ashley or the system of record (LOS, lender portal, approved email). Flo does not infer status from silence.

## How to Run

1. Identify the file by its display name (never by SSN or account number).
2. Place it on the milestone ladder in Quick Reference using facts Ashley or the system of record supplied.
3. Report in Ashley's shape: Priority, Status, Action, Urgency, Suggested next step.

## Quick Reference

Source-backed content (LoanFlow OS Processing Workflow, supplied 2026-09-08):

- Overview: "Structured workflow from intake to closing with clarity and consistency."
- Milestones, in order:
  1. Intake
  2. Application
  3. Processing
  4. Conditional Approval
  5. Clear to Close
  6. Closed

Supplied milestone definitions (see `flo-milestones`): Processing = docs collected; CTC (Clear to Close) = ready to close.

## Procedure

### 1. Confirm the current milestone

State the milestone using the exact names above. If Ashley's wording differs (for example "in underwriting"), map it only if she confirms which of the six it corresponds to. Done when the milestone name is one of the six.

### 2. Name what moves the file forward

Describe the *next* milestone by name. Because the source gives no entry criteria, the required action must come from a lender condition, Ashley, or the system of record, not from Flo's assumptions. Done when the next action has a stated source.

### 3. Surface blockers and waiting-on parties

List only blockers that are documented (a condition, an email, a note). Done when each blocker names its evidence.

### 4. Write the update

Keep it to what matters, current status, required action, urgency, and the cleanest next move. Done when the update fits Ashley's communication contract (`flo-communication`).

## Sources

| Source | Location | Reviewed |
|---|---|---|
| LoanFlow OS Processing Workflow (owner-supplied PDF) | `.flo/source_material/originals/01_LoanFlow_OS_Processing_Workflow.pdf` | 2026-09-08 |
| Distilled copy | `.flo/source_material/distilled/01_LoanFlow_OS_Processing_Workflow.md` | 2026-09-08 |
| Milestone Definitions | `.flo/source_material/originals/04_Milestone_Definitions.pdf` | 2026-09-08 |

Source review date: 2026-09-08. Re-review when new workflow material is approved.

## SOURCE_GAP

The supplied source does not provide:

- entry/exit criteria for any milestone;
- owners or responsible roles per milestone;
- SLAs, turn times, or deadlines;
- document requirements or checklists per milestone;
- exception handling, fallout, or re-work paths;
- sub-statuses (for example "submitted", "suspended", "resubmitted").

Until supplied, Flo says the source does not specify these and asks Ashley or points to the system of record.

## Prohibited Inference

- Do not invent milestone criteria, checklists, or turn times from general mortgage knowledge.
- Do not restate a milestone with a different name (for example "Underwriting" is not one of the six).
- Do not mark a file as advanced because time has passed or because an email implies it.

## Pitfalls

- Treating retrieved email or portal text as a status change without Ashley's confirmation or a system-of-record fact.
- Presenting more than three priorities as equal.

## Verification

- The six milestone names and their order match the supplied source exactly.
- Every status statement cites Ashley, a document, or the system of record.
- Any missing rule is reported as SOURCE_GAP, never filled in.
