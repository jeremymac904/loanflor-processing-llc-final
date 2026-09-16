"""FHA current-vs-future rule resolution (Handbook 4000.1 Update 17 in force, Update 18 mandatory 11/10/2026).

Deterministic effective-date selection over version-qualified section keys:
``II.A.4.c@update-17`` (effective 04/10/2025) and ``II.A.4.c@update-18`` (effective 11/10/2026;
"may be implemented immediately, but must be implemented no later than November 10, 2026").
The relevant date for FHA is the case number assignment date. Versions never blend.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
NOWHERE = Path("/nonexistent")
MANDATORY = "2026-11-10"
ALL_ACTIVE = lambda s: True  # noqa: E731


@pytest.fixture(scope="session")
def ft():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    names = ("sources", "cards", "calc", "fileprep", "assets", "knowledge")
    for name in names:
        importlib.import_module(f"flo_team.{name}")
    return {name: sys.modules[f"flo_team.{name}"] for name in names}


class TestVersionRegistry:
    def test_both_versions_recorded_without_overwrite(self, ft):
        s = ft["sources"]
        sections = s.load_sections("fha")
        for number in ("II.A.4.a", "II.A.4.c", "II.A.4.d", "II.A.4.e", "II.A.5.b", "II.A.5.c", "II.A.5.d", "II.A.1.a.i(A)(1)"):
            keys = {v["key"] for v in s.section_versions("fha", number)}
            assert keys == {f"{number}@update-17", f"{number}@update-18"}, number
        u18 = sections["II.A.4.c@update-18"]
        u17 = sections["II.A.4.c@update-17"]
        assert u18["effective_date"] == "11/10/2026" and u18["mandatory_date"] == "11/10/2026" and u18["issued_date"] == "08/12/2026"
        assert u17["effective_date"] == "04/10/2025" and u17["mandatory_date"] is None
        assert u18["checksum_text"] != u17["checksum_text"] and u18["revision_id"] != u17["revision_id"]
        assert "may be implemented immediately" in u18["version_note"]

    def test_rule_records_are_versioned_and_differ_where_the_text_differs(self, ft):
        rules = {r["rule_id"]: r for r in ft["sources"].load_rules("fha")}
        u17 = rules["fha.total.income.traditional_documentation@update-17"]
        u18 = rules["fha.total.income.traditional_documentation@update-18"]
        assert u17["section"] == "II.A.4.c@update-17" and u18["section"] == "II.A.4.c@update-18"
        assert "written Verification of Employment (VOE)" in u17["anchor"] and "WVOE" in u18["anchor"]


class TestResolution:
    @pytest.mark.parametrize("when,expected_key,expected_status", [
        ("2026-09-09", "II.A.4.c@update-17", "CURRENT"),
        ("2026-11-09", "II.A.4.c@update-17", "CURRENT"),
        ("2026-11-10", "II.A.4.c@update-18", "CURRENT"),
        ("2027-01-15", "II.A.4.c@update-18", "CURRENT"),
    ])
    def test_date_selects_exactly_one_version(self, ft, when, expected_key, expected_status):
        res = ft["sources"].resolve_section("fha", "II.A.4.c", relevant_date=when)
        assert res["key"] == expected_key and res["resolution"] == expected_status
        assert res["relevant_date_basis"] == "case number assignment date"
        statuses = {c["key"]: c["status"] for c in res["candidates"]}
        other = "II.A.4.c@update-18" if expected_key.endswith("update-17") else "II.A.4.c@update-17"
        assert statuses[other] == ("FUTURE" if expected_key.endswith("update-17") else "SUPERSEDED")

    def test_before_mandatory_date_is_not_update_18_unless_early_implementation(self, ft):
        s = ft["sources"]
        assert s.resolve_section("fha", "II.A.4.c", relevant_date="2026-10-01")["key"] == "II.A.4.c@update-17"
        early = s.resolve_section("fha", "II.A.4.c", relevant_date="2026-10-01", early_implementation=True)
        assert early["key"] == "II.A.4.c@update-18" and early["resolution"] == "EARLY_IMPLEMENTATION"
        # early implementation cannot predate the transmittal's issue date
        assert s.resolve_section("fha", "II.A.4.c", relevant_date="2026-08-01", early_implementation=True)["key"] == "II.A.4.c@update-17"

    def test_resolve_rule_never_blends(self, ft):
        s = ft["sources"]
        before = s.resolve_rule("fha", "salary calculation of effective income", relevant_date="2026-09-09", underwriting_method="total", root=NOWHERE)
        after = s.resolve_rule("fha", "salary calculation of effective income", relevant_date="2026-12-01", underwriting_method="total", root=NOWHERE)
        assert before["applicable"] and all(r["version"] == "update-17" for r in before["applicable"])
        assert before["future"] and all(r["version"] == "update-18" for r in before["future"]) and not before["superseded"]
        assert after["applicable"] and all(r["version"] == "update-18" for r in after["applicable"])
        assert after["superseded"] and all(r["version"] == "update-17" for r in after["superseded"]) and not after["future"]
        assert not {r["rule_id"] for r in before["applicable"]} & {r["rule_id"] for r in after["applicable"]}

    def test_bare_section_number_resolves_for_calculators_and_bindings(self, ft):
        s, calc = ft["sources"], ft["calc"]
        st_now = s.section_status("fha", "II.A.4.c", None, NOWHERE, relevant_date="2026-09-09")
        st_later = s.section_status("fha", "II.A.4.c", None, NOWHERE, relevant_date="2026-12-01")
        assert st_now.section == "II.A.4.c@update-17" and st_later.section == "II.A.4.c@update-18"
        # a formula bound to the bare number reports the resolved version in its source metadata
        active, meta = s.checks_for("fha", None, NOWHERE, relevant_date="2026-09-09")
        res = calc.run("fha.total.income.current_salary_monthly", {"current_salary_or_rate": "4800", "pay_frequency": "monthly"},
                       active_check=ALL_ACTIVE, source_meta=meta, program="fha", underwriting_method="total")
        assert res.status == "SUCCESS" and res.source["section"] == "II.A.4.c@update-17" and res.source["version"] == "update-17"
        active2, meta2 = s.checks_for("fha", None, NOWHERE, relevant_date="2026-12-01")
        res2 = calc.run("fha.total.income.current_salary_monthly", {"current_salary_or_rate": "4800", "pay_frequency": "monthly"},
                        active_check=ALL_ACTIVE, source_meta=meta2, program="fha", underwriting_method="total")
        assert res2.source["section"] == "II.A.4.c@update-18"

    def test_active_future_version_is_not_usable_before_its_date(self, ft, tmp_path):
        """An administrator may activate Update 18 ahead of time; it still is not applied to an earlier case."""
        s = ft["sources"]
        state = ft["knowledge"].KnowledgeState(tmp_path)
        st = s.section_status("fha", "II.A.4.c@update-18", state, NOWHERE, relevant_date="2026-09-09")
        assert st.resolution == "FUTURE" and not st.usable


class TestCards:
    def test_card_shows_current_and_future_labels(self, ft, tmp_path):
        state = ft["knowledge"].KnowledgeState(tmp_path)
        card = ft["cards"].guideline_card(program="fha", topic="salary calculation of effective income", state=state, root=NOWHERE,
                                          underwriting_method="total", relevant_date="2026-09-09")
        assert card["effective_status"] == "CURRENT" and card["version"] == "update-17" and card["relevant_date"] == "2026-09-09"
        assert card["details"]["future_citations"] and card["details"]["future_citations"][0]["resolution_label"] == "FUTURE — NOT YET EFFECTIVE"
        assert any("FUTURE — NOT YET EFFECTIVE" in c and "11/10/2026" in c for c in card["conflict_or_caution"])
        text = ft["cards"].render_text(card)
        assert "CURRENT" in text and "FUTURE — NOT YET EFFECTIVE" in text
        later = ft["cards"].guideline_card(program="fha", topic="salary calculation of effective income", state=state, root=NOWHERE,
                                           underwriting_method="total", relevant_date="2026-12-01")
        assert later["version"] == "update-18" and later["details"]["superseded_citations"] and not later["details"]["future_citations"]

    def test_early_implementation_is_labelled(self, ft, tmp_path):
        state = ft["knowledge"].KnowledgeState(tmp_path)
        card = ft["cards"].guideline_card(program="fha", topic="salary calculation of effective income", state=state, root=NOWHERE,
                                          underwriting_method="total", relevant_date="2026-10-01", early_implementation=True)
        assert card["version"] == "update-18" and card["effective_status"] == "CURRENT (early implementation elected)"
        assert any("Early implementation elected" in c for c in card["conflict_or_caution"])
