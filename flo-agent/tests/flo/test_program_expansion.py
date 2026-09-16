"""Program expansion — Freddie, FHA (TOTAL/Manual), VA, USDA on the proven Fannie infrastructure.

Layers:

* metadata: every program ships sections.json + rules.json with provenance, anchors and
  namespaced rule ids (fannie.* freddie.* fha.total.* fha.manual.* va.* usda.*);
* deterministic calculators per program with injected active checks (no cache needed);
* cross-program isolation matrix (fail closed on program / method mismatch);
* AUS envelope normalization; standard Guideline Card; approval identity;
* whole-team Golden Loan Path per program in a sandbox home that copies this machine's
  private cache (skipped where the cache is absent).
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
FIXTURES = REPO / "tests" / "flo" / "fixtures" / "golden_loan"
PROGRAMS = ("fannie", "freddie", "fha", "va", "usda")
FIXTURE_FOR = {"fannie": "golden_loan.json", "freddie": "freddie_golden_loan.json", "fha": "fha_golden_loan.json", "va": "va_golden_loan.json", "usda": "usda_golden_loan.json"}
ALL_ACTIVE = lambda s: True  # noqa: E731
META = lambda s: {"section": s, "title": f"Section {s}", "official_url": f"https://example.invalid/{s}", "page_date": "03/04/2026", "revision_id": f"rev-{s}", "checksum": "abc"}  # noqa: E731

VA_TABLE_TEXT = (
    "Table 9: Table of Residual Incomes by Region for Loan Amounts of $79,999 and Below | Family Size | Northeast | Midwest | South | West | "
    "1 | $390 | $382 | $382 | $425 | 2 | $654 | $641 | $641 | $713 | 3 | $788 | $772 | $772 | $859 | 4 | $888 | $868 | $868 | $967 | 5 | $921 | $902 | $902 | $1,004 "
    "For Family Size Over 5: Add $75 for each additional member up to a family of seven. "
    "Table 10: Table of Residual Incomes by Region for Loan Amounts of $80,000 and Above | Family Size | Northeast | Midwest | South | West | "
    "1 | $450 | $441 | $441 | $491 | 2 | $755 | $738 | $738 | $823 | 3 | $909 | $889 | $889 | $990 | 4 | $1,025 | $1,003 | $1,003 | $1,117 | 5 | $1,062 | $1,039 | $1,039 | $1,158 "
    "For Family Size Over 5: Add $80 for each additional member up to a family of seven. "
    "Table 11: Key to Geographic Regions Used on the Preceding Tables (Tables 6 and 7) | Geographic Region | States | Northeast | Connecticut, Maine | "
    "Midwest | Illinois, Indiana | South | Alabama, Georgia, Texas | West | Arizona, California | Examples A Veteran"
)


@pytest.fixture(scope="session")
def ft():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    names = ("tools", "fannie", "sources", "cards", "calc", "assets", "aus", "du", "fileprep", "golden_path", "knowledge", "identity", "income_structures", "workspace")
    for name in names:
        importlib.import_module(f"flo_team.{name}")
    return {name: sys.modules[f"flo_team.{name}"] for name in names}


def _fixture(program):
    return json.loads((FIXTURES / FIXTURE_FOR[program]).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# metadata / registry
# ---------------------------------------------------------------------------

class TestMultiProgramRegistry:
    @pytest.mark.parametrize("program", PROGRAMS)
    def test_sections_recorded_with_provenance_and_never_active(self, ft, program):
        sections = ft["sources"].load_sections(program)
        assert sections, program
        for sid, meta in sections.items():
            keys = ("official_url", "retrieved_at", "checksum_text", "revision_id", "rights") + (("capture_method",) if program != "fannie" else ())
            for key in keys:  # the Fannie records predate capture_method and are left untouched (activated rules)
                assert meta.get(key), f"{program} {sid}: {key}"
            assert meta["official_url"].startswith("https://")
            assert meta["lifecycle"] == "detected", "the repository never ships an active revision"
            assert meta["revision_id"].startswith(f"{program}-")

    @pytest.mark.parametrize("program", PROGRAMS)
    def test_rules_are_namespaced_and_anchored(self, ft, program):
        rules = ft["sources"].load_rules(program)
        sections = ft["sources"].load_sections(program)
        assert len(rules) >= 15
        for r in rules:
            assert r["rule_id"].startswith(program + "."), r["rule_id"]
            assert r["program"] == program
            assert r["section"] in sections, f"{r['rule_id']} cites unrecorded section {r['section']}"
            assert r["anchor"] and r["text"] and r["topic"]
        if program == "fha":
            for r in rules:
                if r["section"].startswith("II.A.4."):
                    assert r["underwriting_method"] == "total" and r["rule_id"].startswith("fha.total.")
                if r["section"].startswith("II.A.5."):
                    assert r["underwriting_method"] == "manual" and r["rule_id"].startswith("fha.manual.")
            ids = {r["rule_id"] for r in rules}
            for base in ("fha.total.income.salary_calculation", "fha.manual.income.salary_calculation"):
                assert {f"{base}@update-17", f"{base}@update-18"} <= ids, "both TOTAL/Manual and both Handbook versions preserved"
            assert all(r.get("version") in ("update-17", "update-18") and r.get("section_number") for r in rules)

    def test_no_generic_conventional_rule_and_no_source_text_committed(self):
        for program in PROGRAMS:
            folder = PLUGIN / "knowledge" / program
            assert not list(folder.glob("*.txt")) and not list(folder.glob("*.html")) and not list(folder.glob("*.pdf"))
            assert (folder / "rules.json").stat().st_size < 40_000
        freddie = json.loads((PLUGIN / "knowledge" / "freddie" / "rules.json").read_text(encoding="utf-8"))
        assert not any(r["rule_id"].startswith("conventional.") for r in freddie["rules"])
        assert not (PLUGIN / "knowledge" / "conventional").exists()

    def test_fha_section_versions_resolve_by_date(self, ft):
        s = ft["sources"]
        current = s.section_status("fha", "II.A.4.c", None, Path("/nonexistent"), relevant_date="2026-09-09")
        assert current.section == "II.A.4.c@update-17" and current.resolution == "CURRENT" and current.underwriting_method == "total"
        future = s.section_status("fha", "II.A.4.c@update-18", None, Path("/nonexistent"), relevant_date="2026-09-09")
        assert future.resolution == "FUTURE" and future.effective_date == "11/10/2026" and any("FUTURE — NOT YET EFFECTIVE" in c for c in future.cautions)

    def test_usda_income_fields_stay_distinct(self, ft):
        ids = {f["formula_id"] for f in ft["calc"].list_formulas("usda")}
        assert {"usda.annual_income.household", "usda.adjusted_annual_income", "usda.repayment_income.monthly"} <= ids
        assert not any("qualifying_income" in f for f in ids)


# ---------------------------------------------------------------------------
# calculators per program (active check injected)
# ---------------------------------------------------------------------------

class TestFreddieCalculators:
    def test_base_non_fluctuating_table(self, ft):
        calc = ft["calc"]
        for freq, amt, exp in (("biweekly", "2307.69", "5000.00"), ("weekly", "1153.85", "5000.02"), ("semi_monthly", "2500", "5000.00"), ("monthly", "5000", "5000.00"), ("annual", "60000", "5000.00")):
            res = calc.run("freddie.base_income.monthly", {"gross_pay": amt, "pay_frequency": freq}, active_check=ALL_ACTIVE, source_meta=META, program="freddie")
            assert res.status == "SUCCESS" and res.result == exp, res.to_dict()
            assert res.program == "freddie" and res.source["section"] == "5303.1" and res.rule_ref == "freddie.base_income.calc_table"
        hourly = calc.run("freddie.base_income.monthly", {"gross_pay": "30", "pay_frequency": "hourly", "hours_per_week": "40"}, active_check=ALL_ACTIVE, source_meta=META, program="freddie")
        assert hourly.result == "5200.00"

    def test_fluctuating_hourly_bands(self, ft):
        calc = ft["calc"]
        consistent = calc.run("freddie.fluctuating_hourly.average", {"ytd_amount": "25000", "ytd_months": "5", "prior_year_amount": "58000", "prior_year_months": "12"}, active_check=ALL_ACTIVE, source_meta=META, program="freddie")
        assert consistent.status == "SUCCESS" and consistent.result == "4882.35" and any(s.get("value") == "consistent" for s in consistent.steps)
        raise_ = calc.run("freddie.fluctuating_hourly.average", {"ytd_amount": "30000", "ytd_months": "5", "prior_year_amount": "58000", "prior_year_months": "12"}, active_check=ALL_ACTIVE, source_meta=META, program="freddie")
        assert any("above 10% and up to 30%" in w for w in raise_.warnings)
        declining = calc.run("freddie.fluctuating_hourly.average", {"ytd_amount": "18000", "ytd_months": "5", "prior_year_amount": "58000", "prior_year_months": "12"}, active_check=ALL_ACTIVE, source_meta=META, program="freddie")
        assert declining.result == "3600.00" and any("Declining trend exceeds 10%" in w for w in declining.warnings)

    def test_assets_reserves_tolerance_dti(self, ft):
        calc = ft["calc"]
        assert calc.run("freddie.assets.large_deposit_threshold", {"total_monthly_qualifying_income": "5000"}, active_check=ALL_ACTIVE, source_meta=META, program="freddie").result == "2500.00"
        assert calc.run("freddie.reserves.months", {"reserves": "7440", "monthly_payment_amount": "2480"}, active_check=ALL_ACTIVE, source_meta=META, program="freddie").result == "3.00"
        tol = calc.run("freddie.lpa.dti_resubmission_check", {"aus_dti": "40.1", "recalculated_dti": "43.5"}, active_check=ALL_ACTIVE, source_meta=META, program="freddie")
        assert any("Resubmission to Loan Product Advisor required" in w for w in tol.warnings)
        ok = calc.run("freddie.lpa.dti_resubmission_check", {"aus_dti": "40.1", "recalculated_dti": "42.0"}, active_check=ALL_ACTIVE, source_meta=META, program="freddie")
        assert any("Within Loan Product Advisor" in w for w in ok.warnings)
        dti = calc.run("freddie.dti.ratio", {"monthly_housing_expense": "2480", "monthly_liabilities": "600", "stable_monthly_income": "5000"}, active_check=ALL_ACTIVE, source_meta=META, program="freddie")
        assert dti.result == "61.60" and any("above 45%" in w for w in dti.warnings)


class TestFhaCalculators:
    def test_total_and_manual_are_separate_formulas(self, ft):
        calc = ft["calc"]
        total = calc.run("fha.total.income.current_salary_monthly", {"current_salary_or_rate": "57600", "pay_frequency": "annual"}, active_check=ALL_ACTIVE, source_meta=META, program="fha", underwriting_method="total")
        manual = calc.run("fha.manual.income.current_salary_monthly", {"current_salary_or_rate": "57600", "pay_frequency": "annual"}, active_check=ALL_ACTIVE, source_meta=META, program="fha", underwriting_method="manual")
        assert total.result == manual.result == "4800.00"
        assert total.source["section"] == "II.A.4.c" and manual.source["section"] == "II.A.5.b"
        assert any("plain annualization" in w for w in total.warnings)

    def test_hourly_varying_overtime_and_manual_ratios(self, ft):
        calc = ft["calc"]
        avg = calc.run("fha.total.income.hourly_varying_average", {"prior_year_1_total": "48000", "prior_year_2_total": "52000"}, active_check=ALL_ACTIVE, source_meta=META, program="fha", underwriting_method="total")
        assert avg.result == "4166.67"
        raise_ = calc.run("fha.total.income.hourly_varying_average", {"prior_year_1_total": "48000", "prior_year_2_total": "52000", "documented_pay_increase": True, "average_monthly_hours_12mo": "160", "current_hourly_rate": "30"},
                          active_check=ALL_ACTIVE, source_meta=META, program="fha", underwriting_method="total")
        assert raise_.result == "4800.00"
        ot = calc.run("fha.manual.income.overtime_bonus_tip", {"total_earned_period": "12000", "months_earned": "24", "previous_year_total": "5400"}, active_check=ALL_ACTIVE, source_meta=META, program="fha", underwriting_method="manual")
        assert ot.result == "450.00" and ot.steps[-2]["op"] == "lesser_of"
        ratios = calc.run("fha.manual.ratios.pti_dti", {"total_mortgage_payment": "1910", "other_monthly_obligations": "400", "effective_income": "4800"}, active_check=ALL_ACTIVE, source_meta=META, program="fha", underwriting_method="manual")
        assert ratios.result == "48.13" and any("exceeds 31/43" in w for w in ratios.warnings)
        assert calc.run("fha.total.assets.large_deposit_threshold", {"total_monthly_effective_income": "4800"}, active_check=ALL_ACTIVE, source_meta=META, program="fha", underwriting_method="total").result == "2400.00"


class TestVaCalculators:
    def test_residual_tables_are_parsed_from_official_text(self, ft):
        calc = ft["calc"]
        tables = calc.va_residual_tables(VA_TABLE_TEXT)
        assert tables["80k_and_above"]["rows"][4]["South"] == Decimal("1003") and tables["below_80k"]["over_5_increment"] == Decimal("75")
        req = calc.run("va.residual_income.required", {"family_size": "4", "loan_amount": "285000", "state": "Texas"}, active_check=ALL_ACTIVE, source_meta=META, program="va", source_text=lambda s: VA_TABLE_TEXT)
        assert req.status == "SUCCESS" and req.result == "1003.00"
        big = calc.run("va.residual_income.required", {"family_size": "8", "loan_amount": "150000", "state": "Georgia"}, active_check=ALL_ACTIVE, source_meta=META, program="va", source_text=lambda s: VA_TABLE_TEXT)
        assert big.result == "1199.00" and any("beyond seven" in w for w in big.warnings)
        small = calc.run("va.residual_income.required", {"family_size": "3", "loan_amount": "79999", "state": "Arizona"}, active_check=ALL_ACTIVE, source_meta=META, program="va", source_text=lambda s: VA_TABLE_TEXT)
        assert small.result == "859.00"
        gap = calc.run("va.residual_income.required", {"family_size": "3", "loan_amount": "79999", "state": "Arizona"}, active_check=ALL_ACTIVE, source_meta=META, program="va", source_text=lambda s: "no tables here")
        assert gap.status == "SOURCE_GAP"

    def test_residual_income_check_and_dti(self, ft):
        calc = ft["calc"]
        res = calc.run("va.residual_income.monthly", {"gross_monthly_income": "6200", "federal_income_tax": "620", "state_income_tax": "0", "social_security_and_other_deductions": "474.30",
                                                      "shelter_expense": "2150", "gross_living_area_sqft": "1800", "monthly_debts": "1650"}, active_check=ALL_ACTIVE, source_meta=META, program="va")
        assert res.result == "1053.70" and any(s.get("right") == "0.14" for s in res.steps)
        check = calc.run("va.residual_income.check", {"residual_income": "1053.70", "required_residual": "1003"}, active_check=ALL_ACTIVE, source_meta=META, program="va")
        assert Decimal(check.result) > 100 and any("less than 20 percent" in w for w in check.warnings)
        dti = calc.run("va.dti.ratio", {"housing_expense": "2150", "installment_and_other_obligations": "1650", "gross_monthly_income": "6200"}, active_check=ALL_ACTIVE, source_meta=META, program="va")
        assert dti.result == "61.29" and any("above 41 percent" in w for w in dti.warnings)


class TestUsdaCalculators:
    def test_three_income_figures_and_ratios(self, ft):
        calc = ft["calc"]
        annual = calc.run("usda.annual_income.household", {"adult_member_annual_incomes": ["46800", "18000"], "full_time_student_annual_incomes": ["6000"]}, active_check=ALL_ACTIVE, source_meta=META, program="usda")
        assert annual.result == "65280.00" and annual.period == "annual"
        adjusted = calc.run("usda.adjusted_annual_income", {"annual_income": "65280", "eligible_deductions": "480,480"}, active_check=ALL_ACTIVE, source_meta=META, program="usda")
        assert adjusted.result == "64320.00"
        repayment = calc.run("usda.repayment_income.monthly", {"note_party_monthly_incomes": ["3900"]}, active_check=ALL_ACTIVE, source_meta=META, program="usda")
        assert repayment.result == "3900.00"
        ratios = calc.run("usda.ratios.piti_td", {"piti": "1250", "other_monthly_debts": "420", "repayment_income": "3900"}, active_check=ALL_ACTIVE, source_meta=META, program="usda")
        assert ratios.result == "42.82" and any("exceeds 29/41" in w for w in ratios.warnings)


# ---------------------------------------------------------------------------
# cross-program isolation matrix
# ---------------------------------------------------------------------------

class TestCrossProgramIsolation:
    @pytest.mark.parametrize("formula,inputs,wrong_program", [
        ("fannie.base_income.monthly", {"gross_pay": "1000", "pay_frequency": "monthly"}, "freddie"),
        ("freddie.base_income.monthly", {"gross_pay": "1000", "pay_frequency": "monthly"}, "fannie"),
        ("va.residual_income.monthly", {"gross_monthly_income": "1", "federal_income_tax": "0", "state_income_tax": "0", "social_security_and_other_deductions": "0", "shelter_expense": "0", "monthly_debts": "0", "maintenance_and_utilities": "0"}, "fannie"),
        ("usda.annual_income.household", {"adult_member_annual_incomes": ["1"]}, "freddie"),
        ("fha.total.income.current_salary_monthly", {"current_salary_or_rate": "1", "pay_frequency": "monthly"}, "va"),
    ])
    def test_formula_refuses_other_program(self, ft, formula, inputs, wrong_program):
        res = ft["calc"].run(formula, inputs, active_check=ALL_ACTIVE, source_meta=META, program=wrong_program, underwriting_method="total")
        assert res.status == "UNSUPPORTED" and "program mismatch" in res.warnings[0] and res.result is None

    def test_fha_total_cannot_run_as_manual_and_method_is_required(self, ft):
        calc = ft["calc"]
        wrong = calc.run("fha.total.income.current_salary_monthly", {"current_salary_or_rate": "1", "pay_frequency": "monthly"}, active_check=ALL_ACTIVE, source_meta=META, program="fha", underwriting_method="manual")
        assert wrong.status == "UNSUPPORTED" and "underwriting method mismatch" in wrong.warnings[0]
        none = calc.run("fha.manual.ratios.pti_dti", {"total_mortgage_payment": "1", "other_monthly_obligations": "0", "effective_income": "1"}, active_check=ALL_ACTIVE, source_meta=META, program="fha")
        assert none.status == "NEEDS_INPUT" and none.missing_inputs == ["underwriting_method"]

    def test_rule_matching_never_crosses_programs_or_methods(self, ft):
        s = ft["sources"]
        for program in PROGRAMS:
            for rule in s.match_rules(program, "paystub W-2 base income calculation documentation large deposit reserves dti"):
                assert rule["program"] == program and rule["rule_id"].startswith(program + ".")
        total = s.match_rules("fha", "salary calculation of effective income", underwriting_method="total")
        manual = s.match_rules("fha", "salary calculation of effective income", underwriting_method="manual")
        assert total and all(r["underwriting_method"] == "total" for r in total)
        assert manual and all(r["underwriting_method"] == "manual" for r in manual)
        assert not s.match_rules("freddie", "DU findings approve/eligible B3-3.3-01", rules=s.load_rules("fannie"))

    def test_aus_findings_from_wrong_system_are_rejected(self, ft):
        aus = ft["aus"]
        du_doc = {"type": "du_findings", "ref": "x", "recommendation": "Approve/Eligible"}
        env = aus.normalize(du_doc, program="freddie")
        assert env["mismatch"] and "cannot be applied to a freddie file" in env["mismatch"]
        assert aus.normalize(du_doc, program="fannie")["mismatch"] is None
        gus = aus.normalize({"type": "gus_findings", "ref": "g", "underwriting_recommendation": "Accept / Eligible"}, program="fannie")
        assert gus["mismatch"]
        review = aus.review(documents=[du_doc], program="freddie", active_check=ALL_ACTIVE, section_meta=META)
        assert review["status"] == "mismatch" and review["requirements"] == []

    def test_workbenches_fail_closed_without_a_method_or_program_binding(self, ft):
        with pytest.raises(ValueError):
            ft["assets"].review(accounts=[], transaction_type="purchase", total_monthly_qualifying_income="1", funds_needed="0", active_check=ALL_ACTIVE, section_meta=META, program="fha")
        with pytest.raises(ValueError):
            ft["fileprep"].build_matrix(workspace={}, documents=[], active_check=ALL_ACTIVE, section_meta=META, program="fha")
        with pytest.raises(ValueError):
            ft["assets"].review(accounts=[], transaction_type="purchase", total_monthly_qualifying_income="1", funds_needed="0", active_check=ALL_ACTIVE, section_meta=META, program="jumbo")

    def test_fannie_data_cannot_invoke_freddie_bindings(self, ft):
        fx = _fixture("fannie")
        matrix = ft["fileprep"].build_matrix(workspace={"workspace_id": "w"}, documents=fx["documents"], application_date="2026-08-24", active_check=ALL_ACTIVE, section_meta=META, program="freddie")
        aus_item = next(i for i in matrix["items"] if i["category"] == "aus" and "Feedback Certificate" in i["item"])
        assert aus_item["state"] == "needs_review" and "cannot be applied to a freddie file" in aus_item["note"]
        assert all(not i["provenance"].startswith("fannie:") for i in matrix["items"])
        assert all(i["provenance"].split(":")[0] in {"freddie", "workflow", "ashley", "du", "lpa", "aus"} for i in matrix["items"])


# ---------------------------------------------------------------------------
# AUS envelope, cards, identity, income structures
# ---------------------------------------------------------------------------

class TestEnvelopeCardsIdentity:
    @pytest.mark.parametrize("program", PROGRAMS)
    def test_aus_envelope_preserves_wording(self, ft, program):
        fx = _fixture(program)
        review = ft["aus"].review(documents=fx["documents"], program=program, underwriting_method=fx["workspace"].get("underwriting_method"), active_check=ALL_ACTIVE, section_meta=META)
        env = review["envelope"]
        for key in ("aus_system", "aus_result", "aus_version", "findings_ref", "findings_date", "program", "messages", "source_document"):
            assert key in env, key
        assert env["mismatch"] is None and env["program"] == program
        assert review["statement"].endswith(f"{env['aus_result']}.") and "approved" not in review["statement"].lower()
        assert review["statement"].startswith({"fannie": "DU", "freddie": "LPA", "fha": "TOTAL", "va": "DU", "usda": "GUS"}[program])

    @pytest.mark.parametrize("program", PROGRAMS)
    def test_standard_card_fields_and_source_gap_when_inactive(self, ft, program, tmp_path):
        state = ft["knowledge"].KnowledgeState(tmp_path)
        card = ft["cards"].guideline_card(program=program, topic="paystub documentation for base income", state=state, root=tmp_path, underwriting_method="total" if program == "fha" else None)
        for key in ft["cards"].STANDARD_FIELDS:
            assert key in card, key
        assert card["conclusion"] == "SOURCE_GAP" and card["guideline_supported_conclusion"] == "SOURCE_GAP"
        assert card["citations"] and all(not c["usable"] for c in card["citations"])
        assert card["program_key"] == program and card["summary"]["status"] == "SOURCE_GAP"
        if program == "fha":
            assert all(c["underwriting_method"] == "total" for c in card["citations"])
            assert all(c["version"] == "update-17" and c["resolution"] == "CURRENT" for c in card["citations"])
            assert card["details"]["future_citations"] and all(c["version"] == "update-18" for c in card["details"]["future_citations"])
            assert any("FUTURE — NOT YET EFFECTIVE" in c and "11/10/2026" in c for c in card["conflict_or_caution"])
        text = ft["cards"].render_text(card)
        assert "Conclusion: SOURCE_GAP" in text and "Next:" in text

    def test_identity_records(self, ft, monkeypatch):
        ident_mod = ft["identity"]
        monkeypatch.delenv("FLO_APPROVER_ID", raising=False)
        monkeypatch.delenv("FLO_APPROVER_NAME", raising=False)
        local = ident_mod.current_identity()
        assert local.source == "local_dev" and local.user_id.startswith("local-dev:") and local.display_name
        monkeypatch.setenv("FLO_APPROVER_ID", "auth:12345")
        monkeypatch.setenv("FLO_APPROVER_NAME", "Ashley")
        env = ident_mod.current_identity()
        assert env.user_id == "auth:12345" and env.display_name == "Ashley" and env.source == "environment"
        rec = ident_mod.approval_record(env, reason="Program expansion directive", source_revision_id="freddie-5303.1-abc", regression_receipt="regr_x", checksum="c")
        assert ident_mod.validate_approval(rec)["ok"] and "@" not in rec["approved_by_user_id"] and rec["environment"]
        migrated = ident_mod.migrate_legacy_approval({"approver": "owner", "basis": "Golden Loan Path directive 2026-09-08", "at": "2026-09-09T00:00:00Z"}, source_revision_id="fannie-b3-3.3-01-x")
        assert migrated["schema_version"] == 2 and migrated["approved_by_user_id"] == "legacy:owner" and migrated["identity_source"] == "legacy"
        assert ident_mod.validate_approval(migrated)["ok"]

    def test_self_employed_and_rental_structures_are_source_gap(self, ft):
        inc = ft["income_structures"]
        se = inc.SelfEmploymentIncome(borrower_ref="b1", business_name="Synthetic LLC", entity_type="s_corp", ownership_percent="100", years_in_business="4",
                                      tax_forms=[inc.TaxFormRef(form="form_1120s", tax_year=2025, document_ref="doc://1120s-2025"), inc.TaxFormRef(form="schedule_k1", tax_year=2025, document_ref="doc://k1-2025")],
                                      profit_and_loss=inc.ProfitAndLoss(document_ref="doc://pl", period_start="2026-01-01", period_end="2026-06-30"))
        assert inc.validate_self_employment(se)["ok"] and inc.source_gap("self_employment", "freddie", structure_id=se.structure_id)["status"] == "SOURCE_GAP"
        rent = inc.RentalProperty(property_ref="p1", role="departing_residence", leases=[{"document_ref": "doc://lease", "monthly_rent": "1800"}])
        assert inc.validate_rental(rent)["ok"] and inc.source_gap("rental", "fha")["status"] == "SOURCE_GAP"
        assert not any(f.startswith(("fannie.self_employment", "freddie.rental", "fha.total.self_employment")) for f in ft["calc"].FORMULAS)


# ---------------------------------------------------------------------------
# whole team per program, deterministic, sandbox home with the slice activated
# ---------------------------------------------------------------------------

def _real_cache(program):
    candidates = []
    if os.environ.get("FLO_SOURCE_CACHE"):
        candidates.append(Path(os.environ["FLO_SOURCE_CACHE"]).parent / program if Path(os.environ["FLO_SOURCE_CACHE"]).name == "fannie" else Path(os.environ["FLO_SOURCE_CACHE"]) / program)
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "hermes" / "flo" / "sources" / "cache" / program)
    candidates.append(Path.home() / ".hermes" / "flo" / "sources" / "cache" / program)
    return next((c for c in candidates if c.exists() and any(c.glob("*.txt"))), None)


@pytest.fixture()
def program_sandbox(request, tmp_path, monkeypatch, ft):
    program = request.param
    real_cache = _real_cache(program)
    if real_cache is None:
        pytest.skip(f"private {program} source cache not present on this machine (run the fetch script)")
    root = tmp_path / "hermes"
    (root / "profiles" / "flo").mkdir(parents=True)
    shutil.copytree(real_cache, root / "flo" / "sources" / "cache" / program, ignore=shutil.ignore_patterns("*.pdf", "*.pages.json"))
    monkeypatch.setenv("HERMES_HOME", str(root / "profiles" / "flo"))
    monkeypatch.delenv("HERMES_PROFILE_NAME", raising=False)
    monkeypatch.setattr(ft["tools"], "_STATE_ROOT_OVERRIDE", root / "flo" / "team")
    state = ft["knowledge"].KnowledgeState(root / "flo" / "team")
    s = ft["sources"]
    ident = ft["identity"].Identity(user_id="test:admin", display_name="test-admin", source="explicit")
    for sid, meta in s.load_sections(program).items():
        rev = meta["revision_id"]
        state.detect(source_id=f"{program}-{sid.lower()}", version=str(meta.get("page_date")), official_url=meta["official_url"], detected_by="test", checksum=meta["checksum_text"], revision_id=rev)
        state.advance(rev, "pending_review", by="test", source="model")
        result = s.regression(program, sid, root)
        if result["checked"] == 0:
            continue  # sections captured for context without rule records stay pending
        assert result["ok"], result
        state.advance(rev, "regression", by="test", source="model")
        state.advance(rev, "approval", by=ident.user_id, source="user", regression_receipt=result["receipt"])
        doc = state.docs.get(rev)
        doc["approval"] = ft["identity"].approval_record(ident, reason="test activation", source_revision_id=rev, regression_receipt=result["receipt"], checksum=meta["checksum_text"])
        state.docs.put(rev, doc)
        state.advance(rev, "active", by=ident.user_id, source="user")
    return program, root, state


@pytest.mark.parametrize("program_sandbox", ["freddie", "fha", "va", "usda"], indirect=True)
def test_golden_loan_path_per_program(program_sandbox, ft):
    program, root, state = program_sandbox
    fixture = FIXTURES / FIXTURE_FOR[program]
    report = ft["golden_path"].run(fixture, state_root=root / "flo" / "team", knowledge_state=state, tools=ft["tools"])
    syn = report["synthesis"]
    assert [s["step"] for s in report["steps"]] == ["flo.handoff_to_malcolm", "malcolm.review", "sage.guideline_cards", "whisper.draft"]
    assert syn["program_key"] == program and syn["underwriting_decision"] is False and "approved" not in syn["status"].lower()
    assert syn["readiness"]["status"] in ("IN_PROGRESS", "BLOCKED")
    assert syn["draft_communication"]["status"] == "draft"
    assert syn["income"]["status"] != "SOURCE_GAP", syn["income"]
    cites = {c["section"] for card in syn["guideline_cards"] for c in card["citations"]}
    assert all(c["usable"] for card in syn["guideline_cards"] for c in card["citations"])
    items = {i["item"]: i for i in report["matrix"]["items"]}
    provs = {i["provenance"].split(":")[0] for i in report["matrix"]["items"]}
    assert "fannie" not in provs and program in provs
    if program == "freddie":
        assert syn["aus"]["statement"] == "LPA findings show Accept."
        assert syn["income"]["qualifying_monthly"] == "5000.00"
        assert any("3200" in q for q in syn["assets"]["sourcing_questions"])
        assert any("more than 30 days" in (i.get("note") or "") for i in report["matrix"]["items"] if i["category"] == "income")
        assert items["10-day pre-closing verification (Form 90 verbal VOE, e-mail VOE or written VOE)"]["state"] == "missing"
        assert all(c.startswith("5") for c in cites)
    if program == "fha":
        assert syn["aus"]["statement"] == "TOTAL Mortgage Scorecard findings show Accept."
        assert syn["income"]["qualifying_monthly"] == "4800.00" and syn["underwriting_method"] == "total"
        assert any("3000" in q for q in syn["assets"]["sourcing_questions"])
        assert any("W-2 missing for 2024" in (i.get("note") or "") for i in report["matrix"]["items"])
        assert all(c.startswith("II.A.4") or c.startswith("II.A.1") for c in cites), cites
        assert all(c.endswith("@update-17") for c in cites), "case number assigned 2026-08-25 -> Update 17 text governs"
        assert any("FUTURE — NOT YET EFFECTIVE" in c for card in syn["guideline_cards"] for c in card["conflict_or_caution"])
        assert report["income_review"]["traces"][0]["source"]["version"] == "update-17"
    if program == "va":
        ri = syn["income"]["residual_income"]
        assert ri["required_residual"] == "1003.00" and ri["region"] == "South" and ri["residual_income"] == "1053.70"
        assert ri["status"] == "NEEDS_REVIEW" and any("supervisor" in w for w in ri["warnings"])
        assert syn["aus"]["statement"] == "DU findings show Approve/Eligible."
        assert any("120" in (i.get("note") or "") for i in report["matrix"]["items"] if i["category"] == "disclosures_workflow")
        assert syn["assets"]["missing_pages"]
    if program == "usda":
        hh = syn["income"]["household_income"]
        assert hh["annual_income"] == "65280.00" and hh["adjusted_annual_income"] == "64320.00" and hh["repayment_income"] == "3900.00"
        assert syn["aus"]["statement"] == "GUS findings show Accept / Eligible."
        assert any("1500" in q for q in syn["assets"]["sourcing_questions"])
        assert items["Verbal verification of employment within 10 business days of closing"]["state"] == "missing"
    # no NPI shapes in the synthesis
    blob = json.dumps(syn)
    assert "123-45-6789" not in blob
