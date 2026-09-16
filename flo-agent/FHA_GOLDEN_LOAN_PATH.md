# FHA Golden Loan Path (2026-09-09)

Scope: FHA forward purchase, salaried W-2 income, depository assets, TOTAL Mortgage Scorecard findings, minimum documentation, readiness — with the TOTAL Mortgage Scorecard path (Handbook 4000.1 II.A.4) and Manual Underwriting (II.A.5) kept structurally apart. Every FHA rule, formula, asset binding and File Prep binding carries `underwriting_method: total | manual`; a call without it fails closed.

## Source and the effective-date finding

* Official source: HUD Handbook 4000.1, **Update 18** PDF (published 08/12/2026, `hud.gov/sites/default/files/Housing/documents/40001-hsgh-Update-18.pdf`), text extracted per page and sliced by the Handbook's own headings (`scripts/flo/fetch_pdf_sources.py --program fha`).
* Sections captured: II.A.1.a.i(A)(1) Maximum Age of Mortgage Documents; II.A.4.a (TOTAL scorecard/AUS), II.A.4.c (TOTAL income), II.A.4.d (TOTAL assets), II.A.4.e (TOTAL final decision); II.A.5.b (Manual income), II.A.5.c (Manual assets), II.A.5.d (Manual final decision incl. Approvable Ratio chart).
* **Every captured section's heading date is 11/10/2026 — after today.** The Update 18 text is therefore recorded with `effective_date: 11/10/2026`, `in_force: false`. It was activated (the human boundary is the same), but every Guideline Card and calculation trace bound to these sections carries the caution that the section is not yet in force and that the currently effective text is not in the cache. For a case number assigned before 11/10/2026 the applicable text is a **SOURCE_GAP** (the previous Handbook version was not captured). This is deliberate: the alternative was to guess.

## Preserved TOTAL-vs-Manual differences

| Topic | TOTAL (II.A.4) | Manual (II.A.5) |
|---|---|---|
| Traditional current employment documentation | most recent pay stub + WVOE covering two years (or EVOE) | pay stubs covering a minimum of 30 consecutive Days (28 if paid weekly/bi-weekly) + WVOE covering two years (or EVOE) |
| Salary / hourly / overtime calculation | `fha.total.income.*` bound to II.A.4.c | `fha.manual.income.*` bound to II.A.5.b (same arithmetic, separate section and record) |
| Deposits > 50% of total monthly Effective Income | `fha.total.assets.large_deposit_threshold` (II.A.4.d) | `fha.manual.assets.large_deposit_threshold` (II.A.5.c) |
| Ratios | not in the TOTAL slice (scorecard governs) | `fha.manual.ratios.pti_dti` against the Approvable Ratio Requirements (Manual) chart (31/43; 37/47, 40/40, 40/50 with listed compensating factors; 33/45 EEH) |
| Final decision | Accept: underwrite under II.A.4; Refer → manual | II.A.5.d worksheets and compensating factors |

Where the Handbook states the same rule in both places, both records exist and each points to its own section, so a TOTAL citation is never used on a manual file.

## Consistency chain

| Step | Result |
|---|---|
| Cache + checksum | `<hermes root>/flo/sources/cache/fha/` (PDF, per-page JSON, section slices); revision ids `fha-ii.a.4.c-…` etc. |
| Rule records | 31 (`fha.total.*` 18, `fha.manual.*` 12, `fha.docs.age_120_days` 1); regression green |
| Activation | 8 sections ACTIVE on this install, all flagged not yet in force |
| Calculators | `fha.total.income.current_salary_monthly`, `.hourly_varying_average`, `.overtime_bonus_tip`, `.assets.large_deposit_threshold`; the same four for `fha.manual.*` plus `fha.manual.ratios.pti_dti` |
| File Prep | `fileprep.build_matrix(program="fha", underwriting_method=…)`: pay stub with YTD, W-2s for the previous two years, WVOE/EVOE + Reverification within 10 Days of the Note, Effective Income calculation, VOD + statement or prior-ending-balance statement (else two months), TOTAL Feedback Certificate/Finding Report (or manual ratio worksheet), 120 Days at Disbursement |
| Synthetic loan | Synthetic-Okafor (`fha_golden_loan.json`), TOTAL Accept, monthly salary 4,800 |
| Live validation | `LIVE_AGENT_HANDOFF_RESULTS.md` § FHA |

## Intentional defects

1. Only the 2025 W-2 in the file; alternative documentation needs original W-2s from the previous two years (II.A.4.c) → `needs_review` "W-2 missing for 2024".
2. Unsourced 3,000 counter deposit above 50 percent of total monthly Effective Income (threshold 2,400.00) → documentation required (II.A.4.d); verified funds reduced accordingly.
3. No WVOE/EVOE/Reverification in the file (II.A.4.c) → `missing`.
4. One statement that does not show the previous month's ending balance → two months required (II.A.4.d alternative documentation) → `missing` one statement.

## Deterministic whole-team run (`test_golden_loan_path_per_program[fha]`)

AUS statement `TOTAL Mortgage Scorecard findings show Accept.`; Effective Income 4,800.00 (`fha.total.income.current_salary_monthly`, monthly identity, with the labelled note that the Handbook states "use the current salary" and the month conversion is plain arithmetic); every card cites II.A.4.* only and carries the 11/10/2026 caution; Whisper draft only.

## SOURCE_GAP remaining (FHA)

* The currently in-force (pre-Update-18) text of every captured section.
* Part-time, seasonal, family business, commission, self-employment (II.A.4.c.iv-x / II.A.5.b), gifts, retirement, cash on hand (beyond definition), MRI sourcing details, TOTAL reserve requirements beyond the definitions captured.
* Credit sections (II.A.4.b / II.A.5.a), property, MIP.
