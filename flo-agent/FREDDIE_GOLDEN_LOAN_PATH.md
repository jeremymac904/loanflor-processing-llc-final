# Freddie Mac Golden Loan Path (2026-09-09)

Scope, exactly as directed: Freddie Mac conventional purchase, W-2 base non-fluctuating earnings (fluctuating hourly only where the Guide is explicit), depository assets, Loan Product Advisor findings, minimum documentation, submission readiness. No generic "conventional" rule exists: Freddie rules live in `plugins/flo-team/knowledge/freddie/rules.json` (namespace `freddie.*`) and are matched only for `program=freddie`.

## Consistency chain

| Step | Where | Result |
|---|---|---|
| Official source | guide.freddiemac.com, Single-Family Seller/Servicer Guide (the site's own JSON: `/cc/data/getAnswerById/answerId/<id>`; section → id from `getContentLookupFor/GUIDE/SECTION_NUMBER`) | 21 sections captured with the Guide's `publishedDate`, `version` and `GUIDE/EFFECTIVE_DATE` |
| Versioned cache + checksum | `<hermes root>/flo/sources/cache/freddie/<section>.txt/.html` (private, never committed); `knowledge/freddie/sections.json` holds sha-256, revision id `freddie-<section>-<sha12>`, retrieval timestamp, rights | done |
| Rule records | 36 records, each with an anchor phrase that must exist in the cached text | regression green for all 12 rule-bearing sections |
| Regression anchors | `sources.regression("freddie", <section>)` → receipt | receipts recorded in the per-install knowledge state |
| Human activation | `scripts/flo/activate_sources.py --program freddie --review/--approve/--activate` with the structured approval identity (`identity.py`) | 11 sections ACTIVE on this install (5101.1, 5101.2, 5101.3, 5102.4, 5301.1, 5302.2, 5303.1, 5401.2, 5501.1, 5501.2, 5501.3); 9 context-only sections stay `pending_review` |
| Sage Guideline Card | `cards.guideline_card(program="freddie", …)` — Program, Agency, Underwriting Method (LPA), Topic, Source, Section, Published, Effective, Revision, AUS, Lender Overlay, Investor Overlay, Guideline-Supported Conclusion, Calculation Trace, Missing Documentation, Conflict/Caution, Best Next Move | section-level citations with the Guide's published and effective dates |
| Deterministic calculator | `freddie.base_income.monthly` (5303.1(c)(i) table), `freddie.fluctuating_hourly.average` (5303.1(d)(i) averaging, fluctuation bands, declining rule), `freddie.assets.large_deposit_threshold` (5501.1(f)(ii)), `freddie.reserves.months` (5501.2(a)), `freddie.lpa.dti_resubmission_check` (5101.3(b)), `freddie.dti.ratio` (5401.2) | 6 PRODUCTION formulas, all bound to ACTIVE sections; refuse `program≠freddie` |
| Malcolm File Prep | `fileprep.build_matrix(program="freddie", documentation_level=…)`: paystub within 30 days of the Application Received Date (5302.2(a)), W-2 for the most recent calendar year (5302.2(b)), 10-day PCV (5302.2(d)), income calculation (5303.1), statements per Documentation Level (5501.3(a)), large-deposit sourcing (5501.1(f)), Feedback Certificate (5101.1), verifications within 120 days of the Note Date (5102.4) | provenance `freddie:<section>` / `lpa:<message>` / workflow / ashley |
| Synthetic loan | `tests/flo/fixtures/golden_loan/freddie_golden_loan.json` — Synthetic-Bellamy, bi-weekly 2,307.69, 2025 W-2 59,400, two complete statements, LPA Accept / Standard Documentation | intentional defects below |
| Live validation | see `LIVE_AGENT_HANDOFF_RESULTS.md` § Freddie | recorded there |

## Intentional defects (all from activated rules only)

1. Most recent paystub dated 2026-07-20 vs Application Received Date 2026-08-24 → more than 30 days (5302.2(a)) → `needs_review`.
2. Unsourced 3,200 mobile deposit on 2026-08-01: above 50% of stable monthly income (threshold 2,500.00 from `freddie.assets.large_deposit_threshold`), within 60 days before the Application Received Date, purchase → sourcing question; verified funds reduced by 3,200 (5501.1(f)(ii)).
3. No 10-day pre-closing verification in the file (5302.2(d)) → `missing`.

## Deterministic whole-team run (test `test_golden_loan_path_per_program[freddie]`)

* Flo → Malcolm → Sage → Whisper → Flo; readiness IN_PROGRESS/BLOCKED, never "approved".
* AUS statement: `LPA findings show Accept.`
* Stable monthly income 5,000.00 (`freddie.base_income.monthly`, bi-weekly × 26 / 12, source 5303.1 v65.0 published 06/03/2026); YTD comparison and W-2 comparison recorded as processor review lines (the Guide states no tolerance; none is invented).
* Assets: available 88,418.13 (July + August statements, Standard = two-month period), undocumented large deposit 3,200.00, eligible 85,218.13 vs funds needed 79,800.00; reserves 2.18 months of the monthly payment amount (5501.2(a)); LPA reserves required 0.00.
* Sage cards cite 5303.1 / 5302.2 (published and effective dates from the Guide record) with `usable: true`; overlay NOT_LOADED ("confirm with AE").
* Whisper draft created, status `draft`; nothing sent.

## Program/AUS identification in every output

Cards, calculation traces, asset and File Prep outputs carry `program: freddie` / `Freddie Mac Conventional`, `aus_system: LPA`, the exact section, the Guide's published and effective dates, the revision id and the overlay state. Freddie's Documentation Level (Streamlined Accept vs Standard) is an explicit input (`documentation_level`); when it is not supplied the workbench assumes Standard and says so.

## SOURCE_GAP remaining (Freddie)

* Bonus/commission/overtime (5303.1(d)(ii)), income commencing after the Note Date (5303.2), temporary leave (5303.3), automated income assessment/AIM (5303.4, 5302.6), tax-return documentation (5302.4), 4506-C (5302.5), third-party verification (5302.3), housing expense ratio (5401.1): captured but without rule records — `pending_review`, not citable.
* Gifts, retirement, business funds, sale proceeds (5501.3(b)-(o) beyond depository), Home Possible/HeritageOne minimums.
* Lender overlays (none loaded).
