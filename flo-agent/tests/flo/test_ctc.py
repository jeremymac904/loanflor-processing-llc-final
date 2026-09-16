"""CTC readiness + lender CTC notice detection + milestone confirmation.

All synthetic fixtures.
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

from flo_team import ctc  # noqa: E402


def _ws(*conditions, milestone="Processing"):
    return {"workspace_id": "loan_test", "display_name": "Test", "milestone": milestone,
            "conditions": [{"id": f"c{i}", "state": s, "text": t}
                            for i, (s, t) in enumerate(conditions)]}


def _cond(state, text="Most recent paystub"):
    return (state, text)


# ── readiness ──────────────────────────────────────────────────────────────

class TestReadiness:
    def test_no_conditions_yet(self):
        ws = _ws()
        r = ctc.ctc_readiness(ws)
        assert r["open_count"] == 0
        assert r["waiting_count"] == 0
        assert r["needs_review_count"] == 0
        assert r["cleared_count"] == 0
        assert r["all_tracked"] is False
        assert "nothing tracked" in r["summary"].lower()

    def test_open_conditions_counted(self):
        ws = _ws(_cond("open"), _cond("open"))
        r = ctc.ctc_readiness(ws)
        assert r["open_count"] == 2
        assert "2 open" in r["summary"]

    def test_waiting_and_needs_review_counted(self):
        ws = _ws()
        ws["conditions"] = [
            {"id": "1", "state": "waiting"},
            {"id": "2", "state": "open"},
            {"id": "3", "state": "open", "needs_review": True},
        ]
        r = ctc.ctc_readiness(ws)
        assert r["waiting_count"] == 1
        assert r["open_count"] == 1
        assert r["needs_review_count"] == 1
        assert "almost there" in r["summary"]

    def test_all_cleared(self):
        ws = _ws()
        ws["conditions"] = [
            {"id": "1", "state": "cleared"},
            {"id": "2", "state": "cleared"},
        ]
        r = ctc.ctc_readiness(ws)
        assert r["all_tracked"] is True
        assert "everything" in r["summary"].lower()
        assert "waiting on the lender" in r["summary"].lower()

    def test_does_not_say_ctc_when_open_items_remain(self):
        # Critical: Flo must not say "Clear to Close" itself.
        ws = _ws()
        ws["conditions"] = [
            {"id": "1", "state": "cleared"},
            {"id": "2", "state": "open"},
        ]
        r = ctc.ctc_readiness(ws)
        assert r["all_tracked"] is False
        # The summary must NOT contain "you are clear to close" or similar
        forbidden = ("you are clear to close", "you\u2019re clear to close", "approved for closing")
        for f in forbidden:
            assert f not in r["summary"].lower()


# ── lender notice detection ───────────────────────────────────────────────

class TestLenderCtcDetection:
    @pytest.mark.parametrize("body,subject,sender,expect_ctc,confidence", [
        # Strong signals
        ("The loan is approved and we are clear to close.",
            "Clear to Close", "uw@bank.example", True, "high"),
        ("Clear-to-Close issued for loan #12345.",
            "CTC notice", "closer@bank.example", True, "high"),
        ("Final approval — ready to close.",
            "Final approval", "funding@bank.example", True, "high"),
        # Medium: phrase but no recognized sender
        ("You are clear to close. Funding is approved.",
            "Status update", "", True, "medium"),
        ("We are clear to close on this file.",
            "Update", "random@example.com", True, "medium"),
        # Negative
        ("", "", "", False, "low"),
        ("Loan is moving along, conditions still outstanding.",
            "Update", "uw@bank.example", False, "low"),
        ("NOT clear to close yet — please send the paystub.",
            "Update", "uw@bank.example", False, "low"),
        ("Cannot issue CTC until conditions clear.",
            "Update", "uw@bank.example", False, "low"),
    ])
    def test_detect(self, body, subject, sender, expect_ctc, confidence):
        r = ctc.looks_like_lender_ctc(body, sender=sender, subject=subject)
        assert r["is_ctc"] is expect_ctc
        assert r["confidence"] == confidence


# ── confirm_clear_to_close ────────────────────────────────────────────────

class TestConfirm:
    def test_sets_milestone(self):
        ws = _ws()
        out = ctc.confirm_clear_to_close(ws, confirmed_by="ashley",
                                            source="lender_email",
                                            source_ref="msg_123",
                                            evidence="We are clear to close.")
        assert out["already_ctc"] is False
        assert ws["milestone"] == "Clear to Close"
        assert ws["ctc_confirmed_by"] == "ashley"
        assert ws["ctc_source"] == "lender_email"
        assert ws["ctc_source_ref"] == "msg_123"
        assert "clear to close" in ws["ctc_evidence"]

    def test_idempotent(self):
        ws = _ws()
        ctc.confirm_clear_to_close(ws, confirmed_by="ashley", source="lender_email")
        out2 = ctc.confirm_clear_to_close(ws, confirmed_by="ashley", source="lender_email")
        assert out2["already_ctc"] is True

    def test_evidence_truncated(self):
        ws = _ws()
        ctc.confirm_clear_to_close(ws, confirmed_by="ashley", source="manual",
                                    evidence="x" * 1000)
        assert len(ws["ctc_evidence"]) == 400


# ── celebration message ───────────────────────────────────────────────────

class TestCelebration:
    def test_short_with_borrower_name(self):
        ws = {"workspace_id": "loan_j", "display_name": "Johnson"}
        s = ctc.ctc_celebration(ws)
        assert "Johnson" in s
        assert "CTC" in s
        assert "💚" in s

    def test_falls_back_to_workspace_id(self):
        ws = {"workspace_id": "loan_xyz"}
        s = ctc.ctc_celebration(ws)
        assert "loan_xyz" in s
