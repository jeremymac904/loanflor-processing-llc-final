# USDA Guaranteed Golden Loan Path (2026-09-09)

Scope: USDA Single Family Housing Guaranteed Loan Program purchase, W-2 base wages, depository assets, GUS findings, minimum documentation, readiness — with USDA's three income concepts kept as **three distinct fields**: annual (household) income, adjusted annual income, repayment income. There is no `qualifying_income` field anywhere in the USDA path.

## Source

* Official source: HB-1-3555 SFH Guaranteed Loan Program Technical Handbook chapter PDFs on rd.usda.gov (Chapter 9 revised 08-05-25 PN 649; Chapter 11 revised 11-25-25 PN 651; Chapter 5), text per page, sliced by the Handbook's own upper-case headings (`scripts/flo/fetch_pdf_sources.py --program usda`). The site's edge rejects bare clients; a browser-style header set is required and recorded in the script.
* Sections: 9.3 Annual income, 9.4 Calculating income from assets (context only), 9.5 Adjusted annual income, 9.7-9.8 Repayment income / stable and dependable income, Attachment 9-A (income and documentation matrix), 5.3 GUS, 11.2-11.3 Ratios and waivers.
* 20 rule records (`usda.*`), regression green; 6 sections ACTIVE on this install (9.4 has no rule records and stays pending).

## The three incomes

| Figure | Section | Formula | Who counts |
|---|---|---|---|
| Annual income | 9.3 | `usda.annual_income.household` — gross annual income of every adult household member; only the first $480 of an adult full-time student's earned income | all adult household members, not only note parties |
| Adjusted annual income | 9.5 | `usda.adjusted_annual_income` — annual income minus the 7 CFR 3555.152(c) deductions supplied on the lender's worksheet; compared to the area income limit (limit itself is a lender/GUS input, SOURCE_GAP as cached text) | eligibility |
| Repayment income | 9.7-9.8 | `usda.repayment_income.monthly` — stable and dependable monthly income of the note parties only | ratios |
| Ratios | 11.2-11.3 | `usda.ratios.piti_td` — PITI ≤ 29 percent and total debt ≤ 41 percent of repayment income; above → debt ratio waiver with compensating factors | repayment income only |

Synthetic-Lindqvist: applicant 3,900/month (46,800/yr) + non-applicant spouse 18,000 + adult student 6,000 (counted 480) → annual **65,280.00**; deductions 480 + 480 → adjusted **64,320.00** (under the stated synthetic limit 110,650); repayment **3,900.00**; PITI ratio 32.05% and total debt ratio 42.82% → waiver required.

## GUS vs manual

`aus.py` maps `gus_findings` → system GUS; statement `GUS findings show Accept / Eligible.` (as printed). Rules 5.3: GUS returns a recommendation (accept or refer for manual underwriting), does not evaluate the dependability of repayment income, and applicants are never approved or denied solely on a GUS assessment; final-submission data tolerance $50 cumulative. A GUS report on any other program is a mismatch.

## Consistency chain

| Step | Result |
|---|---|
| File Prep | paystubs with YTD dated within 30 days of the initial application (9.3), W-2 for the most recent year, VVOE within 10 business days of closing (9.3), the three income figures and the adjusted-income-vs-limit worksheet, two months of statements or VOD + statement (9-A), non-recurring deposits over $1,000 and recurring non-wage deposits investigated (9-A), GUS findings (5.3); no document-age section captured → workflow SOURCE_GAP item |
| Assets | USDA binding: $1,000 non-recurring threshold and recurring-deposit investigation from Attachment 9-A; reserves not required (5.3(E)) |
| Guideline Card | program USDA Guaranteed (SFHGLP), agency USDA Rural Development, AUS GUS, Handbook section with the PN revision recorded as edition |
| Synthetic loan | `usda_golden_loan.json` |
| Live validation | `LIVE_AGENT_HANDOFF_RESULTS.md` § USDA |

## Intentional defects

1. PITI/TD 32.05/42.82 above 29/41 → debt ratio waiver with compensating factors (11.2/11.3) → guideline question to Sage.
2. Non-recurring 1,500 mobile deposit above $1,000, not investigated (9-A).
3. Paystub dated 2026-07-15 vs application 2026-08-24 → more than 30 days (9.3).
4. No VVOE in the file (9.3).

## SOURCE_GAP remaining (USDA)

* Area income limits and the 7 CFR 3555.152(c) deduction amounts (lender worksheet inputs; not cached text).
* Pay-period-to-monthly conversion (not stated in the captured chapters; a non-monthly paystub returns SOURCE_GAP), overtime/bonus/commission trend analysis, self-employment (9-A rows beyond base wages), rental, income from assets (9.4 recorded but no rules), document-age policy, debt ratio waiver compensating-factor specifics (11.3 captured; rules limited to the ratio thresholds and documentation).
