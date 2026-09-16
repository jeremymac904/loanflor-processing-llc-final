"""Reliability regression scenarios (FLO_RELIABILITY_HARDENING): source diff/impact, overlays, guidance capture, audit identity.

Scenarios 1-2 (FHA early/late selection) live in test_fha_effective_dates.py; 3-4 (unsupported prose) in
test_source_bound_response.py; 5-6 (duplicate draft/order) in test_idempotency.py; 7-11 (provider 429/402/
unavailable/slow/sensitive fail-closed) in test_provider_failover.py. This file covers 12-14 and the review tooling.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
NOWHERE = Path("/nonexistent")


@pytest.fixture(scope="session")
def ft():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    names = ("sources", "sourcediff", "impact", "overlays", "guidance", "identity", "cards", "knowledge", "calc", "tools")
    for name in names:
        importlib.import_module(f"flo_team.{name}")
    return {name: sys.modules[f"flo_team.{name}"] for name in names}


def _identity(ft, source="explicit"):
    ident = ft["identity"].Identity(user_id="admin:test", display_name="Test Admin", source=source)
    return ft["identity"].approval_record(ident, reason="test", source_revision_id="n/a", regression_receipt=None, checksum=None)


class TestSourceDiffAndImpact:
    def test_fha_version_diff_lists_changes_and_impact(self, ft):
        cache = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" if os.environ.get("LOCALAPPDATA") else None
        root = cache if cache and (cache / "flo" / "sources" / "cache" / "fha").exists() else None
        diff = ft["sourcediff"].compare_versions("fha", "update-17", "update-18", root=root)
        assert not diff["new_sections"] and not diff["removed_sections"]
        assert {c["section"] for c in diff["changed_sections"]} >= {"II.A.4.c", "II.A.5.b", "II.A.4.a"}
        assert "update affects" in diff["impact_summary"] and "regression scenario" in diff["summary"]
        if root:
            c = next(c for c in diff["changed_sections"] if c["section"] == "II.A.4.c")
            assert c["text_diff"]["similarity"] < 1 and (c["text_diff"]["added_count"] or c["text_diff"]["removed_count"])
        assert "fha.total.income.current_salary_monthly" in diff["affected_calculators"]

    def test_impact_index_links_rules_to_calculators_workflows_and_tests(self, ft):
        rows = {r["rule_id"]: r for r in ft["impact"].index("freddie")}
        calc_rule = rows["freddie.base_income.calc_table"]
        assert "freddie.base_income.monthly" in calc_rule["calculators"]
        assert any("income_calc" in p or "paystub" in p for p in calc_rule["fileprep_requirements"])
        assert "freddie_golden_loan.json" in calc_rule["synthetic_evals"] and any(t.startswith("test_") for t in calc_rule["tests"])
        out = ft["impact"].affected("freddie", changed_rule_ids=["freddie.base_income.calc_table"])
        # section-level impact: every formula bound to 5303.1 is affected when one of its rules changes
        assert set(out["affected_calculators"]) >= {"freddie.base_income.monthly", "freddie.fluctuating_hourly.average"}
        assert "Freddie Mac Conventional update affects 1 rule record" in out["summary"]

    def test_snapshot_diff_detects_changed_text(self, ft, tmp_path):
        s = ft["sourcediff"]
        old = {"5303.1": {"checksum_text": "old", "text_chars": 10, "effective_date": "01/01/2026"}, "5999.9": {"checksum_text": "gone", "text_chars": 5}}
        out = s.compare_snapshots("freddie", old, root=NOWHERE)
        assert "5999.9" in out["removed_sections"] and any(c["section"] == "5303.1" for c in out["changed_sections"])
        assert any(x.startswith("5") for x in out["new_sections"])


class TestScenario12SourceRevisionChangedAfterActivation:
    def test_changed_cache_locks_calculator_and_card(self, ft, tmp_path):
        s, calc, cards, knowledge = ft["sources"], ft["calc"], ft["cards"], ft["knowledge"]
        src = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "flo" / "sources" / "cache" / "freddie"
        if not src.exists():
            pytest.skip("private Freddie cache not on this machine")
        root = tmp_path / "hermes"
        shutil.copytree(src, root / "flo" / "sources" / "cache" / "freddie", ignore=shutil.ignore_patterns("*.html"))
        state = knowledge.KnowledgeState(root / "flo" / "team")
        meta = s.load_sections("freddie")["5303.1"]
        state.detect(source_id="freddie-5303.1", version="v", official_url=meta["official_url"], detected_by="test", checksum=meta["checksum_text"], revision_id=meta["revision_id"])
        state.advance(meta["revision_id"], "pending_review", by="t", source="model")
        state.advance(meta["revision_id"], "regression", by="t", source="model")
        state.advance(meta["revision_id"], "approval", by="admin", source="user", regression_receipt="regr_x")
        state.advance(meta["revision_id"], "active", by="admin", source="user")
        active, meta_fn = s.checks_for("freddie", state, root)
        assert calc.run("freddie.base_income.monthly", {"gross_pay": "1000", "pay_frequency": "monthly"}, active_check=active, source_meta=meta_fn, program="freddie").status == "SUCCESS"
        # the guide text changes on disk after activation
        path = root / "flo" / "sources" / "cache" / "freddie" / "5303.1.txt"
        path.write_text(path.read_text(encoding="utf-8").replace("Multiply the biweekly gross pay by 26", "Multiply the biweekly gross pay by 24"), encoding="utf-8")
        st = s.section_status("freddie", "5303.1", state, root)
        assert st.lifecycle == "STALE_SOURCE" and not st.usable
        assert calc.run("freddie.base_income.monthly", {"gross_pay": "1000", "pay_frequency": "monthly"}, active_check=active, source_meta=meta_fn, program="freddie").status == "SOURCE_GAP"
        card = cards.guideline_card(program="freddie", topic="biweekly base income calculation", state=state, root=root)
        assert card["conclusion"] == "SOURCE_GAP"


class TestScenario13OverlayConflict:
    def test_overlay_layers_on_baseline_and_conflict_is_flagged_not_resolved(self, ft, tmp_path):
        ov, cards, knowledge = ft["overlays"], ft["cards"], ft["knowledge"]
        store = ov.OverlayStore(tmp_path)
        with pytest.raises(ov.OverlayError):
            store.propose(program="freddie", lender="Loan Factory", overlay_source="", text="two months reserves")
        row = store.propose(program="freddie", lender="Loan Factory", overlay_source="Loan Factory Conventional Guide §3.2 (synthetic test reference)", text="Lender requires the year-to-date paystub dated within 15 days of application.",
                            agency_rule_ref="freddie.docs.paystub", effective_date="01/01/2026", product="Conventional 30 fixed", proposed_by="admin:test")
        with pytest.raises(ov.OverlayError):
            store.activate(row["overlay_id"], identity=_identity(ft))  # AE confirmation missing
        row = store.propose(program="freddie", lender="Loan Factory", overlay_source="Loan Factory Conventional Guide §3.2 (synthetic test reference)", text="Lender requires the year-to-date paystub dated within 15 days of application.",
                            agency_rule_ref="freddie.docs.paystub", effective_date="01/01/2026", proposed_by="admin:test", ae_confirmation_status="confirmed", confirmed_by="AE (test)")
        with pytest.raises(ov.OverlayError):
            store.activate(row["overlay_id"], identity={"identity_source": "model", "approved_by_user_id": "bot"})
        store.activate(row["overlay_id"], identity=_identity(ft))
        state = knowledge.KnowledgeState(tmp_path)
        card = cards.guideline_card(program="freddie", topic="paystub documentation age", state=state, root=NOWHERE, lender="Loan Factory", team_root=tmp_path)
        assert card["lender_overlay"]["state"] == "LOADED" and card["lender_overlay"]["overlays"][0]["overlay_source"].startswith("Loan Factory")
        assert any(c["rule_id"] == "freddie.docs.paystub" for c in card["citations"])  # agency baseline still present
        assert any("Overlay" in c and "freddie.docs.paystub" in c and "neither is overwritten" in c for c in card["conflict_or_caution"])
        assert "Overlay not loaded — confirm with AE." not in card["conflict_or_caution"]
        assert card["layers"]["agency_baseline"] is not None


class TestScenario14FileConditionNotPromotedGlobally:
    def test_guidance_stays_loan_specific_until_an_admin_promotes(self, ft, tmp_path):
        g, cards, knowledge = ft["guidance"], ft["cards"], ft["knowledge"]
        store = g.GuidanceStore(tmp_path)
        item = store.propose(text="AE confirmed Loan Factory requires two months of reserves for this product.", scope="loan_specific", source_ref="mail://synthetic/ae-2026-09-09",
                             recorded_by="flo", workspace_id="loan_a", program="freddie", lender="Loan Factory")
        assert item["status"] == "pending_review" and item["global"] is False
        state = knowledge.KnowledgeState(tmp_path)
        same_room = cards.guideline_card(program="freddie", topic="reserves", state=state, root=NOWHERE, team_root=tmp_path, workspace_id="loan_a")
        other_room = cards.guideline_card(program="freddie", topic="reserves", state=state, root=NOWHERE, team_root=tmp_path, workspace_id="loan_b")
        assert same_room["guidance"] and same_room["guidance"][0]["layer"] == "file_condition"
        assert any("AE/UW guidance (pending_review" in c for c in same_room["details"]["file_conditions"])
        assert not other_room["guidance"] and same_room["lender_overlay"]["state"] == "NOT_LOADED"  # never an overlay, never global
        with pytest.raises(g.GuidanceError):
            store.decide(item["guidance_id"], status="promoted", identity={"identity_source": "model", "approved_by_user_id": "sage"})
        promoted = store.decide(item["guidance_id"], status="promoted", identity=_identity(ft), reason="verified with AE")
        assert promoted["status"] == "promoted" and "overlay_id" not in promoted  # loan-specific never becomes an overlay
        reusable = store.propose(text="Loan Factory: paystub within 15 days.", scope="lender_specific", source_ref="mail://synthetic/ae-2", recorded_by="flo", program="freddie", lender="Loan Factory", confirmed_by="AE")
        out = store.decide(reusable["guidance_id"], status="promoted", identity=_identity(ft))
        overlay = ft["overlays"].OverlayStore(tmp_path).docs.get(out["overlay_id"])
        assert overlay["lifecycle"] == "proposed" and overlay["ae_confirmation_status"] == "confirmed"  # still needs overlay activation


class TestAuditIdentity:
    def test_approval_records_use_the_structured_identity(self, ft):
        knowledge_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "flo" / "team" / "knowledge"
        if not knowledge_dir.exists():
            pytest.skip("no install on this machine")
        bad = []
        for path in knowledge_dir.glob("*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            appr = doc.get("approval")
            if doc.get("lifecycle") == "active" and (not appr or appr.get("schema_version") != 2 or not ft["identity"].validate_approval(appr)["ok"] or "@" in str(appr.get("approved_by_user_id"))):
                bad.append(path.name)
        assert not bad, bad
