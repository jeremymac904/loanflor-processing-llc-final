"""Integration tests for the flo_ctc_email tool handler.

Drives the handler end-to-end against an isolated workspace root.
Flo never grants CTC: email can DESCRIBE the milestone change; Ashley
must CONFIRM. The apply path is refused if the recognition verdict
isn't 'is_ctc=True' (defense-in-depth — keeps the tool from writing
the milestone on a vague email).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"


def _load_flo_team():
    if "flo_team" not in sys.modules:
        _spec = importlib.util.spec_from_file_location(
            "flo_team", PLUGIN / "__init__.py",
            submodule_search_locations=[str(PLUGIN)],
        )
        mod = importlib.util.module_from_spec(_spec)
        sys.modules["flo_team"] = mod
        _spec.loader.exec_module(mod)
    return sys.modules["flo_team"]


@pytest.fixture()
def ft(tmp_path, monkeypatch):
    _load_flo_team()
    import flo_team.tools as tools_mod
    import flo_team.workspace as workspace_mod
    monkeypatch.setattr(tools_mod, "_root", lambda: tmp_path)
    store = workspace_mod.WorkspaceStore(tmp_path)
    store.create(display_name="Johnson", workspace_id="loan_j", milestone="Processing",
                  program="fha")
    return sys.modules["flo_team"]


def _call(ft, **kwargs):
    return json.loads(ft.tools.handle_flo_ctc_email(kwargs))


class TestPropose:
    def test_detects_lender_ctc_phrase(self, ft):
        result = _call(ft, action="propose",
                        raw_text="We are clear to close on this file. Funding is approved.",
                        sender="uw@bank.example",
                        subject="Clear to Close")
        assert result["stage"] == "propose"
        assert result["is_ctc"] is True
        assert result["confidence"] == "high"
        assert result["matched_phrase"]

    def test_rejects_negative_phrase(self, ft):
        result = _call(ft, action="propose",
                        raw_text="Not clear to close yet. Please send the paystub.",
                        sender="uw@bank.example")
        assert result["is_ctc"] is False
        assert "not clear" in result["reason"]

    def test_rejects_ambiguous_phrase(self, ft):
        # no positive or negative phrase
        result = _call(ft, action="propose",
                        raw_text="Loan is moving along, please send the W-2.",
                        sender="uw@bank.example")
        assert result["is_ctc"] is False
        assert result["confidence"] == "low"

    def test_phrase_only_phrase_without_lender_sender(self, ft):
        result = _call(ft, action="propose",
                        raw_text="You are clear to close. Funding is approved.",
                        sender="random@example.com")
        assert result["is_ctc"] is True
        assert result["confidence"] == "medium"  # phrase but no lender hint

    def test_negative_phrase_takes_precedence_over_positive(self, ft):
        # Body says both "not clear to close" and "clear to close" — the
        # negative wins.
        result = _call(ft, action="propose",
                        raw_text="We are not clear to close yet, even though someone said clear to close.",
                        sender="uw@bank.example")
        assert result["is_ctc"] is False


class TestApply:
    def test_writes_milestone_after_ashley_confirmation(self, ft):
        body = "Clear to close issued. We have approved."
        result = _call(ft, action="apply",
                        workspace_id="loan_j", raw_text=body,
                        sender="uw@bank.example",
                        subject="CTC",
                        source_ref="msg_ctc_1")
        assert result["stage"] == "apply"
        assert result["milestone"] == "Clear to Close"
        ws = ft.workspace.WorkspaceStore(_root_for_ft(ft)).get("loan_j")
        assert ws["milestone"] == "Clear to Close"
        assert ws["ctc_confirmed_by"] == "ashley"
        assert ws["ctc_source"] == "lender_email"
        assert ws["ctc_source_ref"] == "msg_ctc_1"
        assert "celebration" in result
        assert "Johnson is CTC" in result["celebration"]

    def test_refuses_non_ctc_email(self, ft):
        result = _call(ft, action="apply",
                        workspace_id="loan_j",
                        raw_text="Not yet clear to close. Conditions outstanding.",
                        sender="uw@bank.example")
        assert "error" in result
        ws = ft.workspace.WorkspaceStore(_root_for_ft(ft)).get("loan_j")
        assert ws["milestone"] == "Processing"  # NOT changed

    def test_refuses_ambiguous_email_even_when_apply_called(self, ft):
        # Defense-in-depth: the recognition runs again inside apply so
        # a vague email can't sneak through.
        result = _call(ft, action="apply",
                        workspace_id="loan_j",
                        raw_text="Hi, please send the W-2.",
                        sender="uw@bank.example")
        assert "error" in result
        ws = ft.workspace.WorkspaceStore(_root_for_ft(ft)).get("loan_j")
        assert ws["milestone"] == "Processing"

    def test_apply_requires_workspace_id(self, ft):
        result = _call(ft, action="apply",
                        raw_text="Clear to close issued.",
                        sender="uw@bank.example")
        assert "error" in result
        assert "workspace_id" in result["error"].lower()

    def test_idempotent_double_apply(self, ft):
        body = "Approved. Clear to close issued for loan Johnson."
        kwargs = {"action": "apply", "workspace_id": "loan_j", "raw_text": body,
                   "sender": "uw@bank.example", "source_ref": "msg_ctc_2"}
        r1 = _call(ft, **kwargs)
        r2 = _call(ft, **kwargs)
        assert r1["milestone"] == "Clear to Close"
        assert r2["already_ctc"] is True

    def test_duplicate_email_id_does_not_create_duplicate_audit(self, ft):
        body = "Clear to close issued."
        kwargs = {"action": "apply", "workspace_id": "loan_j", "raw_text": body,
                   "sender": "uw@bank.example", "source_ref": "msg_ctc_3"}
        r1 = _call(ft, **kwargs)
        r2 = _call(ft, **kwargs)
        assert r1["already_ctc"] is False or r1["already_ctc"] is None
        assert r2["already_ctc"] is True
        # Audit fields stay the same — second call didn't overwrite.
        ws = ft.workspace.WorkspaceStore(_root_for_ft(ft)).get("loan_j")
        assert ws["ctc_source_ref"] == "msg_ctc_3"


# ── safety: email cannot change other workspace state ─────────────────────

class TestSafetyBoundary:
    def test_apply_does_not_touch_other_files(self, ft):
        # Seed a second workspace; CTC apply on loan_j must not affect loan_b.
        ft.workspace.WorkspaceStore(_root_for_ft(ft)).create(
            display_name="Bell", workspace_id="loan_b", milestone="Processing")
        _call(ft, action="apply", workspace_id="loan_j",
              raw_text="Clear to close issued.",
              sender="uw@bank.example")
        loan_b = ft.workspace.WorkspaceStore(_root_for_ft(ft)).get("loan_b")
        assert loan_b["milestone"] == "Processing"
        assert "ctc_confirmed_at" not in loan_b


# ── helpers ────────────────────────────────────────────────────────────────

def _root_for_ft(ft):
    return ft.tools._root()
