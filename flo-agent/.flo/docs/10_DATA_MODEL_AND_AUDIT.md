# Data Model and Audit

## Core domain object - Loan Workspace

The exact implementation may evolve, but design around a structured loan workspace rather than free-form chat memory alone.

Suggested conceptual fields:

- `loan_id` - internal opaque ID;
- `display_name` - human-friendly file/borrower label;
- `milestone`;
- `status_summary`;
- `next_action`;
- `blockers[]`;
- `waiting_on[]`;
- `due_dates[]`;
- `participants[]` - references, not unnecessary personal data;
- `conditions[]`;
- `document_refs[]`;
- `email_thread_refs[]`;
- `notes[]`;
- `source_provenance[]`;
- `risk_flags[]`;
- `created_at`;
- `updated_at`.

## Condition object

Suggested fields:

- `condition_id`;
- `source`;
- `original_text_ref`;
- `plain_language_summary`;
- `required_actions[]`;
- `owner`;
- `status`;
- `urgency`;
- `due_at`;
- `evidence_refs[]`.

## Action proposal

External effects should use an explicit proposal object:

- `proposal_id`;
- `action_type`;
- `resource`;
- `recipient_or_destination`;
- `summary`;
- `data_categories`;
- `created_by`;
- `policy_result`;
- `requires_confirmation`;
- `confirmed_by`;
- `confirmed_at`;
- `execution_result`.

The action runner consumes an approved proposal rather than free-form model text.

## Audit event

Capture:
- timestamp;
- actor;
- profile;
- loan reference if applicable;
- capability/tool;
- operation;
- resource metadata;
- policy decision;
- approval state;
- result/status;
- provider/model metadata where useful.

Avoid raw sensitive payloads unless there is a specific approved need.

## Memory boundaries

Global Flo/Ashley memory:
- stable work preferences;
- communication preferences;
- non-sensitive product settings.

Loan workspace:
- loan-specific status and references.

System of record:
- original email;
- Drive documents;
- lender/LOS records.

Do not intentionally store full sensitive source documents in general chat memory.

## Underwriting and income domain contracts

Canonical semantics: `UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md`.

- LoanUnderwritingContext: program, agency, method/AUS, lender/investor/product, occupancy/transaction, named application/note/case-assignment/AUS-submission dates; unknown stays unknown.
- SourceRevision: immutable revision ID, stable source ID, official URL/locator, issuer and scope, publication/effective trigger/bounds, retrieval/checksum, parser/version, rights/review/approval, supersession and ruleset membership. Research check time is not ingestion time.
- RuleRevision: source revision IDs + exact citations, scoped applicability predicates, required documents, calculator/version references and allowed parameters. No source text executed as code.
- RuleSetSnapshot: immutable ordered revision membership, approval/hash/test receipt, activated_at, replaced_by, rollback lineage. Historical calculations pin snapshots.
- Overlay: lender/investor/product scope and revision; NOT_LOADED differs from NOT_APPLICABLE_WITH_EVIDENCE. File-specific UW conditions require loan_id and cannot become global rules.
- IncomeStream / DocumentFact: synthetic or scoped borrower/employer/business references, income classification, value/currency/unit/period, evidence reference/page, extraction/confirmation status. No raw borrower evidence in global memory.
- CalculationRun: input snapshot/hash, context, ruleset/calculator version, Decimal operation trace, rounding, trend, typed result, monthly amount nullable, missing items/warnings, citations and overlay contribution.
- USDA outputs: annual_household_income, adjusted_annual_income and repayment_income separately typed; VA residual result separate from DTI. Never fill missing values with zero.
- DocumentRequirementEvaluation: rule citation + reason, allowed evidence, satisfied/missing/expired/conflicting/unknown, loan-scoped condition proposal.
- SourceUpdateProposal: old/new hashes, affected rules, rights decision, regression receipt, approver and expiry; activation validates exact content and is audited. Loan worksheet saved/exported as an immutable snapshot with disclosure that it is not underwriting approval.

Keep evidence in access-controlled stores outside Git; audit identifiers, hashes and decisions rather than raw borrower records. Source citations/trace are explainable evidence, not chain-of-thought.
