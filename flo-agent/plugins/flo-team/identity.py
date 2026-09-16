"""Approver identity for source activation (audit identity abstraction).

Approval and activation of a source revision are the human boundary of the
knowledge lifecycle. Every approval record must carry a *stable* identity so
the audit trail survives renames and does not depend on an email address:

    approved_by_user_id      stable id (auth subject when available)
    approved_by_display_name human-readable name
    approved_at              ISO-8601 UTC
    approval_reason          why (instruction, ticket, review note)
    source_revision_id       the exact revision approved
    environment              where the approval happened (local_dev | desktop | server)
    identity_source          how the identity was established

The desktop/auth layer does not yet expose user ids to plugins, so the local
development abstraction derives a stable id from the OS account
(``local-dev:<user>``) and lets the operator override it with
``FLO_APPROVER_ID`` / ``FLO_APPROVER_NAME``. When authentication provides
ids, :func:`current_identity` is the single place to swap the source in.
"""

from __future__ import annotations

import getpass
import os
import platform
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .store import now_iso

IDENTITY_SOURCES = ("explicit", "environment", "local_dev", "legacy")


@dataclass(frozen=True)
class Identity:
    user_id: str
    display_name: str
    source: str  # one of IDENTITY_SOURCES

    def to_dict(self) -> Dict[str, Any]:
        return {"user_id": self.user_id, "display_name": self.display_name, "source": self.source}


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._@-]+", "-", value.strip()).strip("-").lower() or "unknown"


def local_dev_identity() -> Identity:
    """Stable id for this machine account; the fallback until auth provides ids."""
    try:
        user = getpass.getuser()
    except Exception:  # pragma: no cover - exotic environments
        user = os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"
    host = platform.node() or "localhost"
    return Identity(user_id=f"local-dev:{_slug(user)}@{_slug(host)}", display_name=user, source="local_dev")


def current_identity(*, explicit_id: Optional[str] = None, explicit_name: Optional[str] = None) -> Identity:
    """Resolve the approver identity: explicit args > FLO_APPROVER_* env > local dev identity."""
    if explicit_id or explicit_name:
        ident = explicit_id or f"explicit:{_slug(explicit_name or '')}"
        return Identity(user_id=ident, display_name=explicit_name or explicit_id or ident, source="explicit")
    env_id = os.environ.get("FLO_APPROVER_ID")
    env_name = os.environ.get("FLO_APPROVER_NAME")
    if env_id or env_name:
        return Identity(user_id=env_id or f"env:{_slug(env_name or '')}", display_name=env_name or env_id or "", source="environment")
    return local_dev_identity()


def environment_name() -> str:
    if os.environ.get("FLO_ENVIRONMENT"):
        return os.environ["FLO_ENVIRONMENT"]
    if os.environ.get("HERMES_DESKTOP") or os.environ.get("HERMES_GATEWAY"):
        return "desktop"
    return "local_dev"


def approval_record(identity: Identity, *, reason: str, source_revision_id: str, regression_receipt: Optional[str],
                    checksum: Optional[str], action: str = "approval", environment: Optional[str] = None) -> Dict[str, Any]:
    """The structured approval record stored on a revision (schema_version 2)."""
    return {
        "schema_version": 2,
        "action": action,
        "approved_by_user_id": identity.user_id,
        "approved_by_display_name": identity.display_name,
        "identity_source": identity.source,
        "approved_at": now_iso(),
        "approval_reason": reason,
        "source_revision_id": source_revision_id,
        "regression_receipt": regression_receipt,
        "checksum": checksum,
        "environment": environment or environment_name(),
    }


def migrate_legacy_approval(legacy: Dict[str, Any], *, source_revision_id: str) -> Dict[str, Any]:
    """Upgrade a v1 approval dict (``approver``/``basis``/``at``) without inventing identity data."""
    if legacy.get("schema_version") == 2:
        return legacy
    approver = str(legacy.get("approver") or "unknown")
    return {
        "schema_version": 2,
        "action": "approval",
        "approved_by_user_id": f"legacy:{_slug(approver)}",
        "approved_by_display_name": approver,
        "identity_source": "legacy",
        "approved_at": legacy.get("at"),
        "approval_reason": legacy.get("basis", ""),
        "source_revision_id": source_revision_id,
        "regression_receipt": legacy.get("regression_receipt"),
        "checksum": legacy.get("checksum"),
        "environment": "local_dev",
        "migrated_from": {k: legacy.get(k) for k in ("approver", "basis", "at")},
    }


def validate_approval(record: Dict[str, Any]) -> Dict[str, Any]:
    required = ("approved_by_user_id", "approved_by_display_name", "approved_at", "approval_reason", "source_revision_id", "environment")
    missing = [k for k in required if not record.get(k)]
    return {"ok": not missing, "missing": missing}
