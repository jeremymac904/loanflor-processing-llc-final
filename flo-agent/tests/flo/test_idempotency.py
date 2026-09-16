"""Draft and side-effect idempotency: one active draft / order / execution, never three."""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"


@pytest.fixture(scope="session")
def ft():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    names = ("tools", "intents", "drafts", "approvals_center", "marketing", "workspace")
    for name in names:
        importlib.import_module(f"flo_team.{name}")
    mods = {name: sys.modules[f"flo_team.{name}"] for name in names}
    mods["plugin"] = sys.modules["flo_team"]
    return mods


@pytest.fixture()
def env(tmp_path, monkeypatch, ft):
    monkeypatch.setattr(ft["tools"], "_STATE_ROOT_OVERRIDE", tmp_path / "team")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "profiles" / "flo"))
    monkeypatch.setenv("HERMES_PROFILE_NAME", "flo")
    ws = json.loads(ft["tools"].handle_flo_workspace({"action": "create", "display_name": "Synthetic-Idem", "fields": {"program": "conventional", "agency": "freddie"}}))
    return tmp_path / "team", ws["workspace_id"]


def _as(monkeypatch, name):
    monkeypatch.setenv("HERMES_PROFILE_NAME", name)


class TestDraftIdempotency:
    BODY_A = "Hi Riley, we need your most recent paystub with year-to-date earnings and the August bank statement. Thanks!"
    BODY_B = "Hello Riley — please send the newest paystub (with YTD) and your August statement when you can."

    def _create(self, ft, wid, body, needed="most recent paystub with YTD; August bank statement", source_task="task_1"):
        return json.loads(ft["tools"].handle_flo_draft({"action": "create", "workspace_id": wid, "audience": "borrower", "purpose": "missing document request",
                                                        "body": body, "needed": needed, "urgency": "can wait", "source_task": source_task}))

    def test_repeated_identical_handoff_returns_the_same_draft(self, env, ft, monkeypatch):
        root, wid = env
        _as(monkeypatch, "whisper")
        first = self._create(ft, wid, self.BODY_A)
        second = self._create(ft, wid, self.BODY_A)
        assert first["decision"] == "create_new" and second["decision"] == "return_existing" and second["draft_id"] == first["draft_id"]
        drafts = ft["workspace"].WorkspaceStore(root).get(wid)["drafts"]
        assert len(drafts) == 1

    def test_retry_with_different_wording_is_still_one_draft(self, env, ft, monkeypatch):
        root, wid = env
        _as(monkeypatch, "whisper")
        first = self._create(ft, wid, self.BODY_A)
        retry = self._create(ft, wid, self.BODY_B, needed="August bank statement; most recent paystub (with YTD)")
        assert retry["draft_id"] == first["draft_id"] and retry["deduplicated"]
        assert len(ft["workspace"].WorkspaceStore(root).get(wid)["drafts"]) == 1

    def test_resubmitted_task_and_duplicate_delivery_do_not_multiply(self, env, ft, monkeypatch):
        root, wid = env
        _as(monkeypatch, "whisper")
        for task in ("task_1", "task_1", "task_2"):  # duplicate message_agent delivery, then Flo resubmits the task
            self._create(ft, wid, self.BODY_A, source_task=task)
        assert len(ft["workspace"].WorkspaceStore(root).get(wid)["drafts"]) == 1

    def test_materially_different_request_is_a_new_draft(self, env, ft, monkeypatch):
        root, wid = env
        _as(monkeypatch, "whisper")
        self._create(ft, wid, self.BODY_A)
        other = self._create(ft, wid, "Please send the 2024 W-2.", needed="2024 W-2")
        assert other["decision"] == "create_new"
        assert len(ft["workspace"].WorkspaceStore(root).get(wid)["drafts"]) == 2

    def test_sent_or_rejected_draft_allows_a_fresh_one(self, env, ft, monkeypatch):
        root, wid = env
        _as(monkeypatch, "whisper")
        first = self._create(ft, wid, self.BODY_A)
        ft["tools"].handle_flo_draft({"action": "mark", "workspace_id": wid, "draft_id": first["draft_id"], "status": "rejected"})
        again = self._create(ft, wid, self.BODY_A)
        assert again["decision"] == "create_new" and again["draft_id"] != first["draft_id"]
        intent = ft["intents"].IntentRegistry(root).find_by_record(again["draft_id"])
        assert intent and intent["state"] == "pending" and intent["intent_id"] == first["draft_intent_id"]


class TestOrderAndExecutionIdempotency:
    def test_duplicate_title_order_retry_returns_existing(self, env, ft, monkeypatch):
        root, wid = env
        _as(monkeypatch, "chadwick")
        args = {"action": "propose", "workspace_id": wid, "order_type": "title", "purpose": "title commitment",
                "inputs": {"property_ref": "prop://synthetic/1", "borrower_ref": "brw://synthetic/1", "vendor": "Synthetic Title Co"}}
        first = json.loads(ft["tools"].handle_flo_order(args))
        retry = json.loads(ft["tools"].handle_flo_order({**args, "purpose": "Title commitment (retry after timeout)"}))
        assert first["decision"] == "create_new" and retry["decision"] == "return_existing" and retry["order_id"] == first["order_id"]
        assert len(ft["workspace"].WorkspaceStore(root).get(wid)["orders"]) == 1
        # once placed with an execution ref, a retry still returns the placed order and never proposes again
        ft["tools"].handle_flo_order({"action": "transition", "workspace_id": wid, "order_id": first["order_id"], "state": "approved", "approval_id": "appr_x"})
        ft["tools"].handle_flo_order({"action": "transition", "workspace_id": wid, "order_id": first["order_id"], "state": "ordered", "execution_ref": "zap_123"})
        again = json.loads(ft["tools"].handle_flo_order(args))
        assert again["decision"] == "return_existing" and again["state"] == "ordered" and "already ordered" in again["note"]

    def test_executed_side_effect_is_blocked_on_retry(self, env, ft, monkeypatch):
        root, _ = env
        hooks = ft["plugin"].FloTeamHooks(root=root)
        monkeypatch.setenv("HERMES_PROFILE_NAME", "whisper")
        args = {"to": "borrower@example.invalid", "subject": "Documents", "body": "Please send the paystub."}
        first = hooks.pre_tool_call(tool_name="flo_email_send", args=args, session_id="s1", tool_call_id="tc1")
        assert first and first["action"] == "approve"
        hooks.post_tool_call(tool_name="flo_email_send", result={"ok": True, "id": "msg_abc"}, tool_call_id="tc1")
        second = hooks.pre_tool_call(tool_name="flo_email_send", args=args, session_id="s2", tool_call_id="tc2")
        assert second and second["action"] == "block" and "DUPLICATE side effect prevented" in second["message"]
        changed = hooks.pre_tool_call(tool_name="flo_email_send", args={**args, "body": "Please send the paystub and the W-2."}, session_id="s2", tool_call_id="tc3")
        assert changed and changed["action"] == "approve"

    def test_marketing_content_is_deduplicated_until_published(self, env, ft):
        root, _ = env
        factory = ft["marketing"].ContentFactory(root)
        a = factory.create(channel="blog", title="Five things to know about FHA loans", body="draft body")
        b = factory.create(channel="blog", title="Five  things to know about FHA loans ", body="reworded body")
        assert b["content_id"] == a["content_id"] and b["deduplicated"]
