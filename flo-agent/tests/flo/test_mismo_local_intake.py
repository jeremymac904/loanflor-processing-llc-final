from __future__ import annotations

import importlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "flo-team"
if "flo_team" not in sys.modules:
    spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["flo_team"] = module
    spec.loader.exec_module(module)
for _name in ("manifest", "store", "workspace", "documents", "mismo", "local_intake", "tools"):
    importlib.import_module(f"flo_team.{_name}")
from flo_team import documents
from flo_team.local_intake import LocalIntakeError, bind_session, intake
from flo_team.mismo import parse_file
from flo_team import tools
from flo_team.workspace import WorkspaceStore

FIXTURE = Path(__file__).parent / "fixtures" / "mismo34_synthetic.xml"


def test_mismo_34_parser_extracts_structured_facts_and_provenance(tmp_path):
    record = parse_file(FIXTURE)
    assert record["format"] == "MISMO 3.4"
    assert record["loan"]["lender_loan_id"] == "SMITH-TEST-1042"
    assert record["loan"]["base_loan_amount"] == 320000
    assert record["loan"]["interest_rate"] == 6.5
    assert record["loan_provenance"]["base_loan_amount"].startswith("/MESSAGE[")
    assert record["borrowers"][0]["values"]["full_name"] == "Jamie Smith"
    assert record["properties"][0]["kind"] == "subject"
    assert record["properties"][0]["values"]["street"] == "12 Fern Way"
    assert record["assets"][0]["values"]["balance"] == 45000
    assert record["assets"][0]["linked_borrower_ids"] == ["borrower-1"]
    assert record["liabilities"][0]["linked_property_ids"] == ["reo-1"]


def test_missing_mismo_field_stays_missing(tmp_path):
    xml = tmp_path / "minimal.xml"
    xml.write_text('<MESSAGE><ABOUT_VERSION><DataVersionIdentifier>3.4</DataVersionIdentifier></ABOUT_VERSION><LOAN><LoanIdentifier>X-1</LoanIdentifier></LOAN></MESSAGE>')
    record = parse_file(xml)
    assert "total_loan_amount" not in record["loan"]
    assert "interest_rate" not in record["loan"]


def test_mismo_party_layout_maps_borrower_officer_company_and_subject_address(tmp_path):
    xml = tmp_path / "party-layout.xml"
    xml.write_text('''<MESSAGE xmlns:xlink="http://www.w3.org/1999/xlink"><ABOUT_VERSION><DataVersionIdentifier>3.4</DataVersionIdentifier></ABOUT_VERSION>
      <DEALS><DEAL><LOANS><LOAN id="loan-1"><LOANIDENTIFIER>LOCAL-TEST-1</LOANIDENTIFIER><LOANPURPOSETYPE>Purchase</LOANPURPOSETYPE><CLOSINGDATE>2026-10-28</CLOSINGDATE></LOAN></LOANS>
      <PARTIES>
        <PARTY><PARTYROLETYPE>Borrower</PARTYROLETYPE><INDIVIDUAL><NAME><FIRSTNAME>Avery</FIRSTNAME><LASTNAME>River</LASTNAME></NAME></INDIVIDUAL><ROLES><ROLE id="role-borrower"/></ROLES></PARTY>
        <PARTY><PARTYROLETYPE>LoanOriginator</PARTYROLETYPE><INDIVIDUAL><NAME><FIRSTNAME>Jordan</FIRSTNAME><LASTNAME>Lee</LASTNAME></NAME></INDIVIDUAL></PARTY>
        <PARTY><PARTYROLETYPE>LoanOriginationCompany</PARTYROLETYPE><LEGALENTITY><NAME><FULLNAME>Harbor Lending</FULLNAME></NAME></LEGALENTITY></PARTY>
      </PARTIES><COLLATERALS><COLLATERAL><SUBJECTPROPERTY><ADDRESS><ADDRESSLINETEXT>12 Fern Way</ADDRESSLINETEXT><CITYNAME>Springfield</CITYNAME><STATECODE>FL</STATECODE><POSTALCODE>32000</POSTALCODE></ADDRESS></SUBJECTPROPERTY></COLLATERAL></COLLATERALS>
      <ASSETS><ASSET id="asset-1"><ASSETCASHVALUEAMOUNT>10000</ASSETCASHVALUEAMOUNT></ASSET></ASSETS>
      <RELATIONSHIPS><RELATIONSHIP xlink:from="#asset-1" xlink:to="#role-borrower"><RELATIONSHIPDETAILTYPE>ASSET_IsAssociatedWith_ROLE</RELATIONSHIPDETAILTYPE></RELATIONSHIP></RELATIONSHIPS>
      </DEAL></DEALS></MESSAGE>''')
    record = parse_file(xml)
    assert record["display_name"] == "Avery River"
    assert record["borrowers"][0]["borrower_id"] == "role-borrower"
    assert record["borrowers"][0]["values"]["full_name"] == "Avery River"
    assert record["loan_officers"][0]["values"]["full_name"] == "Jordan Lee"
    assert record["origination_companies"][0]["values"]["full_name"] == "Harbor Lending"
    assert record["properties"][0]["values"]["street"] == "12 Fern Way"
    assert record["loan"]["closing_date"] == "2026-10-28"
    assert record["assets"][0]["linked_borrower_ids"] == ["role-borrower"]


def test_ambiguous_or_unresolved_liability_relationship_is_flagged(tmp_path):
    xml = tmp_path / "ambiguous.xml"
    xml.write_text('''<MESSAGE><ABOUT_VERSION><DataVersionIdentifier>3.4</DataVersionIdentifier></ABOUT_VERSION>
      <LOAN><LoanIdentifier>X-2</LoanIdentifier></LOAN><SUBJECT_PROPERTY id="p1"><StreetAddress>1 Main</StreetAddress></SUBJECT_PROPERTY>
      <REO_PROPERTY id="p2"><StreetAddress>2 Main</StreetAddress></REO_PROPERTY>
      <LIABILITY id="l1"><CreditorName>Bank</CreditorName><PROPERTY_REFERENCE xlink:href="#not-a-property" xmlns:xlink="http://www.w3.org/1999/xlink"/></LIABILITY></MESSAGE>''')
    record = parse_file(xml)
    assert record["liabilities"][0]["needs_review"]
    assert record["needs_review"]


def test_conflicting_liability_property_relationships_are_flagged(tmp_path):
    xml = tmp_path / "ambiguous-two-properties.xml"
    xml.write_text('''<MESSAGE xmlns:xlink="http://www.w3.org/1999/xlink"><ABOUT_VERSION><DataVersionIdentifier>3.4</DataVersionIdentifier></ABOUT_VERSION>
      <LOAN><LoanIdentifier>X-3</LoanIdentifier></LOAN><SUBJECT_PROPERTY id="p1"><StreetAddress>1 Main</StreetAddress></SUBJECT_PROPERTY>
      <REO_PROPERTY id="p2"><StreetAddress>2 Main</StreetAddress></REO_PROPERTY>
      <LIABILITY id="l1"><CreditorName>Bank</CreditorName><PROPERTY_REFERENCE xlink:href="#p1"/></LIABILITY>
      <RELATIONSHIP><RELATIONSHIP_TYPE>LiabilitySecuredByProperty</RELATIONSHIP_TYPE><FROM_ENTITY xlink:href="#l1"/><TO_ENTITY xlink:href="#p2"/></RELATIONSHIP></MESSAGE>''')
    record = parse_file(xml)
    assert set(record["liabilities"][0]["linked_property_ids"]) == {"p1", "p2"}
    assert "multiple properties" in record["liabilities"][0]["needs_review"]


def test_local_intake_creates_pipeline_workspace_preserves_xml_and_runs_idempotently(tmp_path):
    source = tmp_path / "Smith Client Folder"
    source.mkdir()
    xml = source / "Smith_3.4.xml"
    shutil.copyfile(FIXTURE, xml)
    (source / "1003.pdf").write_bytes(b"%PDF-1.4\n% synthetic fixture")
    (source / "income").mkdir()
    (source / "income" / "paystub.pdf").write_bytes(b"%PDF-1.4\n% synthetic paystub")
    (source / "random.bin").write_bytes(b"ignored")
    team_root = tmp_path / "flo" / "team"

    first = intake(team_root, source)
    assert first["created"] is True
    assert first["workspace_id"].startswith("loan_")
    ws = WorkspaceStore(team_root).get(first["workspace_id"])
    assert ws["milestone"] == "Intake"
    assert ws["loan_number"] == "SMITH-TEST-1042"
    assert ws["display_name"] == "Jamie Smith"
    assert ws["borrowers"][0]["values"]["full_name"] == "Jamie Smith"
    assert ws["mismo"]["source_sha256"] == first["source_sha256"]
    assert len(documents.DocumentStore(team_root).list(first["workspace_id"])) == 3
    xml_record = next(row for row in documents.DocumentStore(team_root).list(first["workspace_id"]) if row["original_filename"].endswith(".xml"))
    assert Path(xml_record["local_path"]).read_bytes() == xml.read_bytes()
    assert xml.read_bytes() == FIXTURE.read_bytes()
    assert first["unsupported"] == ["random.bin"]

    second = intake(team_root, source)
    assert second["workspace_id"] == first["workspace_id"]
    assert second["created"] is False
    assert second["duplicate_source"] is True
    assert len(list(WorkspaceStore(team_root).docs.all())) == 1
    assert len(documents.DocumentStore(team_root).list(first["workspace_id"])) == 3


def test_metadata_refresh_uses_existing_xml_without_reimporting_documents(tmp_path):
    from flo_team.local_intake import refresh_existing_workspace_metadata

    source = tmp_path / "Downloads"
    source.mkdir()
    xml = source / "Smith_3.4.xml"
    shutil.copyfile(FIXTURE, xml)
    team_root = tmp_path / "flo" / "team"
    result = intake(team_root, xml)
    workspace_store = WorkspaceStore(team_root)
    wid = result["workspace_id"]
    workspace_store.docs.update(wid, lambda doc: doc.update({"display_name": "Downloads", "mismo_summary_refreshed_at": None}))
    before = len(documents.DocumentStore(team_root).list(wid))

    refreshed = refresh_existing_workspace_metadata(team_root, wid)

    saved = workspace_store.get(wid)
    assert refreshed["updated"] is True
    assert saved["display_name"] == "Jamie Smith"
    assert saved["loan_number"] == "SMITH-TEST-1042"
    assert len(documents.DocumentStore(team_root).list(wid)) == before


def test_local_intake_updates_a_workspace_by_lender_loan_id(tmp_path):
    team_root = tmp_path / "flo" / "team"
    store = WorkspaceStore(team_root)
    existing = store.create(display_name="Smith", program="conventional", agency="fannie")
    store.docs.update(existing["workspace_id"], lambda doc: doc.update({"loan_number": "SMITH-TEST-1042"}))
    xml = tmp_path / "Smith_3.4.xml"
    shutil.copyfile(FIXTURE, xml)

    result = intake(team_root, xml)
    assert result["created"] is False
    assert result["workspace_id"] == existing["workspace_id"]
    assert len(list(store.docs.all())) == 1


def test_chat_binding_persists_both_directions(tmp_path):
    team_root = tmp_path / "flo" / "team"
    workspace = WorkspaceStore(team_root).create(display_name="Smith", program="conventional", agency="fannie")
    bound = bind_session(team_root, "session-smith-1", workspace["workspace_id"])
    assert bound["workspace_id"] == workspace["workspace_id"]
    assert WorkspaceStore(team_root).get(workspace["workspace_id"])["chat_sessions"][0]["session_id"] == "session-smith-1"
    from flo_team.store import JsonDocStore
    assert JsonDocStore(team_root / "chat_workspace_bindings").get("sessions")["bindings"]["session-smith-1"] == workspace["workspace_id"]


def test_folder_without_mismo_fails_closed_without_creating_workspace(tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "1003.pdf").write_bytes(b"synthetic")
    team_root = tmp_path / "flo" / "team"
    with pytest.raises(LocalIntakeError, match="no MISMO 3.4 XML"):
        intake(team_root, folder)
    assert list(WorkspaceStore(team_root).docs.all()) == []


def test_ambiguous_existing_loan_does_not_create_a_duplicate(tmp_path):
    team_root = tmp_path / "flo" / "team"
    store = WorkspaceStore(team_root)
    for name in ("Smith One", "Smith Two"):
        workspace = store.create(display_name=name, program="conventional", agency="fannie")
        store.docs.update(workspace["workspace_id"], lambda doc: doc.update({"loan_number": "SMITH-TEST-1042"}))
    xml = tmp_path / "Smith_3.4.xml"
    shutil.copyfile(FIXTURE, xml)

    with pytest.raises(LocalIntakeError, match="more than one Customer File"):
        intake(team_root, xml)
    assert len(list(store.docs.all())) == 2


def test_existing_malcolm_fileprep_handler_saves_deterministic_readiness(tmp_path, monkeypatch):
    team_root = tmp_path / "flo" / "team"
    workspace = WorkspaceStore(team_root).create(display_name="Smith", program="conventional", agency="fannie")
    monkeypatch.setattr(tools, "_STATE_ROOT_OVERRIDE", team_root)
    monkeypatch.setattr(tools, "_me", lambda: tools._manifest().role("flo"))
    monkeypatch.setattr(tools, "_active_check", lambda *args, **kwargs: (lambda _section: False, lambda section: {"section": section}))

    result = json.loads(tools.handle_flo_fileprep({"workspace_id": workspace["workspace_id"], "documents": [], "program": "fannie"}))
    assert result["readiness"]["generated_by"] == "malcolm"
    saved = WorkspaceStore(team_root).get(workspace["workspace_id"])
    assert saved["readiness"]["workspace_id"] == workspace["workspace_id"]
