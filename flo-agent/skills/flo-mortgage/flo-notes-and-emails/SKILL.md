---
name: flo-notes-and-emails
description: "Draft file notes and emails in Ashley's clear voice."
version: 0.1.0
author: Flo Agent bootstrap (Claude Code pass), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Mortgage, Notes, Email, Drafts]
    category: flo-mortgage
    related_skills: [flo-communication, flo-compliance-messaging, flo-milestones]
---

# Flo Notes and Emails Skill

Turns the owner-supplied sample note into a tone seed for file notes, LO updates, lender follow-ups, realtor updates, and portal notes. Drafts only; sending or posting is a confirm-gated action under Flo policy.

## When to Use

- "Write the note for the Mason file."
- "Draft the follow-up to the lender / LO / realtor / title."
- "What do I put in the portal note?"

Borrower-facing reassurance with no specifics belongs to `flo-compliance-messaging`.

## Prerequisites

- `.flo/source_material/distilled/06_Sample_Notes_and_Emails.md` (read with `read_file`).
- File facts from Ashley or the system of record; no facts are invented to fill a draft.

## How to Run

1. Collect the facts: file display name, milestone, what happened, what is needed, from whom, by when.
2. Write in the sample's register: short, factual, milestone-based.
3. Return a DRAFT with any missing fact shown as a bracketed placeholder.

## Quick Reference

Supplied example (Sample Notes and Emails, 2026-09-08):

> File is moving through processing, appraisal ordered.

What the sample teaches: one line, present tense, milestone named, one concrete event, no filler. Use it as a tone seed only; it is not a template library.

Draft shapes (derived from the sample and Ashley's communication contract, not from a supplied template):

| Type | Shape |
|---|---|
| File note | Milestone; what happened; what is outstanding; next step and owner |
| LO update | Status in one line; the only blocker; what is needed from whom; when |
| Lender / AE follow-up | File reference; the specific item; one clear ask; neutral tone |
| Realtor update | Milestone-level status; next expected event; no borrower financials |
| Portal note | Factual, dated, milestone-based; no opinions |

## Procedure

### 1. Gather the facts

List each fact with its source (Ashley, email, document, system of record). Done when nothing in the draft lacks a source or a placeholder.

### 2. Draft in the sample register

Short sentences. Name the milestone. One ask per message. Done when the draft would fit the supplied example's tone.

### 3. Check what must not be there

No SSNs, full account numbers, rates, approval language, or speculation about timelines. Done when the draft passes the `flo-compliance-messaging` "not allowed" list where a borrower could see it.

### 4. Return as DRAFT

Label it, name the recipient and channel, and state that sending needs confirmation. Done when Ashley can approve or edit in one step.

## Sources

| Source | Location | Reviewed |
|---|---|---|
| Sample Notes and Emails (owner-supplied PDF) | `.flo/source_material/originals/06_Sample_Notes_and_Emails.pdf` | 2026-09-08 |
| Distilled copy | `.flo/source_material/distilled/06_Sample_Notes_and_Emails.md` | 2026-09-08 |
| Ashley AI Agent Communication Guide | `.flo/source_material/originals/ASHLEY AI AGENT COMMUNICATION GUIDE.md` | 2026-09-08 |

Source review date: 2026-09-08.

## SOURCE_GAP

- Real examples of Ashley's own notes and emails per recipient type.
- Signature blocks, greetings, and channel conventions.
- Portal-specific note formats or required fields.
- Any note taxonomy the LOS expects.

## Prohibited Inference

- Do not invent file facts, dates, or names to make a draft complete; use placeholders.
- Do not include borrower financial detail in realtor or third-party drafts.
- Do not add guideline or compliance statements.

## Pitfalls

- Long, apologetic, or corporate drafts.
- Multiple asks in one lender email.
- Presenting a draft as already sent.

## Verification

- Every fact in the draft has a source or is a visible placeholder.
- The draft is one clear ask in the sample's register.
- The draft is labelled DRAFT and requires confirmation to send.
