# FHA current-vs-future rule resolution (2026-09-09)

## Sources on record (both, neither overwritten)

| Version | Source | Issued | Section effective dates (captured slices) | Trigger |
|---|---|---|---|---|
| CURRENT — Update 17 | `hud.gov/sites/default/files/OCHCO/documents/40001-hsgh-Update-17.pdf` (the "currently published" link on HUD's Handbook 4000.1 page; previous versions on the HUD Archives site) | 11/26/2025 | II.A.4.a 11/07/2023 · II.A.4.c 04/10/2025 · II.A.4.d 08/19/2024 · II.A.4.e 09/14/2015 · II.A.5.b 04/10/2025 · II.A.5.c 08/19/2024 · II.A.5.d 08/19/2024 · II.A.1.a.i(A)(1) 03/19/2025 | in force |
| FUTURE — Update 18 | `…/Housing/documents/40001-hsgh-Update-18.pdf` | 08/12/2026 | all captured sections 11/10/2026 | transmittal §3: "All other changes: May be implemented immediately, but must be implemented no later than November 10, 2026." |

Section keys are version-qualified (`II.A.4.c@update-17`, `II.A.4.c@update-18`) with `section_number`, `version`, `effective_date`, `issued_date`, `mandatory_date`, `version_note`; rule records are versioned the same way (`fha.total.income.salary_calculation@update-17` / `@update-18`, 60 records), every anchor verified against its own version's text. The only rule whose text differs between versions is TOTAL traditional current-employment documentation (Update 17: "written Verification of Employment (VOE) covering two years"; Update 18: "WVOE"/"EVOE"), preserved as two records.

## Deterministic selection (`sources.resolve_section` / `resolve_rule`, `checks_for(relevant_date=…)`)

```
resolve_rule(program="fha", topic=..., relevant_date=..., underwriting_method=...)
```

* relevant date = the FHA **case number assignment date** when supplied (`case_number_assignment_date` on every tool, `workspace.case_number_assignment_date` in fixtures), else today;
* the applicable version is the latest whose effective date is on or before the relevant date → **CURRENT**; later versions → **FUTURE — NOT YET EFFECTIVE**; earlier ones → **SUPERSEDED**;
* program-specific nuance preserved: with `early_implementation=True` and a relevant date on/after the transmittal's issue date, the future version is selected and labelled **CURRENT (early implementation elected)** with a caution to record the lender's election;
* versions never blend: `applicable` / `future` / `superseded` are disjoint lists, and a bare section number in a calculator, asset or File Prep binding resolves to exactly one version for the date in play.
* an administrator may activate the future version ahead of time; it still is not usable for an earlier relevant date (status "active but future for the relevant date; not applicable").

Sage's Guideline Card shows `effective_status` (CURRENT / FUTURE — NOT YET EFFECTIVE / SUPERSEDED / CURRENT (early implementation elected)), the relevant date and its basis, and lists future versions with their mandatory date; the text rendering prints the FUTURE line explicitly.

## Tests (`tests/flo/test_fha_effective_dates.py`, 13 cases) and results

| Scenario | Expected | Result |
|---|---|---|
| both versions recorded, distinct checksums/revisions, Update 18 not overwritten | pass | pass |
| rule records versioned; differing text preserved | pass | pass |
| 2026-09-09 → `II.A.4.c@update-17` CURRENT, Update 18 FUTURE | pass | pass |
| 2026-11-09 → Update 17 | pass | pass |
| 2026-11-10 → `II.A.4.c@update-18` CURRENT, Update 17 SUPERSEDED | pass | pass |
| 2027-01-15 → Update 18 | pass | pass |
| 2026-10-01 without election → Update 17; with `early_implementation` → Update 18 (EARLY_IMPLEMENTATION); election before 08/12/2026 issue date → Update 17 | pass | pass |
| `resolve_rule` never blends (disjoint applicable/future/superseded across the date boundary) | pass | pass |
| bare section number resolves for calculators and bindings; calc trace carries the version | pass | pass |
| active future version not usable before its date | pass | pass |
| card labels CURRENT and FUTURE — NOT YET EFFECTIVE; text rendering shows both; later date shows SUPERSEDED | pass | pass |
| early implementation labelled on the card | pass | pass |
| whole-team FHA golden path with case number assigned 2026-08-25 cites only `@update-17` and carries the FUTURE caution | pass | pass |

Reliability scenarios 1 and 2 ("future FHA rule incorrectly selected early", "current FHA rule incorrectly selected late") are the parametrized date cases above.

## Activation on this install

`activate_sources.py --program fha --review/--approve/--activate`: 16 section revisions active (8 Update 17, 8 Update 18), approver identity `explicit:owner`, reason "Reliability pass 2026-09-09: Handbook 4000.1 Update 17 (in force) and Update 18 (mandatory 11/10/2026) recorded side by side; anchors verified for both".
