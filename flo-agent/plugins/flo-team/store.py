"""Tiny durable JSON stores for shared team state (no database, no daemon).

Every store is a directory of ``<id>.json`` documents plus append-only JSONL
logs, guarded by a process lock and written atomically (tmp + replace) so a
crash never leaves a half-written workspace or approval. Documents hold
references and metadata, never borrower document bodies or credentials.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-.]{0,79}$")
_lock = threading.RLock()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utcnow().isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def safe_id(value: str) -> str:
    value = str(value or "").strip()
    if not _ID_RE.match(value):
        raise ValueError(f"invalid id {value!r} (letters, digits, '_', '-', '.' only; max 80 chars)")
    return value


def _atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


class JsonDocStore:
    """Directory of ``<id>.json`` documents."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def path(self, doc_id: str) -> Path:
        return self.directory / f"{safe_id(doc_id)}.json"

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        path = self.path(doc_id)
        if not path.exists():
            return None
        with _lock:
            return json.loads(path.read_text(encoding="utf-8"))

    def put(self, doc_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with _lock:
            payload = dict(payload)
            payload["updated_at"] = now_iso()
            _atomic_write(self.path(doc_id), payload)
            return payload

    def update(self, doc_id: str, mutate) -> Dict[str, Any]:
        with _lock:
            current = self.get(doc_id)
            if current is None:
                raise KeyError(doc_id)
            mutate(current)
            return self.put(doc_id, current)

    def ids(self) -> List[str]:
        if not self.directory.exists():
            return []
        return sorted(p.stem for p in self.directory.glob("*.json"))

    def all(self) -> Iterator[Dict[str, Any]]:
        for doc_id in self.ids():
            doc = self.get(doc_id)
            if doc is not None:
                yield doc


class JsonlLog:
    """Append-only event log, one file per UTC day."""

    def __init__(self, directory: Path, stem: str) -> None:
        self.directory = Path(directory)
        self.stem = stem

    def path_for(self, when: Optional[datetime] = None) -> Path:
        when = when or utcnow()
        return self.directory / f"{self.stem}-{when.strftime('%Y-%m-%d')}.jsonl"

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(record)
        record.setdefault("timestamp", now_iso())
        with _lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            with open(self.path_for(), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        return record

    def tail(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.directory.exists():
            return []
        files = sorted(self.directory.glob(f"{self.stem}-*.jsonl"))
        rows: List[Dict[str, Any]] = []
        for path in reversed(files):
            lines = path.read_text(encoding="utf-8").splitlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
                if len(rows) >= limit:
                    return rows
        return rows
