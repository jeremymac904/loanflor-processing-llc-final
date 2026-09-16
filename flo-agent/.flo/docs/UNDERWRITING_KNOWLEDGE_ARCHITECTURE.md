# Underwriting Knowledge Architecture

Status: accepted product architecture, 2026-09-08; implementation staged. A first-class Flo product capability, implemented at Hermes extension boundaries. No production rules, guide ingestion, calculator, or approval enforcement is claimed by this bootstrap.

## Product contract

Flo is Ashley's processing assistant, not the lender or underwriter. Results use “Guideline-supported calculation”, “Based on the documents currently available”, and “Potential issue to confirm with UW”. Never say “I approved this income” or “This loan is approved”. A complete calculation is not a loan approval.

Knowledge must be program-aware, source-backed, versioned, effective-date aware, citation-capable, updateable, lender-overlay aware and calculation-traceable. Rules live in structured reviewed records, not SOUL.md, CLAUDE.md, prompts or model memory. Skills guide usage and presentation; they do not become a competing rule store.

## Fit with pinned Hermes

Pinned upstream: v2026.8.31 / 29112bef099274229cadff79cdff7bf7b99c4b77. Preserve core and upstream mergeability. Backend extension surface: `hermes_cli/plugins.py:PluginContext.register_tool`; profile-aware storage: `hermes_constants.py:get_hermes_home()`. Desktop already uses `tui_gateway` and `apps/shared` transport. The backend owns resolution, calculations, permissions and persisted results; the renderer owns worksheet presentation. No calculator implementation in React or scattered CLI shell calls.

A future Flo-owned backend plugin hosts a registry repository, deterministic resolver, document-requirement evaluator and versioned calculator dispatch. Register narrow read/propose operations through existing Hermes tool conventions. An administrator-only activation operation consumes a separately approved proposal. Do not add core model tools, duplicate an orchestrator, or enable production Google credentials during bootstrap. Runtime stores are profile-scoped, but profile identity alone is not authorization.

Flow: loan context + reviewed document facts → deterministic source applicability → separated applicable rule layers → document checks → approved calculator → immutable trace → concise result + source panel. Retrieval may nominate candidates; similarity ranking never selects the controlling rule.

## Five independent knowledge packs

Scaffolds are `.flo/underwriting/agency/{fannie,freddie,fha,va,usda}/pack.json`. Each declares required topics, source IDs and empty rule/calculator lists. `active=false` and `SOURCE_GAP` are deliberate.

All packs cover borrower eligibility; employment and income; self-employment; rental income; assets and reserves; liabilities/DTI; credit and derogatory credit; property/appraisal; occupancy and transaction type; LTV/CLTV; gifts and interested party contributions; documentation and verification/reverification. These are requested coverage domains, not assertions that every guide uses identical concepts.

| Pack | Authority / required distinction |
| --- | --- |
| Fannie | Selling Guide; Fannie/DU and applicable manual guidance. Never route to Freddie rules. |
| Freddie | Single-Family Seller/Servicer Guide; Freddie/LPA and applicable manual guidance. No generic conventional formula. |
| FHA | Handbook 4000.1 + applicable Mortgagee Letters, FHA INFO and supplements; TOTAL vs manual, compensating factors, source of funds and FHA-specific requirements. |
| VA | Pamphlet 26-7 + applicable Loan Guaranty guidance/Circulars; military income, residual income, debts, DTI, compensating factors, entitlement processing and MPR. Residual income stays a separate VA calculation. |
| USDA Guaranteed | HB-1-3555 + applicable Procedure Notices; GUS vs manual, household eligibility, stable/dependable income and eligible property. Annual household income, adjusted annual income and repayment income are distinct typed outputs. Do not substitute Direct program HB-1-3550. |

Jumbo, Non-QM, DSCR, Bank Statement, Asset Depletion, Investor Cash Flow, Foreign National, ITIN and alternative-documentation products require exact investor/lender product guides. Structure: `lenders/<lender>/overlays/`, `lenders/<lender>/programs/`, `investor/<investor>/<program>/`. No universal specialty formulas or matrices. Loan Factory currently has no loaded overlay; supplied TPO material only directs agency compliance and AE confirmation.

## Source registry and evidence model

Seed registry: `.flo/underwriting/source_registry.json`. A source family has a stable `source_id`; every retrieved document/section revision gets immutable `revision_id`. Never overwrite bytes or reuse an ID for changed text. Index pages are discovery sources, not evidence for a calculation.

Required revision fields: source type, issuer/agency/program, lender/investor/product scope, document title, section/page/anchor, official URL and resolved URL, publication date, effective interval, applicability trigger/predicate, version, retrieved timestamp, SHA-256 of exact original bytes, parser version and extraction checksum, cache reference, supersedes/superseded_by relations, review/rights status, approver/time, active deployment membership and notes. Store null + a reason for unknown facts; never manufacture a date or checksum.

Research `checked_at` differs from source `retrieved_at`: this bootstrap checked official pages but did not ingest original guides. Checksums therefore remain null. Source-ID lists in the pack manifests are discovery dependencies, not approved citation sets.

A normalized RuleRevision references exact source revisions and locators, program/agency/method, topic, applicability predicates, required inputs/documents, supported formulas or calculator ID, exclusions, conflict relationships and human review. Lender rules carry lender/product scope; loan conditions carry `loan_id` and never qualify for global publication. Store permitted concise normalized representations only after rights review; extraction by an LLM does not confer authority.

## Temporal state and deterministic resolution

Keep two independent axes: knowledge lifecycle (`DISCOVERED`, `PENDING_REVIEW`, `APPROVED`, `REJECTED`) and query-relative temporal status (`CURRENT`, `FUTURE`, `SUPERSEDED`, `ARCHIVED`, `UNKNOWN`). `active` means membership in an approved deployed ruleset, not merely the newest publication. An old revision may remain needed for historical loans. Archive retains immutable evidence and supersession links; it is not deletion.

Store effective bounds and the exact date basis: application, note, case assignment, AUS submission, or source-defined trigger. A source may have multiple section-level schedules, transition choices and exceptions. Record those as reviewed predicates; do not infer “effective on publication” or a uniform guide-wide date. Represent date-only values separately from UTC audit timestamps.

Resolution algorithm:

1. Require explicit program, agency/GSE, underwriting method/AUS, product, lender/investor identifiers where relevant, occupancy/transaction facts and applicable loan dates. Missing discriminators return NEEDS_INPUT, never a guessed agency.
2. Load an immutable approved ruleset snapshot and filter exact program/agency/method/product scope. Validate rights, freshness and source integrity. Draft, unknown-effective, unreviewed, missing-byte or corrupted revisions cannot support production conclusions.
3. Evaluate each rule's own effective predicate against its named loan date. Missing trigger yields NEEDS_INPUT. New future text does not displace currently applicable text. Historical resolution pins both loan date and knowledge/ruleset version so prior worksheets are reproducible.
4. Apply documented supersession relationships within the same scope. Do not use “latest timestamp wins”. Cyclic supersession, overlapping inconsistent revisions or incomplete update reconciliation return CONFLICT/STALE_SOURCE.
5. Produce separate agency baseline, lender overlay, investor/product layer and loan-specific conditions. A stricter overlay is applied only when its approved authority and scope support it; “take the strictest” is not a universal algorithm. An apparent relaxation or contradictory requirement requires explicit source-supported exception authority or review.
6. If differences remain after checking agency, program, AUS/manual method, dates, overlays and file conditions, return “Guideline conflict — needs AE/UW confirmation.” Preserve both citations and the unresolved dimension. No qualifying total from an unresolved controlling conflict.

Overlay state is explicit: NOT_LOADED, LOADED, NOT_APPLICABLE_WITH_EVIDENCE, or CONFLICT. “None loaded” never means “no overlays exist”. Baseline-only answers are labeled incomplete when lender/product scope remains unknown. A file condition adds a file-specific checklist entry, not a global guideline.

## Income Calculation Engine

The model may classify income/documents, explain context, propose extracted facts and identify conflicts. Ashley confirms ambiguous classification; extracted facts carry evidence location and validation status. Deterministic code performs arithmetic only after supported rule resolution. No runtime eval of model-generated formulas or source text.

Request contract: calculation ID; loan reference; program/agency/method; income type and income stream ID; borrower/employer/business references; verified documentation facts; relevant dates/history; applicable ruleset and overlay references; units/currency. Response is typed SUCCESS, NEEDS_INPUT, MISSING_DOCS, SOURCE_GAP, STALE_SOURCE, CONFLICT or UNSUPPORTED. Failure returns no invented monthly qualifying amount; null is not zero.

Use Decimal/fixed precision, explicit units and periods, source-backed rounding points, explicit signs and no double counting across streams. Missing months are not zero-income months. Period overlap, YTD cutoffs, declining trends, currency conversion, inconsistent documents and negative values must be handled by approved rules; generic arithmetic helpers cannot decide eligibility. Do not average, annualize, add back depreciation or ignore rental losses without a reviewed rule. Pin calculator version/hash and approved parameters separately from the guide version.

Trace contains evidence references and confirmed values; dates/history used; rule revision + section; formula ID/version; ordered arithmetic operations and intermediate values; rounding; trend method/result; monthly qualifying amount when supported; missing documents; source-backed warnings; overlay contribution and result status. This is an auditable arithmetic record, not chain-of-thought. Store immutable input snapshots or content hashes with scoped evidence references so later changes do not rewrite a saved worksheet.

### Coverage backlog (all source-gated)

Employment: salary, fixed/variable hourly, overtime, bonus, commission, tips, shift differential, secondary, seasonal, temporary and union employment.

Self-employment: sole proprietor/Schedule C, partnership, S corporation, corporation, LLC tax treatment, K-1, business/personal returns, YTD P&L, balance sheet, liquidity, declining income, business-use-of-home, depreciation/depletion/amortization and recurring/nonrecurring adjustments. LLC label alone cannot determine tax treatment. Every adjustment requires approved authority.

Rental: subject/non-subject, departing residence, investment property, multi-unit primary, leases, appraisal rent schedules, Schedule E, PITIA, losses, newly acquired rentals and short-term rental treatment where supported.

Other: Social Security, pension, retirement, annuity, disability, alimony, child support, separate maintenance, trust, note receivable, interest/dividend, capital gains, stock/RSU/restricted stock, foster care, unemployment, public assistance, military pay/allowances, VA benefits, boarder, royalty, foreign and miscellaneous recurring income. A category's presence does not mean it is acceptable for every program.

Tax-document vocabulary: 1040, Schedules 1/B/C/D/E/F, 1065, 1120, 1120-S, K-1, W-2, 1099s, P&L and balance sheet. Recognizing a form does not license an add-back or supply a missing formula.

## Document requirements and Income Analysis UI

DocumentRequirement records reference applicable RuleRevision, reason, program/method, acceptable evidence alternatives and any source-supported age/reverification trigger. Evaluate available evidence into satisfied/missing/expired/conflicting/unknown; only claim something is required with a citation. Emit proposed Conditions/File Progress entries with rule and loan provenance. Deduplicate by requirement identity; do not silently mark an underwriter condition satisfied or write to an external system.

Workspace flow: select/upload authorized documents → identify borrower/employer/business/streams → confirm ambiguous classifications → resolve rules → run deterministic calculator → show Income Stream, Documentation, Calculation, Monthly Qualifying Income, Trend, Missing Items, Guideline Source and Warnings. Save/export a versioned processing worksheet on user action. External upload/send/share remains behind Flo policy and exact human approval.

Default result is concise, with “Source”/“View guideline” for title, program, section, publication/effective date and trigger, immutable revision, official link, overlay status and calculation trace. Confidence is evidence status, not a model probability. A citation must point to the version used, not silently to a changed live page. If rights prevent cached source display, retain permitted metadata and official link with version/date and disclose when historical text cannot be displayed.

## Controlled updates and rights

Manual/admin workflow: inspect allowed official channel → detect metadata/byte change → stage a new immutable revision in a rights-approved private cache → verify extraction/section anchors and effective predicates → compare impact to current ruleset → PENDING_REVIEW → regression tests against proposed rules → explicit admin approval bound to revision/checksums/test receipt → atomic activate ruleset → retain previous snapshot/archive and rollback route. Retrieval itself never activates rules. Re-check hashes and approval expiry at activation to prevent review/apply races.

Future monitoring only creates review candidates. It must respect source terms and never scrape/activate unattended. No recurring automation is created now. Define freshness SLA per source with admin; until verified, report UNKNOWN/STALE_SOURCE instead of “current”. Publication after the research date requires a new review. Rollback is also an audited permissioned change. Existing saved calculations stay pinned and are marked “new guidance available” rather than silently recalculated.

Raw guide bytes, OCR, embeddings and borrower evidence stay outside Git in authorized profile/tenant-scoped storage with encryption, access control and retention limits. Public source cache and borrower evidence store are separate. Do not send borrower data to coding-agent sessions. Retrieved text and extracted formulas are untrusted; no plugin, shell, credential access or approval may be granted by them.

Copyright decision for this bootstrap: metadata/official links only, no third-party guide PDFs or extracted guide corpus committed. [Fannie copyright terms](https://selling-guide.fanniemae.com/copyright-and-preface) contain limited professional-use permissions; do not interpret those as unrestricted application redistribution. [Freddie terms](https://www.freddiemac.com/terms) restrict automated collection/caching and redistribution; obtain an authorized ingestion route before indexing. Private storage alone does not establish permission. Government materials also require artifact-level review for embedded third-party content, marks and usage notices; no blanket redistribution determination is made. Normalized rules require a rights decision too.

## Official source research — checked 2026-09-08

| Program | Observed official source | Verified scope / remaining gap |
| --- | --- | --- |
| Fannie | [Selling Guide](https://selling-guide.fanniemae.com/) shows published September 2, 2026; [SEL-2026-08](https://singlefamily.fanniemae.com/news-events/announcement-sel-2026-08-selling-guide-updates) opened | Edition marker confirmed; individual effective dates, rules and licensed ingestion pending. |
| Freddie | [Single-Family Guide](https://guide.freddiemac.com/) | Returned no readable guide body; latest edition and Bulletin completeness UNKNOWN. Manual/authorized access needed, not an older search PDF substitute. |
| FHA | [HUD official index](https://www.hud.gov/hudclips/handbooks/housing) lists August 12, 2026 Handbook update | Publication verified; linked PDF fetch failed. Section applicability not verified. [Mortgagee Letters](https://www.hud.gov/hudclips/letters/mortgagee), [FHA INFO](https://www.hud.gov/hud-partners/single-family-fha-info) and [supplements](https://www.hud.gov/hud-partners/single-family-handbook-references) registered separately. |
| VA | [Pamphlet route](https://www.benefits.va.gov/warms/pam26_7.asp) redirects to KnowVA; [Circulars](https://www.benefits.va.gov/homeloans/resources_circulars.asp) readable | Current chapter revisions UNKNOWN due to welcome-shell redirect. Circular index includes 2026 entries; individual scope/effectiveness and rescission review pending. |
| USDA | [HB-1-3555 official portal](https://www.usda.gov/guidance-documents/rhs-handbook/rhs/hb-1-3555-sfh-guaranteed-loan-program-technical-handbook) shows issued May 5, 2025; [Procedure Notices](https://www.rd.usda.gov/resources/directives/procedures-notices) lists later changes | Portal issue date does not prove current consolidated edition. PN 657 references HB-1-3555; PN 659 references 3555 forms. Reconcile applicable revisions before activation. |

This is a current-source discovery registry, not a certification that all five current rule libraries have been ingested. All production-active counts remain zero. No secondary mortgage blog, training site, Reddit or SEO summary is authority.

## Delivery phases and acceptance

Now: canonical architecture, five manifests, registry, source/rights gaps and synthetic acceptance scenarios. Preserve bootstrap/rebrand ordering.

After baseline: implement source schema/storage and deterministic resolver with synthetic rules; prove program/method/date isolation and conflict refusal. Then approve narrow real source slices and calculator modules with documentation/citation traces. Add Income Analysis/Conditions views after backend contracts. Extend tax-return, specialty and overlay packs only when authorized sources exist. Admin update activation is tested before any production ruleset ships.

Every positive real-rule test needs an approved revision/section and independently reviewed expected result. Synthetic formula tests are labeled TEST_ONLY and may never populate production packs. See `.flo/underwriting/evals/scenarios.json` and `12_TEST_AND_ACCEPTANCE_PLAN.md`. No mortgage outcome or calculator correctness is claimed before executable implementation and tests.
