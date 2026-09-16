# Multi-program source registry (2026-09-09)

One source layer for every program (`plugins/flo-team/sources.py`): official source → versioned private cache → checksum → rule records with anchors → regression receipt → human approval with a structured identity → ACTIVE per install. Official text is never committed; it lives in `<hermes root>/flo/sources/cache/<program>/`. `Status` is this machine's activation state at generation time; the repository always ships `detected`.

| Program | Retrieval | Rights basis |
|---|---|---|
| Fannie Mae Conventional | Selling Guide HTML pages fetched directly (`scripts/flo/fetch_fannie_sources.py`) | Fannie Mae limited professional-use permission; private cache |
| Freddie Mac Conventional | Guide JSON API behind guide.freddiemac.com (`/cc/data/getAnswerById`, `scripts/flo/fetch_freddie_sources.py`); the Guide's own `publishedDate`, `version` and `GUIDE/EFFECTIVE_DATE` recorded | Freddie Mac Guide terms: professional use, no redistribution; private cache |
| FHA | Handbook 4000.1 Update 18 PDF from hud.gov, text per page, heading-located slices (`scripts/flo/fetch_pdf_sources.py --program fha`) | U.S. Government work; private cache |
| VA | VA Pamphlet 26-7 Chapter 4 from VA's KnowVA article API (`/system/ws/v11/ss/article/<id>`, `scripts/flo/fetch_va_sources.py`) | U.S. Government work; private cache |
| USDA Guaranteed (SFHGLP) | HB-1-3555 chapter PDFs from rd.usda.gov (browser-style headers required by its edge), heading-located slices (`scripts/flo/fetch_pdf_sources.py --program usda`) | U.S. Government work; private cache |

## Fannie Mae Conventional — Fannie Mae Selling Guide

AUS: DU; underwriting methods: du, manual; rule records: 34; namespace `fannie.*`

| Section | Title | Published | Effective | In force | Revision | Rules | Status (this install) | Official URL |
|---|---|---|---|---|---|---|---|---|
| B1-1-03 | Allowable Age of Credit Documents and Federal Income Tax Returns | 04/02/2025 | 04/02/2025 | yes | `fannie-b1-1-03-d19e85a799e2` | 1 | active | https://selling-guide.fanniemae.com/sel/b1-1-03/allowable-age-credit-documents-and-federal-income-tax-returns |
| B3-2-10 | Accuracy of DU Data, DU Tolerances, and Errors in the Credit Report | 12/04/2019 | 12/04/2019 | yes | `fannie-b3-2-10-45b8a014ccb7` | 2 | active | https://selling-guide.fanniemae.com/sel/b3-2-10/accuracy-du-data-du-tolerances-and-errors-credit-report |
| B3-2-11 | DU Underwriting Findings Report | 09/07/2022 | 09/07/2022 | yes | `fannie-b3-2-11-dcbba1093184` | 1 | active | https://selling-guide.fanniemae.com/sel/b3-2-11/du-underwriting-findings-report |
| B3-3.1-01 | General Income Information | 03/04/2026 | 03/04/2026 | yes | `fannie-b3-3.1-01-69941a7d4648` | 3 | active | https://selling-guide.fanniemae.com/sel/b3-3.1-01/general-income-information |
| B3-3.1-04 | Verbal Verification of Employment | 03/04/2026 | 03/04/2026 | yes | `fannie-b3-3.1-04-850c04a51301` | 1 | active | https://selling-guide.fanniemae.com/sel/b3-3.1-04/verbal-verification-employment |
| B3-3.2-01 | Standards for Employment and Income Documentation | 03/04/2026 | 03/04/2026 | yes | `fannie-b3-3.2-01-7ef253f338df` | 4 | active | https://selling-guide.fanniemae.com/sel/b3-3.2-01/standards-employment-and-income-documentation |
| B3-3.2-02 | Standards for Employment-Related Income | 03/04/2026 | 03/04/2026 | yes | `fannie-b3-3.2-02-9e2f20f2822e` | 3 | active | https://selling-guide.fanniemae.com/sel/b3-3.2-02/standards-employment-related-income |
| B3-3.3-01 | Base Income | 03/04/2026 | 03/04/2026 | yes | `fannie-b3-3.3-01-23295e8b3b2d` | 9 | active | https://selling-guide.fanniemae.com/sel/b3-3.3-01/base-income |
| B3-3.3-02 | Bonus, Commission, Overtime, and Tip Income | 03/04/2026 | 03/04/2026 | yes | `fannie-b3-3.3-02-71c0337b8a7d` | 3 | active | https://selling-guide.fanniemae.com/sel/b3-3.3-02/bonus-commission-overtime-and-tip-income |
| B3-4.1-01 | Minimum Reserve Requirements | 08/07/2024 | 08/07/2024 | yes | `fannie-b3-4.1-01-a1523932fa1a` | 2 | active | https://selling-guide.fanniemae.com/sel/b3-4.1-01/minimum-reserve-requirements |
| B3-4.2-01 | Verification of Deposits and Assets | 05/04/2022 | 05/04/2022 | yes | `fannie-b3-4.2-01-e2bec9337187` | 2 | active | https://selling-guide.fanniemae.com/sel/b3-4.2-01/verification-deposits-and-assets |
| B3-4.2-02 | Depository Accounts | 12/14/2022 | 12/14/2022 | yes | `fannie-b3-4.2-02-852468d807a3` | 3 | active | https://selling-guide.fanniemae.com/sel/b3-4.2-02/depository-accounts |

## Freddie Mac Conventional — Freddie Mac Single-Family Seller/Servicer Guide

AUS: LPA; underwriting methods: lpa, manual; rule records: 36; namespace `freddie.*`

| Section | Title | Published | Effective | In force | Revision | Rules | Status (this install) | Official URL |
|---|---|---|---|---|---|---|---|---|
| 5101.1 | General information for using Loan Product Advisor&reg; | 02/04/2026 | 02/04/2026 | yes | `freddie-5101.1-2286cd3cdce7` | 1 | active | https://guide.freddiemac.com/app/guide/section/5101.1 |
| 5101.2 | Loan Product Advisor&reg; Risk Class | 02/04/2026 | 02/04/2026 | yes | `freddie-5101.2-b234b8df191d` | 1 | active | https://guide.freddiemac.com/app/guide/section/5101.2 |
| 5101.3 | Resubmission requirements | 02/04/2026 | 02/04/2026 | yes | `freddie-5101.3-6854a0891244` | 2 | active | https://guide.freddiemac.com/app/guide/section/5101.3 |
| 5102.3 | General requirements for verifying documents | 08/06/2025 | 08/06/2025 | yes | `freddie-5102.3-5c02378aa987` | 0 | pending_review | https://guide.freddiemac.com/app/guide/section/5102.3 |
| 5102.4 | Age of documentation | 02/04/2026 | 02/04/2026 | yes | `freddie-5102.4-4a048f12663b` | 1 | active | https://guide.freddiemac.com/app/guide/section/5102.4 |
| 5301.1 | General requirements for all stable monthly income | 03/04/2026 | 03/04/2026 | yes | `freddie-5301.1-3a2801d9b908` | 5 | active | https://guide.freddiemac.com/app/guide/section/5301.1 |
| 5302.1 | Introduction to documentation requirements | 07/02/2025 | 07/02/2025 | yes | `freddie-5302.1-e6cdb1a5ad56` | 0 | pending_review | https://guide.freddiemac.com/app/guide/section/5302.1 |
| 5302.2 | Employed income documentation and verification requirements | 05/06/2026 | 05/06/2026 | yes | `freddie-5302.2-7bc791228fa1` | 6 | active | https://guide.freddiemac.com/app/guide/section/5302.2 |
| 5302.3 | Third-party verification service providers: employment and income veri | 06/03/2026 | 06/03/2026 | yes | `freddie-5302.3-5680407b5815` | 0 | pending_review | https://guide.freddiemac.com/app/guide/section/5302.3 |
| 5302.4 | Tax returns and tax return information: documentation and verification | 04/01/2026 | 04/01/2026 | yes | `freddie-5302.4-feadec1feba1` | 0 | pending_review | https://guide.freddiemac.com/app/guide/section/5302.4 |
| 5302.5 | Internal Revenue Service (IRS) Form 4506-C requirements for all income | 08/05/2026 | 08/05/2026 | yes | `freddie-5302.5-6c656ade7766` | 0 | pending_review | https://guide.freddiemac.com/app/guide/section/5302.5 |
| 5302.6 | Automated employment assessment with Loan Product Advisor&reg; | 06/23/2026 | 06/03/2026 | yes | `freddie-5302.6-35f94c613808` | 0 | pending_review | https://guide.freddiemac.com/app/guide/section/5302.6 |
| 5303.1 | Employed income | 06/03/2026 | 06/03/2026 | yes | `freddie-5303.1-eb95d0b1a0eb` | 10 | active | https://guide.freddiemac.com/app/guide/section/5303.1 |
| 5303.2 | Income commencing after the Note Date | 05/08/2026 | 05/06/2026 | yes | `freddie-5303.2-3d027d557ce3` | 0 | pending_review | https://guide.freddiemac.com/app/guide/section/5303.2 |
| 5303.3 | Income while on temporary leave | 08/05/2026 | 08/05/2026 | yes | `freddie-5303.3-e85a816e49c2` | 0 | pending_review | https://guide.freddiemac.com/app/guide/section/5303.3 |
| 5303.4 | Automated income assessment using employed income data | 09/02/2026 | 09/02/2026 | yes | `freddie-5303.4-69c2cc8b3469` | 0 | pending_review | https://guide.freddiemac.com/app/guide/section/5303.4 |
| 5401.1 | Monthly housing expense-to-income ratio | 05/06/2026 | 05/06/2026 | yes | `freddie-5401.1-a130f40f8b43` | 0 | pending_review | https://guide.freddiemac.com/app/guide/section/5401.1 |
| 5401.2 | Monthly debt payment-to-income (DTI) ratio | 08/13/2026 | 08/05/2026 | yes | `freddie-5401.2-2938ce5a56b5` | 2 | active | https://guide.freddiemac.com/app/guide/section/5401.2 |
| 5501.1 | Funds required for the Mortgage transaction | 08/05/2026 | 08/05/2026 | yes | `freddie-5501.1-a7272199d9a9` | 3 | active | https://guide.freddiemac.com/app/guide/section/5501.1 |
| 5501.2 | Reserves | 03/04/2026 | 03/04/2026 | yes | `freddie-5501.2-ab316e767253` | 2 | active | https://guide.freddiemac.com/app/guide/section/5501.2 |
| 5501.3 | Borrower personal funds | 08/13/2026 | 07/01/2026 | yes | `freddie-5501.3-0b02d8348f96` | 3 | active | https://guide.freddiemac.com/app/guide/section/5501.3 |

Sections without rule records (5102.3, 5302.1, 5302.3-5302.6, 5303.2-5303.4, 5401.1) are captured for context and stay `pending_review`; they are citable only once rule records with anchors are added and a human activates them.

## FHA — FHA Single Family Housing Policy Handbook 4000.1

AUS: TOTAL; underwriting methods: total, manual; rule records: 60; namespace `fha.*` (`fha.total.*` / `fha.manual.*`)

| Section | Title | Published | Effective | In force | Revision | Rules | Status (this install) | Official URL |
|---|---|---|---|---|---|---|---|---|
| II.A.1.a.i(A)(1)@update-17 | Maximum Age of Mortgage Documents (Applications and Disclosures, gener | 11/26/2025 | 03/19/2025 | yes | `fha-ii.a.1.a.i_a__1__update-17-decbfeafe68d` | 1 | active | https://www.hud.gov/sites/default/files/OCHCO/documents/40001-hsgh-Update-17.pdf |
| II.A.1.a.i(A)(1)@update-18 | Maximum Age of Mortgage Documents (Applications and Disclosures, gener | 08/12/2026 | 03/19/2025 | yes | `fha-ii.a.1.a.i_a__1__update-18-c43828165562` | 1 | active | https://www.hud.gov/sites/default/files/Housing/documents/40001-hsgh-Update-18.pdf |
| II.A.4.a@update-17 | TOTAL Mortgage Scorecard: Underwriting with an Automated Underwriting  | 11/26/2025 | 11/07/2023 | yes | `fha-ii.a.4.a_update-17-22a0d132f869` | 3 | active | https://www.hud.gov/sites/default/files/OCHCO/documents/40001-hsgh-Update-17.pdf |
| II.A.4.a@update-18 | TOTAL Mortgage Scorecard: Underwriting with an Automated Underwriting  | 08/12/2026 | 11/10/2026 | **no** | `fha-ii.a.4.a_update-18-9f47e2452c50` | 3 | active | https://www.hud.gov/sites/default/files/Housing/documents/40001-hsgh-Update-18.pdf |
| II.A.4.c@update-17 | TOTAL: Income Requirements | 11/26/2025 | 04/10/2025 | yes | `fha-ii.a.4.c_update-17-104476516c85` | 9 | active | https://www.hud.gov/sites/default/files/OCHCO/documents/40001-hsgh-Update-17.pdf |
| II.A.4.c@update-18 | TOTAL: Income Requirements | 08/12/2026 | 11/10/2026 | **no** | `fha-ii.a.4.c_update-18-7d516686fa8b` | 9 | active | https://www.hud.gov/sites/default/files/Housing/documents/40001-hsgh-Update-18.pdf |
| II.A.4.d@update-17 | TOTAL: Asset Requirements | 11/26/2025 | 08/19/2024 | yes | `fha-ii.a.4.d_update-17-01a3b5997248` | 4 | active | https://www.hud.gov/sites/default/files/OCHCO/documents/40001-hsgh-Update-17.pdf |
| II.A.4.d@update-18 | TOTAL: Asset Requirements | 08/12/2026 | 11/10/2026 | **no** | `fha-ii.a.4.d_update-18-f7e8bfb14d8c` | 4 | active | https://www.hud.gov/sites/default/files/Housing/documents/40001-hsgh-Update-18.pdf |
| II.A.4.e@update-17 | TOTAL: Final Underwriting Decision | 11/26/2025 | 09/14/2015 | yes | `fha-ii.a.4.e_update-17-18786113f592` | 1 | active | https://www.hud.gov/sites/default/files/OCHCO/documents/40001-hsgh-Update-17.pdf |
| II.A.4.e@update-18 | TOTAL: Final Underwriting Decision | 08/12/2026 | 11/10/2026 | **no** | `fha-ii.a.4.e_update-18-9c2d59e22ad1` | 1 | active | https://www.hud.gov/sites/default/files/Housing/documents/40001-hsgh-Update-18.pdf |
| II.A.5.b@update-17 | Manual: Income Requirements | 11/26/2025 | 04/10/2025 | yes | `fha-ii.a.5.b_update-17-a50456493688` | 7 | active | https://www.hud.gov/sites/default/files/OCHCO/documents/40001-hsgh-Update-17.pdf |
| II.A.5.b@update-18 | Manual: Income Requirements | 08/12/2026 | 11/10/2026 | **no** | `fha-ii.a.5.b_update-18-3f7452bda40a` | 7 | active | https://www.hud.gov/sites/default/files/Housing/documents/40001-hsgh-Update-18.pdf |
| II.A.5.c@update-17 | Manual: Asset Requirements | 11/26/2025 | 08/19/2024 | yes | `fha-ii.a.5.c_update-17-0da967cf4518` | 2 | active | https://www.hud.gov/sites/default/files/OCHCO/documents/40001-hsgh-Update-17.pdf |
| II.A.5.c@update-18 | Manual: Asset Requirements | 08/12/2026 | 11/10/2026 | **no** | `fha-ii.a.5.c_update-18-e3a5f0bd3133` | 2 | active | https://www.hud.gov/sites/default/files/Housing/documents/40001-hsgh-Update-18.pdf |
| II.A.5.d@update-17 | Manual: Final Underwriting Decision | 11/26/2025 | 08/19/2024 | yes | `fha-ii.a.5.d_update-17-8acf044c0810` | 3 | active | https://www.hud.gov/sites/default/files/OCHCO/documents/40001-hsgh-Update-17.pdf |
| II.A.5.d@update-18 | Manual: Final Underwriting Decision | 08/12/2026 | 11/10/2026 | **no** | `fha-ii.a.5.d_update-18-a09104b2d219` | 3 | active | https://www.hud.gov/sites/default/files/Housing/documents/40001-hsgh-Update-18.pdf |

Every FHA rule record carries `underwriting_method`; the Handbook's TOTAL (II.A.4) and Manual (II.A.5) text is recorded as separate sections and separate rules even where the wording is identical, and where it differs the difference is preserved (e.g. manual traditional documentation requires pay stubs covering 30 consecutive Days / 28 if paid weekly or biweekly, TOTAL requires the most recent pay stub). All Update 18 sections captured are **effective 11/10/2026**: they are activated with an `in_force: false` flag, every card/calculation carries the caution, and the currently in-force text is a recorded SOURCE_GAP.

## VA — VA Pamphlet 26-7 Lenders Handbook

AUS: AUS; underwriting methods: aus, manual; rule records: 20; namespace `va.*`

| Section | Title | Published | Effective | In force | Revision | Rules | Status (this install) | Official URL |
|---|---|---|---|---|---|---|---|---|
| Chapter 4 | VA Pamphlet VAP26-7 Chapter 04 Credit Underwriting | 08/26/2026 | 08/26/2026 | yes | `va-chapter_4-73bc8cbb8b41` | 20 | active | https://www.knowva.ebenefits.va.gov/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/554400000001018/content/554400000330850/VA-Pamphlet-VAP26-7-Chapter-04-Credit-Underwriting |

Chapter 4 is one KnowVA article (topics 1-10, per-topic change dates recorded in `topic_change_dates`). Residual income Tables 9/10/11 are parsed from the cached text at run time (`calc.va_residual_tables`); no table value is typed into code.

## USDA Guaranteed (SFHGLP) — HB-1-3555 SFH Guaranteed Loan Program Technical Handbook

AUS: GUS; underwriting methods: gus, manual; rule records: 20; namespace `usda.*`

| Section | Title | Published | Effective | In force | Revision | Rules | Status (this install) | Official URL |
|---|---|---|---|---|---|---|---|---|
| 11.2-11.3 | Ratio analysis: the ratios, debt ratio waivers and compensating factor |  |  |  | `usda-11.2-11.3-1797540a34f1` | 3 | active | https://www.rd.usda.gov/files/3555-1chapter11.pdf |
| 5.3 | Utilizing the Guaranteed Underwriting System (GUS) |  |  |  | `usda-5.3-ff015cd5dfff` | 3 | active | https://www.rd.usda.gov/files/3555-1chapter05.pdf |
| 9-A | Attachment 9-A income and documentation matrix | 08/05/2025 | 08/05/2025 | yes | `usda-9-a-775c061a1ce8` | 4 | active | https://www.rd.usda.gov/sites/default/files/3555-1chapter09.pdf |
| 9.3 | Annual income (household income eligibility) | 08/05/2025 | 08/05/2025 | yes | `usda-9.3-546ab6cf78a7` | 6 | active | https://www.rd.usda.gov/sites/default/files/3555-1chapter09.pdf |
| 9.4 | Calculating income from assets | 08/05/2025 | 08/05/2025 | yes | `usda-9.4-580dfa75ef4d` | 0 | pending_review | https://www.rd.usda.gov/sites/default/files/3555-1chapter09.pdf |
| 9.5 | Adjusted annual income | 08/05/2025 | 08/05/2025 | yes | `usda-9.5-7c2779dae56e` | 1 | active | https://www.rd.usda.gov/sites/default/files/3555-1chapter09.pdf |
| 9.7-9.8 | Repayment income: overview, stable and dependable income | 08/05/2025 | 08/05/2025 | yes | `usda-9.7-9.8-fa076598b1f7` | 3 | active | https://www.rd.usda.gov/sites/default/files/3555-1chapter09.pdf |

Three income concepts stay separate: annual (household) income (9.3), adjusted annual income (9.5, eligibility), repayment income (9.7-9.8, note parties). No `qualifying_income` field exists for USDA.

## Approval identity

Approval and activation records use `plugins/flo-team/identity.py` (schema 2): `approved_by_user_id`, `approved_by_display_name`, `identity_source`, `approved_at`, `approval_reason`, `source_revision_id`, `regression_receipt`, `checksum`, `environment`. No e-mail address is stored. Until authentication provides ids, `current_identity()` uses `FLO_APPROVER_ID/NAME` or the local development identity (`local-dev:<os user>@<host>`); the Fannie records approved on 2026-09-08 were migrated in place (`legacy:owner`, `identity_source: legacy`, original fields kept under `migrated_from`).

## Activation commands

```
python scripts/flo/activate_sources.py --program <fannie|freddie|fha|va|usda> --status
python scripts/flo/activate_sources.py --program <p> --review
python scripts/flo/activate_sources.py --program <p> --approve --reason "<why>" [--approver-id <id> --approver-name <name>]
python scripts/flo/activate_sources.py --program <p> --activate
```

