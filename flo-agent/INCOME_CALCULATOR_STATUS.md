# Income calculator status (2026-09-08)

Deterministic Decimal arithmetic in `plugins/flo-team/calc.py`; the model never computes. Every result carries inputs, document references, formula id/version, ordered steps with intermediate values, rounding (ROUND_HALF_UP to 0.01 at the final step), result, rule id, source section metadata (title, URL, page date, revision, checksum), warnings and missing inputs. No hidden reasoning is emitted; the trace is the record.

## Production formulas (bound to ACTIVE Selling Guide sections)

| Formula | Section / rule | Status |
|---|---|---|
| `fannie.base_income.monthly` — annual /12; monthly; twice-monthly ×2; biweekly ×26/12; weekly ×52/12; hourly × avg hours/week ×52/12 | B3-3.3-01 calculation table (`fannie.base_income.calc_table`) | **real**, tested for all six frequencies |
| `fannie.variable_income.average_income` — YTD + prior year over months covered (≥12 months); trend detection; decreasing → YTD / months elapsed with a stabilization warning | B3-3.3-01 (`fannie.base_income.variable_average_income`) | real, tested (stable, decreasing, <12 months refused) |
| `fannie.variable_income.average_hours` — average monthly hours (≥12 months) × current fixed hourly rate | B3-3.3-01 (`fannie.base_income.variable_average_hours`) | real, tested |
| `fannie.income.ytd_consistency` — YTD monthly rate as % of qualifying monthly; review flag | B3-3.3-01 (`fannie.base_income.ytd_consistency`) | real; the 5% review tolerance is labelled an internal threshold (the guide requires consistency without a number) |
| `fannie.du.dti_resubmission_check` — DTI change in points; resubmit if >45% or +3 | B3-2-10 (`fannie.du.resubmit_dti`) | real, tested |
| `fannie.reserves.months` — liquid reserves / PITIA | B3-4.1-01 (`fannie.reserves.definition`) | real, tested |
| `fannie.assets.large_deposit_threshold` — 50% of total monthly qualifying income | B3-4.2-02 (`fannie.assets.large_deposit_definition`) | real, tested |

Lock: when the referenced section is not ACTIVE (or its cache checksum changed), the formula returns `SOURCE_GAP` naming the section. Unknown patterns (e.g. `fannie.self_employment.schedule_c`) return `UNSUPPORTED`; nothing is extrapolated.

Remaining TEST_ONLY (synthetic demonstrations, require `allow_test_only`): `test.average_of_periods`, `test.ratio_percent`.

## Malcolm's income review on the golden loan (`golden_path.income_review`)

Biweekly gross 2,538.46 → 5,500.00 monthly (B3-3.3-01 table); YTD consistency 103.8% (within the internal threshold); 2025 W-2 58,900 vs current annualized 66,000 → 12% higher → `NEEDS_REVIEW` with a guideline question routed to Sage (fixed base income with a raise: what documentation supports the current rate — B3-3.3-01 / B3-3.2-02 pay-raise conditions).

## Not supported yet (SOURCE_GAP)

Self-employment (Schedule C, K-1, 1120/1065), rental, other income (SS, pension, alimony…), commission/tip beyond the trend rule, seasonal/temporary, RSU, foreign income; program-specific rounding or trend methods beyond the two B3-3.3-01 methods; any lender overlay.

## Generalization

The engine, gating, trace and status vocabulary are program-agnostic. Adding Freddie/FHA/VA/USDA means new rule records with anchors for their sections and formulas bound to those sections; the Fannie base-income table is Fannie's and must not be reused for other programs without their own source.
