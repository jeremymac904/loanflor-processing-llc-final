---
name: flo-compliance-messaging
description: "Use only the supplied compliance-safe borrower template."
version: 0.1.0
author: Flo Agent bootstrap (Claude Code pass), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Mortgage, Compliance, Templates, Borrower]
    category: flo-mortgage
    related_skills: [flo-communication, flo-notes-and-emails, flo-milestones]
---

# Flo Compliance Messaging Skill

Holds the single compliance-safe borrower template the owner supplied and the rule that Flo may not extend it. This is a product requirement, not legal advice: Flo is not a compliance officer and never claims a message is compliant beyond "this is the approved template".

## When to Use

- A borrower-facing status message where nothing specific needs to be said.
- Ashley asks for "the safe update" or "the compliant version".
- Any outbound borrower draft that would otherwise state rates, approvals, timelines, or guarantees.

## Prerequisites

- `.flo/source_material/distilled/07_Compliance_Safe_Templates.md` (read with `read_file`).
- Outbound sending is a confirm-gated action under Flo policy; this skill only produces the draft.

## How to Run

1. Start from the approved template verbatim.
2. Add only the milestone name (from `flo-milestones`) and the file/borrower display name if Ashley wants it personalised.
3. Do not add rates, dates, promises, approval language, or explanations.
4. Hand the draft back for Ashley's confirmation before anything is sent.

## Quick Reference

Approved template (Compliance Safe Templates, supplied 2026-09-08):

> Your loan is progressing. We will update you at next milestone.

This is one supplied template, not a template library.

Allowed light edits: greeting with the borrower's first name; the milestone name; Ashley's sign-off (SOURCE_GAP: not yet supplied).

Not allowed: interest rates, closing dates, approval or denial language, "guaranteed", "no problem", timelines, reasons for delay, or any regulatory citation.

## Procedure

### 1. Confirm the message needs no specifics

If Ashley needs to convey a specific request (a document, a signature), use `flo-notes-and-emails` and `flo-communication` instead. Done when the intent is "reassure, no new information".

### 2. Produce the draft

Template first, minimal personalisation second. Done when the body still contains the approved sentences unchanged.

### 3. Mark it as a draft

Label it DRAFT and state that sending needs Ashley's confirmation. Done when the draft cannot be mistaken for a sent message.

## Sources

| Source | Location | Reviewed |
|---|---|---|
| Compliance Safe Templates (owner-supplied PDF) | `.flo/source_material/originals/07_Compliance_Safe_Templates.pdf` | 2026-09-08 |
| Distilled copy | `.flo/source_material/distilled/07_Compliance_Safe_Templates.md` | 2026-09-08 |

Source review date: 2026-09-08.

## SOURCE_GAP

- Any second template (document request, appraisal update, closing scheduled, delay notice).
- Required disclosures, disclaimers, or regulatory language for borrower communication.
- Which channels the template may be used on (email, text, portal).
- Ashley's or the company's approved signature block.

## Prohibited Inference

- Do not draft new "compliant" templates from general knowledge of mortgage communication rules.
- Do not assert that any message is compliant with a named regulation.
- Do not add approval, rate, or timeline language to reassure a borrower.

## Pitfalls

- "Improving" the template with helpful detail.
- Treating a lender's or LO's wording as an approved Flo template.

## Verification

- The draft contains the approved sentences unchanged.
- The draft is labelled DRAFT and gated behind confirmation.
- No rate, date, approval, or regulatory language appears.
