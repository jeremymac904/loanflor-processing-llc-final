# Asset workbench status (2026-09-08)

`plugins/flo-team/assets.py` (`flo_assets` tool; used by `flo_fileprep` and the golden path). Depository accounts only, Fannie slice, all rules from ACTIVE sections; the workbench returns `SOURCE_GAP` for the whole review when any of B3-4.2-01, B3-4.2-02, B3-4.1-01, B1-1-03 is not active.

## Output

available assets · eligible amount (purchase: minus undocumented large deposits) · funds needed · surplus · reserves in months of PITIA (with DU's Reserves Required to be Verified beside it) · sourcing questions · missing statements/pages · per-account issues · sources (section metadata) · warnings · status (OK | NEEDS_REVIEW | SOURCE_GAP) · `underwriting_decision: false`.

## Rules applied

| Check | Section | Behaviour |
|---|---|---|
| Statement identifies institution, borrower as holder, last four digits, period covered, all deposit/withdrawal transactions, ending balance | B3-4.2-01 | missing identity fields → issue; missing pages → "incomplete, cannot show all transactions and ending balance" + missing-pages item |
| Purchase: most recent full two-month period; refinance: one month | B3-4.2-01 | fewer periods → issue + missing statement item |
| Latest statement > 45 days before application | B3-4.2-01 | supplemental documentation issue |
| Large deposit = single deposit > 50% of total monthly qualifying income | B3-4.2-02 | threshold computed by `fannie.assets.large_deposit_threshold`; purchase: unsourced portion reduces eligible funds + sourcing question; refinance: note only |
| Reserves = liquid reserves / PITIA; DU one-unit primary has no minimum | B3-4.1-01 | months computed; 90% DU reserves tolerance warning from B3-2-10 |
| Document age four months at note date | B1-1-03 | applied in the file-prep matrix from statement end dates |

## Golden loan result

Available 91,340.18; one unsourced 4,000 deposit (threshold 2,750.00) → eligible 87,340.18 vs funds needed 84,250.00; July statement pages 5 of 5 missing → missing-pages item; reserves computed from the surplus; status NEEDS_REVIEW.

## Not implemented (by design)

Gifts, retirement accounts, business funds, sale proceeds, virtual currency, stocks/bonds, seasoning, earnest money treatment. Accounts of those types are listed under `unsupported` with a SOURCE_GAP note. No universal sourcing/seasoning rule was created.
