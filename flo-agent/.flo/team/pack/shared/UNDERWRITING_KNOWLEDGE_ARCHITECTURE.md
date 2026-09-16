# Underwriting Knowledge Architecture

Sage owns guideline interpretation. Malcolm consumes Sage-approved rules for file prep.

## Core program libraries

- Fannie Mae Conventional
- Freddie Mac Conventional
- FHA
- VA
- USDA Guaranteed
- Non-QM / Jumbo / specialty by actual lender/investor guide only

## Rule resolution order

1. Identify loan program and agency/investor.
2. Identify AUS/manual path.
3. Resolve effective official source.
4. Apply lender overlay when loaded.
5. Apply product/investor overlay when loaded.
6. Consider file-specific AUS findings.
7. Consider file-specific UW conditions.
8. If conflict remains, require AE/UW confirmation.

## Calculation engine

Arithmetic should be deterministic.

The model may:
- classify income/document types;
- identify relevant rules;
- explain;
- identify missing evidence.

The calculator should:
- record inputs;
- record formula;
- record result;
- record rule/source;
- preserve calculation trace.

## Income categories to prepare

Employment:
salary, fixed hourly, variable hourly, overtime, bonus, commission, tips, shift differential, secondary/seasonal/temporary.

Self-employment:
Schedule C, partnership, S corporation, corporation, K-1, P&L and other required docs when source-backed.

Rental:
subject/non-subject, departing residence, leases, Schedule E, appraiser rent forms, rental losses where applicable.

Other:
Social Security, pension, retirement, disability, alimony/child support, trust, note, interest/dividend, military, and other categories only as supported by the selected program source.

## Assets

Prepare rule-backed handling for:
- depository accounts;
- gifts;
- retirement assets;
- sale proceeds;
- earnest money;
- reserves;
- large deposits;
- business assets;
- other accepted sources.

Do not create universal sourcing/seasoning rules.

## Outputs

Sage should return:
- program;
- question/topic;
- answer;
- source;
- section;
- published/effective date;
- overlay status;
- calculation trace if applicable;
- missing documentation;
- caution/conflict;
- recommended next action.
