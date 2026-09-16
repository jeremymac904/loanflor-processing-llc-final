"""Ashley's Today view and one-file summary: plain English, same rules as the desktop screens."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"


@pytest.fixture(scope="module")
def today():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    import importlib as _il

    return _il.import_module("flo_team.today")


OKAFOR = {
    "workspace_id": "loan_okafor", "display_name": "Okafor", "milestone": "Processing", "program": "fha", "blockers": [], "orders": [], "conditions": [],
    "drafts": [{"draft_id": "draft_1", "status": "draft", "audience": "borrower", "purpose": "2024 W-2 request", "body": "Hi"}],
    "readiness": {"status": "IN_PROGRESS", "score": 58, "missing_count": 1, "missing": [{"item": "2024 W-2", "owner": "borrower"}], "aus_findings": "present",
                  "best_next_move": "Only blocker right now: 2024 W-2 from borrower. One clean follow-up.",
                  "income_assets": {"income_prep_complete": True, "assets_prep_complete": False}},
    "updated_at": "2026-09-09T14:00:00+00:00",
}
BELL = {
    "workspace_id": "loan_bell", "display_name": "Bell", "milestone": "Conditional Approval",
    "orders": [{"order_id": "ord_1", "order_type": "title", "state": "overdue", "vendor_or_destination": "Approved Title Vendor"}],
    "readiness": {"status": "IN_PROGRESS", "score": 70, "missing_count": 0, "missing": [], "aus_findings": "present"},
    "updated_at": "2026-09-09T15:00:00+00:00",
}
MASON = {"workspace_id": "loan_mason", "display_name": "Mason", "milestone": "Processing",
         "readiness": {"status": "READY_FOR_NEXT_STEP", "score": 100, "missing_count": 0, "missing": [], "aus_findings": "present"}}
APPROVAL = {"proposal_id": "prop_1", "workspace_id": "loan_mason", "agent": "whisper", "action_type": "email_send", "tool_name": "flo_email_send",
            "recipient_or_destination": "borrower (Mason)", "summary": "Send the missing-paystub request to the borrower", "payload_hash": "abc123",
            "payload_preview": {"subject": "Quick item", "body": "Hi John", "audience": "borrower"}, "policy_result": "confirm", "status": "pending",
            "created_at": "2026-09-09T15:30:00+00:00", "expires_at": "2099-01-01T00:00:00+00:00"}
ACTIVITY = [
    {"timestamp": "2026-09-09T14:12:49+00:00", "actor": "malcolm", "event": "readiness.updated", "workspace_id": "loan_okafor"},
    {"timestamp": "2026-09-09T14:21:36+00:00", "actor": "whisper", "event": "draft.added", "workspace_id": "loan_okafor"},
    {"timestamp": "2026-09-09T14:30:00+00:00", "actor": "flo", "event": "handoff.created", "workspace_id": "loan_bell", "to": "sage"},
    {"timestamp": "2026-09-09T14:31:00+00:00", "actor": "provider_state", "event": "provider.transition"},
]


class TestPlainStatus:
    def test_only_six_words_and_worst_news_wins(self, today):
        assert today.plain_status(OKAFOR) == "Needs Ashley"
        assert today.plain_status(BELL) == "At Risk"
        assert today.plain_status(MASON) == "Done"
        assert today.plain_status({**OKAFOR, "drafts": [], "blockers": [{"text": "Lender portal locked"}]}) == "Blocked"
        assert today.plain_status({**OKAFOR, "drafts": []}) == "Waiting"
        working = [{"task_id": "t", "workspace_id": "loan_okafor", "status": "sent"}]
        assert today.plain_status({**OKAFOR, "drafts": [], "readiness": None}, [], working) == "Working"
        assert today.plain_status(MASON, [APPROVAL]) == "Needs Ashley"
        assert set(today.STATUSES) == {"Done", "Needs Ashley", "Waiting", "Working", "At Risk", "Blocked"}

    def test_readiness_in_words(self, today):
        assert today.readiness_label(OKAFOR) == "Needs 1 item"
        assert today.readiness_label({**OKAFOR, "readiness": {**OKAFOR["readiness"], "missing_count": 0, "missing": []}}) == "Almost ready"
        assert today.readiness_label(MASON) == "Ready"
        assert today.readiness_label({**OKAFOR, "readiness": None}) == "Not checked yet"


class TestFileSummary:
    def test_one_clean_summary_never_says_approved(self, today):
        s = today.file_summary(OKAFOR)
        assert (s["name"], s["status"], s["readiness"], s["aus"], s["income"], s["assets"], s["orders"], s["conditions"]) == (
            "Okafor", "Needs Ashley", "Needs 1 item", "Findings on file", "Reviewed", "Needs attention", "Nothing ordered yet", "None open")
        assert s["best_next_move"] == "Request the missing documents."
        assert "2024 W-2" in today.best_next_move({**OKAFOR, "blockers": [{"text": "Lender portal locked"}]})
        assert s["is_underwriting_decision"] is False
        assert "approved" not in str(s).lower()
        assert s["say_it_like"].startswith("Okafor — needs 1 item (needs ashley, Processing).")
        assert "Whisper has the request drafted" in s["say_it_like"]
        assert today.file_summary(BELL)["risk"] == "Title is overdue"
        assert today.file_summary(BELL)["orders"] == "Title: overdue"


class TestToday:
    def test_top_three_fastest_win_biggest_risk_and_counts(self, today):
        model = today.build([OKAFOR, BELL, MASON], [APPROVAL], [], ACTIVITY, now=datetime(2026, 9, 9, 13, 0))
        assert model["greeting"] == "Afternoon Ash"
        assert [t["name"] for t in model["top"]] == ["Bell", "Okafor", "Mason"]
        assert model["top"][0]["line"] == "Title is overdue"
        assert model["biggest_risk"]["line"] == "Bell: Title is overdue."
        assert model["fastest_win"]["line"] == "Approve: Send borrower email for Mason."
        assert model["needs_you"] == 2 and model["waiting_on_others"] == 2
        assert model["handling"] == ["Sage is checking a guideline on Bell.", "Whisper drafted a message for Okafor.", "Malcolm checked the Okafor file."]
        assert model["say_it_like"].splitlines()[1] == "Best next move: Bell — Title is overdue"
        assert today.greeting(datetime(2026, 9, 9, 8, 0)) == "Morning Ash ☕"
        for word in ("pending_review", "handoff", "provider", "READY_FOR_NEXT_STEP", "IN_PROGRESS"):
            assert word not in str(model)

    def test_from_root_reads_the_team_state(self, today, tmp_path):
        import json

        (tmp_path / "workspaces").mkdir()
        (tmp_path / "workspaces" / "loan_bell.json").write_text(json.dumps(BELL), encoding="utf-8")
        model = today.from_root(tmp_path)
        assert model["top"][0]["name"] == "Bell" and model["needs_you"] == 0
