"""Golden Loan Path — Fannie conventional, W-2 base income, depository assets, DU.

Synthetic data only (tests/flo/fixtures/golden_loan). Two layers:

* unit tests with an injected ``active_check`` (no official text needed);
* an integration run that activates the slice in a *sandbox* Hermes home
  (copying this machine's private source cache when present; skipped
  otherwise) and executes the whole team flow deterministically.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
FIXTURE = REPO / "tests" / "flo" / "fixtures" / "golden_loan" / "golden_loan.json"
SECTIONS = ["B3-3.1-01", "B3-3.2-01", "B3-3.2-02", "B3-3.3-01", "B3-3.3-02", "B3-3.1-04", "B3-4.2-01", "B3-4.2-02", "B3-4.1-01", "B1-1-03", "B3-2-10", "B3-2-11"]


@pytest.fixture(scope="session")
def ft():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    for name in ("tools", "fannie", "calc", "assets", "du", "fileprep", "golden_path", "knowledge", "providers", "redaction"):
        importlib.import_module(f"flo_team.{name}")
    return {name: sys.modules[f"flo_team.{name}"] for name in ("tools", "fannie", "calc", "assets", "du", "fileprep", "golden_path", "knowledge", "providers", "workspace")}


ALL_ACTIVE = lambda s: True  # noqa: E731
META = lambda s: {"section": s, "title": f"Section {s}", "official_url": f"https://selling-guide.fanniemae.com/sel/{s.lower()}", "page_date": "03/04/2026", "revision_id": f"rev-{s}", "checksum": "abc"}  # noqa: E731


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# sources / rules
# ---------------------------------------------------------------------------

class TestSourceRecords:
    def test_sections_and_rules_are_recorded_with_provenance(self, ft):
        sections = ft["fannie"].load_sections()
        assert set(SECTIONS) <= set(sections)
        for sid, meta in sections.items():
            for key in ("official_url", "page_date", "retrieved_at", "checksum_text", "checksum_html", "revision_id", "rights"):
                assert meta.get(key), f"{sid}: {key}"
            assert meta["official_url"].startswith("https://selling-guide.fanniemae.com/sel/")
            assert meta["lifecycle"] == "detected", "the repository never ships an active revision"
        rules = ft["fannie"].load_rules()
        assert len(rules) >= 30
        assert all(r["section"] in sections and r["anchor"] and r["text"] for r in rules)
        assert {r["rule_id"] for r in rules} >= {"fannie.base_income.calc_table", "fannie.assets.large_deposit_definition", "fannie.docs.paystub", "fannie.du.resubmit_dti"}

    def test_no_guide_text_committed(self):
        # Metadata only: the rules file is paraphrase + anchors, far below any section's size.
        assert (PLUGIN / "knowledge" / "fannie" / "rules.json").stat().st_size < 20_000
        assert not list((PLUGIN / "knowledge" / "fannie").glob("*.html"))
        assert not list((PLUGIN / "knowledge" / "fannie").glob("*.txt"))

    def test_inactive_section_locks_everything(self, ft, tmp_path):
        state = ft["knowledge"].KnowledgeState(tmp_path)
        st = ft["fannie"].section_status("B3-3.3-01", state, tmp_path)  # no cache in tmp
        assert not st.usable and "private cache" in st.reason
        res = ft["calc"].run("fannie.base_income.monthly", {"gross_pay": "1000", "pay_frequency": "monthly"}, active_check=lambda s: False)
        assert res.status == "SOURCE_GAP" and "not ACTIVE" in res.warnings[0]
        card = ft["fannie"].guideline_card("hourly employment income", state=state, root=tmp_path)
        assert card["conclusion"] == "SOURCE_GAP" and card["citations"] and card["citations"][0]["usable"] is False


# ---------------------------------------------------------------------------
# calculators (B3-3.3-01 table etc.)
# ---------------------------------------------------------------------------

class TestIncomeCalculators:
    @pytest.mark.parametrize("freq,amount,hours,expected", [
        ("annual", "60000", None, "5000.00"),
        ("monthly", "5000", None, "5000.00"),
        ("twice_monthly", "2500", None, "5000.00"),
        ("biweekly", "2538.46", None, "5500.00"),
        ("weekly", "1153.85", None, "5000.02"),
        ("hourly", "28.85", "40", "5000.67"),
    ])
    def test_base_income_table(self, ft, freq, amount, hours, expected):
        res = ft["calc"].run("fannie.base_income.monthly", {"gross_pay": amount, "pay_frequency": freq, "hours_per_week": hours}, active_check=ALL_ACTIVE, source_meta=META)
        assert res.status == "SUCCESS" and res.result == expected, res.to_dict()
        assert res.tier == "PRODUCTION" and res.rule_ref == "fannie.base_income.calc_table" and res.source["section"] == "B3-3.3-01"
        assert res.steps[-1]["op"] == "round"

    def test_hourly_requires_hours(self, ft):
        res = ft["calc"].run("fannie.base_income.monthly", {"gross_pay": "20", "pay_frequency": "hourly"}, active_check=ALL_ACTIVE, source_meta=META)
        assert res.status == "NEEDS_INPUT" and "hours_per_week" in res.missing_inputs

    def test_variable_average_income_trend(self, ft):
        up = ft["calc"].run("fannie.variable_income.average_income", {"ytd_amount": "42000", "ytd_months": "8", "prior_year_amount": "58000", "prior_year_months": "12"}, active_check=ALL_ACTIVE, source_meta=META)
        assert up.status == "SUCCESS" and up.result == "5000.00" and not any("Declining" in w for w in up.warnings)
        down = ft["calc"].run("fannie.variable_income.average_income", {"ytd_amount": "30000", "ytd_months": "8", "prior_year_amount": "58000", "prior_year_months": "12"}, active_check=ALL_ACTIVE, source_meta=META)
        assert down.status == "SUCCESS" and down.result == "3750.00" and any("Declining" in w for w in down.warnings)
        short = ft["calc"].run("fannie.variable_income.average_income", {"ytd_amount": "3000", "ytd_months": "2", "prior_year_amount": "5000", "prior_year_months": "4"}, active_check=ALL_ACTIVE, source_meta=META)
        assert short.status == "NEEDS_INPUT" and "12 months" in short.warnings[0]

    def test_average_hours_needs_twelve_months(self, ft):
        ok = ft["calc"].run("fannie.variable_income.average_hours", {"average_monthly_hours": "160", "hourly_rate": "25", "months_of_hours_history": "12"}, active_check=ALL_ACTIVE, source_meta=META)
        assert ok.result == "4000.00"
        bad = ft["calc"].run("fannie.variable_income.average_hours", {"average_monthly_hours": "160", "hourly_rate": "25", "months_of_hours_history": "6"}, active_check=ALL_ACTIVE, source_meta=META)
        assert bad.status == "NEEDS_INPUT"

    def test_ytd_consistency_flags_and_labels_internal_tolerance(self, ft):
        res = ft["calc"].run("fannie.income.ytd_consistency", {"qualifying_monthly": "5500", "ytd_amount": "42653", "ytd_months": "7.47"}, active_check=ALL_ACTIVE, source_meta=META)
        assert res.status == "SUCCESS" and Decimal(res.result) < Decimal("105")
        assert any("internal review threshold" in w for w in res.warnings)
        assert not any("needs review" in w for w in res.warnings)
        off = ft["calc"].run("fannie.income.ytd_consistency", {"qualifying_monthly": "5500", "ytd_amount": "46000", "ytd_months": "7.47"}, active_check=ALL_ACTIVE, source_meta=META)
        assert any("needs review" in w for w in off.warnings)

    def test_unsupported_pattern_is_source_gap_not_extrapolation(self, ft):
        assert ft["calc"].run("fannie.self_employment.schedule_c", {}, active_check=ALL_ACTIVE).status == "UNSUPPORTED"
        assert "fannie.self_employment.schedule_c" not in ft["calc"].production_formulas()

    def test_du_tolerance_and_reserves(self, ft):
        tol = ft["calc"].run("fannie.du.dti_resubmission_check", {"du_dti": "38.4", "recalculated_dti": "42.0"}, active_check=ALL_ACTIVE, source_meta=META)
        assert tol.result == "3.60" and any("Resubmission" in w for w in tol.warnings)
        ok = ft["calc"].run("fannie.du.dti_resubmission_check", {"du_dti": "38.4", "recalculated_dti": "40.0"}, active_check=ALL_ACTIVE, source_meta=META)
        assert any("Within DU tolerance" in w for w in ok.warnings)
        res = ft["calc"].run("fannie.reserves.months", {"liquid_reserves": "7830", "pitia": "2610"}, active_check=ALL_ACTIVE, source_meta=META)
        assert res.result == "3.00"


# ---------------------------------------------------------------------------
# assets, DU, matrix
# ---------------------------------------------------------------------------

class TestAssetsDuMatrix:
    def test_asset_workbench_finds_missing_page_and_large_deposit(self, ft):
        fx = _fixture()
        accounts = ft["golden_path"].accounts_from_documents(fx["documents"])
        out = ft["assets"].review(accounts=accounts, transaction_type="purchase", total_monthly_qualifying_income="5500.00", funds_needed="84250.00",
                                  application_date="2026-08-24", pitia="2610.00", du_reserves_required="0.00", active_check=ALL_ACTIVE, section_meta=META)
        assert out["status"] == "NEEDS_REVIEW"
        assert out["missing_statements_or_pages"] == [{"account_ref": "Cascade Community Bank (synthetic) …4471", "statement_end": "2026-07-31", "need": "pages 5-5"}]
        assert Decimal(out["large_deposit_threshold"]["result"]) == Decimal("2750.00")
        assert any("4000" in q for q in out["sourcing_questions"])
        assert out["available_assets"] == "91340.18" and out["undocumented_large_deposits"] == "4000.00" and out["eligible_amount"] == "87340.18"
        assert Decimal(out["reserves"]["months"]) > 0 and "no minimum reserve" in out["reserves"]["note"]
        assert {s["section"] for s in out["sources"]} == {"B3-4.2-01", "B3-4.2-02", "B3-4.1-01", "B1-1-03"}

    def test_asset_workbench_locks_without_active_sections_and_rejects_other_types(self, ft):
        out = ft["assets"].review(accounts=[], transaction_type="purchase", total_monthly_qualifying_income="5000", funds_needed="0", active_check=lambda s: False)
        assert out["status"] == "SOURCE_GAP"
        out = ft["assets"].review(accounts=[{"account_ref": "gift", "type": "gift", "ending_balance": "10000"}], transaction_type="purchase",
                                  total_monthly_qualifying_income="5000", funds_needed="0", active_check=ALL_ACTIVE, section_meta=META)
        assert out["unsupported"][0]["type"] == "gift" and out["available_assets"] == "0"

    def test_du_review_language_and_requirements(self, ft):
        fx = _fixture()
        out = ft["du"].review(documents=fx["documents"], recalculated_dti="38.9", active_check=ALL_ACTIVE, section_meta=META)
        assert out["present"] and out["statement"] == "DU findings show Approve/Eligible."
        assert "approved" not in out["statement"].lower()
        kinds = {r["document_kind"]: r["state"] for r in out["requirements"]}
        assert kinds["paystub"] == "satisfied" and kinds["credit_report"] == "missing"
        assert kinds["bank_statement"] == "needs_review", "a statement with a missing page must not satisfy an all-pages message"
        assert out["conflicts"] and out["conflicts"][0]["route_to"] == "sage"
        assert "Within DU tolerance" in out["dti_tolerance"]["warnings"][0]
        missing = ft["du"].review(documents=[d for d in fx["documents"] if d["type"] != "du_findings"], active_check=ALL_ACTIVE, section_meta=META)
        assert not missing["present"] and missing["status"] == "missing"

    def test_fileprep_matrix_has_provenance_and_states(self, ft):
        fx = _fixture()
        docs = fx["documents"]
        income = ft["golden_path"].income_review(docs, active_check=ALL_ACTIVE, section_meta=META)
        assert income["qualifying_monthly"] == "5500.00" and income["status"] == "NEEDS_REVIEW"
        assert income["w2_comparison"]["w2_wages"] == "58900.00" and income["guideline_questions"]
        accounts = ft["golden_path"].accounts_from_documents(docs)
        assets = ft["assets"].review(accounts=accounts, transaction_type="purchase", total_monthly_qualifying_income=income["qualifying_monthly"], funds_needed="84250.00",
                                     application_date="2026-08-24", active_check=ALL_ACTIVE, section_meta=META)
        matrix = ft["fileprep"].build_matrix(workspace={"workspace_id": "loan_x", "estimated_note_date": "2026-10-09"}, documents=docs, application_date="2026-08-24",
                                             transaction_type="purchase", income_review=income, asset_review=assets, active_check=ALL_ACTIVE, section_meta=META)
        by_item = {i["item"]: i for i in matrix["items"]}
        assert by_item["Verbal verification of employment (or Form 1005)"]["state"] == "missing"
        assert by_item["Verbal verification of employment (or Form 1005)"]["provenance"] == "fannie:B3-3.3-01"
        assert by_item["Most recent W-2 (tax year 2025)"]["state"] == "complete"
        assert by_item["Base income calculation reconciled to YTD and W-2"]["state"] == "needs_review"
        assert by_item["Loan application (Form 1003) and identification"]["state"] == "source_gap"
        assert all(i["provenance"].split(":")[0] in {"fannie", "du", "workflow", "ashley"} for i in matrix["items"])
        assert matrix["counts"]["source_gap"] >= 2 and matrix["counts"]["missing"] >= 2
        checklist = ft["fileprep"].as_checklist(matrix)
        assert all(c["state"] != "source_gap" for c in checklist)

    def test_matrix_without_active_sections_is_all_source_gap(self, ft):
        fx = _fixture()
        matrix = ft["fileprep"].build_matrix(workspace={"workspace_id": "loan_x"}, documents=fx["documents"], application_date="2026-08-24", active_check=lambda s: False)
        assert all(i["state"] == "source_gap" for i in matrix["items"] if i["provenance"].startswith("fannie:"))


# ---------------------------------------------------------------------------
# whole team, deterministic, in a sandbox home with the slice activated
# ---------------------------------------------------------------------------

@pytest.fixture()
def activated_sandbox(tmp_path, monkeypatch, ft):
    """Sandbox Hermes root with the private cache copied (if this machine has it) and the slice activated by a test admin."""
    import os

    candidates = []
    if os.environ.get("FLO_SOURCE_CACHE"):
        candidates.append(Path(os.environ["FLO_SOURCE_CACHE"]))
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "hermes" / "flo" / "sources" / "cache" / "fannie")
    candidates.append(Path.home() / ".hermes" / "flo" / "sources" / "cache" / "fannie")
    real_cache = next((c for c in candidates if c.exists() and any(c.glob("*.txt"))), None)
    if real_cache is None:
        pytest.skip("private Fannie source cache not present on this machine (run scripts/flo/fetch_fannie_sources.py)")
    root = tmp_path / "hermes"
    (root / "profiles" / "flo").mkdir(parents=True)
    shutil.copytree(real_cache, root / "flo" / "sources" / "cache" / "fannie")
    monkeypatch.setenv("HERMES_HOME", str(root / "profiles" / "flo"))
    monkeypatch.delenv("HERMES_PROFILE_NAME", raising=False)
    monkeypatch.setattr(ft["tools"], "_STATE_ROOT_OVERRIDE", root / "flo" / "team")
    state = ft["knowledge"].KnowledgeState(root / "flo" / "team")  # docs at <team root>/knowledge/, like the activation script
    fannie = ft["fannie"]
    for sid, meta in fannie.load_sections().items():
        rev = meta["revision_id"]
        state.detect(source_id=f"fannie-{sid.lower()}", version=str(meta.get("page_date")), official_url=meta["official_url"], detected_by="test", checksum=meta["checksum_text"], revision_id=rev)
        state.advance(rev, "pending_review", by="test", source="model")
        result = fannie.regression(sid, root)
        assert result["ok"], result
        state.advance(rev, "regression", by="test", source="model")
        state.advance(rev, "approval", by="test-admin", source="user", regression_receipt=result["receipt"])
        state.advance(rev, "active", by="test-admin", source="user")
    return root, state


class TestGoldenPathEndToEnd:
    def test_whole_team_flow(self, activated_sandbox, ft):
        root, state = activated_sandbox
        for sid in SECTIONS:
            assert ft["fannie"].is_active(sid, state, root), sid
        # The tool surface must resolve the same state the activation script wrote (no doubled path).
        active, _ = ft["tools"]._active_check()
        assert active("B3-3.3-01")
        assert json.loads(ft["tools"].handle_flo_calc({"action": "list"}))["production_formulas_active"]
        report = ft["golden_path"].run(FIXTURE, state_root=root / "flo" / "team", knowledge_state=state, tools=ft["tools"])
        syn = report["synthesis"]
        # Flo → Malcolm → (Sage) → Whisper → Flo
        steps = [s["step"] for s in report["steps"]]
        assert steps == ["flo.handoff_to_malcolm", "malcolm.review", "sage.guideline_cards", "whisper.draft"]
        assert report["steps"][0]["send_with"] == "message_agent"
        # DU language
        assert syn["aus"]["statement"] == "DU findings show Approve/Eligible."
        assert "approved" not in syn["status"].lower()
        # income + assets deterministic, source-backed
        assert syn["income"]["qualifying_monthly"] == "5500.00" and syn["income"]["status"] == "NEEDS_REVIEW"
        assert syn["assets"]["missing_pages"] and syn["assets"]["sourcing_questions"]
        # readiness never an approval; intentional issues surfaced
        assert syn["readiness"]["status"] in ("IN_PROGRESS", "BLOCKED") and syn["readiness"]["disclaimer"]
        missing_text = " ".join(syn["missing_items"]).lower()
        assert "verbal verification" in missing_text
        assert any("W-2" in r or "differs" in r for r in syn["risks"])
        # Sage cards are real, section-level
        assert syn["guideline_cards"] and all(c["conclusion"] != "SOURCE_GAP" for c in syn["guideline_cards"])
        sections = {c["section"] for card in syn["guideline_cards"] for c in card["citations"]}
        assert "B3-3.3-01" in sections
        assert all(c["official_url"].startswith("https://selling-guide.fanniemae.com/sel/") and c["usable"] for card in syn["guideline_cards"] for c in card["citations"])
        assert any("selling-guide.fanniemae.com/sel/b3-3.3-01" in u for u in syn["source_links"])
        # Whisper draft is a draft; nothing sent
        assert syn["draft_communication"]["status"] == "draft"
        ws = ft["workspace"].WorkspaceStore(root / "flo" / "team").get(report["workspace_id"])
        assert ws["drafts"][0]["status"] == "draft" and ws["aus"]["recommendation_as_shown"] == "Approve/Eligible"
        assert "franklin" in ws["excluded_members"]
        # no NPI shapes in the synthesis
        blob = json.dumps(syn)
        assert "123-45-6789" not in blob and syn["underwriting_decision"] is False

    def test_cache_tampering_demotes_to_stale(self, activated_sandbox, ft):
        root, state = activated_sandbox
        cache = root / "flo" / "sources" / "cache" / "fannie" / "B3-3.3-01.txt"
        cache.write_text(cache.read_text(encoding="utf-8") + " tampered", encoding="utf-8")
        st = ft["fannie"].section_status("B3-3.3-01", state, root)
        assert st.lifecycle == "STALE_SOURCE" and not st.usable
        res = ft["calc"].run("fannie.base_income.monthly", {"gross_pay": "1", "pay_frequency": "monthly"}, active_check=lambda s: ft["fannie"].is_active(s, state, root))
        assert res.status == "SOURCE_GAP"


# ---------------------------------------------------------------------------
# providers
# ---------------------------------------------------------------------------

class TestProviders:
    def test_discover_and_choose(self, ft, team=None):
        prov = ft["providers"]
        team = sys.modules["flo_team.manifest"].manifest()
        healthy_local = ft["fannie"]  # placeholder to keep flake happy
        del healthy_local

        def fake_health(base_url, model, **kw):
            rep = sys.modules["flo_team.models"].HealthReport(provider="flo_local", base_url=base_url, model=model)
            if "11434" in base_url:
                rep.reachable = rep.model_listed = rep.context_ok = rep.smoke_ok = rep.healthy = True
                rep.resolved_model_id = "qwen3-flo:latest"
                rep.context_length = 65536
            else:
                rep.error = "unreachable"
            return rep

        rows = prov.discover(config={"providers": {"flo_local": {"base_url": "http://localhost:11434/v1", "model": "qwen3-flo"}}},
                             health_check=fake_health, auth_check=lambda p: p == "openai-codex", smoke=False)
        by = {r.provider_id: r for r in rows}
        assert by["ollama_local"].status == "healthy" and by["ollama_local"].sensitive_data_permission
        assert by["unsloth_studio"].status == "unconfigured"
        assert by["openai_codex"].status == "healthy" and not by["openai_codex"].sensitive_data_permission
        assert by["opencode_free"].status == "unauthenticated"
        for row in rows:
            assert {"endpoint", "reachable", "available_model", "context_capability", "latency_ms", "sensitive_data_permission", "status"} <= set(row.to_dict())
        choice = prov.choose(team.role("malcolm"), rows, sensitive=True, team=team)
        assert choice.status == "OK" and choice.provider_id == "ollama_local"
        # local slow + sensitive → fail closed, never cloud (the deterministic class is code, not a fallback LLM)
        by["ollama_local"].status = "slow"
        assert prov.choose(team.role("malcolm"), rows, sensitive=True, team=team).status == "FAIL_CLOSED"
        assert prov.choose(team.role("whisper"), rows, sensitive=True, team=team).status == "FAIL_CLOSED"
        assert prov.choose(team.role("whisper"), rows, sensitive=True, team=team, allow_slow=True).provider_id == "ollama_local"
        # non-sensitive: cloud allowed for roles that list cloud_reasoning; others only with the explicit owner fallback
        assert prov.choose(team.role("sage"), rows, sensitive=False, team=team).provider_id == "openai_codex"
        assert prov.choose(team.role("whisper"), rows, sensitive=False, team=team).status == "UNCONFIGURED"
        assert prov.choose(team.role("whisper"), rows, sensitive=False, team=team, allow_any_cloud=True).provider_id == "openai_codex"
        # sensitive + allow_any_cloud still fails closed
        assert prov.choose(team.role("whisper"), rows, sensitive=True, team=team, allow_any_cloud=True).status == "FAIL_CLOSED"
