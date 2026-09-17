"""Email → Flo router tests (synthetic fixtures).

Drives the router end-to-end against an isolated workspace root and
exercises every classifier path. The IMAP connector is not exercised
itself; that part is the existing repo's adapter. This file covers the
floor that's ours: the classify → match → dispatch path.
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
def ft(tmp_path):
    """Stand up the flo_team module pointed at an isolated workspace root,
    with a 'Johnson' workspace seeded so a high-confidence match is
    possible for matching emails."""
    flo_team = _load_flo_team()
    # Load submodules explicitly — __init__.py doesn't auto-import them.
    import flo_team.email_router as _er  # noqa: F401  (side-effect import)
    import flo_team.conditions_ingest as _ci  # noqa: F401
    import flo_team.ctc as _ctc  # noqa: F401
    import flo_team.conditions_normalize as _cn  # noqa: F401
    # monkey-patch _root so the tool handlers write to our tmp workspace.
    import flo_team.tools as tools_mod
    tools_mod._root = lambda: tmp_path

    import flo_team.workspace as workspace_mod
    store = workspace_mod.WorkspaceStore(tmp_path)
    store.create(display_name="Johnson", workspace_id="loan_j",
                  milestone="Processing", program="fha")
    store.create(display_name="Bell", workspace_id="loan_b",
                  milestone="Processing", program="fha")
    return flo_team


def _msg(**kw):
    """Default IMAP-style message dict for a lender/UW email."""
    base = {
        "sender_addr": "uw@bank.example",
        "sender_name": "Underwriter",
        "subject": "Conditions update",
        "body": "",
        "message_id": "<gmailmsg001@bank.example>",
        "thread_id": "thread_001",
        "in_reply_to": "",
        "received_at": "2026-09-16T12:00:00+00:00",
    }
    base.update(kw)
    return base


# ── classifier gates ───────────────────────────────────────────────────────

class TestLenderGate:
    @pytest.mark.parametrize("sender,subject,body,expect", [
        ("uw@bank.example",                    "Conditions", "",                              True),
        ("loan_officer@bank.example",          "Update",   "we have conditions for you", True),
        ("john.borrower@gmail.example",        "My paystub", "Here is my most recent paystub", False),
        ("uw@bank.example",                    "Hi",       "Random question",                False),
        ("random.user@somewhere.example",      "Conditions", "loan is moving along",  False),  # too noisy
        ("noreply@bank.example",               "Conditions", "approval needed",        False),  # not allow-list-style lender
    ])
    def test_gate(self, sender, subject, body, expect):
        ft = _load_flo_team()
        import flo_team.email_router  # noqa: F401  (load side-effect)
        assert ft.email_router.is_lender_or_uw_email(
            sender=sender, subject=subject, body=body) is expect


class TestConditionDetection:
    @pytest.mark.parametrize("body,expect", [
        ("Conditional approval — please send paystub.",     True),
        ("Prior to doc we need updated W-2.",                True),
        ("Below are the conditions: 1. Paystub 2. W-2",      True),
        ("We have conditions of approval for this file.",    True),
        ("Loan is moving along, thanks.",                    False),
        ("OK thanks",                                         False),
    ])
    def test_looks_like_condition_email(self, body, expect):
        ft = _load_flo_team()
        import flo_team.email_router  # noqa: F401
        assert ft.email_router.looks_like_condition_email(body=body) is expect


class TestCtcDetection:
    @pytest.mark.parametrize("body,expect", [
        ("We are clear to close on this file. Funding is approved.",   True),
        ("Clear-to-Close issued for loan #12345.",                    True),
        ("Not clear to close yet — please send the paystub.",          False),
        ("We cannot issue CTC until conditions clear.",                 False),
        ("Almost clear to close — just two more items.",                False),
        ("Loan is moving along, thanks.",                              False),
    ])
    def test_looks_like_ctc_email(self, body, expect):
        ft = _load_flo_team()
        import flo_team.email_router  # noqa: F401
        assert ft.email_router.looks_like_ctc_email(body=body) is expect


# ── end-to-end routing ─────────────────────────────────────────────────────

CONDITION_EMAIL_BODY = """\
Hi Ashley,

We have the following conditions on loan Johnson:
1. Provide most recent paystub from borrower 1
2. Bank statement: most recent 2 months
3. Title company to provide updated title commitment

Thank you,
Underwriter
"""

CTC_EMAIL_BODY = "Clear to close issued. We have approved."


class TestRouteEndToEnd:
    def test_condition_email_high_confidence_stores_card(self, ft):
        result = ft.email_router.route_inbound_email(_msg(
            subject="Conditions on loan Johnson",
            body=CONDITION_EMAIL_BODY,
        ))
        assert result["stage"] == "dispatched"
        # one of the dispatched items is the conditions card with a
        # high-confidence workspace match → card lands on Johnson
        kinds = [d["kind"] for d in result["dispatched"]]
        assert "conditions" in kinds
        conditions_dispatch = next(d for d in result["dispatched"] if d["kind"] == "conditions")
        assert conditions_dispatch["workspace_id_for_card"] == "loan_j"

    def test_ctc_email_high_confidence_stores_card(self, ft):
        result = ft.email_router.route_inbound_email(_msg(
            subject="CTC issued for Johnson",
            body=CTC_EMAIL_BODY,
        ))
        assert result["stage"] == "dispatched"
        kinds = [d["kind"] for d in result["dispatched"]]
        assert "ctc" in kinds

    def test_borrower_email_skipped_quietly(self, ft):
        result = ft.email_router.route_inbound_email(_msg(
            sender_addr="john.borrower@gmail.example",
            subject="My paystub",
            body="Here is my most recent paystub, please confirm receipt.",
        ))
        # No card, no notification — this is borrower → borrower
        # message, not lender / UW content.
        assert result["stage"] == "skipped"

    def test_unrelated_lender_email_skipped(self, ft):
        # No CTC phrase, no condition phrase — generic lender status.
        result = ft.email_router.route_inbound_email(_msg(
            sender_addr="uw@bank.example",
            subject="Loan is moving along",
            body="Thanks for the update, we are reviewing. ",
        ))
        # "Reviewing" is too weak. The router should not surface anything.
        assert result["stage"] == "skipped"

    def test_negative_ctc_email_skipped(self, ft):
        result = ft.email_router.route_inbound_email(_msg(
            subject="Update",
            body="Not clear to close yet. Please send the paystub.",
        ))
        assert result["stage"] == "negative_ctc_skipped"

    def test_duplicate_message_id_does_not_create_duplicate_cards(self, ft):
        # Run the same message through the router twice. The second
        # call's `flo_conditions_ingest action=propose` should mark
        # email_already_applied=True so the desktop doesn't stack
        # two cards.
        kwargs = _msg(subject="Conditions on loan Johnson", body=CONDITION_EMAIL_BODY)
        r1 = ft.email_router.route_inbound_email(kwargs)
        r2 = ft.email_router.route_inbound_email(kwargs)
        assert r1["stage"] == "dispatched"
        assert r2["stage"] == "dispatched"
        cond1 = next(d for d in r1["dispatched"] if d["kind"] == "conditions")
        cond2 = next(d for d in r2["dispatched"] if d["kind"] == "conditions")
        apply_result1 = cond1["tool_result"]
        apply_result2 = cond2["tool_result"]
        assert len(apply_result1.get("new_conditions", [])) == 3
        # Second call: dedupe sees the email_id and produces 0 new.
        assert apply_result2.get("new_conditions", []) == []
        assert apply_result2.get("email_already_applied") is True

    def test_same_thread_different_message_id_are_separate(self, ft):
        # Thread reply with a NEW message id is a separate event —
        # dedup is per-message-id, so each can produce its own batch.
        m1 = _msg(message_id="<a@bank.example>", body=CONDITION_EMAIL_BODY)
        m2 = _msg(message_id="<b@bank.example>",
                   subject="Re: Conditions",
                   body="Updated condition: please also send HOI dec page.")
        r1 = ft.email_router.route_inbound_email(m1)
        r2 = ft.email_router.route_inbound_email(m2)
        assert r1["stage"] == "dispatched"
        assert r2["stage"] == "dispatched"
        # The reply adds a 2nd batch of new conditions (its own
        # message id), but doesn't double-count the original 3.
        a = next(d for d in r1["dispatched"] if d["kind"] == "conditions")
        b = next(d for d in r2["dispatched"] if d["kind"] == "conditions")
        assert len(a["tool_result"].get("new_conditions", [])) == 3
        assert len(b["tool_result"].get("new_conditions", [])) == 1
        assert b["tool_result"].get("email_already_applied") is False

    def test_ambiguous_workspace_match_does_not_store_card(self, ft):
        # No explicit workspace_id, no borrower hint in body — the
        # matcher has no signal. The router must NOT silently attach.
        result = ft.email_router.route_inbound_email(_msg(
            sender_addr="uw@unknown-bank.example",
            subject="Conditions",
            body=CONDITION_EMAIL_BODY,  # doesn't mention any borrower
        ))
        # Conditions-conditions path requires `workspace_match.confidence`
        # to be 'high' to store the card; otherwise no card lands.
        conditions_dispatch = next(d for d in result["dispatched"]
                                    if d["kind"] == "conditions")
        assert conditions_dispatch["workspace_id_for_card"] is None
        # The tool result is still returned (with no proposed_card in
        # the workspace), so the desktop can ask Ashley which file.

    def test_wrong_workspace_never_writes(self, ft):
        # Make it look plausible for Bell instead of Johnson.
        result = ft.email_router.route_inbound_email(_msg(
            sender_addr="uw@bank.example",
            subject="Conditions on loan Bell",
            body="Conditions for Bell: 1. Provide paystub for Bell.",
        ))
        conditions_dispatch = next(d for d in result["dispatched"]
                                    if d["kind"] == "conditions")
        assert conditions_dispatch["workspace_id_for_card"] == "loan_b"
        # Verify the proposal landed on Bell, not on Johnson.
        import json
        from pathlib import Path
        bell = json.loads(Path(ft.tools._root(), "workspaces", "loan_b.json").read_text())
        johnson = json.loads(Path(ft.tools._root(), "workspaces", "loan_j.json").read_text())
        pendings_bell = [c for c in (bell.get("pending_email_ingests") or [])
                         if c.get("status") == "pending"]
        pendings_johnson = [c for c in (johnson.get("pending_email_ingests") or [])
                            if c.get("status") == "pending"]
        assert len(pendings_bell) == 1
        assert len(pendings_johnson) == 0

    def test_email_cannot_self_authorize_milestone_via_router(self, ft):
        # Even with a CTC email, the router only calls propose — the
        # milestone stays Processing until Ashley confirms.
        ft.email_router.route_inbound_email(_msg(
            subject="Clear to close for Johnson",
            body=CTC_EMAIL_BODY,
        ))
        johnson = json.loads(
            (Path(ft.tools._root()) / "workspaces" / "loan_j.json").read_text()
        )
        assert johnson["milestone"] == "Processing"
        assert "ctc_confirmed_at" not in johnson
        # A pending CTC card SHOULD exist (router stored a proposal for
        # Ashley to confirm).
        assert any(c.get("status") == "pending"
                    for c in (johnson.get("pending_ctc_proposals") or []))
