"""Provider discovery and routing — one registry, no machine-specific profiles.

``providers.yaml`` (next to this file) lists *candidate* endpoints by logical
kind: local OpenAI-compatible servers (Ollama, Unsloth Studio, LM Studio) and
cloud providers known to Hermes' auth store. :func:`discover` probes each
candidate and returns a health record:

    endpoint, reachable, available_model, context_capability, latency_ms,
    sensitive_data_permission, status (healthy | slow | unhealthy | unauthenticated | unconfigured)

:func:`choose` picks a provider for a role from its model-class preferences
and the sensitivity of the task; a sensitive task never lands on a provider
whose ``pii_allowed`` is false (FAIL_CLOSED instead). Local providers that are
healthy but slower than ``max_latency_ms`` are marked ``slow`` and used only
when nothing faster is allowed.

Profile configs stay generic: the installer writes the *chosen* provider at
install time, and ``flo_model_health action=discover`` shows the live table.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import models as models_mod
from .manifest import RoleSpec, TeamManifest, manifest as _manifest

HERE = Path(__file__).resolve().parent
REGISTRY_PATH = HERE / "providers.yaml"


@dataclass
class ProviderHealth:
    provider_id: str
    kind: str                       # local | cloud
    hermes_provider: str            # value for model.provider
    endpoint: Optional[str]
    model: Optional[str]
    reachable: bool = False
    available_model: Optional[str] = None
    context_capability: Optional[int] = None
    latency_ms: Optional[int] = None
    prompt_tps: Optional[float] = None
    sensitive_data_permission: bool = False
    status: str = "unconfigured"
    classes: List[str] = field(default_factory=list)
    checks: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    import yaml

    return yaml.safe_load((path or REGISTRY_PATH).read_text(encoding="utf-8")) or {}


def _auth_logged_in(provider: str) -> bool:
    try:
        from hermes_cli.auth import get_auth_status  # type: ignore

        return bool(get_auth_status(provider).get("logged_in"))
    except Exception:
        return False


def discover(
    *,
    registry: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    health_check: Optional[Callable[..., models_mod.HealthReport]] = None,
    auth_check: Optional[Callable[[str], bool]] = None,
    cloud_smoke: Optional[Callable[[str, str], Dict[str, Any]]] = None,
    max_latency_ms: Optional[int] = None,
    smoke: bool = True,
) -> List[ProviderHealth]:
    """Probe every candidate.

    ``cloud_smoke(hermes_provider, model)`` may return ``{"ok": bool, "latency_ms": int, "error": str}``
    from a real one-line completion (the installer runs it through the Hermes CLI); without it a
    cloud provider counts as healthy when credentials exist.
    """
    registry = registry or load_registry()
    health_check = health_check or models_mod.health_check
    auth_check = auth_check or _auth_logged_in
    max_latency = int(max_latency_ms or registry.get("max_latency_ms", 15000))
    rows: List[ProviderHealth] = []
    providers_cfg = (config or {}).get("providers") if isinstance((config or {}).get("providers"), dict) else {}
    for cand in registry.get("candidates", []):
        row = ProviderHealth(provider_id=cand["id"], kind=cand["kind"], hermes_provider=cand.get("hermes_provider", "custom"),
                             endpoint=cand.get("base_url"), model=cand.get("model"), sensitive_data_permission=bool(cand.get("pii_allowed")),
                             classes=list(cand.get("classes") or []))
        # Config overrides for the local adapter block.
        if cand["kind"] == "local":
            block = providers_cfg.get(cand.get("config_key") or "", {}) if providers_cfg else {}
            if isinstance(block, dict):
                row.endpoint = block.get("base_url") or row.endpoint
                row.model = block.get("model") or block.get("default_model") or row.model
            if not row.endpoint or not row.model:
                row.status = "unconfigured"
                rows.append(row)
                continue
            started = time.monotonic()
            rep = health_check(row.endpoint, row.model, declared_context=cand.get("context_length"), smoke=smoke, throughput=smoke, timeout=float(cand.get("timeout", 8)))
            row.latency_ms = int((time.monotonic() - started) * 1000)
            row.reachable, row.available_model, row.context_capability, row.checks, row.error = rep.reachable, rep.resolved_model_id, rep.context_length, rep.checks, rep.error
            row.prompt_tps = getattr(rep, "prompt_tps", None)
            min_tps = float(registry.get("min_prompt_tps", 0) or 0)
            if rep.healthy:
                too_slow = row.latency_ms > max_latency or (min_tps and row.prompt_tps is not None and row.prompt_tps < min_tps)
                row.status = "slow" if too_slow else "healthy"
                if too_slow and row.prompt_tps is not None:
                    row.checks.append(f"below min_prompt_tps {min_tps}: a ~20K-token agent turn would take ~{int(20000 / max(row.prompt_tps, 0.1))}s")
            elif rep.reachable and rep.model_listed and rep.context_ok and "timed out" in (rep.error or ""):
                row.status = "slow"   # everything but the completion budget: usable, but not for interactive turns
            else:
                row.status = "unhealthy"
        else:
            if not auth_check(row.hermes_provider):
                row.status = "unauthenticated"
                row.checks.append("no credentials in auth store")
            else:
                row.reachable = True
                row.available_model = row.model
                row.context_capability = cand.get("context_length")
                if cloud_smoke is not None:
                    probe = cloud_smoke(row.hermes_provider, row.model or "")
                    row.latency_ms = probe.get("latency_ms")
                    if probe.get("ok"):
                        row.status = "slow" if (row.latency_ms or 0) > max_latency * 4 else "healthy"
                        row.checks.append("credentials present; smoke completion ok")
                    else:
                        row.status = "unhealthy"
                        row.error = probe.get("error")
                        row.checks.append("credentials present; smoke completion failed")
                else:
                    row.status = "healthy"
                    row.checks.append("credentials present (no completion probe run)")
                    row.latency_ms = cand.get("observed_latency_ms")
        rows.append(row)
    return rows


@dataclass(frozen=True)
class Choice:
    status: str                  # OK | FAIL_CLOSED | UNCONFIGURED
    provider_id: Optional[str]
    hermes_provider: Optional[str]
    model: Optional[str]
    base_url: Optional[str]
    model_class: Optional[str]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def choose(role: RoleSpec, rows: List[ProviderHealth], *, sensitive: bool, team: Optional[TeamManifest] = None,
           allow_slow: bool = False, allow_any_cloud: bool = False) -> Choice:
    """Pick the LLM provider for ``role``.

    Walks the role's model classes in order (the ``deterministic`` class is code, not an LLM,
    and is skipped here). ``sensitive`` tasks only accept providers with sensitive-data
    permission and otherwise FAIL_CLOSED. ``allow_any_cloud`` (non-sensitive only) lets a role
    with no cloud class still use a healthy cloud provider — the owner's "best working
    provider" directive — and is reported as such.
    """
    team = team or _manifest()
    by_class: Dict[str, List[ProviderHealth]] = {}
    for row in rows:
        for cls in row.classes:
            by_class.setdefault(cls, []).append(row)

    def _ok(row: ProviderHealth) -> bool:
        if sensitive and not row.sensitive_data_permission:
            return False
        return row.status == "healthy" or (allow_slow and row.status == "slow")

    for cls in role.model_classes:
        spec = team.model_classes.get(cls) or {}
        if spec.get("provider") == "code":
            continue
        for row in by_class.get(cls, []):
            if _ok(row):
                return Choice("OK", row.provider_id, row.hermes_provider, row.available_model or row.model, row.endpoint, cls,
                              f"{row.status} ({row.latency_ms} ms)" if row.latency_ms is not None else row.status)
    if sensitive:
        return Choice("FAIL_CLOSED", None, None, None, None, None, "no healthy provider with sensitive-data permission for this role's classes; refusing cloud fallback")
    if allow_any_cloud:
        for row in rows:
            if row.kind == "cloud" and _ok(row):
                return Choice("OK", row.provider_id, row.hermes_provider, row.available_model or row.model, row.endpoint, "cloud_reasoning",
                              f"role lists no cloud class; owner directive fallback ({row.status}, {row.latency_ms} ms)")
    return Choice("UNCONFIGURED", None, None, None, None, None, "no healthy provider for this role's classes")
