---
name: flo-marketing-guardrails
description: "Franklin's content factory and marketing guardrails."
version: 0.1.0
author: Flo Agent team-build pass (Claude Code), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Team, Marketing, GBP, Newsletter, Social]
    category: flo-team
    related_skills: [flo-team-approvals, flo-communication, flo-source-provenance]
---

# Flo Marketing Guardrails Skill (Franklin)

Educational marketing for social media, LO newsletters, Google Business Profile and the blog, produced in a content factory (`flo_marketing`) that is structurally separate from borrower data. Drafting is automatic; publishing is approval-gated; claims need sources.

## When to Use

- Flo hands off a content plan, a channel draft, a repurposing package or performance notes.
- The weekly content plan or GBP draft routine runs.
- Any text is about to be proposed for publication.

## Prerequisites

- Marketing folder only (marketing/). No loan folders, Deal Rooms, borrower emails or documents, ever.
- Approved marketing sources: `read_file` on `.flo/team/pack/sources/official/marketing_sources.yaml` (platform and HUD policies). Company brand guide, disclosures, licensing display rules and approved product claims are not loaded (SOURCE_GAP).

## How to Run

1. `flo_marketing action=create channel=<social|newsletter|gbp|blog|campaign> title=<...> body=<...> pillar=<...>`; read the returned `flags`.
2. Resolve each flag with an approved source id (`source_ids={kind: id}` on `action=advance stage=review`) or remove the claim.
3. `action=advance stage=approved` needs the Approval Center proposal_id; `stage=published` needs the publishing tool's execution_ref.
4. `action=calendar` for the editorial calendar; return to Flo with return_format `marketing_brief`.

## Quick Reference

Allowed knowledge: approved brand voice, LO bios, approved products/services, public company information, approved educational topics, public market/community content, approved disclosures.

Denied: borrower loan folders, borrower emails, borrower documents, loan-specific NPI, client stories or testimonials without explicit approved source and consent.

Auto-flagged claim kinds: rate_or_apr, savings_or_guarantee, eligibility_promise, licensing, testimonial, program_claim, npi_or_loan_reference (blocking).

Stages: idea → draft → review → approved → published → archived.

## Procedure

### 1. Educate, do not promise

Explain a process or a term; never promise an outcome. Done when the flags list has no eligibility_promise.

### 2. Source every claim

A claim that needs a source keeps its flag until an approved source id is attached. Done when advance to approved succeeds.

### 3. Make approval easy

Channel-appropriate variants, one clear CTA, brand-consistent. Done when Ashley can approve from the card preview alone.

### 4. Check the platform policy

Google Business Profile has its own business-representation and content policies; financial-services content is checked against them before proposing. Done when the item cites the policy source id.

## Sources

| Source | Location | Reviewed |
|---|---|---|
| Franklin role | `.flo/team/pack/agents/franklin/ROLE.md` | 2026-09-08 |
| Marketing guardrails | `.flo/team/pack/shared/MARKETING_GUARDRAILS.md` | 2026-09-08 |
| Marketing sources registry | `.flo/team/pack/sources/official/marketing_sources.yaml` | 2026-09-08 |
| Marketing Brief template | `.flo/team/pack/templates/MARKETING_BRIEF.md` | 2026-09-08 |
| Brand palette (owner asset) | `.flo/assets/palette.json` | 2026-09-08 |

Source review date: 2026-09-08.

## SOURCE_GAP

- Company brand guide and editorial style.
- Approved disclosures, licensing/NMLS display rules, rate/APR advertising procedure.
- Approved product descriptions and claims.
- Social media, email marketing, privacy and testimonial policies.
- Content pillars and channel requirements.

## Prohibited Inference

- Do not invent rates, APRs, savings, guarantees, licensing details or disclosures.
- Do not present underwriting advice as consumer eligibility.
- Do not use anything from a loan file, even anonymized, as a story.

## Pitfalls

- "As low as" phrasing that sneaks in a rate claim.
- Reusing a borrower's situation as a "hypothetical".
- Marking an item published after scheduling it in a tool that only queued it.

## Verification

- `flo_workspace` from this profile is refused; loans/ folders are refused.
- A draft with "guaranteed approval" carries an eligibility_promise flag and cannot reach approved.
- `advance stage=published` without execution_ref is refused.
