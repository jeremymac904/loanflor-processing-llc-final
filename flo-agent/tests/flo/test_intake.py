"""Website loan submission intake: deterministic Deal Room + Malcolm task, idempotent, no NPI, token-protected endpoint."""

from __future__ import annotations

import http.client
import importlib
import importlib.util
import json
import os
import sys
import threading
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
sys.path.insert(0, str(REPO / "scripts" / "flo"))


@pytest.fixture(scope="module")
def mods():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    return {name: importlib.import_module(f"flo_team.{name}") for name in ("intake", "workspace", "handoff", "today")}


def payload(**overrides):
    p = {
        "schemaVersion": "1.0", "submissionId": "sub_0123456789abcdef01234567", "submittedAt": "2026-09-09T14:42:00.000Z", "source": "lfprocessing.net",
        "loanOfficer": {"name": "Matt Combs", "email": "matt@synthetic-mortgage.test", "phone": "(904) 555-0101", "company": "Synthetic Mortgage Group", "nmls": "123456", "dateSubmitted": "2026-09-09"},
        "borrowers": [{"role": "borrower", "name": "Ariana Justinvil-Synthetic", "email": "ariana@synthetic.test", "phone": "(904) 555-0102"}],
        "loan": {"investor": "PRMG", "propertyAddress": "123 Synthetic Way, Jacksonville, FL 32256", "expectedClosingDate": "2026-09-23", "loanAmount": 314000, "interestRate": 6.25,
                 "ltv": 95.15, "cltv": None, "occupancy": "primary", "transactionType": "purchase", "program": "fha", "conventionalAgency": None, "programOther": "", "aus": "total",
                 "refinanceType": None, "homeType": "single_family", "homeTypeOther": ""},
        "fees": {"channel": "brokered", "compensation": "lender_paid", "originationFees": {"lpCompPercent": 2.75, "box1": None, "discountPoints": None, "credits": None},
                 "thirdPartyFees": {"creditReportFee": 152, "processingFee": 995}, "lenderBuyingOutFee": "no", "buyoutNotes": ""},
        "appraisal": {"orderTiming": "prior_to_inspection", "notes": ""},
        "parties": {"nonOccupantCoBorrower": "no", "nonBorrowingTitleParty": {"applies": False, "name": "", "email": "", "phone": "", "willBeOnTitle": None}},
        "setup": {"pmi": "yes", "subordinationRequired": "no", "loanLocked": "no", "escrowWaiver": "no"},
        "communicationPreferences": ["realtor_voice", "borrower_email_cc_lo"],
        "hoa": {"present": "no", "company": "", "phone": "", "contact": "", "email": "", "condoQuestionnaireStatus": None},
        "income": [{"borrower": "borrower", "incomeType": "w2", "employerOrSource": "Synthetic Health System", "loStatedMonthlyIncome": 7842, "calculationBasis": "current_income", "documentsIncluded": ["paystubs", "w2s"], "notes": "", "verified": False}],
        "credit": {"borrower": {"status": ["as_per_credit_pull"], "omittedDebtsNotes": ""}, "coBorrower": {"status": [], "omittedDebtsNotes": ""}},
        "assets": [{"sourceType": "borrower_bank_account", "nameOrInstitution": "Synthetic Credit Union", "accountReference": "checking ••1234", "amount": 18500, "notes": ""}],
        "title": {"selected": True, "company": "Hawes Law Firm (synthetic)", "contact": "", "phone": "(678) 555-0103", "email": "closings@synthetic-title.test"},
        "insurance": {"selected": False, "company": "", "contact": "", "phone": "", "email": ""},
        "agents": {"listing": {"name": "Michael Capo (synthetic)", "license": "267977", "phone": "(404) 555-0104", "email": "listing@synthetic.test", "brokerage": "Synthetic Realty", "brokerageLicense": "62466"},
                   "buyer": {"name": "", "license": "", "phone": "", "email": "", "brokerage": "", "brokerageLicense": ""}},
        "notes": "This is a rush file, closing in 2 weeks.",
        "documentRefs": [{"category": "loan_application", "fileName": "synthetic-1003.pdf", "sizeBytes": 412000, "contentType": "application/pdf", "status": "pending_secure_upload"}],
    }
    for k, v in overrides.items():
        p[k] = v
    return p


class TestReceive:
    def test_creates_deal_room_and_one_malcolm_task_once(self, mods, tmp_path):
        intake, workspace, handoff = mods["intake"], mods["workspace"], mods["handoff"]
        rec = intake.receive(tmp_path, payload(), today=date(2026, 9, 9))
        assert rec["duplicate"] is False and rec["workspace_id"].startswith("loan_") and rec["task_id"].startswith("task_")
        ws = workspace.WorkspaceStore(tmp_path).get(rec["workspace_id"])
        assert ws["display_name"] == "Justinvil-Synthetic" and ws["milestone"] == "Intake" and ws["program"] == "fha" and ws["agency"] == "fha"
        assert ws["submission"]["loan_officer"]["name"] == "Matt Combs" and ws["submission"]["review_status"] == "pending"
        assert ws["submission"]["lo_stated_income"][0]["verified"] is False
        assert ws["next_action"] == "Malcolm is reviewing the new submission."
        assert ws["status_summary"].startswith("New submission from Matt Combs (Synthetic Mortgage Group). Purchase • FHA. Expected close 2026-09-23")
        assert ws["document_refs"][0]["status"] == "listed"  # no fetchUrl on this ref: listed only
        assert rec["task_id"] in ws["agent_tasks"]
        task = handoff.TaskRegistry(tmp_path).get(rec["task_id"])
        assert task.to_agent == "malcolm" and task.from_agent == "flo" and task.status == "sent" and task.return_format == "file_prep_report"
        assert task.objective == "Review this new submission and tell Ashley what is missing."
        assert task.urgency == "today"  # closing in 14 days
        assert any("NOT verified" in f for f in task.facts)
        assert "flo-handoff" in rec["send_with"]["message"] and rec["send_with"]["target"] == "malcolm"
        assert rec["ashley_line"] == "New loan came in — Justinvil-Synthetic.\n\nNo documents came with it.\n\nMalcolm is reviewing everything now. 💚"
        # Same submission again (double click / retry / redelivery) -> same workspace, no second task.
        again = intake.receive(tmp_path, payload())
        assert again["duplicate"] is True and again["workspace_id"] == rec["workspace_id"] and again["task_id"] == rec["task_id"]
        assert len(workspace.WorkspaceStore(tmp_path).list()) == 1
        assert len(list(handoff.TaskRegistry(tmp_path).docs.all())) == 1

    def test_dispatch_returns_the_packet_once(self, mods, tmp_path):
        intake = mods["intake"]
        rec = intake.receive(tmp_path, payload())
        assert intake.IntakeStore(tmp_path).pending_dispatch()[0]["submission_id"] == rec["submission_id"]
        first = intake.dispatch(tmp_path, rec["submission_id"])
        assert first["dispatched_at"] and first["send_with"]["target"] == "malcolm"
        assert intake.IntakeStore(tmp_path).pending_dispatch() == []
        second = intake.dispatch(tmp_path, rec["submission_id"])
        assert "already dispatched" in second["note"]

    def test_validation_rejects_bad_schema_missing_fields_and_npi(self, mods, tmp_path):
        intake = mods["intake"]
        assert intake.validate(payload(schemaVersion="0.9"))
        assert "borrowers[0].name is required" in intake.validate(payload(borrowers=[]))
        bad = payload(notes="SSN 123-45-6789")
        assert any("sensitive" in p for p in intake.validate(bad))
        acct = payload(assets=[{"sourceType": "borrower_bank_account", "nameOrInstitution": "Bank", "accountReference": "123456789012", "amount": 1}])
        assert any("sensitive" in p for p in intake.validate(acct))
        # Hex ids / storage keys / checksums with an embedded digit run are not account numbers.
        ids = payload(submissionId="sub_582779223a8c79e018858462",
                      documentRefs=[{"documentId": "doc_597104a7c486314bd7f84cce", "category": "income", "fileName": "x.pdf", "storageKey": "submissions/sub_582779223a8c79e018858462/income/x.pdf",
                                     "sha256": "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff", "fetchUrl": "https://lfprocessing.net/api/internal/documents/sub_582779223a8c79e018858462/doc_597104a7c486314bd7f84cce"}])
        assert intake.validate(ids) == []
        with pytest.raises(intake.IntakeError):
            intake.receive(tmp_path, bad)
        assert intake.validate(payload()) == []

    def test_conventional_agency_and_today_line(self, mods, tmp_path):
        intake, workspace, today = mods["intake"], mods["workspace"], mods["today"]
        p = payload(submissionId="sub_aaaaaaaaaaaaaaaaaaaaaaaa")
        p["loan"] = {**p["loan"], "program": "conventional", "conventionalAgency": "freddie_mac", "aus": "lpa", "transactionType": "refinance_rate_term", "refinanceType": "standard", "expectedClosingDate": "2026-11-30"}
        rec = intake.receive(tmp_path, p, today=date(2026, 9, 9))
        ws = workspace.WorkspaceStore(tmp_path).get(rec["workspace_id"])
        assert ws["agency"] == "freddie" and ws["aus"] == "LPA"
        assert mods["handoff"].TaskRegistry(tmp_path).get(rec["task_id"]).urgency == "this_week"
        model = today.build([ws], [], [{"task_id": rec["task_id"], "workspace_id": ws["workspace_id"], "status": "sent"}], [])
        assert model["top"][0]["status"] == "Working"
        assert model["top"][0]["line"] == "Submitted by Matt Combs • Conventional • Refinance (rate & term) • Expected closing November 30. Malcolm is reviewing it."
        assert model["new_loans"] == [{"workspace_id": ws["workspace_id"], "name": "Justinvil-Synthetic", "submitted_by": "Matt Combs", "program": "Conventional • Refinance (rate & term)",
                                       "expected_closing": "November 30", "documents_received": 0, "line": "Malcolm is reviewing it."}]
        assert "New loan came in — Justinvil-Synthetic.\n\nNo documents came with it.\n\nMalcolm is reviewing everything now. 💚" in model["say_it_like"]
        summary = today.file_summary(ws, [], [])
        assert summary["readiness"] == "New submission" and "Malcolm is reviewing" in summary["best_next_move"]
        # Malcolm's readiness report replaces the placeholder and marks the submission reviewed.
        store = workspace.WorkspaceStore(tmp_path)
        store.set_readiness(ws["workspace_id"], "malcolm", {"status": "IN_PROGRESS", "score": 40, "missing_count": 2, "aus_findings": "unknown",
                                                            "missing": [{"item": "Signed 1003", "owner": "borrower"}, {"item": "HOI contact", "owner": "lo"}],
                                                            "best_next_move": "Only blocker right now: Signed 1003 from borrower. One clean follow-up."})
        after = store.get(ws["workspace_id"])
        assert after["submission"]["review_status"] == "reviewed" and after["next_action"].startswith("Only blocker right now")
        reviewed = today.file_summary(after, [], [])
        assert reviewed["readiness"] == "Needs 2 items" and reviewed["best_next_move"] == "Request the missing documents." and reviewed["status"] == "Waiting"
        assert [m["item"] for m in reviewed["missing"]] == ["Signed 1003", "HOI contact"]


class TestServer:
    @pytest.fixture
    def server(self, mods, tmp_path):
        import intake_server

        srv = intake_server.serve("127.0.0.1", 0, token="unit-test-token-0123456789abcdef", root=tmp_path, spawn=False)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        yield srv
        srv.shutdown()

    def _post(self, server, body, token="unit-test-token-0123456789abcdef"):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request("POST", "/intake/loan-submissions", body=json.dumps(body), headers=headers)
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read() or b"{}")

    def test_endpoint_accepts_once_then_reports_duplicate_and_requires_the_token(self, server, mods, tmp_path):
        status, body = self._post(server, payload())
        assert status == 201 and body["status"] == "accepted" and body["workspaceId"].startswith("loan_")
        status, again = self._post(server, payload())
        assert status == 200 and again["status"] == "duplicate" and again["workspaceId"] == body["workspaceId"]
        assert self._post(server, payload(), token="wrong")[0] == 401
        assert self._post(server, payload(), token="")[0] == 401
        assert self._post(server, payload(notes="SSN 123-45-6789", submissionId="sub_bbbbbbbbbbbbbbbbbbbbbbbb"))[0] == 400
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
        conn.request("GET", "/intake/health")
        health = json.loads(conn.getresponse().read())
        assert health["ok"] and health["pendingDispatch"] == 1
        assert len(mods["workspace"].WorkspaceStore(tmp_path).list()) == 1

    def test_refuses_to_start_without_a_token(self, mods, monkeypatch):
        import intake_server

        monkeypatch.delenv("FLO_INTAKE_TOKEN", raising=False)
        assert intake_server.main([]) == 2
        monkeypatch.setenv("FLO_INTAKE_TOKEN", "short")
        assert intake_server.main([]) == 2

    def _post_path(self, server, path, body, token="unit-test-token-0123456789abcdef"):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request("POST", path, body=json.dumps(body), headers=headers)
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read() or b"{}")

    def test_esign_webhook_endpoint_requires_the_token_and_an_envelope_id(self, server, monkeypatch):
        monkeypatch.delenv("DOCUMENSO_API_URL", raising=False)
        monkeypatch.delenv("DOCUMENSO_API_TOKEN", raising=False)
        assert self._post_path(server, "/intake/esign-webhook", {"envelopeId": "envelope_x"}, token="wrong")[0] == 401
        assert self._post_path(server, "/intake/esign-webhook", {"envelopeId": "envelope_x"}, token="")[0] == 401
        status, body = self._post_path(server, "/intake/esign-webhook", {})
        assert status == 400 and "envelopeId" in body["error"]
        # esign not configured on this process: a valid ping is still acknowledged (200), never a 500,
        # and never trusts anything from the body beyond envelopeId
        status, body = self._post_path(server, "/intake/esign-webhook", {"envelopeId": "envelope_x", "status": "COMPLETED", "downloadUrl": "https://evil.example"})
        assert status == 200 and body["ok"] is True and "not configured" in body["note"]
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
        conn.request("GET", "/intake/health")
        health = json.loads(conn.getresponse().read())
        assert health["esign"] == "not configured"

    def test_esign_webhook_triggers_a_real_recheck_against_the_configured_client(self, server, mods, tmp_path, monkeypatch):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from mock_documenso import MockDocumensoServer

        mock = MockDocumensoServer()
        try:
            monkeypatch.setenv("DOCUMENSO_API_URL", mock.base_url)
            monkeypatch.setenv("DOCUMENSO_API_TOKEN", mock.token)
            esign = importlib.import_module("flo_team.esign")
            workspace_mod = mods["workspace"]
            ws = workspace_mod.WorkspaceStore(tmp_path).create(display_name="Webhook-Synthetic")
            docs = importlib.import_module("flo_team.documents")
            doc = {"document_id": "doc_webhook1", "workspace_id": ws["workspace_id"], "category": "other", "subcategory": None,
                   "borrower_ref": "borrower", "original_filename": "loe.pdf", "display_name": "loe.pdf", "storage_key": None,
                   "mime_type": "application/pdf", "size_bytes": 10, "sha256": "c" * 64, "uploaded_at": "2026-09-10T00:00:00Z",
                   "uploaded_by": "malcolm", "received_at": "2026-09-10T00:00:00Z", "status": "received", "classification_source": "malcolm",
                   "notes": "", "local_path": None, "text_path": None, "text_chars": 0, "page_count": 1, "checks": {}, "history": []}
            docs.DocumentStore(tmp_path).add(ws["workspace_id"], doc)
            client = esign.DocumensoClient(mock.base_url, mock.token)
            env = {"DOCUMENSO_LOE_TEMPLATE_ID": "tmpl_loe_0001"}
            rec = esign.create_and_send(tmp_path, client, workspace_id=ws["workspace_id"], document=doc, template_key="loe",
                                        recipients=[{"name": "Borrower", "email": "b@synthetic.test", "role": "SIGNER"}], message="", by="whisper", env=env)
            mock.sign(rec["documenso_envelope_id"], "b@synthetic.test")
            status, body = self._post_path(server, "/intake/esign-webhook", {"envelopeId": rec["documenso_envelope_id"]})
            assert status == 200 and body["status"] == "retrieved"
            assert esign.SignatureRequestStore(tmp_path).get(ws["workspace_id"], rec["request_id"])["status"] == "retrieved"
        finally:
            mock.stop()
