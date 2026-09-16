"""Conditions waiting-state: mark_waiting / clear_waiting / mark_waiting_by_owner.

Pure backend logic. Synthetic workspaces only.
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

from flo_team import conditions  # noqa: E402
from flo_team import conditions_normalize as cn  # noqa: E402


def _ws(*conditions):
    ws = {"workspace_id": "loan_test", "display_name": "Test", "conditions": list(conditions)}
    cn.normalize_workspace(ws)
    return ws


def _cond(id, owner, *, text=None, state="open", required_item="item"):
    return {"id": id, "text": text or f"{owner} task {id}", "owner": owner,
            "required_item": required_item, "state": state, "status": state.title()}


# ── mark_waiting ────────────────────────────────────────────────────────────

class TestMarkWaiting:
    def test_marks_open_conditions_waiting(self):
        ws = _ws(_cond("c1", "Borrower"), _cond("c2", "Title"))
        out = conditions.mark_waiting(ws, ["c1", "c2"])
        assert len(out) == 2
        assert ws["conditions"][0]["state"] == "waiting"
        assert ws["conditions"][0]["status"] == "Waiting"
        assert "waiting_at" in ws["conditions"][0]
        assert "waiting_by" in ws["conditions"][0]

    def test_idempotent_no_double_mark(self):
        ws = _ws(_cond("c1", "Borrower"))
        conditions.mark_waiting(ws, ["c1"])
        out2 = conditions.mark_waiting(ws, ["c1"])
        assert out2 == []  # already waiting
        assert ws["conditions"][0]["state"] == "waiting"

    def test_cleared_conditions_not_flipped(self):
        ws = _ws(_cond("c1", "Borrower", state="cleared"))
        out = conditions.mark_waiting(ws, ["c1"])
        assert out == []
        assert ws["conditions"][0]["state"] == "cleared"

    def test_unknown_id_no_error(self):
        ws = _ws(_cond("c1", "Borrower"))
        out = conditions.mark_waiting(ws, ["unknown"])
        assert out == []
        assert ws["conditions"][0]["state"] == "open"

    def test_reason_truncated(self):
        ws = _ws(_cond("c1", "Borrower"))
        conditions.mark_waiting(ws, ["c1"], reason="x" * 500)
        assert len(ws["conditions"][0]["waiting_reason"]) == 200


# ── mark_waiting_by_owner ───────────────────────────────────────────────────

class TestMarkWaitingByOwner:
    def test_flips_all_open_borrower(self):
        ws = _ws(
            _cond("c1", "Borrower"),
            _cond("c2", "Borrower"),
            _cond("c3", "Title"),
            _cond("c4", "Loan Officer"),
        )
        out = conditions.mark_waiting_by_owner(ws, "Borrower", actor="whisper",
                                                reason="borrower email sent")
        assert [c["condition_id"] for c in out] == ["c1", "c2"]
        for c in ws["conditions"]:
            if c["id"] in {"c1", "c2"}:
                assert c["state"] == "waiting"
            else:
                assert c["state"] == "open"

    def test_skips_cleared_in_owner(self):
        ws = _ws(
            _cond("c1", "Borrower"),
            _cond("c2", "Borrower", state="cleared"),
        )
        out = conditions.mark_waiting_by_owner(ws, "Borrower")
        assert [c["condition_id"] for c in out] == ["c1"]
        assert ws["conditions"][1]["state"] == "cleared"  # untouched

    def test_empty_owner_is_no_op(self):
        ws = _ws(_cond("c1", "Borrower"))
        out = conditions.mark_waiting_by_owner(ws, "")
        assert out == []

    def test_unknown_owner_is_no_op(self):
        ws = _ws(_cond("c1", "Borrower"))
        out = conditions.mark_waiting_by_owner(ws, "Imaginary Vendor")
        assert out == []


# ── clear_waiting ───────────────────────────────────────────────────────────

class TestClearWaiting:
    def test_reverts_waiting_to_open(self):
        ws = _ws(_cond("c1", "Borrower", state="waiting", text="open"))
        ws["conditions"][0]["state"] = "waiting"
        ws["conditions"][0]["status"] = "Waiting"
        out = conditions.clear_waiting(ws, ["c1"])
        assert out == ["c1"]
        assert ws["conditions"][0]["state"] == "open"

    def test_only_affects_waiting(self):
        ws = _ws(_cond("c1", "Borrower"))
        out = conditions.clear_waiting(ws, ["c1"])
        assert out == []

    def test_drops_waiting_metadata(self):
        ws = _ws(_cond("c1", "Borrower"))
        conditions.mark_waiting(ws, ["c1"], reason="test")
        conditions.clear_waiting(ws, ["c1"])
        cond = ws["conditions"][0]
        for key in ("waiting_at", "waiting_by", "waiting_reason"):
            assert key not in cond


# ── waiting helpers (read-only) ────────────────────────────────────────────

class TestWaitingRead:
    def test_waiting_owners_returns_only_present(self):
        ws = _ws(
            _cond("c1", "Borrower", state="waiting"),
            _cond("c2", "Title"),
        )
        assert conditions.waiting_owners(ws) == ["Borrower"]  # Title still open

    def test_waiting_label_known_owner(self):
        assert conditions.waiting_label("Borrower") == "Waiting on borrower"
        assert conditions.waiting_label("Title") == "Waiting on title"
        assert conditions.waiting_label("Lender/UW") == "Waiting on lender"

    def test_waiting_label_unknown_owner_falls_back(self):
        assert "imaginary" in conditions.waiting_label("Imaginary Vendor").lower()


# ── cross-check with auto-clear ────────────────────────────────────────────

class TestInteropWithAutoClear:
    def test_cleared_via_doc_does_not_block_waiting(self):
        # already-cleared conditions stay cleared when mark_waiting runs.
        ws = _ws(_cond("c1", "Borrower"), _cond("c2", "Title"))
        # simulate an auto-clear on c1
        ws["conditions"][0]["state"] = "cleared"
        conditions.mark_waiting_by_owner(ws, "Borrower")
        # c1 stays cleared (skipped), c2 still open (different owner)
        assert ws["conditions"][0]["state"] == "cleared"
        assert ws["conditions"][1]["state"] == "open"

    def test_waiting_then_cleared_flips_to_cleared(self):
        ws = _ws(_cond("c1", "Borrower", text="Most recent paystub",
                       required_item="paystub"))
        cn.normalize_workspace(ws)
        conditions.mark_waiting(ws, ["c1"])
        assert ws["conditions"][0]["state"] == "waiting"
        # simulate the auto-clear hook firing
        fake_doc = {
            "document_id": "doc_001",
            "category": "income", "subcategory": "paystub",
            "borrower_ref": "borrower", "status": "received",
            "page_count": 1, "checks": {"pages": {"missing": [], "expected": 1}},
            "display_name": "paystub.pdf", "text_path": None,
        }
        decisions = conditions.evaluate_document_for_conditions(ws["conditions"], fake_doc)
        conditions.apply_decisions(ws, decisions)
        assert ws["conditions"][0]["state"] == "cleared"
