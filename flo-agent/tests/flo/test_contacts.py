from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "flo-team"
if "flo_team" not in sys.modules:
    spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["flo_team"] = module
    spec.loader.exec_module(module)
contacts = importlib.import_module("flo_team.contacts")
mismo = importlib.import_module("flo_team.mismo")
workspace_mod = importlib.import_module("flo_team.workspace")


def _contact(contact_id: str, *, name: str, email: str = "", role: str = "loan_officer"):
    return {
        "contact_id": contact_id, "role": role, "name": name, "email": email,
        "preferred_communication_method": "not_set",
    }


def test_contact_roles_seed_from_mismo_source_without_inventing_missing_values():
    rows = contacts.from_mismo({
        "source_file": "synthetic.xml",
        "borrowers": [{"borrower_id": "b1", "role": "borrower", "provenance": {"full_name": "/PARTY/NAME"},
                       "values": {"full_name": "Avery River", "email": "avery@example.test"}}],
        "loan_officers": [{"party_id": "p1", "role": "LoanOriginator", "provenance": {},
                           "values": {"full_name": "Jordan Lee", "phone": "+19045550100", "nmls_id": "123456"}}],
        "origination_companies": [{"party_id": "p2", "role": "LoanOriginationCompany", "values": {"company": "Harbor Lending"}}],
        "lenders": [], "account_executives": [], "contacts": [],
    })
    by_role = {row["role"]: row for row in rows}
    assert by_role["borrower"]["name"] == "Avery River"
    assert by_role["borrower"]["email"] == "avery@example.test"
    assert by_role["loan_officer"]["phone"] == "+19045550100"
    assert by_role["loan_officer"]["nmls_license_id"] == "123456"
    assert by_role["lender"]["company"] == "Harbor Lending"
    assert "lender_ae" not in by_role
    assert by_role["borrower"]["source"]["kind"] == "MISMO 3.4"


def test_existing_submission_contacts_migrate_with_submission_provenance(tmp_path):
    store = workspace_mod.WorkspaceStore(tmp_path / "team")
    ws = store.create(display_name="River")
    store.docs.update(ws["workspace_id"], lambda doc: doc.update({
        "submission": {
            "submission_id": "synthetic-submission",
            "loan_officer": {"name": "Jordan Lee", "company": "Harbor Lending", "email": "jordan@example.test", "phone": "+19045550100", "nmls": "123456"},
            "borrowers": [{"role": "borrower", "name": "Avery River", "email": "avery@example.test"}],
        }
    }))

    roster, migrated = contacts.load_workspace_contacts(store, ws["workspace_id"])
    assert migrated is True
    by_role = {row["role"]: row for row in roster}
    assert by_role["borrower"]["email"] == "avery@example.test"
    assert by_role["borrower"]["source"]["kind"] == "Loan Submission"
    assert by_role["loan_officer"]["nmls_license_id"] == "123456"
    assert by_role["loan_officer"]["source"]["path"] == "submission.loan_officer"
    assert {row["role"] for row in store.list()[0]["contacts"]} == {"borrower", "loan_officer"}
    assert contacts.load_workspace_contacts(store, ws["workspace_id"])[1] is False


def test_import_refresh_preserves_manual_edits_and_does_not_duplicate_same_person():
    source = contacts.from_mismo({
        "source_file": "synthetic.xml",
        "borrowers": [{"borrower_id": "b1", "role": "borrower", "values": {"full_name": "Avery River", "phone": "+19045550100"}}],
    })[0]
    existing = [{**source, "contact_id": "manual-contact", "email": "avery@custom.test", "notes": "Confirmed with Ashley"}]
    refreshed = contacts.merge_imported(existing, [source])
    assert len(refreshed) == 1
    assert refreshed[0]["contact_id"] == "manual-contact"
    assert refreshed[0]["email"] == "avery@custom.test"
    assert refreshed[0]["notes"] == "Confirmed with Ashley"
    assert refreshed[0]["source"]["kind"] == "MISMO 3.4"


def test_role_resolution_returns_not_set_ambiguous_or_selected_contact():
    assert contacts.resolve([], "LO")["status"] == "not_set"
    rows = [_contact("lo1", name="Jordan Lee"), _contact("lo2", name="Morgan Ray")]
    ambiguous = contacts.resolve(rows, "Loan Officer")
    assert ambiguous["status"] == "ambiguous"
    assert {row["contact_id"] for row in ambiguous["candidates"]} == {"lo1", "lo2"}
    assert contacts.resolve(rows, "LO", "lo2")["contact"]["name"] == "Morgan Ray"


def test_contact_save_validates_roles_email_and_preferred_method():
    clean = contacts.normalize_contacts([{
        "contact_id": "lo1", "role": "loan_officer", "name": "Jordan Lee",
        "email": "jordan@example.test", "preferred_communication_method": "email",
    }])
    assert clean[0]["email"] == "jordan@example.test"
    import pytest
    with pytest.raises(ValueError, match="valid email"):
        contacts.normalize_contacts([{"role": "borrower", "email": "not-an-email"}])
    with pytest.raises(ValueError, match="supported contact role"):
        contacts.normalize_contacts([{"role": "unknown_role"}])


def test_mismo_party_contacts_keep_role_details_and_source_path(tmp_path):
    source = tmp_path / "contacts.xml"
    source.write_text('''<MESSAGE><ABOUT_VERSION><DataVersionIdentifier>3.4</DataVersionIdentifier></ABOUT_VERSION>
      <DEALS><DEAL><LOANS><LOAN><LOANIDENTIFIER>CONTACTS-1</LOANIDENTIFIER></LOAN></LOANS><PARTIES>
        <PARTY id="agent-1"><PARTYROLETYPE>BuyersAgent</PARTYROLETYPE>
          <INDIVIDUAL><NAME><FIRSTNAME>Synthetic</FIRSTNAME><LASTNAME>Agent</LASTNAME></NAME></INDIVIDUAL>
          <CONTACTPOINT><CONTACTPOINTEMAILVALUE>agent@example.test</CONTACTPOINTEMAILVALUE><CONTACTPOINTTELEPHONEVALUE>+19045550111</CONTACTPOINTTELEPHONEVALUE></CONTACTPOINT>
        </PARTY>
      </PARTIES></DEAL></DEALS></MESSAGE>''')
    parsed = mismo.parse_file(source)
    roster = contacts.from_mismo(parsed)
    assert len(roster) == 1
    assert roster[0]["role"] == "buyers_agent"
    assert roster[0]["name"] == "Synthetic Agent"
    assert roster[0]["email"] == "agent@example.test"
    assert roster[0]["phone"] == "+19045550111"
    assert roster[0]["source"]["source_file"] == "contacts.xml"
    assert roster[0]["source"]["path"].startswith("/")


def test_workspace_contact_read_migrates_mismo_and_save_is_the_resolution_source(tmp_path):
    store = workspace_mod.WorkspaceStore(tmp_path / "team")
    ws = store.create(display_name="River")
    store.docs.update(ws["workspace_id"], lambda doc: doc.update({
        "mismo": {
            "source_file": "river.xml",
            "borrowers": [{"borrower_id": "b1", "role": "borrower", "values": {"full_name": "Avery River"}}],
            "loan_officers": [{"party_id": "lo1", "role": "LoanOriginator", "values": {"full_name": "Jordan Lee", "email": "jordan@example.test"}}],
        }
    }))

    migrated, changed = contacts.load_workspace_contacts(store, ws["workspace_id"])
    assert changed is True
    assert {row["role"] for row in migrated} == {"borrower", "loan_officer"}
    assert contacts.load_workspace_contacts(store, ws["workspace_id"])[1] is False

    edited = [{**migrated[1], "name": "Jordan Lee", "email": "jordan-updated@example.test"}]
    saved = contacts.save_workspace_contacts(store, ws["workspace_id"], edited)
    resolution = contacts.resolve(store.get(ws["workspace_id"])["contacts"], "LO")
    assert saved[0]["email"] == "jordan-updated@example.test"
    assert resolution["status"] == "resolved"
    assert resolution["contact"]["contact_id"] == saved[0]["contact_id"]
    assert store.get(ws["workspace_id"])["contacts"] == saved
