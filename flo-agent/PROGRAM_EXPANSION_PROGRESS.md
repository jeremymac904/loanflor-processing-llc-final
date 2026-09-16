# Program expansion progress (2026-09-09)

Sequence as directed: Freddie Mac conventional → FHA → VA → USDA Guaranteed, one narrow Golden Loan Path each, on the proven Fannie infrastructure. Architecture unchanged: official source → versioned cache → checksum → rule records → regression anchors → human activation → Sage Guideline Card → deterministic calculator → Malcolm File Prep → synthetic loan → live Flo/Sage/Malcolm validation. Non-QM / Jumbo / investor-specific underwriting not started (by instruction).

Checkpoint before starting: `a8b130c8e776f94d8f35791780c8b9fcaa9af74c` (2026-09-09, tag `flo/fannie-golden-loan-path-2026-09-09`); Fannie tests preserved (23/23) and the activated Fannie rules untouched. Code checkpoint after the build: `11f98d7197`.

## 1. Active sections by program (this install)

| Program | Active sections | Rule records | Note |
|---|---|---|---|
| Fannie Mae | 12 (B1-1-03, B3-2-10, B3-2-11, B3-3.1-01, B3-3.1-04, B3-3.2-01, B3-3.2-02, B3-3.3-01, B3-3.3-02, B3-4.1-01, B3-4.2-01, B3-4.2-02) | 34 | unchanged; approval records migrated to the structured identity schema |
| Freddie Mac | 11 (5101.1, 5101.2, 5101.3, 5102.4, 5301.1, 5302.2, 5303.1, 5401.2, 5501.1, 5501.2, 5501.3) | 36 | 9 more sections captured for context (`pending_review`) |
| FHA | 8 (II.A.1.a.i(A)(1); II.A.4.a/c/d/e TOTAL; II.A.5.b/c/d Manual) | 31 (18 total, 12 manual, 1 shared) | all effective 11/10/2026 → `in_force: false` caution |
| VA | 1 (Chapter 4, one KnowVA article, 107k chars) | 20 | topic change dates recorded |
| USDA | 6 (9.3, 9.5, 9.7-9.8, 9-A, 5.3, 11.2-11.3) | 20 | 9.4 captured, no rules |

## 2. Production calculations by program

| Program | Formulas |
|---|---|
| Fannie | 7 (unchanged) |
| Freddie | `freddie.base_income.monthly`, `freddie.fluctuating_hourly.average`, `freddie.assets.large_deposit_threshold`, `freddie.reserves.months`, `freddie.lpa.dti_resubmission_check`, `freddie.dti.ratio` |
| FHA TOTAL | `fha.total.income.current_salary_monthly`, `fha.total.income.hourly_varying_average`, `fha.total.income.overtime_bonus_tip`, `fha.total.assets.large_deposit_threshold` |
| FHA Manual | the same four as `fha.manual.*` plus `fha.manual.ratios.pti_dti` |
| VA | `va.residual_income.required` (tables parsed from official text), `va.residual_income.monthly`, `va.residual_income.check`, `va.dti.ratio` |
| USDA | `usda.annual_income.household`, `usda.adjusted_annual_income`, `usda.repayment_income.monthly`, `usda.ratios.piti_td` |

All bound to ACTIVE sections; program (and FHA method) mismatches return `UNSUPPORTED`; every trace carries program, section, revision, effective date and in-force flag.

## 3. SOURCE_GAP remaining

* Fannie: unchanged from `FLO_GOLDEN_LOAN_PATH.md`.
* Freddie: bonus/commission/overtime detail, income after Note Date, temporary leave, AIM/automated assessment, tax-return and 4506-C documentation, third-party verification, housing expense ratio (captured, no rules); gifts/retirement/business/sale-proceeds assets; overlays.
* FHA: the currently in-force (pre-Update-18) text; part-time/seasonal/family-business/commission/self-employment income; gifts, retirement, MRI sourcing, reserves beyond definitions; credit; property; MIP.
* VA: pay-period conversion, other income types, tax and social security amounts (inputs), deposit-sourcing thresholds, gifts, entitlement/funding fee.
* USDA: area income limits and deduction amounts (inputs), pay-period conversion, overtime/bonus trend analysis, self-employment, rental, income from assets (9.4), document age, waiver compensating-factor specifics.
* All programs: self-employed (Schedule C/1065/1120/1120-S/K-1/P&L/balance sheet) and rental (Schedule E/lease/rent schedule/departing residence/rental loss) — data structures only, formulas SOURCE_GAP by design.

## 4. AUS handling by program

Common envelope (`aus.py`): DU (Fannie), LPA (Freddie), TOTAL via DU/LPA (FHA), DU/LPA as VA-approved AUS (VA), GUS (USDA). Result wording preserved; wrong system for a program → `mismatch`; tolerance checks only where an activated rule exists (Fannie B3-2-10, Freddie 5101.3(b)); guide-vs-findings employment-verification conflicts routed to Sage. `AUS_NORMALIZATION.md`.

## 5. Malcolm coverage

`fileprep.build_matrix(program=…)` bindings for all five programs (paystub age, W-2 years, employment verification item, income calculation line, statements per program rule, deposit sourcing, AUS report, document age, VA residual worksheet, USDA three-income worksheet); provenance `<program>:<section>` / `<aus>:<message>` / workflow / ashley. Asset workbench bindings for all five (Freddie Documentation Level; FHA method; VA VOD-or-two-statements; USDA $1,000 non-recurring and recurring-deposit investigation).

## 6. Sage citation coverage

`cards.py` standard card for every program: Program, Agency, Underwriting Method, Topic, Source, Section, Published, Effective, Revision, AUS, Lender Overlay, Investor Overlay, Guideline-Supported Conclusion, Calculation Trace, Missing Documentation, Conflict/Caution, Best Next Move; `summary` (one screen) + `details` (citations, pending revisions); `render_text()` concise view. Rule matching is filtered by program and FHA method; not-in-force sections add a caution automatically.

## 7. Live handoff results

All four programs completed the full loop live — Flo → Malcolm → Sage → Malcolm → Flo with model-generated replies, then a live Whisper draft — from one Flo query each (`LIVE_AGENT_HANDOFF_RESULTS.md` has the per-hop tables, ids and calc ids):

| Program | Deal Room | Elapsed | Readiness (final) | Sage citations | Draft |
|---|---|---|---|---|---|
| Freddie | `loan_f5d43116111d` | ≈13 min | BLOCKED 17/100 | 5302.2, 5303.1, 5501.1, 5102.4 | `draft_39c96f1e478b` |
| FHA TOTAL | `loan_fcf85b2c914e` | ≈10.5 min | BLOCKED 19/100 | II.A.4.c, II.A.4.d, II.A.1.a.i(A)(1) — SOURCE_GAP for current-effective authority | `draft_d4db4e88bf2c` |
| VA | `loan_ec9516f95fbe` | ≈13 min | BLOCKED 26/100 | Chapter 4 (residual 1,003.00 / 1,053.70 / 105.05%; DTI 61.29%) | internal HOLD `draft_914a5a387ae3` |
| USDA | `loan_d52e3da70bb0` | ≈22 min (12 min provider outage) | BLOCKED 12/100 | 9.3, 9.5, 9.7-9.8, 11.2-11.3 | `draft_4a7b2e8ae3df` (+2 duplicates) |

No send tool was invoked; no bot said "approved"; every figure quoted by a bot came from a tool trace.

## 8. Cross-program isolation results

`CROSS_PROGRAM_REGRESSION_RESULTS.md`: all isolation tests pass (Fannie data cannot invoke Freddie bindings; FHA TOTAL cannot apply to a manual file; VA residual cannot run on Fannie; USDA household income cannot run on conventional; DU-on-Freddie and GUS-on-Fannie envelopes flagged).

## 9. Provider / model performance

Codex (`gpt-6-astra`) reached its usage limit (HTTP 429, `usage_limit_reached`, reset 17:24 UTC) at the first live turn; opencode-free `deepseek-v4-flash-free` answered "Model is unavailable" even though the discovery smoke had passed; Nous Portal (`nous`, `openai/gpt-6-astra` 24 s round trip, `deepseek/deepseek-v4-flash-0731` 12–15 s) passed and was used. Observed per-hop wall clock on gpt-6-astra: Flo 45–75 s, Malcolm 1–2.5 min, Sage 1.7–3.7 min, Whisper 25–70 s. Mid-way through the USDA run Nous returned HTTP 402 (credits insufficient for a gpt-6-astra request); the profiles were moved to `deepseek/deepseek-v4-flash-0731` on the same provider and the chain resumed (Malcolm ≈ 1.5 min, Sage 2 min, Whisper 1.2 min per hop). `nous_portal` added to `providers.yaml`. Local Ollama remains `slow` (≈ 42 s per probe); sensitive routing still fails closed.

## 10. Full regression results

`tests/flo` 152 passed; `tests/plugins` + `tests/skills` 3629 passed / 23 environmental failures in untouched plugins (Windows baseline). Details in `CROSS_PROGRAM_REGRESSION_RESULTS.md`.

## 11. New security findings

* No official text, token, MCP URL or auth file is committed (verified with `git status`/`.gitignore`; the caches live under `%LOCALAPPDATA%\hermes\flo\sources\cache`).
* rd.usda.gov blocks bare clients (Akamai 403) — the fetcher sends browser-style headers; documented, not hidden. Freddie's Guide and VA's KnowVA expose JSON APIs behind their JS apps; both are the official sites' own data channels and are recorded as `capture_method: official_json_api`.
* Approval records no longer hold free-text approver names only; identity source is explicit and no e-mail is stored (the sandbox classifier that blocked an e-mail on the command line last pass is now moot).
* The opencode-free discovery smoke can pass while the model is unavailable for a real turn: the health check is not a guarantee; the installer's route choice should be re-verified before an interactive session (open question #27).
* Provider exhaustion mid-chain (Nous HTTP 402) leaves a specialist task in `received` with a stored readiness result; the chain resumed cleanly from a direct continuation instruction, but there is no automatic retry/route-over — a `pre_llm_call`-level fallback is still unimplemented (decision D8's honest limit).
* `flo_draft action=create` has no idempotency guard: the deepseek model created the same draft three times in one turn (open question #31). Nothing was sent; the duplicates are visible in the Deal Room.
* Sage's role policy refused her attempt to write an export file into a loan folder (read-only for Sage); she reported the refusal rather than working around it.
* A model can still assert more than the cached text: Sage called a dependent deduction "not recognized" when the cached 9.5 text lists the category but not the amount (open question #32). The cards themselves stayed within the activated sections; the overreach was in her prose.

## 12. Highest-value source library next

1. FHA: fetch and activate the currently in-force Handbook version alongside Update 18 (case-number-date selection).
2. Freddie: rule records for the captured 5303.1(d)(ii) bonus/commission/overtime, 5302.4 tax returns, 5303.4/5302.6 AIM.
3. Fannie/Freddie/FHA self-employment sections (B3-3.2-01/B3-3.4-*, 5304.1, II.A.4.c.x/II.A.5.b.x) to give the new data structures their formulas.
4. Rental income (B3-3.1-08, 5306.1, FHA rental) for the departing-residence pattern.
5. VA Chapter 4 Topic 2/3 detail (income types, tax tables) and USDA Attachment 9-C deductions + area income limits.
6. Lender overlays (Loan Factory) as an overlay pack — the one layer every card still reports NOT_LOADED.
