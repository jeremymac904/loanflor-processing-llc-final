"""Document intake: secure pull through the connector, clean naming, text extraction, missing pages, duplicates, inventory, tool."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
sys.path.insert(0, str(REPO / "scripts" / "flo"))
SCRATCH_PDFS = Path(__file__).resolve().parent / "fixtures" / "documents"


def _pdf(pages):
    """Minimal PDF with a text layer (same generator as the synthetic docs)."""
    objs = []

    def add(s):
        objs.append(s)
        return len(objs)

    font = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pages_obj = add("PLACEHOLDER")
    ids = []
    for lines in pages:
        content = "BT /F1 11 Tf 50 740 Td 14 TL " + " ".join(f"({l}) Tj T*" for l in lines) + " ET"
        stream = add(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
        ids.append(add(f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 612 792] /Contents {stream} 0 R /Resources << /Font << /F1 {font} 0 R >> >> >>"))
    objs[pages_obj - 1] = f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in ids)}] /Count {len(ids)} >>"
    catalog = add(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>")
    out, offsets = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer << /Size {len(objs) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin1")


FILES = {
    "doc_1003": ("loan_application", None, "1003_application.pdf", _pdf([["Uniform Residential Loan Application (Form 1003)", "Borrower: Riley Johnson SYNTHETIC"]])),
    "doc_credit": ("credit_report", None, "credit_report.pdf", _pdf([["Tri-Merge Credit Report - SYNTHETIC", "Tradelines: 6 open"]])),
    "doc_du": ("aus_findings", None, "du_findings.pdf", _pdf([["Desktop Underwriter Findings - SYNTHETIC", "Recommendation: Approve/Eligible"]])),
    "doc_pay1": ("income", None, "scan0042.pdf", _pdf([["Earnings Statement - SYNTHETIC HEALTH SYSTEM", "Pay period ending 09/04/2026"]])),
    "doc_pay2": ("income", "paystub", "scan0043.pdf", _pdf([["Earnings Statement - SYNTHETIC HEALTH SYSTEM", "Pay period ending 08/21/2026"]])),
    "doc_w2": ("income", "w2", "w2_2025.pdf", _pdf([["Form W-2 Wage and Tax Statement 2025 - SYNTHETIC"]])),
    "doc_bank": ("assets", "bank_statement", "bank_statement_july.pdf", _pdf([["Synthetic Credit Union - Statement", "Page 1 of 4"], ["Page 2 of 4", "07/22 Deposit 3,000.00"], ["Page 4 of 4", "Ending balance 18,500.00"]])),
    "doc_contract": ("purchase_contract", None, "purchase_contract.pdf", _pdf([["Residential Purchase Agreement - SYNTHETIC"], ["Page 2 Signatures"]])),
    "doc_dup": ("income", "paystub", "scan0042 copy.pdf", _pdf([["Earnings Statement - SYNTHETIC HEALTH SYSTEM", "Pay period ending 09/04/2026"]])),
}


def refs(names=None):
    out = []
    for key, (cat, sub, fname, data) in FILES.items():
        if names and key not in names:
            continue
        out.append({"documentId": key, "category": cat, "subcategory": sub, "borrowerRef": "borrower" if cat in ("income", "assets") else None, "originalFilename": fname,
                    "displayName": f"2026-09-09_{(sub or cat)}_{fname[:4]}.pdf", "storageKey": f"submissions/sub_x/{cat}/{fname}", "mimeType": "application/pdf",
                    "sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "uploadedAt": "2026-09-09T20:00:00Z", "uploadedBy": "loan_officer",
                    "status": "duplicate" if key == "doc_dup" else "received", "fetchUrl": f"https://lfprocessing.net/api/internal/documents/sub_x/{key}"})
    return out


def fake_fetch(ref):
    key = ref["fetchUrl"].rsplit("/", 1)[-1]
    if key == "doc_fail":
        raise ConnectionError("storage down")
    return FILES[key][3]


@pytest.fixture(scope="module")
def mods():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)
    return {n: importlib.import_module(f"flo_team.{n}") for n in ("documents", "intake", "workspace", "handoff", "today")}


SUBMISSION = {"lo_stated_income": [{"borrower": "borrower", "incomeType": "w2", "documentsIncluded": ["paystubs", "w2s"]}], "funds_to_close": [{"sourceType": "borrower_bank_account"}],
              "transaction_type": "purchase"}


class TestIngest:
    def test_pulls_files_names_them_extracts_text_and_flags_gaps(self, mods, tmp_path):
        documents = mods["documents"]
        team_root = tmp_path / "team"
        team_root.mkdir()
        result = documents.ingest(team_root, "loan_test", "sub_x", refs(), fetch=fake_fetch)
        assert result["received"] == 8 and result["duplicates"] == 1
        by = {d["website_document_id"]: d for d in result["documents"]}
        bank = by["doc_bank"]
        assert bank["status"] == "missing_pages" and bank["checks"]["pages"]["missing"] == [3] and bank["page_count"] == 3
        assert "Pages 3 of 4" in bank["notes"]
        assert Path(bank["local_path"]).exists() and Path(bank["local_path"]).parent.name == "borrower1" and Path(bank["local_path"]).parent.parent.name == "assets"
        assert Path(bank["text_path"]).read_text(encoding="utf-8").startswith("Synthetic Credit Union")
        assert by["doc_pay1"]["subcategory"] == "paystub" and by["doc_pay1"]["classification_source"] == "text"  # LO left the subtype blank
        assert by["doc_pay2"]["classification_source"] == "loan_officer"
        assert by["doc_dup"]["status"] == "duplicate" and by["doc_dup"]["local_path"] == by["doc_pay1"]["local_path"]
        assert by["doc_1003"]["local_path"].replace("\\", "/").endswith("/loan_test/application/2026-09-09_loan_application_1003.pdf")
        # nothing sensitive in names, originals untouched
        assert all(Path(d["local_path"]).read_bytes() == FILES[d["website_document_id"]][3] for d in result["documents"] if d["status"] != "duplicate")
        # inventory: everything received, bank statement needs clarification (missing page), nothing invented
        inv = documents.inventory(team_root, "loan_test", SUBMISSION, program="fannie", rule_check=lambda p, r: True)
        assert [w["key"] for w in inv["missing"]] == []
        assert any("Missing pages" in (w.get("problem") or "") for w in inv["needs_clarification"])
        assert inv["counts"]["documents"] == 8
        # without the paystub and with an inactive rule the item is a clarification, with an active rule it is missing
        documents.DocumentStore(team_root).update("loan_test", by["doc_pay1"]["document_id"], {"status": "not_needed"}, by="malcolm")
        documents.DocumentStore(team_root).update("loan_test", by["doc_pay2"]["document_id"], {"status": "not_needed"}, by="malcolm")
        inv_gap = documents.inventory(team_root, "loan_test", SUBMISSION, program="fannie", rule_check=lambda p, r: False)
        assert any(w["key"] == "paystub" and w["basis"] == "SOURCE_GAP" for w in inv_gap["needs_clarification"])
        inv_rule = documents.inventory(team_root, "loan_test", SUBMISSION, program="fannie", rule_check=lambda p, r: r == "fannie.docs.paystub")
        assert [w["basis"] for w in inv_rule["missing"]] == ["fannie.docs.paystub"]

    def test_failed_fetch_is_kept_for_retry_and_reclassification_is_editable(self, mods, tmp_path):
        documents = mods["documents"]
        team_root = tmp_path / "team"
        team_root.mkdir()
        bad = dict(refs(["doc_1003"])[0], documentId="doc_fail", fetchUrl="https://lfprocessing.net/api/internal/documents/sub_x/doc_fail", sha256="0" * 64, status="received")
        result = documents.ingest(team_root, "loan_t2", "sub_x", [bad], fetch=fake_fetch)
        rec = result["documents"][0]
        assert rec["status"] == "needs_review" and rec["checks"].get("fetch_failed") and rec["local_path"] is None
        fixed = documents.refetch(team_root, "loan_t2", rec["document_id"], fetch=lambda r: FILES["doc_1003"][3], fetch_url=bad["fetchUrl"])
        assert fixed["status"] == "received" and Path(fixed["local_path"]).exists()
        store = documents.DocumentStore(team_root)
        upd = store.update("loan_t2", rec["document_id"], {"category": "income", "subcategory": "paystub", "borrower_ref": "co_borrower", "status": "reviewed"}, by="malcolm")
        assert upd["classification_source"] == "malcolm" and upd["history"][-1]["changes"]["status"] == "reviewed"
        with pytest.raises(ValueError):
            store.update("loan_t2", rec["document_id"], {"status": "approved"}, by="malcolm")
        with pytest.raises(ValueError):
            store.update("loan_t2", rec["document_id"], {"local_path": "x"}, by="malcolm")

    def test_ashley_adds_a_file_from_her_machine(self, mods, tmp_path):
        documents = mods["documents"]
        team_root = tmp_path / "team"
        team_root.mkdir()
        src = tmp_path / "hoi quote.pdf"
        src.write_bytes(_pdf([["Homeowners Insurance Declarations Page - SYNTHETIC"]]))
        rec = documents.add_local(team_root, "loan_t3", str(src), category="insurance", by="ashley")
        assert rec["status"] == "received" and rec["uploaded_by"] == "ashley" and src.exists() and Path(rec["local_path"]).parent.name == "insurance"
        (tmp_path / "x.exe").write_bytes(b"MZ\x90\x00 not a document")
        with pytest.raises(ValueError):
            documents.add_local(team_root, "loan_t3", str(tmp_path / "x.exe"), category="other")


class TestIntakeWithDocuments:
    def test_submission_with_documents_lands_organized_in_the_deal_room(self, mods, tmp_path):
        spec = importlib.util.spec_from_file_location("flo_test_intake_fixture", Path(__file__).with_name("test_intake.py"))
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        payload = fixture.payload

        intake, workspace, today = mods["intake"], mods["workspace"], mods["today"]
        p = payload(documentRefs=refs())
        rec = intake.receive(tmp_path, p, document_fetch=fake_fetch, rule_check=lambda prog, r: True)
        assert rec["documents_received"] == 8
        assert rec["ashley_line"] == "New loan came in — Justinvil-Synthetic.\n\n8 documents came with it.\n\nMalcolm is reviewing everything now. 💚"
        ws = workspace.WorkspaceStore(tmp_path).get(rec["workspace_id"])
        assert ws["documents_summary"]["received"] == 8 and ws["documents_summary"]["duplicates"] == 1
        assert any("Missing pages" in c for c in ws["documents_summary"]["needs_clarification"])
        assert len(ws["document_refs"]) == 9 and all(r["ref"].startswith("doc://") for r in ws["document_refs"])
        assert not any("storage_key" in r for r in ws["document_refs"])
        task = mods["handoff"].TaskRegistry(tmp_path).get(rec["task_id"])
        assert any(f.startswith("Documents received: 8") for f in task.facts)
        assert any("Pages 3 of 4" in f for f in task.facts)
        card = today.new_loan_card(ws)
        assert card["documents_received"] == 8 and card["line"] == "8 documents received. Malcolm is reviewing it."
        assert today.review_line(ws) is None  # not reviewed yet
        reviewed = {**ws, "readiness": {"status": "IN_PROGRESS", "missing_count": 2, "missing": [{"item": "Most recent paystub", "owner": "borrower"}, {"item": "Bank statement page 3", "owner": "borrower"}]}}
        assert today.review_line(reviewed) == "Justinvil-Synthetic is reviewed.\n\n8 documents received.\n\nWe're missing 2 items.\n\nBiggest blocker:\nMost recent paystub.\n\nBest next move:\nRequest the missing docs."
        assert today.file_summary(reviewed)["review_line"] == today.review_line(reviewed)
        board = today.document_board({**reviewed, "readiness": {**reviewed["readiness"], "missing": [{"item": "Most recent paystub"}, {"item": "Bank statement page 3"}, {"item": "HOI declarations page"}]}})
        assert [(g["label"], len(g["documents"]), g["missing"], g["waiting"]) for g in board] == [
            ("Application", 1, [], False), ("Credit", 1, [], False), ("AUS", 1, [], False), ("Income", 4, ["Most recent paystub"], False),
            ("Assets", 1, ["Bank statement page 3"], False), ("Contract", 1, [], False), ("Title / Property", 0, [], True), ("Insurance", 0, ["HOI declarations page"], False)]
        assert next(g for g in board if g["label"] == "Assets")["documents"][0]["attention"] is True
        grouped = mods["documents"].ashley_documents(tmp_path, rec["workspace_id"])
        assert [g["label"] for g in grouped["groups"]] == ["Application", "Credit", "AUS", "Income", "Assets", "Contract"]
        assert grouped["count"] == 8
        # redelivery: same submission, no second ingest
        again = intake.receive(tmp_path, p, document_fetch=fake_fetch)
        assert again["duplicate"] is True and len(mods["documents"].DocumentStore(tmp_path).list(rec["workspace_id"])) == 9

    def test_flo_documents_tool_for_malcolm_and_not_for_franklin(self, mods, tmp_path, monkeypatch):
        spec = importlib.util.spec_from_file_location("flo_test_intake_fixture2", Path(__file__).with_name("test_intake.py"))
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        tools = importlib.import_module("flo_team.tools")
        root = tmp_path / "hermes" / "flo" / "team"
        root.mkdir(parents=True)
        monkeypatch.setattr(tools, "_STATE_ROOT_OVERRIDE", root)
        rec = mods["intake"].receive(root, fixture.payload(documentRefs=refs()), document_fetch=fake_fetch)
        wid = rec["workspace_id"]

        monkeypatch.setenv("HERMES_PROFILE_NAME", "malcolm")
        listed = json.loads(tools.handle_flo_documents({"action": "list", "workspace_id": wid}))
        assert len(listed["documents"]) == 9 and not any("local_path" in d or "sha256" in d for d in listed["documents"])
        bank = next(d for d in listed["documents"] if d["subcategory"] == "bank_statement")
        got = json.loads(tools.handle_flo_documents({"action": "get", "workspace_id": wid, "document_id": bank["document_id"], "max_chars": 40}))
        assert got["text"].startswith("Synthetic Credit Union") and len(got["text"]) <= 40
        inv = json.loads(tools.handle_flo_documents({"action": "inventory", "workspace_id": wid}))
        assert inv["counts"]["documents"] == 8 and inv["note"].startswith("Only items backed by an ACTIVE source rule")
        upd = json.loads(tools.handle_flo_documents({"action": "update", "workspace_id": wid, "document_id": bank["document_id"], "fields": {"status": "reviewed", "notes": "page 3 requested"}}))
        assert upd["status"] == "reviewed" and upd["classification_source"] == "loan_officer"  # a status change is not a reclassification
        recl = json.loads(tools.handle_flo_documents({"action": "update", "workspace_id": wid, "document_id": bank["document_id"], "fields": {"borrower_ref": "co_borrower"}}))
        assert recl["classification_source"] == "malcolm" and recl["borrower_ref"] == "co_borrower"
        ws = mods["workspace"].WorkspaceStore(root).get(wid)
        assert next(r for r in ws["document_refs"] if r["document_id"] == bank["document_id"])["status"] == "reviewed"
        assert ws["documents_summary"]["needs_clarification"] == []
        src = tmp_path / "hoi.pdf"
        src.write_bytes(_pdf([["Homeowners Insurance Declarations Page - SYNTHETIC"]]))
        added = json.loads(tools.handle_flo_documents({"action": "add", "workspace_id": wid, "path": str(src), "category": "insurance"}))
        assert added["status"] == "received" and len(mods["workspace"].WorkspaceStore(root).get(wid)["document_refs"]) == 10
        bad = json.loads(tools.handle_flo_documents({"action": "update", "workspace_id": wid, "document_id": bank["document_id"], "fields": {"status": "approved"}}))
        assert "error" in bad

        monkeypatch.setenv("HERMES_PROFILE_NAME", "franklin")
        denied = json.loads(tools.handle_flo_documents({"action": "list", "workspace_id": wid}))
        assert "error" in denied and "excluded" in denied["error"]
