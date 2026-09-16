# Flo Golden Loan Path (2026-09-08)

The first production vertical slice: **Fannie Mae Conventional + W-2 base income (salary/hourly) + depository assets + DU findings + minimum documentation + File Prep/QC + guideline validation + borrower communication + submission-readiness report**, run by Flo, Malcolm, Sage and Whisper against one shared Loan Workspace, with every rule traced to an activated official source section.

## The flow (deterministic backbone: `plugins/flo-team/golden_path.py`; test: `tests/flo/test_golden_loan.py`)

1. **Ashley → Flo**: "Prep this file for submission and tell me what's missing."
2. **Flo** opens/uses the Deal Room (`flo_workspace`), attaches the document references, and hands Malcolm a File Prep packet (`flo_handoff` → `message_agent`).
3. **Malcolm** receives the packet and reviews the synthetic documents:
   - DU findings (`flo_du`): "DU findings show Approve/Eligible." recorded as shown; verification messages compared with the file; DTI tolerance (B3-2-10); a findings-vs-guide gap (no verbal VOE message) routed to Sage.
   - Income (deterministic `flo_calc`): biweekly base → 5,500.00 monthly (B3-3.3-01 table), YTD consistency, prior-year W-2 comparison → NEEDS_REVIEW with a guideline question.
   - Assets (`flo_assets`): July statement missing page 5 of 5, an unsourced 4,000 deposit above the 50% threshold, eligible funds vs funds needed, reserves in months of PITIA.
   - File Prep matrix (`flo_fileprep`): every item with provenance (`fannie:<section>`, `du:<message>`, `workflow`, `ashley`) and state complete / missing / needs_review / not_applicable / source_gap.
   - File Readiness report (`flo_readiness`) — a checklist score, never an approval.
4. **Flo → Sage**: each guideline question becomes a handoff; **Sage** answers with section-level Guideline Cards from the ACTIVE Fannie slice (`flo_guideline_card program=fannie`): program, topic, source, section, section date/version, retrieval timestamp, checksum, rule text, overlay status (not loaded — confirm with AE), DU findings reference, best next move.
5. **Flo → Whisper**: missing-document request draft for the borrower (`flo_draft`); the draft stays a draft; sending would stop at the Approval Center.
6. **Flo → Ashley**: Priority · Status · Readiness · AUS · Income · Assets · Missing items · Risks · Best next move · Draft communication · Source links (all `https://selling-guide.fanniemae.com/sel/…`).

## The golden synthetic loan (`tests/flo/fixtures/golden_loan/golden_loan.json`)

Entirely invented: borrower "Harper, Jordan (synthetic)", employer "Northwind Logistics LLC (synthetic)", bank "Cascade Community Bank (synthetic)", DU casefile `SYN-DU-000001`. Two biweekly paystubs with YTD, 2025 and 2024 W-2s, June and July 2026 statements, DU findings (Approve/Eligible, three verification messages), a 1003 summary. Intentional issues: July statement missing page 5 of 5; paystub-implied annual (66,000) vs 2025 W-2 (58,900) discrepancy; no verbal VOE / Form 1005; one unsourced 4,000 deposit above the large-deposit threshold.

## What the deterministic run produces

Readiness IN_PROGRESS with a transparent score; missing items include the verbal VOE and the statement page; risks include the W-2 discrepancy and the large deposit; one Sage card citing B3-3.3-01 (fixed base income, pay raises) with usable citations; a borrower draft listing the missing items; source links to the cited sections; `underwriting_decision: false` everywhere; Franklin excluded from the Deal Room.

## Real vs scaffold

Real and tested: source fetch/checksum/lifecycle/activation; 34 rule records with verified anchors; seven production formulas; asset workbench (depository); DU review; File Prep matrix with provenance; readiness; Sage section-level cards; Whisper draft; Flo synthesis; approval gating on sends; tampering demotes sources to STALE_SOURCE.

Partial / not yet: the model-driven run (see `LIVE_AGENT_HANDOFF_RESULTS.md`); internal LoanFlow document requirements (the supplied workflow source defines milestones only → `source_gap` rows); property/appraisal; lender overlays; per-rule policy effective dates (section dates recorded; announcement-level effective dates not resolved).

## Reusable across programs

Program-agnostic: fetch/cache/checksum/lifecycle, regression anchors, Guideline Card renderer, calc engine + gating, asset workbench structure, DU review structure (AUS-agnostic fields), File Prep matrix builder, readiness, handoff/workspace/draft/approval machinery, provider discovery, log redaction. Program-specific: section lists and slugs, rule records, formula bindings, the DU-specific tolerance rule, and the asset statement-period numbers.
