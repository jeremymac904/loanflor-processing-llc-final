"""Source-bound prose: Sage cannot materially overstate activated rules without validation catching it."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"


@pytest.fixture(scope="session")
def ft():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    for name in ("sage_response", "cards", "knowledge", "calc"):
        importlib.import_module(f"flo_team.{name}")
    return {name: sys.modules[f"flo_team.{name}"] for name in ("sage_response", "cards", "knowledge", "calc")}


def _card(rules, *, future=(), source_gap=False):
    cites = [{"rule_id": f"r{i}", "section": s, "rule": t, "usable": True, "resolution": "CURRENT", "resolution_label": "CURRENT", "effective": "01/01/2026",
              "version": None, "revision_id": "rev", "official_url": "https://example.invalid", "lifecycle": "active", "section_number": s} for i, (s, t) in enumerate(rules)]
    fut = [{"rule_id": f"f{i}", "section": s, "rule": t, "usable": False, "resolution": "FUTURE", "resolution_label": "FUTURE — NOT YET EFFECTIVE", "effective": "11/10/2026",
            "version": "update-18", "revision_id": "rev2", "official_url": "https://example.invalid", "lifecycle": "active", "section_number": s} for i, (s, t) in enumerate(future)]
    return {"topic": "t", "citations": cites, "details": {"future_citations": fut, "pending_revisions": []}, "conflict_or_caution": ["Overlay not loaded — confirm with AE."],
            "conclusion": "SOURCE_GAP" if source_gap else "ok", "confidence": "none" if source_gap else "source-backed", "missing_documentation": []}


USDA_RULES = [
    ("9.5", "Adjusted annual income is the annual income minus the eligible deductions in 7 CFR 3555.152(c) (dependents, child care, elderly household, care of household members with disabilities, medical expenses); it determines program eligibility."),
    ("9.3", "Include only the first $480 of earned income from adult full-time students who are not an applicant or an applicant's spouse."),
    ("11.2-11.3", "Applicants have repayment ability when the proposed monthly housing expense (PITI) does not exceed 29 percent of repayment income."),
]


class TestBuild:
    def test_bound_object_has_the_five_lists_and_allowed_numbers(self, ft):
        sr = ft["sage_response"]
        calc = {"calc_id": "calc_x", "formula_id": "usda.adjusted_annual_income", "status": "SUCCESS", "result": "64320.00", "unit": "USD", "period": "annual",
                "inputs": {"annual_income": "65280", "eligible_deductions": "[\"480\", \"480\"]"}, "steps": [], "warnings": [], "source": {"section": "9.5"}}
        bound = sr.build(cards=[_card(USDA_RULES)], calculations=[calc], aus_envelope={"statement": "GUS findings show Accept / Eligible.", "dti": "42.8"})
        for key in ("supported_claims", "calculation_results", "source_refs", "warnings", "source_gaps"):
            assert key in bound
        nums = set(bound["allowed_facts"]["numbers"])
        assert {"480", "29", "64320", "65280", "42.8"} <= nums
        assert bound["underwriting_decision"] is False and bound["digest"]
        text = sr.render(bound)
        assert "Not an underwriting decision." in text and "GUS findings show Accept / Eligible." in text


class TestValidator:
    @pytest.fixture()
    def bound(self, ft):
        calc = {"calc_id": "calc_x", "formula_id": "usda.adjusted_annual_income", "status": "SUCCESS", "result": "64320.00", "inputs": {"annual_income": "65280"}, "steps": [], "warnings": [], "source": {"section": "9.5"}}
        return ft["sage_response"].build(cards=[_card(USDA_RULES)], calculations=[calc], aus_envelope={"statement": "GUS findings show Accept / Eligible.", "dti": "42.8"})

    def test_supported_prose_passes(self, ft, bound):
        text = ("Guideline-supported assessment. Adjusted annual income is the annual income minus the eligible 7 CFR 3555.152(c) deductions (dependents, child care, elderly household, care of household members with disabilities, medical expenses). "
                "Only the first $480 of an adult full-time student's earned income is included. PITI must not exceed 29 percent of repayment income. "
                "The calculation returned 64,320.00 from annual income 65,280. GUS findings show Accept / Eligible. Not an underwriting decision.")
        result = ft["sage_response"].validate(text, bound)
        assert result["ok"], result["violations"]

    def test_unsupported_deduction_amount_fails(self, ft, bound):
        text = "The dependent deduction is $960 per year, which is not a recognized 7 CFR 3555.152(c) deduction."
        result = ft["sage_response"].validate(text, bound)
        kinds = {v["kind"] for v in result["violations"]}
        assert not result["ok"] and "unsupported_dollar" in kinds

    @pytest.mark.parametrize("sentence,kind", [
        ("The total debt ratio may not exceed 43 percent of repayment income.", "unsupported_percent"),
        ("Reserves of $5,000 are required after closing.", "unsupported_dollar"),
        ("A two-year history of receipt is required for this income.", "unsupported_years"),
        ("Provide bank statements covering the most recent 3 months.", "unsupported_months"),
        ("Three months of reserves are required for this program.", "unsupported_months"),
        ("Qualifying ratios are limited to 31/43 without compensating factors.", "unsupported_ratio"),
        ("The paystub must be no more than 45 days old.", "unsupported_days"),
    ])
    def test_material_assertions_outside_the_source_fail(self, ft, bound, sentence, kind):
        result = ft["sage_response"].validate(sentence, bound)
        assert not result["ok"]
        assert kind in {v["kind"] for v in result["violations"]}, result["violations"]

    def test_calendar_dates_and_revision_ids_are_not_ratios(self, ft, bound):
        # Seen live 2026-09-09: Sage's first draft cited "section date 11/26/2025, effective 04/10/2025" and the
        # validator read 11/26 and 04/10 as qualifying-ratio pairs.
        text = ("Handbook 4000.1 II.A.4.c (Update 17; section date 11/26/2025, effective 04/10/2025) governs; "
                "revision fha-ii.a.4.c_update-17-104476516c85. Update 18 is FUTURE — NOT YET EFFECTIVE (mandatory 11/10/2026).")
        result = ft["sage_response"].validate(text, bound)
        assert not [v for v in result["violations"] if v["kind"] == "unsupported_ratio"], result["violations"]
        assert not ft["sage_response"].validate("Qualifying ratios are limited to 31/43 here.", bound)["ok"]

    def test_rule_like_assertion_without_support_fails_but_glue_is_ignored(self, ft, bound):
        sr = ft["sage_response"]
        assert not sr.validate("Gift funds are not permitted on this program.", bound)["ok"]
        glue = "Hi Ashley, here is the summary. Thanks! Next, Malcolm will re-score the file."
        assert sr.validate(glue, bound)["ok"]

    def test_rewrite_drops_only_the_unsupported_sentences(self, ft, bound):
        sr = ft["sage_response"]
        text = ("Only the first $480 of an adult full-time student's earned income is included. "
                "The dependent deduction is $960 per year and is not a recognized deduction. "
                "GUS findings show Accept / Eligible.")
        out = sr.rewrite(text, bound)
        assert out["ok"] and out["validated_after_rewrite"]
        assert "$960" not in out["text"] and "$480" in out["text"] and "removed by the source-bound validator" in out["text"]

    def test_numbers_from_calculation_traces_and_future_rules_are_handled(self, ft):
        sr = ft["sage_response"]
        bound = sr.build(cards=[_card([("II.A.4.c@update-17", "use the current salary to calculate Effective Income")], future=[("II.A.4.c@update-18", "pay stubs must cover a minimum of 28 consecutive Days")])],
                         calculations=[{"calc_id": "c", "formula_id": "fha.total.income.current_salary_monthly", "status": "SUCCESS", "result": "4800.00", "inputs": {"current_salary_or_rate": "57600"}, "steps": [], "warnings": [], "source": {"section": "II.A.4.c@update-17"}}])
        assert sr.validate("Effective Income is 4,800.00 per month from a 57,600 salary.", bound)["ok"]
        # A FUTURE rule's number is quotable only inside the FUTURE caution wording, and the caution is carried
        assert any("FUTURE — NOT YET EFFECTIVE" in w for w in bound["warnings"])
        assert sr.validate("FUTURE — NOT YET EFFECTIVE: Update 18 will require pay stubs covering 28 consecutive Days.", bound)["ok"]


class TestHandoffEnforcement:
    def test_sage_cannot_close_a_guideline_card_without_a_validated_response(self, ft, tmp_path, monkeypatch):
        tools = importlib.import_module("flo_team.tools")
        monkeypatch.setattr(tools, "_STATE_ROOT_OVERRIDE", tmp_path / "team")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "flo"))
        monkeypatch.setenv("HERMES_PROFILE_NAME", "flo")
        import json

        h = json.loads(tools.handle_flo_handoff({"action": "create", "to": "sage", "objective": "paystub age question", "return_format": "guideline_card"}))
        monkeypatch.setenv("HERMES_PROFILE_NAME", "sage")
        json.loads(tools.handle_flo_handoff({"action": "receive", "message": h["send_with"]["message"]}))
        refused = json.loads(tools.handle_flo_handoff({"action": "complete", "task_id": h["task_id"], "result": {"status": "completed"}}))
        assert "validated source-bound response" in refused.get("error", "")
        card = _card(USDA_RULES)
        built = json.loads(tools.handle_flo_sage_response({"action": "build", "cards": [card]}))
        bad = json.loads(tools.handle_flo_sage_response({"action": "validate", "response_id": built["response_id"], "text": "Reserves of $5,000 are required."}))
        assert not bad["ok"]
        still = json.loads(tools.handle_flo_handoff({"action": "complete", "task_id": h["task_id"], "result": {"status": "completed", "validated_response_id": built["response_id"]}}))
        assert "error" in still
        good = json.loads(tools.handle_flo_sage_response({"action": "validate", "response_id": built["response_id"], "text": "Only the first $480 of an adult full-time student's earned income is included."}))
        assert good["ok"]
        done = json.loads(tools.handle_flo_handoff({"action": "complete", "task_id": h["task_id"], "result": {"status": "completed", "validated_response_id": built["response_id"]}}))
        assert done["status"] == "completed" and done["result"]["response_digest"]
