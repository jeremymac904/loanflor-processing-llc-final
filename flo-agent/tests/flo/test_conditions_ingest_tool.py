"""Integration tests for the flo_conditions_ingest tool handler.

Drives the handler end-to-end against an isolated workspace root. No
network, no Gmail connector, no filesystem leakage outside tmp_path.

The CTC email handler (flo_ctc_email) has its own integration tests in
test_ctc_email_tool.py — kept separate so each commit is auditable.
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
    store.create(display_name="Johnson", workspace_id="loan_j", milestone="Processing")
    return sys.modules["flo_team"]


LENDER_EMAIL = """\
Hi Ashley,

We have the following conditions on loan Johnson:
1. Provide most recent paystub from borrower 1
2. Bank statement: most recent 2 months
3. Title company to provide updated title commitment

Thank you,
Underwriter
"""


def _call(ft, **kwargs):
    return json.loads(ft.tools.handle_flo_conditions_ingest(kwargs))


# ── propose ────────────────────────────────────────────────────────────────

class TestPropose:
    def test_returns_diff_without_mutating(self, ft):
        before = json.loads(json.dumps(ft.workspace.WorkspaceStore(_root_for_ft(ft)).get("loan_j")))
        result = _call(ft, action="propose", raw_text=LENDER_EMAIL,
                       borrower_name="Johnson",
                       sender="uw@bank.example", source_ref="msg_1",
                       subject="Conditions", received_at="2026-09-16")
        after = ft.workspace.WorkspaceStore(_root_for_ft(ft)).get("loan_j")
        assert result["stage"] == "propose"
        assert len(result["new_conditions"]) == 3
        assert result["email_already_applied"] is False
        assert before["conditions"] == after["conditions"]  # NOT mutated
        # borrower_name=Johnson is a high-confidence match against the
        # existing Johnson workspace.
        assert result["workspace_match"]["confidence"] == "high"

    def test_explicit_workspace_id_high_confidence(self, ft):
        result = _call(ft, action="propose", raw_text=LENDER_EMAIL,
                       workspace_id="loan_j", source_ref="msg_1")
        assert result["workspace_match"]["confidence"] == "high"
        assert result["workspace_match"]["workspace_id"] == "loan_j"

    def test_no_workspace_match_returns_none(self, ft):
        result = _call(ft, action="propose",
                       raw_text="Conditions on loan Smith: 1. Paystub",
                       source_ref="msg_x")
        # workspace named "Johnson" exists; email mentions "Smith"
        # → no signal match → confidence none
        assert result["workspace_match"]["confidence"] == "none"

    def test_email_already_applied_flag(self, ft):
        # First apply
        _apply_first(ft)
        # Then re-run propose with same email_id
        result = _call(ft, action="propose", raw_text=LENDER_EMAIL,
                       workspace_id="loan_j", source_ref="msg_1")
        assert result["email_already_applied"] is True
        assert result["new_conditions"] == []


# ── apply ──────────────────────────────────────────────────────────────────

class TestApply:
    def test_writes_conditions_with_attribution(self, ft):
        result = _call(ft, action="propose", raw_text=LENDER_EMAIL,
                       workspace_id="loan_j", source_ref="msg_1")
        proposed = result["new_conditions"]
        applied = _call(ft, action="apply", workspace_id="loan_j",
                        raw_text=LENDER_EMAIL, source_ref="msg_1",
                        proposed=proposed)
        assert applied["stage"] == "apply"
        assert applied["written_count"] == 3

        ws = ft.workspace.WorkspaceStore(_root_for_ft(ft)).get("loan_j")
        assert len(ws["conditions"]) == 3
        for c in ws["conditions"]:
            assert c["source"] == "lender_email"
            assert c["source_ref"] == "msg_1"
            assert c["owner"] in {"Borrower", "Title"}
            assert c["plain_english"]
            assert c["required_item"]
            # identity stamped
            assert c.get("identity", "").startswith("cond_")

    def test_idempotent_re_apply_no_double_write(self, ft):
        result = _call(ft, action="propose", raw_text=LENDER_EMAIL,
                       workspace_id="loan_j", source_ref="msg_1")
        proposed = result["new_conditions"]
        _call(ft, action="apply", workspace_id="loan_j", raw_text=LENDER_EMAIL,
              source_ref="msg_1", proposed=proposed)
        ws_after_first = ft.workspace.WorkspaceStore(_root_for_ft(ft)).get("loan_j")
        # re-apply with the same proposed batch — must be a no-op
        applied2 = _call(ft, action="apply", workspace_id="loan_j",
                         raw_text=LENDER_EMAIL, source_ref="msg_1",
                         proposed=proposed)
        ws_after_second = ft.workspace.WorkspaceStore(_root_for_ft(ft)).get("loan_j")
        assert applied2["written_count"] == 0
        assert len(ws_after_first["conditions"]) == len(ws_after_second["conditions"]) == 3

    def test_apply_requires_workspace_id(self, ft):
        result = _call(ft, action="apply", raw_text=LENDER_EMAIL,
                       source_ref="msg_1", proposed=[{"identity": "x"}])
        assert "error" in result
        assert "workspace_id" in result["error"].lower()

    def test_apply_requires_proposed(self, ft):
        result = _call(ft, action="apply", workspace_id="loan_j",
                       raw_text=LENDER_EMAIL)
        assert "error" in result
        assert "proposed" in result["error"].lower()

    def test_email_content_cannot_self_authorize_milestone(self, ft):
        result = _call(ft, action="propose", raw_text=LENDER_EMAIL,
                       workspace_id="loan_j", source_ref="msg_1")
        _call(ft, action="apply", workspace_id="loan_j", raw_text=LENDER_EMAIL,
              source_ref="msg_1", proposed=result["new_conditions"])
        ws = ft.workspace.WorkspaceStore(_root_for_ft(ft)).get("loan_j")
        assert ws["milestone"] == "Processing"  # NOT changed by condition email
        assert "ctc_confirmed_at" not in ws


# ── helpers ────────────────────────────────────────────────────────────────

def _root_for_ft(ft):
    """Pull the tmp_path root the test fixture set via monkeypatch."""
    return ft.tools._root()


def _apply_first(ft):
    """Apply the lender email once so the propose re-run hits the
    'already applied' path."""
    result = _call(ft, action="propose", raw_text=LENDER_EMAIL,
                   workspace_id="loan_j", source_ref="msg_1")
    _call(ft, action="apply", workspace_id="loan_j", raw_text=LENDER_EMAIL,
          source_ref="msg_1", proposed=result["new_conditions"])
