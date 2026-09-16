# Source diff and rule impact (2026-09-09)

## Source diff (`plugins/flo-team/sourcediff.py`)

Two comparison modes:

* `compare_versions(program, "update-17", "update-18")` — versioned programs (FHA today);
* `compare_snapshots(program, previous_sections_json)` / `compare_with_snapshot` — programs whose sections are re-fetched in place (Fannie, Freddie, VA, USDA); the fetchers keep `sections.previous.json` via `save_snapshot`, and `sources.record_section` now also writes a versioned copy of every text (`<section>.<sha12>.txt`) so both revisions' text stay available.

Output per program: `new_sections`, `removed_sections`, `changed_sections` (old/new key, checksums, effective dates, character counts, and a paragraph-level text diff with similarity ratio and the added/removed sentences), `unchanged_sections`, `changed_rule_records` (anchors that no longer match the new text), `affected_calculators`, `affected_workflows`, `affected_tests`, `affected_evals`, and a summary sentence.

Real run on this install (`python scripts/flo/knowledge_center.py --diff fha`):

> FHA update: 0 new, 0 removed, 8 changed section(s); 1 rule record(s) need re-anchoring; affects 30 active rule(s), 9 calculator(s) and 5 regression scenario(s).

II.A.4.c similarity 0.937 (+69 / −91 sentences), II.A.5.b 0.938, II.A.4.e 0.939, the asset and document-age sections above 0.99. The one re-anchor is the TOTAL traditional-documentation rule whose wording changed from "written Verification of Employment (VOE)" to "WVOE" — exactly the record that now exists in two versions.

## Rule impact (`plugins/flo-team/impact.py`)

For every rule record: calculators (formula `rule_ref` or same section number), File Prep bindings, asset workbench bindings, Guideline Card topics, synthetic evals (the program's golden fixture) and test files (text scan of `tests/flo` for the section number or rule id), plus the Malcolm matrix name.

`affected(program, changed_rule_ids, changed_sections)` → affected_rule → affected_calculator → affected_workflow → affected_tests, with the summary "*Program* update affects N rule record(s) (M active), C calculator(s), W File Prep/asset binding(s) and S regression scenario(s)."

Surfaces: `flo_knowledge action=diff|impact` (read-only for bots), `scripts/flo/knowledge_center.py --diff/--impact`, and the Knowledge Center row (impact summary per section revision).

## Tests

`tests/flo/test_reliability_regression.py::TestSourceDiffAndImpact` (FHA version diff with real cache when present, impact index links for Freddie, snapshot diff with removed/changed/new sections).
