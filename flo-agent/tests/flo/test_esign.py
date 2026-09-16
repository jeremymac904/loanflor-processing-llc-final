"""Electronic signatures (Documenso adapter): prepare/send/status/retrieve/remind/cancel, approval binding,
idempotency, cross-loan authorization, catch-up polling, webhook handling.

Every test in this file runs against ``mock_documenso.MockDocumensoServer`` — a local, in-process stand-in
for the Documenso Envelope API, NOT the real product. It proves our own adapter, idempotency, approval
binding and document filing behave correctly given real HTTP responses shaped the way Documenso's docs
describe. It proves nothing about Documenso's own signing UI, audit certificate or email delivery — see
FLO_ESIGN.md for what could not be verified against a live instance in this environment.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mock_documenso import MockDocumensoServer  # noqa: E402


@pytest.fixture()
def mods():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    names = ("esign", "documents", "workspace", "tools", "approvals_center", "intents", "roles", "manifest", "store", "pkg")
    out = {n: importlib.import_module(f"flo_team.{n}") for n in names if n != "pkg"}
    out["pkg"] = sys.modules["flo_team"]
    return out


@pytest.fixture()
def server():
    srv = MockDocumensoServer()
    yield srv
    srv.stop()


ENV = {"DOCUMENSO_LOE_TEMPLATE_ID": "tmpl_loe_0001"}


def make_doc(mods, root, wid, *, category="other", page_count=1, sha256="a" * 64):
    store = mods["documents"].DocumentStore(root)
    rec = {"document_id": mods["store"].new_id("doc"), "website_document_id": None, "submission_id": None, "workspace_id": wid,
           "category": category, "subcategory": None, "borrower_ref": "borrower", "original_filename": "loe.pdf",
           "display_name": "2026-09-10_loe_01.pdf", "storage_key": None, "mime_type": "application/pdf", "size_bytes": 900,
           "sha256": sha256, "uploaded_at": "2026-09-10T00:00:00Z", "uploaded_by": "malcolm", "received_at": "2026-09-10T00:00:00Z",
           "status": "received", "classification_source": "malcolm", "notes": "", "local_path": None, "text_path": None,
           "text_chars": 0, "page_count": page_count, "checks": {}, "history": []}
    store.add(wid, rec)
    return rec


def make_workspace(mods, root, *, name="Justinvil-Synthetic"):
    ws = mods["workspace"].WorkspaceStore(root)
    return ws.create(display_name=name)


RECIPIENTS = [{"name": "Ariana Justinvil-Synthetic", "email": "ariana@synthetic.test", "role": "SIGNER"}]


class TestTemplateEligibility:
    def test_needs_signing_setup_without_a_configured_template(self, mods, tmp_path):
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        with pytest.raises(mods["esign"].EsignError, match="This document needs signing setup."):
            mods["esign"].prepare(tmp_path, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="Please sign.", by="flo", env={})

    def test_needs_signing_setup_when_page_count_does_not_match(self, mods, tmp_path):
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid, page_count=3)  # template expects 1
        with pytest.raises(mods["esign"].EsignError, match="This document needs signing setup."):
            mods["esign"].prepare(tmp_path, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="", by="flo", env=ENV)

    def test_prepare_succeeds_and_hashes_the_material(self, mods, tmp_path):
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        prepared = mods["esign"].prepare(tmp_path, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="Please sign this.", by="flo", env=ENV)
        assert prepared["template_label"] == "Letter of Explanation"
        assert prepared["existing_request"] is None
        again = mods["esign"].prepare(tmp_path, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="Please sign this.", by="flo", env=ENV)
        assert again["material_key"] == prepared["material_key"]
        changed = mods["esign"].prepare(tmp_path, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="A different message.", by="flo", env=ENV)
        assert changed["material_key"] != prepared["material_key"]  # a changed message is a materially different request

    def test_cross_loan_document_is_refused(self, mods, tmp_path):
        wid_a = make_workspace(mods, tmp_path, name="A")["workspace_id"]
        wid_b = make_workspace(mods, tmp_path, name="B")["workspace_id"]
        doc_from_a = make_doc(mods, tmp_path, wid_a)
        with pytest.raises(mods["esign"].EsignError, match="does not belong to this loan"):
            mods["esign"].prepare(tmp_path, workspace_id=wid_b, document=doc_from_a, template_key="loe", recipients=RECIPIENTS, message="", by="flo", env=ENV)


class TestSendStatusRetrieve:
    def test_full_single_signer_flow(self, mods, tmp_path, server):
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        rec = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="Please sign.", by="whisper", env=ENV)
        assert rec["status"] == "sent" and rec["documenso_envelope_id"]
        assert server.call_count("POST", "/api/v2/template/use") == 1 and server.call_count("POST", "/api/v2/envelope/distribute") == 1
        checked = mods["esign"].refresh_status(tmp_path, client, workspace_id=wid, request_id=rec["request_id"])
        assert checked["status"] == "sent"  # not signed yet
        server.sign(rec["documenso_envelope_id"], "ariana@synthetic.test")
        signed = mods["esign"].refresh_status(tmp_path, client, workspace_id=wid, request_id=rec["request_id"])
        assert signed["status"] == "signed"
        filed = mods["esign"].retrieve_completed(tmp_path, client, workspace_id=wid, request_id=rec["request_id"])
        assert filed["status"] == "retrieved" and filed["signed_document_id"]
        new_doc = mods["documents"].DocumentStore(tmp_path).get(wid, filed["signed_document_id"])
        assert new_doc["category"] == doc["category"]  # filed alongside the source doc's category, no new dashboard needed
        assert new_doc["status"] == "received" and "Signed copy" in new_doc["notes"]
        assert Path(new_doc["local_path"]).read_bytes().startswith(b"%PDF")
        # retrieving again is a no-op (never re-downloads once filed)
        again = mods["esign"].retrieve_completed(tmp_path, client, workspace_id=wid, request_id=rec["request_id"])
        assert again["signed_document_id"] == filed["signed_document_id"]
        assert server.call_count("GET", f"/api/v2/envelope/item/{rec['documenso_envelope_id']}_item1/download") == 1

    def test_two_signers_partial_then_complete(self, mods, tmp_path, server):
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        two = [RECIPIENTS[0], {"name": "Co Borrower", "email": "co@synthetic.test", "role": "SIGNER"}]
        rec = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=two, message="", by="whisper", env=ENV)
        server.sign(rec["documenso_envelope_id"], "ariana@synthetic.test")
        partial = mods["esign"].refresh_status(tmp_path, client, workspace_id=wid, request_id=rec["request_id"])
        assert partial["status"] == "partially_signed"
        board_row = mods["esign"].board({"esign_requests": [partial]})[0]
        assert board_row["status_label"] == "Waiting for signature" and "Co Borrower" in board_row["explanation"]
        server.sign(rec["documenso_envelope_id"], "co@synthetic.test")
        done = mods["esign"].refresh_status(tmp_path, client, workspace_id=wid, request_id=rec["request_id"])
        assert done["status"] == "signed"

    def test_recipient_decline(self, mods, tmp_path, server):
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        rec = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="", by="whisper", env=ENV)
        server.reject(rec["documenso_envelope_id"], "ariana@synthetic.test")
        declined = mods["esign"].refresh_status(tmp_path, client, workspace_id=wid, request_id=rec["request_id"])
        assert declined["status"] == "declined"
        assert mods["esign"].board({"esign_requests": [declined]})[0]["explanation"] == "Recipient declined."


class TestDuplicateProtection:
    def test_double_click_send_reuses_the_active_request(self, mods, tmp_path, server):
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        first = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="Please sign.", by="whisper", env=ENV)
        second = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="Please sign.", by="whisper", env=ENV)
        assert second["request_id"] == first["request_id"]
        assert server.call_count("POST", "/api/v2/template/use") == 1  # never a second envelope

    def test_changed_recipients_after_the_first_send_creates_a_fresh_request(self, mods, tmp_path, server):
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        first = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="", by="whisper", env=ENV)
        other = [{"name": "Different Person", "email": "different@synthetic.test", "role": "SIGNER"}]
        second = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=other, message="", by="whisper", env=ENV)
        assert second["request_id"] != first["request_id"]
        assert server.call_count("POST", "/api/v2/template/use") == 2

    def test_ambiguous_send_failure_needs_attention_not_a_silent_retry(self, mods, tmp_path, monkeypatch):
        class BrokenClient:
            def create_from_template(self, *a, **k):
                raise TimeoutError("network timeout")

        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        rec = mods["esign"].create_and_send(tmp_path, BrokenClient(), workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="", by="whisper", env=ENV)
        assert rec["status"] == "needs_attention" and "did not complete cleanly" in rec["notes"]

    def test_download_failure_retries_retrieval_only_never_resends(self, mods, tmp_path, server, monkeypatch):
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        rec = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="", by="whisper", env=ENV)
        server.sign(rec["documenso_envelope_id"], "ariana@synthetic.test")

        real_download = client.download_item

        def broken(item_id):
            raise ConnectionError("dropped")

        monkeypatch.setattr(client, "download_item", broken)
        failed = mods["esign"].retrieve_completed(tmp_path, client, workspace_id=wid, request_id=rec["request_id"])
        assert failed["status"] == "needs_attention" and "retry retrieval" in failed["notes"]
        assert server.call_count("POST", "/api/v2/template/use") == 1  # the send was never repeated
        monkeypatch.setattr(client, "download_item", real_download)
        recovered = mods["esign"].retrieve_completed(tmp_path, client, workspace_id=wid, request_id=rec["request_id"])
        assert recovered["status"] == "retrieved"


class TestCancelRemindPoll:
    def test_remind_and_cancel_operate_on_the_existing_request(self, mods, tmp_path, server):
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        rec = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="", by="whisper", env=ENV)
        reminded = mods["esign"].remind(tmp_path, client, workspace_id=wid, request_id=rec["request_id"], by="flo")
        assert reminded["last_reminded_at"]
        assert server.envelopes[rec["documenso_envelope_id"]]["reminders"] == 1
        cancelled = mods["esign"].cancel(tmp_path, client, workspace_id=wid, request_id=rec["request_id"], reason="LO said skip it", by="flo")
        assert cancelled["status"] == "cancelled"
        assert server.envelopes[rec["documenso_envelope_id"]]["status"] == "CANCELLED"
        with pytest.raises(mods["esign"].EsignError, match="cannot cancel"):
            mods["esign"].cancel(tmp_path, client, workspace_id=wid, request_id=rec["request_id"], reason="again", by="flo")
        with pytest.raises(mods["esign"].EsignError, match="cannot remind"):
            mods["esign"].remind(tmp_path, client, workspace_id=wid, request_id=rec["request_id"], by="flo")

    def test_a_changed_document_needs_a_fresh_request_not_reuse_of_a_cancelled_one(self, mods, tmp_path, server):
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        first = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="", by="whisper", env=ENV)
        mods["esign"].cancel(tmp_path, client, workspace_id=wid, request_id=first["request_id"], reason="revised wording", by="flo")
        second = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="", by="whisper", env=ENV)
        assert second["request_id"] != first["request_id"]  # cancelled requests are never silently reused
        assert server.call_count("POST", "/api/v2/template/use") == 2

    def test_poll_all_catches_up_after_flo_was_closed(self, mods, tmp_path, server):
        """Simulates: Flo sends, is closed, the borrower signs while it's closed, Flo restarts and sweeps."""
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        rec = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="", by="whisper", env=ENV)
        server.sign(rec["documenso_envelope_id"], "ariana@synthetic.test")  # happens while "Flo is closed"
        summary = mods["esign"].poll_all(tmp_path, client)  # Flo "restarts"
        assert summary["checked"] == 1 and summary["results"][0]["status"] == "retrieved"
        store = mods["esign"].SignatureRequestStore(tmp_path)
        assert store.get(wid, rec["request_id"])["status"] == "retrieved"
        # a second sweep finds nothing active left to check
        assert mods["esign"].poll_all(tmp_path, client)["checked"] == 0

    def test_poll_all_does_not_stop_on_one_bad_record(self, mods, tmp_path, server):
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc_a, doc_b = make_doc(mods, tmp_path, wid, sha256="a" * 64), make_doc(mods, tmp_path, wid, sha256="b" * 64)
        good = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc_a, template_key="loe", recipients=RECIPIENTS, message="", by="whisper", env=ENV)
        bad = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc_b, template_key="loe", recipients=RECIPIENTS, message="", by="whisper", env=ENV)
        # corrupt the "bad" record's envelope id so its status check fails
        mods["esign"].SignatureRequestStore(tmp_path).update(wid, bad["request_id"], {"documenso_envelope_id": "envelope_does_not_exist"}, by="test")
        server.sign(good["documenso_envelope_id"], "ariana@synthetic.test")
        summary = mods["esign"].poll_all(tmp_path, client)
        assert summary["checked"] == 2
        statuses = {r["request_id"]: r["status"] for r in summary["results"]}
        assert statuses[good["request_id"]] == "retrieved" and statuses[bad["request_id"]] == "needs_attention"


class TestWebhookPing:
    def test_ping_finds_the_matching_request_by_envelope_id_and_re_fetches(self, mods, tmp_path, server):
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        rec = mods["esign"].create_and_send(tmp_path, client, workspace_id=wid, document=doc, template_key="loe", recipients=RECIPIENTS, message="", by="whisper", env=ENV)
        server.sign(rec["documenso_envelope_id"], "ariana@synthetic.test")
        result = mods["esign"].handle_webhook_ping(tmp_path, client, envelope_id=rec["documenso_envelope_id"])
        assert result["status"] == "retrieved"  # the ping triggered a real re-check + download, not a trust of any payload field

    def test_ping_for_an_unknown_envelope_is_a_harmless_no_op(self, mods, tmp_path, server):
        client = mods["esign"].DocumensoClient(server.base_url, server.token)
        result = mods["esign"].handle_webhook_ping(tmp_path, client, envelope_id="envelope_never_seen")
        assert "no local signature request matches" in result["note"]


class TestToolsAndAuthorization:
    def test_franklin_is_structurally_excluded(self, mods, tmp_path, monkeypatch):
        monkeypatch.setattr(mods["tools"], "_STATE_ROOT_OVERRIDE", tmp_path)
        monkeypatch.setenv("HERMES_PROFILE_NAME", "franklin")
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        out = json.loads(mods["tools"].handle_flo_esign({"action": "list", "workspace_id": wid}))
        assert "error" in out and "excluded" in out["error"]

    def test_unauthorized_cross_loan_document_access_is_refused_at_the_tool_layer(self, mods, tmp_path, monkeypatch):
        monkeypatch.setattr(mods["tools"], "_STATE_ROOT_OVERRIDE", tmp_path)
        monkeypatch.setenv("HERMES_PROFILE_NAME", "whisper")
        wid_a = make_workspace(mods, tmp_path, name="A")["workspace_id"]
        wid_b = make_workspace(mods, tmp_path, name="B")["workspace_id"]
        doc_a = make_doc(mods, tmp_path, wid_a)
        monkeypatch.setenv("DOCUMENSO_LOE_TEMPLATE_ID", "tmpl_loe_0001")
        out = json.loads(mods["tools"].handle_flo_esign({"action": "prepare", "workspace_id": wid_b, "document_id": doc_a["document_id"],
                                                          "template_key": "loe", "recipients": RECIPIENTS, "message": ""}))
        assert "error" in out  # document exists, but not under this workspace -> DocumentStore.get(wid_b, ...) finds nothing

    def test_flo_esign_send_is_gated_by_the_generic_approval_hook_and_bound_to_the_material(self, mods, tmp_path, monkeypatch):
        monkeypatch.setattr(mods["tools"], "_STATE_ROOT_OVERRIDE", tmp_path)
        monkeypatch.setenv("HERMES_PROFILE_NAME", "whisper")
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        hooks = mods["pkg"].build_hooks(root=tmp_path)
        args = {"workspace_id": wid, "document_id": doc["document_id"], "document_checksum": doc["sha256"], "template_key": "loe",
                "recipients": RECIPIENTS, "message": "Please sign this."}
        directive = hooks.pre_tool_call(tool_name="flo_esign_send", args=args, tool_call_id="call-1")
        assert directive["action"] == "approve"
        cards = mods["approvals_center"].ApprovalQueue(tmp_path).list(status="pending")
        assert len(cards) == 1
        assert "ariana@synthetic.test" in cards[0]["payload_preview"]["recipients"][0]  # bounded preview, not the raw payload
        # a second, identical call before approval reuses the same pending card (no card-spam on a double click)
        directive2 = hooks.pre_tool_call(tool_name="flo_esign_send", args=args, tool_call_id="call-2")
        assert "Approval Center card" in directive2["message"]
        assert len(mods["approvals_center"].ApprovalQueue(tmp_path).list(status="pending")) == 1
        # a materially different message would not reuse this card (different payload_hash)
        different = {**args, "message": "A completely different message."}
        digest_a = mods["approvals_center"].payload_hash("flo_esign_send", args)
        digest_b = mods["approvals_center"].payload_hash("flo_esign_send", different)
        assert digest_a != digest_b

    def test_a_terminal_intent_blocks_a_true_retry_after_execution(self, mods, tmp_path, monkeypatch):
        monkeypatch.setattr(mods["tools"], "_STATE_ROOT_OVERRIDE", tmp_path)
        monkeypatch.setenv("HERMES_PROFILE_NAME", "whisper")
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        hooks = mods["pkg"].build_hooks(root=tmp_path)
        args = {"workspace_id": wid, "document_id": doc["document_id"], "document_checksum": doc["sha256"], "template_key": "loe",
                "recipients": RECIPIENTS, "message": "Please sign this."}
        hooks.pre_tool_call(tool_name="flo_esign_send", args=args, tool_call_id="call-1")
        hooks.post_tool_call(tool_name="flo_esign_send", result=json.dumps({"ref": "envelope_mock0001", "status": "sent"}), tool_call_id="call-1")
        card = mods["approvals_center"].ApprovalQueue(tmp_path).list()[0]
        assert card["status"] == "executed" and card["execution_ref"] == "envelope_mock0001"
        retry = hooks.pre_tool_call(tool_name="flo_esign_send", args=args, tool_call_id="call-3")
        assert retry["action"] == "block" and "DUPLICATE side effect prevented" in retry["message"]

    def test_send_via_the_tool_handler_returns_a_ref_the_generic_hook_can_close_the_card_with(self, mods, tmp_path, monkeypatch, server):
        monkeypatch.setattr(mods["tools"], "_STATE_ROOT_OVERRIDE", tmp_path)
        monkeypatch.setenv("HERMES_PROFILE_NAME", "whisper")
        monkeypatch.setenv("DOCUMENSO_API_URL", server.base_url)
        monkeypatch.setenv("DOCUMENSO_API_TOKEN", server.token)
        monkeypatch.setenv("DOCUMENSO_LOE_TEMPLATE_ID", "tmpl_loe_0001")
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        out = json.loads(mods["tools"].handle_flo_esign_send({"workspace_id": wid, "document_id": doc["document_id"], "template_key": "loe",
                                                               "recipients": RECIPIENTS, "message": "Please sign."}))
        assert out["status"] == "sent" and out["ref"] == out["documenso_envelope_id"]
        ws = mods["workspace"].WorkspaceStore(tmp_path).get(wid)
        assert ws["esign_requests"][0]["status"] == "sent"  # filed onto the loan workspace, no separate dashboard

    def test_status_and_retrieve_via_tools_update_the_workspace_board(self, mods, tmp_path, monkeypatch, server):
        monkeypatch.setattr(mods["tools"], "_STATE_ROOT_OVERRIDE", tmp_path)
        monkeypatch.setenv("HERMES_PROFILE_NAME", "flo")
        monkeypatch.setenv("DOCUMENSO_API_URL", server.base_url)
        monkeypatch.setenv("DOCUMENSO_API_TOKEN", server.token)
        monkeypatch.setenv("DOCUMENSO_LOE_TEMPLATE_ID", "tmpl_loe_0001")
        wid = make_workspace(mods, tmp_path)["workspace_id"]
        doc = make_doc(mods, tmp_path, wid)
        sent = json.loads(mods["tools"].handle_flo_esign_send({"workspace_id": wid, "document_id": doc["document_id"], "template_key": "loe",
                                                                "recipients": RECIPIENTS, "message": ""}))
        server.sign(sent["documenso_envelope_id"], "ariana@synthetic.test")
        status_out = json.loads(mods["tools"].handle_flo_esign({"action": "status", "workspace_id": wid, "request_id": sent["request_id"]}))
        assert status_out["status"] == "signed"
        retrieve_out = json.loads(mods["tools"].handle_flo_esign({"action": "retrieve", "workspace_id": wid, "request_id": sent["request_id"]}))
        assert retrieve_out["status"] == "retrieved"
        board = json.loads(mods["tools"].handle_flo_esign({"action": "list", "workspace_id": wid}))
        assert board["requests"][0]["status_label"] == "Signed"
