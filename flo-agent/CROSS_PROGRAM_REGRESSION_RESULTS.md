# Cross-program regression results (2026-09-09)

Suite: `tests/flo/test_program_expansion.py` (47 tests) plus the untouched Fannie suite `tests/flo/test_golden_loan.py` (23) and the team suite (67). Run with `TZ=UTC PYTHONUTF8=1 PYTHONHASHSEED=0` on the Windows host; the per-program whole-team cases copy this machine's private source cache into a sandbox Hermes home and activate the slice with a test identity (they skip where the cache is absent).

| Check | Fannie | Freddie | FHA TOTAL | FHA Manual | VA | USDA |
|---|---|---|---|---|---|---|
| Correct agency selected from the file's program (rules, formulas, bindings namespaced) | pass | pass | pass | pass | pass | pass |
| Wrong agency rejected (formula from another program → `UNSUPPORTED` program mismatch; rules never cross programs) | pass | pass | pass | pass | pass | pass |
| Source revision recorded (revision id, checksum, retrieval time, rights) and never shipped active | pass | pass | pass | pass | pass | pass |
| Effective rule / effective date on every citation | pass | pass (Guide effective date) | pass, flagged **not in force** (11/10/2026) | pass, flagged not in force | pass (article update date + topic change dates) | pass (PN revision) |
| Calculation correctness (fixed inputs → expected Decimal result, rounding at final step only) | 23 cases | 5 pay-period cases + fluctuating bands + threshold/reserves/tolerance/DTI | salary, hourly two-year average, raise option, OT/bonus/tip lesser-of, threshold | same + PTI/DTI vs chart | tables parsed from text (3 cases + SOURCE_GAP case), residual, check, DTI | annual/adjusted/repayment/ratios |
| Citation format (section, published, effective, revision, official URL, usable flag) | pass | pass | pass | pass | pass | pass |
| AUS terminology preserved (`<System> findings show <result as printed>.`; no "approved") | DU Approve/Eligible | LPA Accept | TOTAL Accept | (n/a in fixture) | DU Approve/Eligible (VA AUS) | GUS Accept / Eligible |
| Missing-doc detection from activated rules only | verbal VOE, page 5 | 10-day PCV, paystub age, large deposit | W-2 2024, reverification, second statement, deposit | (manual bindings unit-tested) | VOE age 120 days, second statement, residual/DTI | VVOE, paystub age, $1,000 deposit, ratios |
| Overlay handling (`NOT_LOADED` → "confirm with AE" on every card) | pass | pass | pass | pass | pass | pass |
| No approval claim (synthesis status, AUS statement, cards, calc traces all `underwriting_decision: false`) | pass | pass | pass | pass | pass | pass |

## Explicit isolation tests

| Test | Result |
|---|---|
| Fannie data cannot invoke Freddie bindings: the Fannie fixture (DU findings) through `fileprep.build_matrix(program="freddie")` produces no `fannie:` provenance and a `needs_review` AUS item "DU findings cannot be applied to a freddie file" | pass |
| FHA TOTAL rules cannot apply to a manual file: `fha.total.*` with `underwriting_method=manual` → `UNSUPPORTED`; a manual question matched with `underwriting_method="manual"` returns only manual records; an FHA formula without a method → `NEEDS_INPUT["underwriting_method"]` | pass |
| VA residual income cannot run on a Fannie file: `va.residual_income.monthly` with `program=fannie` → `UNSUPPORTED` | pass |
| USDA household-income logic cannot run on a conventional file: `usda.annual_income.household` with `program=freddie` → `UNSUPPORTED` | pass |
| `freddie.base_income.monthly` / `fha.total.income.current_salary_monthly` for the wrong program → `UNSUPPORTED` | pass |
| Rule matching filtered by program and method for every program; Fannie rule list passed to a Freddie match returns nothing | pass |
| AUS envelope: DU on Freddie, GUS on Fannie → `mismatch`; review returns no requirements | pass |
| Workbenches fail closed: FHA asset/file-prep without a method, unknown program (`jumbo`) → `ValueError` | pass |
| Cache tampering demotes a section to `STALE_SOURCE` and locks the formula (Fannie test, same code path for all programs) | pass |

## Live cross-program check

The four live loops (`LIVE_AGENT_HANDOFF_RESULTS.md`) each stayed inside their own program: Freddie cards cited only 5xxx Guide sections, FHA cards only II.A.4/II.A.1 TOTAL sections with the not-in-force caution, VA only Chapter 4, USDA only HB-1-3555 sections; every calculator the bots invoked carried the file's program; no DU wording appeared on the Freddie file and no "approved" appeared anywhere.

## Full regression

* `tests/flo`: 152 passed (Fannie 23 unchanged, team 67, program expansion 47, redaction 3, delivery workdir 2, others); final rerun after the last edits: `tests/flo` + Flo policy plugin + Flo mortgage skills = 250 passed.
* `tests/plugins`, `tests/skills`: 3629 passed, 23 failed — all environmental on this Windows host and in code untouched by this work (optional `hindsight-client` not installed, symlink privilege, `os.geteuid`, CRLF, temp-path handling, langfuse log assertion); recorded in the Windows baseline note.
* Desktop suites unchanged by this work (no desktop files touched); see `FULL_TEST_RERUN.md` for the last full desktop run.
