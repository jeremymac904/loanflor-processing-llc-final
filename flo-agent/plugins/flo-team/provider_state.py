"""Provider-routing state machine — persisted health for every candidate route.

Discovery (``providers.discover``) answers "can this provider answer one line
right now?". This module answers "can it finish a multi-agent workflow?" by
tracking outcomes over time under ``<team root>/providers/state.json``:

    provider, model, health, last_successful_completion, latency_ms (EWMA),
    context_capacity, rate_limit_state, credit_state, data_classification_allowed,
    workflow_suitability, cooldown_until, retry_after, failure_count

Health states::

    HEALTHY  DEGRADED  RATE_LIMITED  OUT_OF_CREDIT  MODEL_UNAVAILABLE  OFFLINE
    TOO_SLOW  CONTEXT_INSUFFICIENT  DATA_POLICY_BLOCKED

:func:`classify_error` maps a provider error string to a state (HTTP 429 →
RATE_LIMITED with retry-after; HTTP 402 / "insufficient credits" →
OUT_OF_CREDIT; 404 model / "Model is unavailable" / "has been retired" →
MODEL_UNAVAILABLE; connection errors → OFFLINE; timeouts → TOO_SLOW; context
errors → CONTEXT_INSUFFICIENT). :meth:`ProviderState.select` picks a route for a
role and data classification; sensitive data only ever selects a provider whose
``data_classification_allowed`` includes ``sensitive`` and otherwise fails
closed with the message Ashley sees: "AI provider unavailable — your work is saved."
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .store import JsonDocStore, JsonlLog, now_iso, utcnow

STATES = ("HEALTHY", "DEGRADED", "RATE_LIMITED", "OUT_OF_CREDIT", "MODEL_UNAVAILABLE", "OFFLINE", "TOO_SLOW", "CONTEXT_INSUFFICIENT", "DATA_POLICY_BLOCKED", "UNKNOWN")
USABLE_STATES = ("HEALTHY", "DEGRADED")
DEFAULT_COOLDOWN = {"RATE_LIMITED": timedelta(minutes=30), "OUT_OF_CREDIT": timedelta(hours=6), "MODEL_UNAVAILABLE": timedelta(hours=1),
                    "OFFLINE": timedelta(minutes=10), "TOO_SLOW": timedelta(hours=1), "CONTEXT_INSUFFICIENT": timedelta(hours=24), "DATA_POLICY_BLOCKED": timedelta(days=365)}
FAIL_CLOSED_MESSAGE = "AI provider unavailable — your work is saved."
_RETRY_AFTER = re.compile(r"retry[- _]after[^0-9]{0,12}(\d+)", re.I)
_RESET_AT = re.compile(r"reset(?:s|_at)?[^0-9]{0,12}(\d{9,10})", re.I)


def classify_error(message: str) -> Dict[str, Any]:
    """Map an error string to (state, retry_after_seconds, reason)."""
    text = str(message or "")
    low = text.lower()
    retry = None
    m = _RETRY_AFTER.search(text)
    if m:
        retry = int(m.group(1))
    if "429" in low or "usage limit" in low or "rate limit" in low or "too many requests" in low:
        return {"state": "RATE_LIMITED", "retry_after_seconds": retry, "reason": text[:200]}
    if "402" in low or "insufficient" in low and "credit" in low or "out of credit" in low or "quota" in low or "billing" in low:
        return {"state": "OUT_OF_CREDIT", "retry_after_seconds": retry, "reason": text[:200]}
    if "model is unavailable" in low or "model not found" in low or "has been retired" in low or ("404" in low and "model" in low) or "does not exist" in low:
        return {"state": "MODEL_UNAVAILABLE", "retry_after_seconds": retry, "reason": text[:200]}
    if "context" in low and ("length" in low or "window" in low or "too long" in low or "maximum" in low):
        return {"state": "CONTEXT_INSUFFICIENT", "retry_after_seconds": retry, "reason": text[:200]}
    if "timed out" in low or "timeout" in low or "too slow" in low:
        return {"state": "TOO_SLOW", "retry_after_seconds": retry, "reason": text[:200]}
    if "connection" in low or "unreachable" in low or "refused" in low or "dns" in low or "503" in low or "502" in low or "offline" in low:
        return {"state": "OFFLINE", "retry_after_seconds": retry, "reason": text[:200]}
    if "policy" in low and ("data" in low or "pii" in low or "sensitive" in low):
        return {"state": "DATA_POLICY_BLOCKED", "retry_after_seconds": None, "reason": text[:200]}
    return {"state": "DEGRADED", "retry_after_seconds": retry, "reason": text[:200]}


@dataclass
class RouteState:
    provider_id: str
    hermes_provider: str
    model: str
    kind: str = "cloud"
    health: str = "UNKNOWN"
    last_successful_completion: Optional[str] = None
    last_failure: Optional[str] = None
    latency_ms: Optional[float] = None
    context_capacity: Optional[int] = None
    rate_limit_state: Optional[str] = None
    credit_state: Optional[str] = None
    data_classification_allowed: List[str] = field(default_factory=lambda: ["synthetic", "non_sensitive"])
    workflow_suitability: str = "unknown"      # ready | marginal | unsuitable | unknown
    cooldown_until: Optional[str] = None
    retry_after: Optional[str] = None
    failure_count: int = 0
    consecutive_failures: int = 0
    success_count: int = 0
    last_error: Optional[str] = None
    transitions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProviderState:
    """Durable per-route state under ``<team root>/providers/``."""

    def __init__(self, root) -> None:
        self.root = Path(root)
        self.docs = JsonDocStore(self.root / "providers")
        self.log = JsonlLog(self.root / "activity", "activity")

    # -- bookkeeping -------------------------------------------------------

    def _id(self, provider_id: str, model: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.\-]", "_", f"{provider_id}__{model}")[:80]

    def get(self, provider_id: str, model: str) -> Optional[RouteState]:
        raw = self.docs.get(self._id(provider_id, model))
        return RouteState(**{k: v for k, v in raw.items() if k in RouteState.__dataclass_fields__}) if raw else None

    def ensure(self, provider_id: str, hermes_provider: str, model: str, *, kind: str = "cloud", sensitive_allowed: bool = False,
               context_capacity: Optional[int] = None) -> RouteState:
        row = self.get(provider_id, model)
        if row is None:
            row = RouteState(provider_id=provider_id, hermes_provider=hermes_provider, model=model, kind=kind, context_capacity=context_capacity)
            if sensitive_allowed:
                row.data_classification_allowed = ["synthetic", "non_sensitive", "sensitive"]
            self._save(row)
        return row

    def _save(self, row: RouteState) -> RouteState:
        self.docs.put(self._id(row.provider_id, row.model), row.to_dict())
        return row

    def _set(self, row: RouteState, health: str, reason: str, *, cooldown: Optional[timedelta] = None, retry_after_seconds: Optional[int] = None) -> RouteState:
        if health not in STATES:
            raise ValueError(f"unknown health state {health}")
        previous = row.health
        row.health = health
        now = utcnow()
        if health in USABLE_STATES:
            row.cooldown_until = None
            row.retry_after = None
        else:
            wait = timedelta(seconds=retry_after_seconds) if retry_after_seconds else (cooldown or DEFAULT_COOLDOWN.get(health, timedelta(minutes=15)))
            row.cooldown_until = (now + wait).isoformat()
            row.retry_after = row.cooldown_until
        row.rate_limit_state = "limited" if health == "RATE_LIMITED" else ("ok" if health in USABLE_STATES else row.rate_limit_state)
        row.credit_state = "exhausted" if health == "OUT_OF_CREDIT" else ("ok" if health in USABLE_STATES else row.credit_state)
        row.workflow_suitability = self._suitability(row)
        if previous != health:
            row.transitions.append({"at": now_iso(), "from": previous, "to": health, "reason": reason[:200]})
            row.transitions = row.transitions[-50:]
            self.log.append({"event": "provider.transition", "actor": "provider_state", "provider_id": row.provider_id, "model": row.model, "from": previous, "to": health, "reason": reason[:200]})
        return self._save(row)

    @staticmethod
    def _suitability(row: RouteState) -> str:
        if row.health not in USABLE_STATES:
            return "unsuitable"
        if row.consecutive_failures >= 2 or (row.latency_ms or 0) > 90_000:
            return "marginal"
        if row.health == "DEGRADED":
            return "marginal"
        return "ready"

    # -- outcomes ----------------------------------------------------------

    def record_success(self, provider_id: str, model: str, *, latency_ms: Optional[float] = None, hermes_provider: Optional[str] = None) -> RouteState:
        row = self.get(provider_id, model) or self.ensure(provider_id, hermes_provider or provider_id, model)
        row.last_successful_completion = now_iso()
        row.success_count += 1
        row.consecutive_failures = 0
        if latency_ms is not None:
            row.latency_ms = latency_ms if row.latency_ms is None else round(0.7 * row.latency_ms + 0.3 * latency_ms, 1)
        return self._set(row, "HEALTHY", "successful completion")

    def record_failure(self, provider_id: str, model: str, error: str, *, hermes_provider: Optional[str] = None) -> Dict[str, Any]:
        row = self.get(provider_id, model) or self.ensure(provider_id, hermes_provider or provider_id, model)
        cls = classify_error(error)
        row.failure_count += 1
        row.consecutive_failures += 1
        row.last_failure = now_iso()
        row.last_error = str(error)[:300]
        health = cls["state"]
        if health == "DEGRADED" and row.consecutive_failures >= 3:
            health = "OFFLINE"
        self._set(row, health, cls["reason"], retry_after_seconds=cls.get("retry_after_seconds"))
        return {"provider_id": provider_id, "model": model, "health": row.health, "cooldown_until": row.cooldown_until, "classification": cls}

    def record_health(self, provider_id: str, hermes_provider: str, model: str, *, kind: str, status: str, latency_ms: Optional[int],
                      sensitive_allowed: bool, context_capacity: Optional[int], error: Optional[str] = None) -> RouteState:
        """Fold a discovery row (providers.discover) into the state machine."""
        row = self.ensure(provider_id, hermes_provider, model, kind=kind, sensitive_allowed=sensitive_allowed, context_capacity=context_capacity)
        row.latency_ms = latency_ms if latency_ms is not None else row.latency_ms
        row.context_capacity = context_capacity or row.context_capacity
        if status == "healthy":
            return self._set(row, "HEALTHY", "discovery: healthy")
        if status == "slow":
            return self._set(row, "TOO_SLOW", "discovery: slow")
        if status in ("unauthenticated", "unconfigured"):
            return self._set(row, "OFFLINE", f"discovery: {status}", cooldown=timedelta(hours=24))
        cls = classify_error(error or status)
        return self._set(row, cls["state"] if cls["state"] != "DEGRADED" else "OFFLINE", f"discovery: {error or status}")

    def clear_expired_cooldowns(self) -> List[str]:
        cleared = []
        now = utcnow()
        for raw in self.docs.all():
            row = RouteState(**{k: v for k, v in raw.items() if k in RouteState.__dataclass_fields__})
            if row.cooldown_until and datetime.fromisoformat(row.cooldown_until) <= now and row.health not in USABLE_STATES:
                self._set(row, "DEGRADED", "cooldown expired; probe before trusting")
                cleared.append(row.provider_id)
        return cleared

    # -- selection ---------------------------------------------------------

    def rows(self) -> List[RouteState]:
        return [RouteState(**{k: v for k, v in raw.items() if k in RouteState.__dataclass_fields__}) for raw in self.docs.all()]

    def select(self, *, classification: str = "non_sensitive", exclude: Optional[List[str]] = None, prefer: Optional[List[str]] = None,
               min_context: Optional[int] = None) -> Dict[str, Any]:
        """Pick the best usable route for a data classification. Fails closed for sensitive data."""
        self.clear_expired_cooldowns()
        exclude = set(exclude or [])
        candidates = []
        for row in self.rows():
            if row.provider_id in exclude:
                continue
            if classification not in row.data_classification_allowed:
                continue
            if row.health not in USABLE_STATES:
                continue
            if min_context and row.context_capacity and row.context_capacity < min_context:
                continue
            rank = (0 if row.provider_id in (prefer or []) else 1, 0 if row.health == "HEALTHY" else 1, row.consecutive_failures, row.latency_ms or 0)
            candidates.append((rank, row))
        if not candidates:
            return {"status": "FAIL_CLOSED", "route": None, "message": FAIL_CLOSED_MESSAGE,
                    "reason": (f"no provider approved for {classification} data is usable" if classification == "sensitive" else "no usable provider route"),
                    "classification": classification}
        candidates.sort(key=lambda c: c[0])
        row = candidates[0][1]
        return {"status": "OK", "route": {"provider_id": row.provider_id, "hermes_provider": row.hermes_provider, "model": row.model, "health": row.health,
                                          "latency_ms": row.latency_ms, "workflow_suitability": row.workflow_suitability}, "classification": classification,
                "alternatives": [c[1].provider_id for c in candidates[1:]]}

    def table(self) -> List[Dict[str, Any]]:
        self.clear_expired_cooldowns()
        return [r.to_dict() for r in self.rows()]
