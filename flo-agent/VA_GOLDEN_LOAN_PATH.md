# VA Golden Loan Path (2026-09-09)

Scope: VA purchase, salaried W-2 income, depository assets, AUS findings through a VA-approved AUS (DU here), minimum documentation, readiness — and, as the structurally distinct VA piece, **residual income as deterministic logic from the activated official Chapter 4 only**.

## Source

* Official source: VA Pamphlet 26-7 Lenders Handbook, Chapter 4 Credit Underwriting, as published on VA's KnowVA knowledge base (article 554400000330850, "Updated Aug 26, 2026", article version 4). The benefits.va.gov WARMS paths now redirect to KnowVA; the older article id found in earlier notes returns "Requested Article is not available", so the current id was resolved from VA's own search. The article's HTML is fetched from KnowVA's article API (`scripts/flo/fetch_va_sources.py`) so the residual income tables keep their row structure.
* Cached as one section, `Chapter 4` (107,080 characters), revision `va-chapter_4-73bc8cbb8b41`, with the per-topic change dates recorded (`topic_change_dates`).
* 20 rule records (`va.*`), regression green, ACTIVE on this install.

## Residual income — deterministic, table values read from the official text

`calc.va_residual_tables(text)` parses Table 9 (loan amounts of $79,999 and below), Table 10 ($80,000 and above), the over-five-member increments ($75 / $80 per additional member up to a family of seven) and Table 11 (state → region) from the cached Chapter 4 text at run time. No table value is typed into code; if the cached text changes the checksum check demotes the section and the calculator returns SOURCE_GAP.

| Formula | Inputs | Output / rule |
|---|---|---|
| `va.residual_income.required` | family_size, loan_amount, state (or region) | guideline from the tables; loan-amount category, region lookup and over-5 increment as explicit steps; members beyond seven not counted (warning) |
| `va.residual_income.monthly` | gross monthly income, Federal/state income tax, social security/other deductions, shelter expense, maintenance & utilities **or** gross living area (14¢ per square foot, Item 19), monthly debts | balance available for family support (Item 43) |
| `va.residual_income.check` | residual, required | percent of guideline; flags below-guideline and the 20-percent rule for a DTI above 41 percent |
| `va.dti.ratio` | housing expense, installment/other obligations, gross monthly income | VA DTI; "secondary to residual income"; above 41 percent → close scrutiny / supervisor justification unless residual exceeds the guideline by 20 percent |

Synthetic-Reyes: family size 4, Texas → South, loan 285,000 → Table 10 → **1,003.00** required; balance available 1,053.70 (105.05% of guideline); DTI 61.29%. Result: residual meets the guideline by less than 20 percent and DTI exceeds 41 percent → supervisor-signed justification statement required (Chapter 4 Topic 10). The calculator never says approve/deny; Chapter 4's own words ("a guide… should not automatically trigger approval or rejection") are carried as a caution.

## Consistency chain

| Step | Result |
|---|---|
| Rule records | income effectiveness, two years of employment, less than 12 months, standard verification (VOE + 30-day paystubs), 120/180-day age, employment verification services, assets (VOD or last two statements), AUS reduced documentation, Form 26-6393 items (19, 32, 43, 51), residual tables and family-size counting, DTI definition and 41-percent rule, tax-free gross-up (DTI only), compensating factors |
| Guideline Card | program VA, agency U.S. Department of Veterans Affairs, AUS as shown, section "Chapter 4" with the article's updated date, revision id, official KnowVA link |
| File Prep | paystubs covering the most recent 30-day period with YTD, VA Form 26-8497 (or equivalent), Form 26-6393 residual/DTI worksheet, VOD or last two statements, AUS findings with VA risk classification, verifications within 120 days of closing (180 new construction) |
| Assets | VA binding: two statements or VOD; deposit-sourcing thresholds are SOURCE_GAP (not in the captured chapter) |
| Synthetic loan | Synthetic-Reyes (`va_golden_loan.json`) |
| Live validation | `LIVE_AGENT_HANDOFF_RESULTS.md` § VA |

## Intentional defects

1. DTI above 41 percent with residual income under 120 percent of the guideline → supervisor justification required (Topic 10).
2. VOE dated 2026-05-01 with an estimated closing of 2026-10-09 → older than 120 days (Topic 2) → document-age `needs_review`.
3. One bank statement only → VOD or the last two statements required (Topic 4) → `missing` one statement.

## Deterministic whole-team run (`test_golden_loan_path_per_program[va]`)

AUS statement `DU findings show Approve/Eligible.`; gross monthly income 6,200.00 (monthly paystub, identity — Chapter 4 as captured states no pay-period conversion table, so a non-monthly paystub returns SOURCE_GAP rather than an invented conversion); residual and DTI lines as above with calc ids; Whisper draft only.

## SOURCE_GAP remaining (VA)

* Pay-period-to-monthly conversion, overtime/bonus/commission, self-employment, rental, active-duty income, tax-free income for residual (Topics 2-3 beyond the captured rules).
* Deposit sourcing thresholds, gift funds, reserves as a compensating factor amount.
* Federal/state tax and social security amounts (inputs from IRS/state tables per Topic 3; not computed).
* Entitlement/COE, funding fee, appraisal (other chapters).
