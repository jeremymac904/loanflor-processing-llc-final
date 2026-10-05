"""Structured, workspace-scoped Customer File contacts and resolution."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .store import now_iso

ROLES = {
    "borrower", "co_borrower", "loan_officer", "lender", "lender_ae",
    "buyers_agent", "listing_agent", "title_closing_agent", "insurance_agent",
    "employer_voe", "appraiser_amc", "other",
}
COMMUNICATION_METHODS = {"phone", "text", "email", "other", "not_set"}
CONTACT_FIELDS = (
    "role", "custom_role", "name", "company", "phone", "mobile", "email",
    "nmls_license_id", "notes", "preferred_communication_method", "source",
)
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _clean(value: Any, limit: int) -> str | None:
    text = " ".join(str(value or "").split())[:limit]
    return text or None


def _source_contact(role: str, values: dict[str, Any], *, source_file: str, source_path: str,
                    source_id: str | None = None, source_kind: str = "MISMO 3.4") -> dict[str, Any]:
    name = _clean(values.get("full_name") or values.get("name"), 160)
    company = _clean(values.get("company") or values.get("employer"), 160)
    seed = "|".join((role, source_id or "", name or "", company or "", source_path))
    contact_id = "mismo-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]
    return {
        "contact_id": contact_id,
        "role": role,
        "name": name,
        "company": company,
        "phone": _clean(values.get("phone"), 64),
        "mobile": _clean(values.get("mobile"), 64),
        "email": _clean(values.get("email"), 254),
        "nmls_license_id": _clean(values.get("nmls_id") or values.get("nmls") or values.get("license_id"), 64),
        "notes": None,
        "preferred_communication_method": "not_set",
        "source": {"kind": source_kind, "source_file": source_file, "path": source_path},
    }


def _source_path(item: dict[str, Any], fallback: str) -> str:
    provenance = item.get("provenance")
    if isinstance(provenance, str):
        return provenance
    if isinstance(provenance, dict):
        return str(next(iter(provenance.values()), fallback))
    return str(item.get("role") or fallback)


def from_mismo(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """Build only contacts supported by parsed MISMO facts; never invent details."""
    rows: list[dict[str, Any]] = []
    source_file = str(parsed.get("source_file") or "")

    for index, item in enumerate(parsed.get("borrowers") or []):
        values = dict(item.get("values") or {})
        if not values.get("full_name"):
            continue
        role = "co_borrower" if item.get("role") == "co_borrower" else ("borrower" if index == 0 else "co_borrower")
        rows.append(_source_contact(role, values, source_file=source_file,
                                    source_path=_source_path(item, "PARTY/ROLE"),
                                    source_id=str(item.get("borrower_id") or "") or None))

    for key, role in (("loan_officers", "loan_officer"), ("lenders", "lender"),
                      ("account_executives", "lender_ae")):
        for item in parsed.get(key) or []:
            values = dict(item.get("values") or {})
            if values.get("full_name") or values.get("company"):
                rows.append(_source_contact(role, values, source_file=source_file,
                                            source_path=_source_path(item, key),
                                            source_id=str(item.get("party_id") or "") or None))

    if not parsed.get("lenders"):
        for item in parsed.get("origination_companies") or []:
            values = dict(item.get("values") or {})
            if values.get("full_name") or values.get("company"):
                rows.append(_source_contact("lender", values, source_file=source_file,
                                            source_path=_source_path(item, "origination_companies"),
                                            source_id=str(item.get("party_id") or "") or None))

    for item in parsed.get("contacts") or []:
        role = str(item.get("role") or "other")
        if role not in ROLES:
            role = "other"
        values = dict(item.get("values") or {})
        if values.get("full_name") or values.get("company"):
            rows.append(_source_contact(role, values, source_file=source_file,
                                        source_path=_source_path(item, "PARTY/ROLE"),
                                        source_id=str(item.get("party_id") or "") or None))

    # A party may also have been collected by a specialized parser branch.
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique[row["contact_id"]] = row
    return list(unique.values())


def from_submission(submission: dict[str, Any]) -> list[dict[str, Any]]:
    """Build only borrower/LO contacts explicitly present in a saved intake."""
    rows: list[dict[str, Any]] = []
    submission_id = str(submission.get("submission_id") or "")
    source_file = f"submission:{submission_id}" if submission_id else "loan submission"
    loan_officer = submission.get("loan_officer") or {}
    if isinstance(loan_officer, dict) and any(loan_officer.get(key) for key in ("name", "company", "email", "phone", "nmls")):
        rows.append(_source_contact(
            "loan_officer", loan_officer, source_file=source_file,
            source_path="submission.loan_officer", source_id=f"{submission_id}:loan_officer",
            source_kind="Loan Submission",
        ))
    for index, borrower in enumerate(submission.get("borrowers") or []):
        if not isinstance(borrower, dict) or not any(borrower.get(key) for key in ("name", "email", "phone")):
            continue
        role = "co_borrower" if str(borrower.get("role") or "").casefold() in {"co_borrower", "co-borrower", "coborrower"} else "borrower"
        rows.append(_source_contact(
            role, borrower, source_file=source_file, source_path=f"submission.borrowers[{index}]",
            source_id=str(borrower.get("borrower_id") or f"{submission_id}:borrower:{index}"),
            source_kind="Loan Submission",
        ))
    return rows


def merge_imported(existing: list[dict[str, Any]], imported: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Refresh source-backed empty fields while preserving Ashley's edits."""
    result = [dict(row) for row in existing if isinstance(row, dict)]
    by_id = {str(row.get("contact_id")): i for i, row in enumerate(result) if row.get("contact_id")}
    for incoming in imported:
        index = by_id.get(str(incoming["contact_id"]))
        if index is None:
            incoming_name = str(incoming.get("name") or "").strip().casefold()
            incoming_email = str(incoming.get("email") or "").strip().casefold()
            incoming_phone = str(incoming.get("mobile") or incoming.get("phone") or "").strip()
            index = next((
                i for i, current in enumerate(result)
                if current.get("role") == incoming.get("role") and (
                    (incoming_name and incoming_name == str(current.get("name") or "").strip().casefold())
                    or (incoming_email and incoming_email == str(current.get("email") or "").strip().casefold())
                    or (incoming_phone and incoming_phone in {
                        str(current.get("mobile") or "").strip(), str(current.get("phone") or "").strip()
                    })
                )
            ), None)
        if index is None:
            result.append(incoming)
            by_id[str(incoming["contact_id"])] = len(result) - 1
            continue
        current = result[index]
        for key in CONTACT_FIELDS:
            value = incoming.get(key)
            # Imported records contain explicit None values for missing MISMO
            # fields. Do not write those nulls into old records: doing so made
            # each read add new empty keys and look like another migration.
            if key == "source":
                if value is not None:
                    current[key] = value
            elif value is not None and not current.get(key):
                current[key] = value
    return result


def normalize_contacts(raw: Any, existing: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or len(raw) > 100:
        raise ValueError("Provide up to 100 Customer File contacts.")
    previous = {str(row.get("contact_id")): row for row in (existing or []) if row.get("contact_id")}
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Each contact must be a contact record.")
        role = str(item.get("role") or "other").strip().lower()
        if role not in ROLES:
            raise ValueError("Choose a supported contact role.")
        contact_id = _clean(item.get("contact_id"), 100) or "contact-" + hashlib.sha256(
            f"{role}|{item.get('name','')}|{item.get('email','')}|{item.get('phone','')}".encode("utf-8")
        ).hexdigest()[:20]
        if contact_id in seen:
            raise ValueError("Contact IDs must be unique in this Customer File.")
        seen.add(contact_id)
        email = _clean(item.get("email"), 254)
        if email and not _EMAIL.fullmatch(email):
            raise ValueError("Enter a valid email address or leave it blank.")
        method = str(item.get("preferred_communication_method") or "not_set").strip().lower()
        if method not in COMMUNICATION_METHODS:
            raise ValueError("Choose a supported preferred communication method.")
        old = previous.get(contact_id, {})
        row = {
            "contact_id": contact_id,
            "role": role,
            "custom_role": _clean(item.get("custom_role"), 80) if role == "other" else None,
            "name": _clean(item.get("name"), 160),
            "company": _clean(item.get("company"), 160),
            "phone": _clean(item.get("phone"), 64),
            "mobile": _clean(item.get("mobile"), 64),
            "email": email,
            "nmls_license_id": _clean(item.get("nmls_license_id"), 64),
            "notes": _clean(item.get("notes"), 1000),
            "preferred_communication_method": method,
            "source": old.get("source"),
            "updated_at": now_iso(),
        }
        normalized.append(row)
    return normalized


def load_workspace_contacts(store: Any, workspace_id: str) -> tuple[list[dict[str, Any]], bool]:
    """Read the canonical roster and one-time/additively migrate MISMO contacts."""
    workspace = store.get(workspace_id)
    existing = workspace.get("contacts") or []
    imported = from_mismo(workspace.get("mismo") or {})
    imported.extend(from_submission(workspace.get("submission") or {}))
    merged = merge_imported(existing, imported)
    changed = merged != existing
    if changed:
        store.docs.update(workspace_id, lambda doc: doc.__setitem__("contacts", merged))
    return merged, changed


def save_workspace_contacts(store: Any, workspace_id: str, raw: Any, *, actor: str = "flo") -> list[dict[str, Any]]:
    workspace = store.get(workspace_id)
    rows = normalize_contacts(raw, workspace.get("contacts") or [])
    store.docs.update(workspace_id, lambda doc: doc.__setitem__("contacts", rows))
    store._activity(workspace_id, actor, "customer_file.contacts_updated", {"contact_count": len(rows)})
    return rows


def resolve(contacts: list[dict[str, Any]], role: str, contact_id: str | None = None) -> dict[str, Any]:
    key = re.sub(r"[^a-z0-9]+", "_", str(role or "").strip().lower()).strip("_")
    aliases = {
        "lo": "loan_officer", "loan_officer": "loan_officer", "ae": "lender_ae",
        "account_executive": "lender_ae", "loan_officer_contact": "loan_officer",
        "title": "title_closing_agent", "closing": "title_closing_agent",
        "title_agent": "title_closing_agent", "insurance": "insurance_agent", "hoi": "insurance_agent",
        "wvoe": "employer_voe", "employer": "employer_voe", "appraiser": "appraiser_amc",
        "realtor": "buyers_agent", "buyer_agent": "buyers_agent", "buyers_agent": "buyers_agent",
        "listing": "listing_agent", "listing_agent": "listing_agent",
        "borrower": "borrower", "co_borrower": "co_borrower", "lender": "lender",
    }
    key = aliases.get(key, key)
    candidates = [row for row in contacts if row.get("role") == key]
    if contact_id:
        match = next((row for row in candidates if row.get("contact_id") == contact_id), None)
        return {"status": "resolved", "contact": match} if match else {"status": "not_found", "role": key}
    if not candidates:
        return {"status": "not_set", "role": key}
    if len(candidates) > 1:
        return {"status": "ambiguous", "role": key, "candidates": candidates}
    return {"status": "resolved", "contact": candidates[0]}
