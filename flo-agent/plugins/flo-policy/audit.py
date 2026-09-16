"""Flo audit events with sensitive-value redaction.

Every policy decision, approval state change and execution result becomes an
:class:`AuditEvent`. Events carry **metadata** (tool, capability, decision,
resource shape, digests, ids) — never tool arguments, message bodies or
document content. As a second line of defence every string that does get
written passes through :func:`redact`, which masks SSNs, long account-style
digit runs, bearer/authorization headers, OAuth/API-key shaped tokens and
``password``/``refresh_token``-style key/value pairs.
"""

from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from .policy import utcnow

_SSN = re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b")
# 8+ digit runs (account / routing / card numbers); keep last 4 for support.
_LONG_DIGITS = re.compile(r"\b(\d[\d -]{6,}\d)\b")
_AUTH_HEADER = re.compile(r"(?i)\b(authorization|proxy-authorization)\s*[:=]\s*\S+(?:\s+\S+)?")
_BEARER = re.compile(r"(?i)\bbearer\s+[a-z0-9\-._~+/]+=*")
_TOKEN_SHAPES = re.compile(
    r"\b(?:sk-[A-Za-z0-9_\-]{8,}|ya29\.[A-Za-z0-9_\-\.]+|AIza[0-9A-Za-z_\-]{20,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9\-]{10,}|eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)"
)
_SECRET_KV = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|refresh_token|access_token|api[_-]?key|client_secret|token)\b"
    r"(\s*[:=]\s*|\"\s*:\s*\")([^\s,;\"']+)"
)
_SECRET_KEYS = {
    "password", "passwd", "pwd", "secret", "refresh_token", "access_token",
    "api_key", "apikey", "client_secret", "token", "authorization", "cookie",
}


def _mask_digits(match: "re.Match[str]") -> str:
    digits = re.sub(r"\D", "", match.group(1))
    if len(digits) < 8:
        return match.group(0)
    return "[redacted-number-…" + digits[-4:] + "]"


def redact(value: Any) -> Any:
    """Recursively mask sensitive shapes in strings, dicts, lists, tuples."""
    if isinstance(value, str):
        text = _SSN.sub("[redacted-ssn]", value)
        text = _AUTH_HEADER.sub(r"\1: [redacted]", text)
        text = _BEARER.sub("Bearer [redacted]", text)
        text = _TOKEN_SHAPES.sub("[redacted-token]", text)
        text = _SECRET_KV.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted]", text)
        text = _LONG_DIGITS.sub(_mask_digits, text)
        return text
    if isinstance(value, dict):
        out: Dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.strip().lower() in _SECRET_KEYS:
                out[key] = "[redacted]"
            else:
                out[key] = redact(item)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


@dataclass
class AuditEvent:
    """One auditable fact. Field names follow ``.flo/docs/10_DATA_MODEL_AND_AUDIT.md``."""

    event_type: str                      # policy_decision | approval | execution | tool_result
    actor: str                           # "model" | "user:<id>" | "policy"
    tool_name: str
    capability: str
    operation: str = "call"
    policy_decision: Optional[str] = None
    approval_state: Optional[str] = None  # none | requested | granted | denied | consumed | expired
    result_status: Optional[str] = None   # executed | blocked | denied | failed | pending_confirmation
    proposal_id: Optional[str] = None
    approval_id: Optional[str] = None
    loan_ref: Optional[str] = None
    profile: Optional[str] = None
    session_id: Optional[str] = None
    resource_meta: Dict[str, Any] = field(default_factory=dict)
    model_meta: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    timestamp: datetime = field(default_factory=utcnow)
    schema_version: int = 1

    def to_record(self) -> Dict[str, Any]:
        raw = asdict(self)
        raw["timestamp"] = self.timestamp.isoformat()
        return redact(raw)


class AuditLog:
    """Append-only JSONL log, one file per UTC day, redacted on write."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self._lock = threading.Lock()

    def path_for(self, when: Optional[datetime] = None) -> Path:
        when = when or utcnow()
        return self.directory / f"audit-{when.strftime('%Y-%m-%d')}.jsonl"

    def write(self, event: AuditEvent) -> Dict[str, Any]:
        record = event.to_record()
        line = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.path_for(event.timestamp)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        return record

    def read(self, when: Optional[datetime] = None) -> Iterator[Dict[str, Any]]:
        path = self.path_for(when)
        if not path.exists():
            return iter(())
        with open(path, "r", encoding="utf-8") as handle:
            lines = [json.loads(line) for line in handle if line.strip()]
        return iter(lines)


class NullAuditLog(AuditLog):
    """Keeps the interface when no directory is configured (tests)."""

    def __init__(self) -> None:  # noqa: D401 - trivial
        super().__init__(Path("."))
        self.records: list[Dict[str, Any]] = []

    def write(self, event: AuditEvent) -> Dict[str, Any]:
        record = event.to_record()
        self.records.append(record)
        return record
