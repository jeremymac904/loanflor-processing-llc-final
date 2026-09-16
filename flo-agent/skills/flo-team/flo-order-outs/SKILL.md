---
name: flo-order-outs
description: "Chadwick's order proposals, tracking and follow-ups."
version: 0.1.0
author: Flo Agent team-build pass (Claude Code), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Flo, Team, Orders, Title, HOI, VOE]
    category: flo-team
    related_skills: [flo-team-approvals, flo-team-handoff, flo-notes-and-emails]
---

# Flo Order Outs Skill (Chadwick)

Title, HOI, WVOE/VOE, LOE request workflow and configurable order types: propose, get approval, place through an approved tool, track to reconciliation, escalate overdue. The proposal shape is the pack's ORDER_PROPOSAL; the state machine lives in `flo_order`.

## When to Use

- Flo hands off an order need, or a workspace shows a missing title/HOI/VOE item.
- A routine sweep finds an order pending past its expected time.
- A vendor result arrives and must be reconciled to the file.

## Prerequisites

- The Loan Workspace exists; you have title/, insurance/, correspondence/, exports/ access.
- Vendor and contact references from the workspace or Ashley (no approved vendor directory is loaded: SOURCE_GAP). Template: `read_file` on `.flo/team/pack/templates/ORDER_PROPOSAL.md`.

## How to Run

1. `flo_order action=propose workspace_id=<id> order_type=<title|hoi|wvoe|voe|loe_request|custom> inputs={...} purpose=<why> urgency=<...>`.
2. Review `missing_inputs`; collect them before asking for approval.
3. Placing the order (email, portal, Zapier action) stops at Ashley's approval prompt. After the tool confirms, `flo_order action=transition state=ordered execution_ref=<tool ref>`.
4. Track: pending → received → reconciled. Late items: `state=overdue` plus a follow-up draft for approval.

## Quick Reference

States: requested, approved, ordered, vendor_confirmed, pending, received, reconciled, overdue, cancelled.

Rules the tool enforces: approved needs an approval_id; ordered and vendor_confirmed need an execution_ref; a bot cannot declare an order placed.

Structural inputs: title needs property_ref, borrower_ref, vendor; HOI needs property_ref, borrower_ref, agent_or_carrier_ref; WVOE/VOE need employer_ref, borrower_ref, authorization_ref; LOE request needs borrower_ref, topic, draft_ref.

## Procedure

### 1. Turn the need into a proposal

One order per proposal, purpose in one line, inputs as references. Done when missing_inputs is empty or each missing input has an owner.

### 2. Get the approval, then execute through the tool

Never place an order by describing it; the tool result is the only proof. Done when execution_ref is recorded.

### 3. Follow up proportionately

Flag operational risk in one line; propose the cleanest follow-up as a draft. Done when the follow-up is queued, not sent.

### 4. Reconcile the result to the file

Attach the result reference to the workspace, move the order to reconciled, tell Flo. Done when the tracker shows it and Flo has the summary.

## Sources

| Source | Location | Reviewed |
|---|---|---|
| Chadwick role | `.flo/team/pack/agents/chadwick/ROLE.md` | 2026-09-08 |
| Order Proposal template | `.flo/team/pack/templates/ORDER_PROPOSAL.md` | 2026-09-08 |
| Delegation matrix (order rows) | `.flo/team/pack/team/DELEGATION_MATRIX.md` | 2026-09-08 |
| Communication standard | `.flo/team/pack/shared/COMMUNICATION_STANDARD.md` | 2026-09-08 |

Source review date: 2026-09-08.

## SOURCE_GAP

- Approved vendor directory and contacts.
- Order and status SLAs per vendor/order type.
- Vendor-specific input requirements.
- Approved LOE request template and company vendor rules.

## Prohibited Inference

- Do not guess a vendor, contact or portal.
- Do not infer what a vendor requires; ask or mark SOURCE_GAP.
- Do not decide underwriting sufficiency of a returned document.

## Pitfalls

- Marking an order "ordered" after drafting the request email.
- Chasing a vendor daily; keep follow-ups proportionate to the SLA (unknown today).
- Placing a duplicate order after an approval expired; re-propose instead.

## Verification

- `transition state=ordered` without execution_ref is refused.
- `transition state=approved` without approval_id is refused.
- Every external send or order action shows an approval prompt first.
