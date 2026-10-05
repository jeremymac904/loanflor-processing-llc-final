"""Deterministic, local MISMO 3.4 / URLA XML intake helpers.

The parser intentionally returns only fields it can identify structurally. It
does not infer missing values and retains an XML path for every extracted fact.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

MAX_XML_BYTES = 20 * 1024 * 1024
_LOCAL = re.compile(r"\{[^}]+\}")


def local_name(tag: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", _LOCAL.sub("", str(tag)).split(":")[-1]).upper()


def _path(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> str:
    parts = []
    node = element
    while node is not None:
        name = local_name(node.tag)
        parent = parents.get(node)
        siblings = [s for s in list(parent) if local_name(s.tag) == name] if parent is not None else [node]
        index = siblings.index(node) + 1 if node in siblings else 1
        parts.append(f"{name}[{index}]")
        node = parents.get(node)
    return "/" + "/".join(reversed(parts))


def _text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    value = " ".join("".join(element.itertext()).split())
    return value or None


def _find(node: ET.Element, *names: str) -> ET.Element | None:
    wanted = {local_name(name) for name in names}
    return next((child for child in node.iter() if local_name(child.tag) in wanted and _text(child)), None)


def _value(node: ET.Element, *names: str) -> str | None:
    return _text(_find(node, *names))


def _number(value: str | None) -> int | float | None:
    if value is None:
        return None
    cleaned = value.replace(",", "").replace("$", "").strip()
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    return int(number) if number == number.to_integral_value() else float(number)


def _elements(root: ET.Element, *names: str) -> list[ET.Element]:
    wanted = {local_name(name) for name in names}
    return [node for node in root.iter() if local_name(node.tag) in wanted]


def _record(parent: ET.Element, fields: dict[str, tuple[str, ...]], parents: dict[ET.Element, ET.Element], *, numeric=()) -> dict[str, Any]:
    values: dict[str, Any] = {}
    provenance: dict[str, str] = {}
    for field, candidates in fields.items():
        found = _find(parent, *candidates)
        raw = _text(found)
        if raw is not None:
            values[field] = _number(raw) if field in numeric else raw
            provenance[field] = _path(found, parents)
    return {"values": values, "provenance": provenance}


def _node_id(element: ET.Element) -> str | None:
    for key, value in element.attrib.items():
        name = local_name(key)
        if name in {"ID", "LABEL", "ENTITYID", "OBJECTID"} and value.strip():
            return value.strip().lstrip("#")
    return None


def _references(element: ET.Element) -> list[str]:
    refs: list[str] = []
    for node in element.iter():
        for key, value in node.attrib.items():
            name = local_name(key)
            if name in {"HREF", "REF", "IDREF", "ENTITYIDREF", "OBJECTIDREF"} and value.strip():
                ref = value.strip().lstrip("#")
                if ref not in refs:
                    refs.append(ref)
    return refs


LOAN_FIELDS = {
    "lender_loan_id": ("LOANIDENTIFIER", "LENDERLOANID", "LOANNUMBER"),
    "loan_purpose": ("LOANPURPOSETYPE", "LOANPURPOSE"),
    "refinance_type": ("REFINANCETYPE",),
    "base_loan_amount": ("BASELOANAMOUNT",),
    "total_loan_amount": ("TOTALLOANAMOUNT", "LOANAMOUNT"),
    "purchase_price": ("SALESAMOUNT", "PURCHASEPRICE"),
    "estimated_property_value": ("PROPERTYESTIMATEDVALUE", "APPRAISEDVALUE", "ESTIMATEDPROPERTYVALUE"),
    "interest_rate": ("NOTEINTERESTRATE", "INTERESTRATE"),
    "term_months": ("LOANTERMMONTHS", "LOANTERM"),
    "amortization_type": ("AMORTIZATIONTYPE",),
    "lien_position": ("LIENPRIORITYTYPE", "LIENPOSITION"),
    "occupancy": ("PROPERTYUSAGETYPE", "OCCUPANCYTYPE"),
    "loan_type": ("LOANFEATURETYPE", "LOANTYPE", "GOVERNMENTLOANPROGRAMTYPE"),
    "loan_program": ("LOANPROGRAMTYPE", "LOANPRODUCTTYPE"),
    "application_date": ("APPLICATIONRECEIVEDDATE", "APPLICATIONDATE"),
    "closing_date": ("CLOSINGDATE", "SETTLEMENTDATE", "ESTIMATEDCLOSINGDATE"),
    "cash_to_borrower": ("CASHOUTAMOUNT", "CASHFROMBORROWERAMOUNT"),
    "cash_from_borrower": ("CASHTOBORROWERAMOUNT", "CASHFROMBORROWER"),
    "total_payoffs": ("TOTALPAYOFFAMOUNT", "PAYOFFAMOUNT"),
    "lender_credits": ("LENDERCREDITAMOUNT",),
}
BORROWER_FIELDS = {
    "first_name": ("FIRSTNAME",), "middle_name": ("MIDDLENAME",), "last_name": ("LASTNAME",),
    "suffix": ("NAME suffix".replace(" ", ""),), "email": ("CONTACTPOINTEMAILVALUE", "EMAILADDRESS"),
    "phone": ("CONTACTPOINTTELEPHONEVALUE", "PHONENUMBER"), "marital_status": ("MARITALSTATUSTYPE",),
    "citizenship": ("RESIDENCYTYPE", "CITIZENSHIPRESIDENCYTYPE"), "dependents": ("DEPENDENTSCOUNT",),
    "current_street": ("STREETADDRESS", "ADDRESSLINE"), "current_city": ("CITYNAME",),
    "current_state": ("STATECODE",), "current_postal_code": ("POSTALCODE",),
    "employer": ("EMPLOYERNAME",), "employment_status": ("EMPLOYMENTSTATUSTYPE",),
    "monthly_income": ("CURRENTINCOMEITEMMONTHLYAMOUNT", "BASEMONTHLYINCOMEAMOUNT", "TOTALMONTHLYINCOMEAMOUNT"),
}
PROPERTY_FIELDS = {
    "street": ("STREETADDRESS", "ADDRESSLINETEXT", "ADDRESSLINE"), "city": ("CITYNAME",), "state": ("STATECODE",),
    "postal_code": ("POSTALCODE",), "county": ("COUNTYNAME",), "property_type": ("PROPERTYTYPE", "PROPERTYDESCRIPTORTYPE"),
    "units": ("FINANCEDUNITSCOUNT", "UNITSTOTALCOUNT"), "year_built": ("STRUCTUREBUILTYEAR", "YEARBUILT"),
    "occupancy": ("PROPERTYUSAGETYPE",), "ownership_type": ("ESTATETYPE",), "estimated_value": ("PROPERTYESTIMATEDVALUE",),
}


def parse_file(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    raw = source.read_bytes()
    if len(raw) > MAX_XML_BYTES:
        raise ValueError("MISMO XML exceeds the 20 MiB intake limit")
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("DTD/entity declarations are not accepted in MISMO intake")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("The selected XML is not well-formed") from exc
    names = [local_name(n.tag) for n in root.iter()]
    if not any("MISMO" in name or "LOAN" in name for name in names) or not any("VERSION" in name for name in names):
        raise ValueError("XML does not appear to be a MISMO loan file")
    parents = {child: parent for parent in root.iter() for child in parent}

    loan_nodes = _elements(root, "LOAN")
    loan_node = loan_nodes[0] if loan_nodes else root
    loan = _record(loan_node, LOAN_FIELDS, parents, numeric={"base_loan_amount", "total_loan_amount", "purchase_price", "estimated_property_value", "interest_rate", "term_months", "cash_to_borrower", "cash_from_borrower", "total_payoffs", "lender_credits"})

    borrowers = []
    loan_officers = []
    origination_companies = []
    lenders = []
    account_executives = []
    contacts = []

    # MISMO 3.4 commonly puts the borrower's identity under DEAL/PARTIES/PARTY
    # and connects that person to ROLE entities. The older flat BORROWER
    # extraction below is retained for exports that serialize identity there.
    # ROLE ids matter: assets and liabilities often reference ROLE rather than
    # a BORROWER node, so preserve that explicit entity id for relationship
    # resolution instead of associating records by list order.
    for party in _elements(root, "PARTY"):
        party_role = _value(party, "PARTYROLETYPE") or ""
        role_key = re.sub(r"[^a-z]", "", party_role.casefold())
        values = _record(
            party,
            {
                "first_name": ("FIRSTNAME",), "middle_name": ("MIDDLENAME",), "last_name": ("LASTNAME",),
                "suffix": ("NAMESUFFIX",), "full_name": ("FULLNAME",), "street": ("STREETADDRESS", "ADDRESSLINETEXT", "ADDRESSLINE"),
                "city": ("CITYNAME",), "state": ("STATECODE",), "postal_code": ("POSTALCODE",),
                "email": ("CONTACTPOINTEMAILVALUE",), "phone": ("CONTACTPOINTTELEPHONEVALUE",),
                "marital_status": ("MARITALSTATUSTYPE",), "citizenship": ("CITIZENSHIPRESIDENCYTYPE", "RESIDENCYTYPE"),
                "dependents": ("DEPENDENTCOUNT", "DEPENDENTSCOUNT"), "employer": ("EMPLOYERNAME",),
                "employment_status": ("EMPLOYMENTSTATUSTYPE",),
                "monthly_income": ("CURRENTINCOMEITEMMONTHLYAMOUNT", "BASEMONTHLYINCOMEAMOUNT", "TOTALMONTHLYINCOMEAMOUNT"),
                "company": ("LEGALENTITYNAME", "COMPANYNAME"),
                "nmls_id": ("INDIVIDUALNMLSID", "NMLSID", "LICENSEID"),
            },
            parents,
            numeric={"dependents", "monthly_income"},
        )
        vals = values["values"]
        if not vals.get("full_name"):
            name = " ".join(str(vals.get(key)) for key in ("first_name", "middle_name", "last_name", "suffix") if vals.get(key))
            if name:
                vals["full_name"] = name
        party_roles = _elements(party, "ROLE")
        role_id = next((_node_id(node) for node in party_roles if _node_id(node)), None)
        contact_role = {
            "buyeragent": "buyers_agent", "buyersagent": "buyers_agent",
            "listingagent": "listing_agent", "selleragent": "listing_agent",
            "titlecompany": "title_closing_agent", "settlementagent": "title_closing_agent",
            "closingagent": "title_closing_agent", "hazardinsuranceagent": "insurance_agent",
            "insuranceagent": "insurance_agent", "employer": "employer_voe",
            "appraiser": "appraiser_amc", "appraisalmanagementcompany": "appraiser_amc",
        }.get(role_key)
        if contact_role and (vals.get("full_name") or vals.get("company") or vals.get("phone") or vals.get("email")):
            contacts.append({
                "role": contact_role, "party_id": _node_id(party), "values": vals,
                "provenance": _path(party, parents), "source_party_role": party_role,
            })
        if role_key == "borrower" and (vals.get("full_name") or any(k in vals for k in ("first_name", "last_name"))):
            borrowers.append({
                **values, "borrower_id": role_id or _node_id(party), "references": _references(party), "role": "borrower"
            })
        elif role_key in {"loanoriginator", "loanofficer"}:
            if vals.get("full_name"):
                loan_officers.append({**values, "role": party_role, "party_id": _node_id(party)})
        elif role_key in {"loanoriginationcompany", "loancompany"}:
            if vals.get("full_name") or vals.get("company"):
                origination_companies.append({**values, "role": party_role, "party_id": _node_id(party)})
        elif role_key in {"lender", "investor"}:
            if vals.get("full_name") or vals.get("company"):
                lenders.append({**values, "role": party_role, "party_id": _node_id(party)})
        elif role_key in {"accountexecutive", "ae"}:
            if vals.get("full_name"):
                account_executives.append({**values, "role": party_role, "party_id": _node_id(party)})

    flat_borrowers = []
    for index, node in enumerate(_elements(root, "BORROWER")):
        # Ignore references that contain no borrower facts.
        item = _record(node, BORROWER_FIELDS, parents, numeric={"dependents", "monthly_income"})
        if not item["values"]:
            continue
        vals = item["values"]
        item["borrower_id"] = _node_id(node)
        item["references"] = _references(node)
        item["role"] = "borrower" if index == 0 else "co_borrower"
        name = " ".join(str(vals.get(k)) for k in ("first_name", "middle_name", "last_name", "suffix") if vals.get(k))
        if name:
            vals["full_name"] = name
        flat_borrowers.append(item)
    if not borrowers:
        borrowers = flat_borrowers

    properties = []
    for node in _elements(root, "SUBJECT_PROPERTY", "REO_PROPERTY", "PROPERTY"):
        item = _record(node, PROPERTY_FIELDS, parents, numeric={"units", "year_built", "estimated_value"})
        if item["values"]:
            item["entity_id"] = _node_id(node)
            item["references"] = _references(node)
            ancestors = []
            ancestor = parents.get(node)
            while ancestor is not None:
                ancestors.append(local_name(ancestor.tag))
                ancestor = parents.get(ancestor)
            item["kind"] = "subject" if "SUBJECTPROPERTY" in local_name(node.tag) or "SUBJECTPROPERTY" in ancestors else "reo"
            properties.append(item)

    assets = []
    for node in _elements(root, "ASSET"):
        item = _record(node, {"institution": ("ASSETACCOUNTINSTITUTIONNAME", "INSTITUTIONNAME"), "asset_type": ("ASSETTYPE", "ASSETOWNERSHIPTYPE"), "balance": ("ASSETCASHVALUEAMOUNT", "ASSETVALUATIONAMOUNT", "CURRENTBALANCEAMOUNT")}, parents, numeric={"balance"})
        if item["values"]:
            item["entity_id"] = _node_id(node)
            item["references"] = _references(node)
            assets.append(item)

    liabilities = []
    for node in _elements(root, "LIABILITY"):
        item = _record(node, {"creditor": ("CREDITORNAME",), "liability_type": ("LIABILITYTYPE", "LIABILITYPAYMENTFREQUENCYTYPE"), "balance": ("LIABILITYUNPAIDBALANCEAMOUNT", "UNPAIDBALANCEAMOUNT"), "payment": ("LIABILITYMONTHLYPAYMENTAMOUNT", "MONTHLYPAYMENTAMOUNT"), "payoff_indicator": ("LIABILITYPAYMENTSTOFOLLOW", "LIABILITYEXCLUSIONINDICATOR")}, parents, numeric={"balance", "payment"})
        if item["values"]:
            item["entity_id"] = _node_id(node)
            item["references"] = _references(node)
            item["linked_property_ids"] = [ref for ref in item["references"] if any(prop.get("entity_id") == ref for prop in properties)]
            if item["references"] and not item["linked_property_ids"]:
                item["needs_review"] = "A MISMO liability reference did not resolve to a property entity."
            elif len(item["linked_property_ids"]) > 1:
                item["needs_review"] = "A MISMO liability references multiple properties."
            liabilities.append(item)

    officers = []
    for node in _elements(root, "LOAN_ORIGINATOR", "LOAN_OFFICER", "LOAN_ORIGINATOR_DETAIL"):
        item = _record(node, {"name": ("FULLNAME", "NAME"), "company": ("LEGALENTITYNAME", "COMPANYNAME"), "nmls_id": ("INDIVIDUALNMLSID", "NMLSID"), "company_nmls_id": ("LEGALENTITYNMLSID", "COMPANYNMLSID"), "email": ("CONTACTPOINTEMAILVALUE",), "phone": ("CONTACTPOINTTELEPHONEVALUE",)}, parents)
        if item["values"]:
            officers.append(item)
    if not loan_officers:
        loan_officers = officers

    relation_nodes = _elements(root, "RELATIONSHIP")
    relationships = []
    for node in relation_nodes:
        attrs = {local_name(k).lower(): v.lstrip("#") for k, v in node.attrib.items()}
        refs = _references(node)
        # MISMO exports may encode endpoints as child *_ENTITY xlink:href
        # values or directly as xlink:from / xlink:to attributes.
        from_ids = [str(attrs.get("from") or "").rsplit("#", 1)[-1]] if attrs.get("from") else []
        to_ids = [str(attrs.get("to") or "").rsplit("#", 1)[-1]] if attrs.get("to") else []
        for child in node.iter():
            name = local_name(child.tag)
            refs_here = _references(child)
            if name in {"FROMENTITY", "FROM"}:
                from_ids.extend(refs_here)
            elif name in {"TOENTITY", "TO"}:
                to_ids.extend(refs_here)
        if attrs or refs or _text(node):
            relationships.append({
                "attributes": attrs, "references": refs,
                "from_ids": list(dict.fromkeys(from_ids)), "to_ids": list(dict.fromkeys(to_ids)),
                "type": _value(node, "RELATIONSHIPTYPE", "RELATIONSHIPDETAILTYPE") or attrs.get("arcrole"),
                "provenance": _path(node, parents),
            })

    # Resolve explicit MISMO references only. Never associate a borrower,
    # asset, liability, or property by document order.
    borrower_ids = {row.get("borrower_id") for row in borrowers if row.get("borrower_id")}
    property_ids = {row.get("entity_id") for row in properties if row.get("entity_id")}
    relation_edges = [(source, target, row) for row in relationships
                      for source in row.get("from_ids", []) for target in row.get("to_ids", [])]
    for asset in assets:
        direct = [ref for ref in asset.get("references", []) if ref in borrower_ids]
        linked = list(dict.fromkeys(direct + [target if source == asset.get("entity_id") and target in borrower_ids
                                               else source for source, target, _ in relation_edges
                                               if source == asset.get("entity_id") or target == asset.get("entity_id")
                                               if (target if source == asset.get("entity_id") else source) in borrower_ids]))
        asset["linked_borrower_ids"] = linked
        if asset.get("references") and not linked:
            asset["needs_review"] = "A MISMO asset borrower reference did not resolve to a borrower entity."
        elif len(linked) > 1:
            asset["needs_review"] = "A MISMO asset references multiple borrowers."

    for liability in liabilities:
        direct = [ref for ref in liability.get("references", []) if ref in property_ids]
        related = [target if source == liability.get("entity_id") else source
                   for source, target, _ in relation_edges
                   if (source == liability.get("entity_id") and target in property_ids)
                   or (target == liability.get("entity_id") and source in property_ids)]
        linked = list(dict.fromkeys(direct + related))
        liability["linked_property_ids"] = linked
        if liability.get("references") and not linked:
            liability["needs_review"] = "A MISMO liability reference did not resolve to a property entity."
        elif len(linked) > 1:
            liability["needs_review"] = "A MISMO liability references multiple properties."

    disagreements = [item["needs_review"] for item in liabilities if item.get("needs_review")]
    borrower_name = next((b["values"].get("full_name") for b in borrowers if b["values"].get("full_name")), None)
    return {
        "format": "MISMO 3.4", "source_file": source.name,
        "loan": loan["values"], "loan_provenance": loan["provenance"],
        "borrowers": borrowers, "properties": properties, "assets": assets, "liabilities": liabilities,
        "loan_officers": loan_officers, "origination_companies": origination_companies,
        "lenders": lenders, "account_executives": account_executives,
        "contacts": contacts,
        "relationships": relationships,
        "display_name": borrower_name,
        "needs_review": disagreements,
    }
