"""Conditions email ingest: parse → match → dedupe → apply.

All synthetic. Exercises the Gmail-connector path without depending on
the connector itself.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"

if "flo_team" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "flo_team", PLUGIN / "__init__.py",
        submodule_search_locations=[str(PLUGIN)],
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["flo_team"] = _module
    _spec.loader.exec_module(_module)

from flo_team import conditions_ingest as ci  # noqa: E402


def _ws(wid="loan_j", name="Johnson", **extra):
    base = {"workspace_id": wid, "display_name": name, "milestone": "Processing",
            "conditions": []}
    base.update(extra)
    return base


LENDER_EMAIL = """\
Hi Ashley,

We have the following conditions on loan Johnson:
1. Provide most recent paystub from borrower 1
2. Bank statement: most recent 2 months
3. Title company to provide updated title commitment

Thank you,
Underwriter
"""


# ── identity ───────────────────────────────────────────────────────────────

class TestIdentity:
    def test_condition_identity_stable_across_cases(self):
        a = ci.condition_identity({"condition_type": "paystub", "owner": "Borrower",
                                    "original_text": "  Most Recent PAYSTUB!  "})
        b = ci.condition_identity({"condition_type": "paystub", "owner": "Borrower",
                                    "original_text": "most recent paystub"})
        assert a == b

    def test_condition_identity_differs_for_different_owner(self):
        a = ci.condition_identity({"condition_type": "paystub", "owner": "Borrower",
                                    "original_text": "Paystub"})
        b = ci.condition_identity({"condition_type": "paystub", "owner": "Title",
                                    "original_text": "Paystub"})
        assert a != b

    def test_email_identity_changes_with_source_ref(self):
        a = ci.email_identity("gmail", "msg_1", "hello")
        b = ci.email_identity("gmail", "msg_2", "hello")
        assert a != b


# ── parse ──────────────────────────────────────────────────────────────────

class TestParse:
    def test_lender_email_three_conditions(self):
        rows = ci.parse_email_to_conditions(LENDER_EMAIL, source="lender_email")
        types = [r["condition_type"] for r in rows]
        assert types == ["paystub", "bank_statement", "title_commitment"]
        owners = [r["owner"] for r in rows]
        assert owners == ["Borrower", "Borrower", "Title"]
        # every row carries a stable identity
        for r in rows:
            assert r["identity"].startswith("cond_")


# ── workspace match ─────────────────────────────────────────────────────────

class TestWorkspaceMatch:
    def test_high_confidence_by_borrower_name(self):
        ws = [_ws("loan_j", "Johnson"), _ws("loan_b", "Bell")]
        match = ci.match_workspace(ws, borrower_name="Johnson")
        assert match["confidence"] == "high"
        assert match["workspace_id"] == "loan_j"

    def test_high_confidence_by_property_address(self):
        ws = [_ws("loan_a", "Asmith"),
               _ws("loan_b", "Bell", property_address="123 Main St, Springfield")]
        match = ci.match_workspace(ws, property_address="123 Main St")
        assert match["confidence"] == "high"
        assert match["workspace_id"] == "loan_b"

    def test_high_confidence_by_loan_number(self):
        ws = [_ws("loan_a", "Asmith", loan_number="LN-001"),
               _ws("loan_b", "Bell", loan_number="LN-002")]
        match = ci.match_workspace(ws, loan_number="LN-002")
        assert match["confidence"] == "high"
        assert match["workspace_id"] == "loan_b"

    def test_high_confidence_by_sender_domain(self):
        ws = [_ws("loan_a", "Asmith", lender_name="First National Bank"),
               _ws("loan_b", "Bell", lender_name="Wells Fargo")]
        match = ci.match_workspace(ws, sender="uw@firstnational.example")
        assert match["confidence"] == "high"
        assert match["workspace_id"] == "loan_a"

    def test_medium_confidence_when_two_workspaces_equal(self):
        # Both contain "Smith" — no way to disambiguate.
        ws = [_ws("loan_a", "Alice Smith"), _ws("loan_b", "Bob Smith")]
        match = ci.match_workspace(ws, borrower_name="Smith")
        assert match["confidence"] == "medium"
        assert match["workspace_id"] is None
        assert len(match["candidates"]) >= 2

    def test_no_match_returns_none(self):
        ws = [_ws("loan_a", "Asmith")]
        match = ci.match_workspace(ws, borrower_name="Nobody")
        assert match["confidence"] == "none"
        assert match["workspace_id"] is None


# ── dedupe ─────────────────────────────────────────────────────────────────

class TestDedupe:
    def test_new_conditions_pass_through(self):
        ws = _ws()
        rows = ci.parse_email_to_conditions(LENDER_EMAIL)
        diff = ci.diff_against_workspace(rows, ws, email_id="email_1")
        assert len(diff["new"]) == 3
        assert diff["duplicates"] == []

    def test_duplicate_email_already_applied_skipped(self):
        ws = _ws()
        rows = ci.parse_email_to_conditions(LENDER_EMAIL)
        # simulate first apply
        ci.apply_proposed(ws, rows, source="lender_email", source_ref="msg_1",
                          email_id="email_1")
        # second email with the same email_id should produce zero new rows
        diff = ci.diff_against_workspace(rows, ws, email_id="email_1")
        assert diff["new"] == []
        assert diff["email_already_applied"] is True

    def test_duplicate_condition_text_detected(self):
        ws = _ws()
        rows = ci.parse_email_to_conditions("1. Most recent paystub")
        ci.apply_proposed(ws, rows, source="lender_email", source_ref="msg_1")
        # rephrase — same identity, different words
        rows2 = ci.parse_email_to_conditions("Need most recent paystub")
        diff = ci.diff_against_workspace(rows2, ws, email_id="email_2")
        assert diff["new"] == []
        assert len(diff["duplicates"]) == 1

    def test_same_text_different_owner_not_a_duplicate(self):
        # This is the case the auto-clear hook flagged as 'needs_review':
        # same condition text but the owner disagrees. We must NOT collapse
        # it silently — that's a real-world ambiguity and Ashley should
        # see it.
        ws = _ws()
        rows = ci.parse_email_to_conditions("Most recent paystub")
        ci.apply_proposed(ws, rows, source="lender_email")
        # force a same-text, different-owner row
        new_rows = ci.parse_email_to_conditions("Most recent paystub from co-borrower")
        diff = ci.diff_against_workspace(new_rows, ws, email_id="email_2")
        # different owner → different identity → NOT a duplicate
        assert len(diff["new"]) == 1


# ── apply ──────────────────────────────────────────────────────────────────

class TestApply:
    def test_writes_conditions_with_source_attribution(self):
        ws = _ws()
        rows = ci.parse_email_to_conditions(LENDER_EMAIL)
        written = ci.apply_proposed(ws, rows, source="lender_email",
                                     source_ref="msg_abc", email_id="email_xyz")
        assert len(written) == 3
        for c in ws["conditions"]:
            assert c["source"] == "lender_email"
            assert c["source_ref"] == "msg_abc"
            assert any(r.get("email_id") == "email_xyz" for r in c["source_refs"])

    def test_idempotent_double_apply(self):
        ws = _ws()
        rows = ci.parse_email_to_conditions(LENDER_EMAIL)
        written1 = ci.apply_proposed(ws, rows, source="lender_email",
                                      source_ref="msg_1", email_id="email_1")
        written2 = ci.apply_proposed(ws, rows, source="lender_email",
                                      source_ref="msg_1", email_id="email_1")
        assert len(written1) == 3
        assert written2 == []
        assert len(ws["conditions"]) == 3

    def test_email_content_cannot_self_authorize_milestone(self):
        """Email can describe a CTC notice but must not change the milestone
        on its own. The apply path writes conditions only; the milestone
        change goes through a separate confirm path (handled by tests in
        test_ctc.py). This test pins that the apply path doesn't touch
        milestone."""
        ws = _ws(milestone="Processing")
        rows = ci.parse_email_to_conditions(LENDER_EMAIL)
        ci.apply_proposed(ws, rows, source="lender_email")
        assert ws["milestone"] == "Processing"
        # And no CTC fields appear from this code path
        assert "ctc_confirmed_at" not in ws
