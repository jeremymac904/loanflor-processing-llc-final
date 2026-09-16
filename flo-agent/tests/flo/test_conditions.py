"""Conditions auto-clear: high-confidence matches clear, ambiguous go to Needs Review,
judgment-required conditions are never touched. All fixtures are synthetic."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"

# Load the plugin package once at import time so test bodies can call
# `conditions.foo(...)` directly. Mirrors test_today.py's pattern.
if "flo_team" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "flo_team", PLUGIN / "__init__.py",
        submodule_search_locations=[str(PLUGIN)],
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["flo_team"] = _module
    _spec.loader.exec_module(_module)

from flo_team import conditions  # noqa: E402


# ── fixtures ───────────────────────────────────────────────────────────────

def _condition(text, **overrides):
    base = {"id": "cond_001", "text": text, "state": "open"}
    base.update(overrides)
    return base


def _doc(category, subcategory=None, *, borrower_ref="borrower", status="received",
         missing_pages=None, period=None, display_name=None, text=None):
    rec = {
        "document_id": "doc_001",
        "category": category,
        "subcategory": subcategory,
        "borrower_ref": borrower_ref,
        "status": status,
        "page_count": 1,
        "checks": {"pages": {"missing": missing_pages or [], "expected": 4}},
        "display_name": display_name or "",
        "text_path": None,
    }
    if period:
        # write the text sidecar so _doc_period can find it
        pass
    return rec


# ── core match logic ───────────────────────────────────────────────────────

class TestClearsOnMatch:
    def test_paystub_clears_paystub_condition(self):
        cond = _condition("Most recent paystub from borrower 1, current period")
        doc = _doc("income", "paystub", borrower_ref="borrower")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "clear"
        assert "borrower" in decisions[0]["reason"]

    def test_paystub_clears_paystub_condition_via_text(self):
        # No subcategory on the doc; text-based fallback still clears.
        cond = _condition("Updated paystub required, current period")
        doc = _doc("income", None, borrower_ref="borrower", display_name="paystub_2026_09.pdf")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert decisions[0]["decision"] == "clear"

    def test_w2_clears_w2_condition(self):
        cond = _condition("W-2 for 2025 from borrower 1")
        doc = _doc("income", "w2", borrower_ref="borrower")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert decisions[0]["decision"] == "clear"

    def test_bank_statement_clears_bank_statement_condition(self):
        cond = _condition("Bank statement: most recent 2 months, checking account")
        doc = _doc("assets", "bank_statement", borrower_ref="borrower")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert decisions[0]["decision"] == "clear"

    def test_insurance_declaration_clears_hoi_condition(self):
        cond = _condition("Updated HOI required — homeowners insurance declaration page")
        doc = _doc("insurance", "insurance_declaration", borrower_ref="borrower")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert decisions[0]["decision"] == "clear"

    def test_both_borrowers_condition_accepts_either(self):
        cond = _condition("Most recent paystub — borrower or co-borrower",
                          borrower_ref="both")
        doc = _doc("income", "paystub", borrower_ref="co_borrower")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert decisions[0]["decision"] == "clear"


class TestPeriodMatching:
    def test_matching_year_clears(self):
        cond = _condition("Bank statement for 2025")
        rec = _doc("assets", "bank_statement")
        # text_path is None in fixture; period pulled from text or filename
        rec["display_name"] = "stmt_2025_03.pdf"
        decisions = conditions.evaluate_document_for_conditions([cond], rec)
        assert decisions[0]["decision"] == "clear"

    def test_disjoint_periods_needs_review(self):
        cond = _condition("Bank statement for 2025")
        rec = _doc("assets", "bank_statement")
        rec["display_name"] = "stmt_2023_03.pdf"
        decisions = conditions.evaluate_document_for_conditions([cond], rec)
        assert decisions[0]["decision"] == "needs_review"
        assert "period" in decisions[0]["reason"].lower()

    def test_unparseable_period_needs_review_when_condition_has_period(self):
        cond = _condition("Bank statement for 2025")
        rec = _doc("assets", "bank_statement", display_name="scan.pdf")
        decisions = conditions.evaluate_document_for_conditions([cond], rec)
        assert decisions[0]["decision"] == "needs_review"


class TestPageMatching:
    def test_required_page_present_clears(self):
        cond = _condition("Bank statement page 4 missing")
        rec = _doc("assets", "bank_statement", missing_pages=[])
        decisions = conditions.evaluate_document_for_conditions([cond], rec)
        assert decisions[0]["decision"] == "clear"

    def test_required_page_still_missing_needs_review(self):
        cond = _condition("Bank statement page 4 missing")
        rec = _doc("assets", "bank_statement", missing_pages=[4], status="missing_pages")
        decisions = conditions.evaluate_document_for_conditions([cond], rec)
        assert decisions[0]["decision"] == "needs_review"


class TestDoesNotClear:
    def test_wrong_borrower_needs_review(self):
        cond = _condition("Most recent paystub from borrower 1",
                          borrower_ref="borrower")
        doc = _doc("income", "paystub", borrower_ref="co_borrower")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert decisions[0]["decision"] == "needs_review"
        assert "borrower" in decisions[0]["reason"].lower()

    def test_wrong_subcategory_skipped(self):
        cond = _condition("Most recent paystub from borrower 1")
        doc = _doc("income", "w2", borrower_ref="borrower")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert decisions[0]["decision"] == "skip"

    def test_unrelated_pdf_does_not_clear(self):
        cond = _condition("Most recent paystub from borrower 1")
        doc = _doc("other", None, borrower_ref="borrower", display_name="scan123.pdf")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert decisions[0]["decision"] == "skip"

    def test_already_cleared_stays_cleared(self):
        cond = _condition("Most recent paystub from borrower 1", state="cleared")
        doc = _doc("income", "paystub", borrower_ref="borrower")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        # already-cleared conditions are filtered before evaluation; no decision is returned
        assert decisions == []

    def test_unreadable_document_needs_review(self):
        cond = _condition("Most recent paystub from borrower 1")
        doc = _doc("income", "paystub", status="unreadable")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert decisions[0]["decision"] == "needs_review"


class TestJudgmentRequired:
    @pytest.mark.parametrize("text", [
        "Letter of explanation for large deposit",
        "Source of funds letter needed",
        "Source-of-funds verification outstanding",
        "Gift letter from borrower family required",
        "Appraisal review by underwriter pending",
        "Title curative for lien release needed",
        "Underwriting decision pending — 8102 conditions",
    ])
    def test_judgment_conditions_never_clear(self, text):
        cond = _condition(text)
        doc = _doc("income", "paystub", borrower_ref="borrower")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert decisions[0]["decision"] == "skip"
        assert "judgment" in decisions[0]["reason"].lower()

    def test_explicit_judgment_required_flag_respected(self):
        # even a benign-looking text is skipped if the condition explicitly flags it
        cond = _condition("Most recent paystub", judgment_required=True)
        doc = _doc("income", "paystub", borrower_ref="borrower")
        decisions = conditions.evaluate_document_for_conditions([cond], doc)
        assert decisions[0]["decision"] == "skip"


# ── application + workspace side effects ───────────────────────────────────

class TestApplyDecisions:
    def test_apply_clears_condition_and_sets_metadata(self):
        cond = _condition("Most recent paystub from borrower 1")
        ws = {"workspace_id": "loan_okafor", "conditions": [cond]}
        applied = conditions.apply_decisions(
            ws,
            [{"condition_id": "cond_001", "decision": "clear",
              "reason": "category, kind, borrower, and period all match",
              "document_id": "doc_001"}],
        )
        assert len(applied) == 1
        assert ws["conditions"][0]["state"] == "cleared"
        assert ws["conditions"][0]["cleared_by_document_id"] == "doc_001"
        assert ws["conditions"][0]["cleared_by"] == "malcolm"

    def test_duplicate_doc_does_not_re_clear(self):
        cond = _condition("Most recent paystub from borrower 1")
        ws = {"workspace_id": "loan_okafor", "conditions": [cond]}
        conditions.apply_decisions(
            ws,
            [{"condition_id": "cond_001", "decision": "clear",
              "reason": "match", "document_id": "doc_001"}],
        )
        # second pass on the same condition produces no applied entry
        applied2 = conditions.apply_decisions(
            ws,
            [{"condition_id": "cond_001", "decision": "clear",
              "reason": "match", "document_id": "doc_002"}],
        )
        assert applied2 == []  # state is already 'cleared', not re-cleared

    def test_needs_review_keeps_state_open(self):
        cond = _condition("Most recent paystub from borrower 1", borrower_ref="borrower")
        ws = {"workspace_id": "loan_okafor", "conditions": [cond]}
        conditions.apply_decisions(
            ws,
            [{"condition_id": "cond_001", "decision": "needs_review",
              "reason": "borrower mismatch", "document_id": "doc_002"}],
        )
        assert ws["conditions"][0]["state"] == "open"
        assert ws["conditions"][0]["needs_review"] is True
        assert "borrower" in ws["conditions"][0]["needs_review_reason"]

    def test_recompute_next_action_single_clear(self):
        cond = _condition("Most recent paystub from borrower 1")
        ws = {"workspace_id": "loan_okafor", "conditions": [cond]}
        conditions.apply_decisions(
            ws,
            [{"condition_id": "cond_001", "decision": "clear",
              "reason": "match", "document_id": "doc_001"}],
        )
        conditions.recompute_next_action(
            ws,
            [{"condition_id": "cond_001", "decision": "clear", "reason": "match"}],
        )
        assert ws["next_action"] == "Cleared 1 condition. Nothing left to clear here."

    def test_recompute_next_action_partial_clear(self):
        c1 = _condition("Most recent paystub", id="cond_001")
        c2 = _condition("Updated bank statement", id="cond_002")
        ws = {"workspace_id": "loan_okafor", "conditions": [c1, c2]}
        conditions.apply_decisions(
            ws,
            [{"condition_id": "cond_001", "decision": "clear",
              "reason": "match", "document_id": "doc_001"}],
        )
        conditions.recompute_next_action(
            ws,
            [{"condition_id": "cond_001", "decision": "clear", "reason": "match"}],
        )
        assert ws["next_action"] == "Cleared 1 condition. 1 still open."

    def test_recompute_next_action_ambiguous_only(self):
        c1 = _condition("Most recent paystub", id="cond_001", borrower_ref="borrower")
        ws = {"workspace_id": "loan_okafor", "conditions": [c1]}
        conditions.apply_decisions(
            ws,
            [{"condition_id": "cond_001", "decision": "needs_review",
              "reason": "borrower mismatch", "document_id": "doc_002"}],
        )
        conditions.recompute_next_action(
            ws,
            [{"condition_id": "cond_001", "decision": "needs_review",
              "reason": "borrower mismatch"}],
        )
        assert "needs your review" in ws["next_action"]
        assert "still need" in ws["next_action"] or "still needs" in ws["next_action"]

    def test_no_op_when_no_decisions(self):
        cond = _condition("Most recent paystub from borrower 1")
        ws = {"workspace_id": "loan_okafor", "conditions": [cond], "next_action": "unchanged"}
        result = conditions.recompute_next_action(ws, [])
        assert result is None
        assert ws["next_action"] == "unchanged"
