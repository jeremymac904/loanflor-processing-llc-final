"""One provider adapter for the whole team (runtime/UNSLOTH_HERMES_RUNTIME.md,
runtime/MODEL_ROUTING.yaml, runtime/PROVIDER_CONSTRAINTS.md).

* Logical model classes (``local_fast``, ``local_reasoning``,
  ``cloud_reasoning``, ``deterministic``) are declared once in ``team.yaml``;
  profiles list class *preferences*, never endpoints.
* The local provider is one Hermes ``providers.flo_local`` block (OpenAI-
  compatible: Unsloth Studio on ``127.0.0.1:8888/v1``, Ollama on
  ``localhost:11434/v1``, LM Studio, …). The ``unsloth/<model>`` prefix
  finding from the Mac build is handled here — :func:`model_id_candidates`
  tries the id as configured, with and without a vendor prefix — instead of a
  shell wrapper per profile.
* :func:`health_check` verifies: endpoint reachable, model listed, context
  ≥ 64K (from the provider block's ``context_length`` / ``models`` metadata
  or Ollama's ``/api/show``), model-id mapping valid, and a one-token smoke
  completion.
* :func:`route` picks the concrete provider/model for a profile + task.
  **Sensitive tasks never fall back from a local class to a cloud class**:
  when the local provider is unhealthy the answer is ``FAIL_CLOSED`` and the
  bot must say so instead of silently sending borrower data to the cloud.

Only ``urllib`` is used so this module works inside the plugin without extra
dependencies; timeouts are short so a dead endpoint never hangs a turn.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .manifest import RoleSpec, TeamManifest, manifest as _manifest

LOCAL_PROVIDER_KEY = "flo_local"
MIN_CONTEXT = 65536
DEFAULT_TIMEOUT = 6.0
VENDOR_PREFIXES = ("unsloth/", "ollama/", "lmstudio/", "hf/")


@dataclass
class HealthReport:
    provider: str
    base_url: str
    model: str
    reachable: bool = False
    model_listed: bool = False
    resolved_model_id: Optional[str] = None
    context_length: Optional[int] = None
    context_ok: bool = False
    smoke_ok: bool = False
    healthy: bool = False
    prompt_tps: Optional[float] = None     # prompt-processing throughput from the throughput probe
    checks: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Route:
    model_class: str
    provider: str
    model: Optional[str]
    base_url: Optional[str]
    status: str  # OK | FAIL_CLOSED | UNCONFIGURED
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------

def local_provider_config(config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """The ``providers.flo_local`` block: config → env → empty."""
    block: Dict[str, Any] = {}
    if config:
        providers = config.get("providers") if isinstance(config.get("providers"), Mapping) else {}
        raw = providers.get(LOCAL_PROVIDER_KEY) if providers else None
        if isinstance(raw, Mapping):
            block = dict(raw)
    env_url = os.environ.get("FLO_LOCAL_BASE_URL", "").strip()
    env_model = os.environ.get("FLO_LOCAL_MODEL", "").strip()
    if env_url:
        block["base_url"] = env_url
    if env_model:
        block.setdefault("models", {})
        block["model"] = env_model
    return block


def model_id_candidates(model: str) -> List[str]:
    """Ids to try when matching against ``/models``: as given, stripped of a vendor prefix, and with ``unsloth/`` added."""
    model = (model or "").strip()
    if not model:
        return []
    out = [model]
    for prefix in VENDOR_PREFIXES:
        if model.lower().startswith(prefix):
            out.append(model[len(prefix):])
    if "/" not in model:
        out.append(f"unsloth/{model}")
    # Ollama serves tags (``qwen3-flo:latest``); accept either spelling.
    for candidate in list(out):
        if ":" in candidate:
            out.append(candidate.rsplit(":", 1)[0])
        else:
            out.append(f"{candidate}:latest")
    seen, unique = set(), []
    for m in out:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


# ---------------------------------------------------------------------------
# HTTP helpers (urllib only)
# ---------------------------------------------------------------------------

def _get_json(url: str, timeout: float) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - loopback/local provider
        return json.loads(resp.read().decode("utf-8") or "{}")


def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> Any:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8") or "{}")


def _base(url: str) -> str:
    url = url.rstrip("/")
    return url if url.endswith("/v1") else url + "/v1"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def health_check(
    base_url: str,
    model: str,
    *,
    min_context: int = MIN_CONTEXT,
    declared_context: Optional[int] = None,
    timeout: float = DEFAULT_TIMEOUT,
    smoke: bool = True,
    throughput: bool = False,
    throughput_tokens: int = 1500,
    fetch_json=None,
    post_json=None,
) -> HealthReport:
    """Five checks; ``fetch_json``/``post_json`` are injectable for tests.

    ``throughput=True`` adds a sixth, informational probe: a ~``throughput_tokens``-token
    prompt with ``max_tokens=1`` timed to estimate prompt-processing tokens/s — the number
    that decides whether a 20K-token agent turn is interactive or a 20-minute wait.
    """
    fetch_json = fetch_json or _get_json
    post_json = post_json or _post_json
    report = HealthReport(provider=LOCAL_PROVIDER_KEY, base_url=base_url or "", model=model or "")
    if not base_url or not model:
        report.error = "providers.flo_local.base_url and model are not configured"
        report.checks.append("UNCONFIGURED")
        return report
    base = _base(base_url)

    # 1. reachable + 2. model listed + 4. id mapping
    try:
        listing = fetch_json(f"{base}/models", timeout)
        report.reachable = True
        report.checks.append("reachable")
    except Exception as exc:  # noqa: BLE001
        report.error = f"endpoint unreachable: {type(exc).__name__}: {exc}"
        report.checks.append("unreachable")
        return report
    ids = _model_ids(listing)
    for candidate in model_id_candidates(model):
        if candidate in ids:
            report.model_listed = True
            report.resolved_model_id = candidate
            break
    if report.model_listed:
        report.checks.append(f"model listed as {report.resolved_model_id}")
    else:
        report.checks.append(f"model not listed (server has {len(ids)} models)")
        report.error = f"model {model!r} not served; candidates tried: {model_id_candidates(model)}"
        return report

    # 3. context
    ctx = declared_context or _context_from_listing(listing, report.resolved_model_id or model)
    if ctx is None:
        ctx = _context_from_ollama(base_url, report.resolved_model_id or model, fetch_json, post_json, timeout)
    report.context_length = ctx
    if ctx is not None and ctx >= min_context:
        report.context_ok = True
        report.checks.append(f"context {ctx} >= {min_context}")
    else:
        report.checks.append(f"context {ctx} < {min_context}" if ctx is not None else "context unknown (declare providers.flo_local.context_length)")
        report.error = "context requirement not satisfied"
        return report

    # 5. smoke completion
    if smoke:
        try:
            out = post_json(f"{base}/chat/completions", {
                "model": report.resolved_model_id,
                "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
                "max_tokens": 4,
                "temperature": 0,
            }, timeout)
            text = _completion_text(out)
            report.smoke_ok = bool(text) or bool(out)
            report.checks.append("smoke completion ok" if report.smoke_ok else "smoke completion returned nothing")
        except Exception as exc:  # noqa: BLE001
            report.error = f"smoke completion failed: {type(exc).__name__}: {exc}"
            report.checks.append("smoke completion failed")
            return report
    else:
        report.smoke_ok = True
        report.checks.append("smoke completion skipped")
    report.healthy = report.reachable and report.model_listed and report.context_ok and report.smoke_ok
    if throughput and report.healthy:
        import time

        filler = ("The quick brown fox jumps over the lazy dog. " * (max(throughput_tokens, 200) // 10))
        started = time.monotonic()
        try:
            out = post_json(f"{base}/chat/completions", {
                "model": report.resolved_model_id,
                "messages": [{"role": "user", "content": filler + "\nReply with one word."}],
                "max_tokens": 1, "temperature": 0,
            }, max(timeout, 30.0))
            elapsed = max(time.monotonic() - started, 0.001)
            usage = out.get("usage") if isinstance(out, dict) else None
            prompt_tokens = int(usage.get("prompt_tokens")) if isinstance(usage, dict) and usage.get("prompt_tokens") else len(filler) // 4
            report.prompt_tps = round(prompt_tokens / elapsed, 1)
            report.checks.append(f"prompt throughput ~{report.prompt_tps} tok/s ({prompt_tokens} tokens in {elapsed:.1f}s)")
        except Exception as exc:  # noqa: BLE001 - informational
            report.checks.append(f"throughput probe failed: {type(exc).__name__}")
    return report


def _model_ids(listing: Any) -> List[str]:
    if isinstance(listing, dict):
        data = listing.get("data") or listing.get("models") or []
    else:
        data = listing or []
    ids = []
    for row in data:
        if isinstance(row, dict):
            mid = row.get("id") or row.get("name") or row.get("model")
            if mid:
                ids.append(str(mid))
        elif isinstance(row, str):
            ids.append(row)
    return ids


def _context_from_listing(listing: Any, model_id: str) -> Optional[int]:
    data = listing.get("data") if isinstance(listing, dict) else listing
    for row in data or []:
        if isinstance(row, dict) and str(row.get("id") or row.get("name")) == model_id:
            for key in ("context_length", "max_context_length", "context_window", "n_ctx", "max_model_len"):
                value = row.get(key)
                if isinstance(value, int) and value > 0:
                    return value
            meta = row.get("meta") or row.get("metadata") or {}
            if isinstance(meta, dict):
                for key in ("context_length", "n_ctx", "n_ctx_train"):
                    value = meta.get(key)
                    if isinstance(value, int) and value > 0:
                        return value
    return None


def _context_from_ollama(base_url: str, model_id: str, fetch_json, post_json, timeout: float) -> Optional[int]:
    """Ollama exposes num_ctx via POST /api/show; ignore silently for other servers."""
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    try:
        info = post_json(f"{root}/api/show", {"model": model_id}, timeout)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(info, dict):
        return None
    params = str(info.get("parameters") or "")
    for line in params.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "num_ctx" and parts[1].isdigit():
            return int(parts[1])
    model_info = info.get("model_info") or {}
    if isinstance(model_info, dict):
        for key, value in model_info.items():
            if key.endswith(".context_length") and isinstance(value, int):
                return value
    return None


def _completion_text(out: Any) -> str:
    try:
        return str(out["choices"][0]["message"]["content"]).strip()
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route(
    role: RoleSpec,
    *,
    sensitive: bool,
    local_health: Optional[HealthReport],
    cloud: Optional[Mapping[str, Any]] = None,
    team: Optional[TeamManifest] = None,
) -> Route:
    """Pick the first usable class from the role's preference list.

    ``sensitive`` = the task carries borrower data / NPI. A sensitive task may
    only use classes whose ``pii_allowed`` is true; when none of those is
    healthy the result is ``FAIL_CLOSED`` — never a silent cloud fallback.
    """
    team = team or _manifest()
    for cls in role.model_classes:
        spec = team.model_classes.get(cls) or {}
        provider = str(spec.get("provider") or "")
        pii_allowed = spec.get("pii_allowed") is True
        if sensitive and not pii_allowed:
            continue
        if provider == "code":
            return Route(cls, "code", None, None, "OK", "deterministic code path")
        if provider == LOCAL_PROVIDER_KEY:
            if local_health and local_health.healthy:
                return Route(cls, LOCAL_PROVIDER_KEY, local_health.resolved_model_id, local_health.base_url, "OK", "local provider healthy")
            continue
        if provider == "configurable":
            if cloud and cloud.get("provider") and cloud.get("model"):
                return Route(cls, str(cloud["provider"]), str(cloud["model"]), cloud.get("base_url"), "OK", "approved cloud provider")
            continue
    if sensitive:
        return Route("none", "none", None, None, "FAIL_CLOSED",
                     "no healthy PII-approved model class; refusing to fall back to an unapproved cloud provider")
    return Route("none", "none", None, None, "UNCONFIGURED", "no usable model class configured for this role")


def class_summary(team: Optional[TeamManifest] = None) -> Dict[str, Any]:
    team = team or _manifest()
    return {name: dict(spec) for name, spec in team.model_classes.items()}
