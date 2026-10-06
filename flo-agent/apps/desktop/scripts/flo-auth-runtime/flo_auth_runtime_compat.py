"""Flo desktop compatibility bridge for account-level Hermes credentials.

The managed Hermes runtime is updated independently of Flo's Electron bundle.
This entry-point shim restores the account-level credential sources used by Flo
without copying credentials into a profile or consuming the Codex CLI refresh
token. It is deliberately narrow and fails closed when upstream APIs change.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict

logger = logging.getLogger("flo.shared_auth_compat")
_PATCH_MARKER = "_flo_shared_account_auth_compat"
_nous_cache_lock = threading.Lock()
_nous_cache: Dict[str, Any] | None = None


def install_shared_account_auth_compat(
    auth_nous: Any | None = None,
    auth_codex: Any | None = None,
) -> bool:
    """Install read-only shared-account discovery around supported Hermes APIs."""
    if auth_nous is None or auth_codex is None:
        try:
            from hermes_cli import auth_codex as auth_codex_module
            from hermes_cli import auth_nous as auth_nous_module
            auth_nous = auth_nous or auth_nous_module
            auth_codex = auth_codex or auth_codex_module
        except Exception:
            logger.warning("Shared provider auth compatibility unavailable: Hermes auth modules did not load")
            return False

    installed = False
    installed |= _patch_nous(auth_nous)
    installed |= _patch_codex(auth_codex)
    if not installed:
        logger.warning("Shared provider auth compatibility unavailable: Hermes API shape is unsupported")
    return installed


def _patch_nous(module: Any) -> bool:
    resolver = getattr(module, "resolve_nous_runtime_credentials", None)
    shared_resolver = getattr(module, "_resolve_shared_nous_runtime_credentials", None)
    auth_error = getattr(module, "AuthError", None)
    if not callable(resolver) or auth_error is None:
        return False
    if not callable(shared_resolver):
        shared_resolver = _resolve_shared_nous_runtime_credentials
    if getattr(resolver, _PATCH_MARKER, False):
        return True

    def resolve_shared_nous(*, timeout_seconds: float = 15.0, **kwargs: Any) -> Dict[str, Any]:
        try:
            return resolver(timeout_seconds=timeout_seconds, **kwargs)
        except auth_error as exc:
            # Only fall through when the active profile has no Nous auth. Invalid
            # or expired profile credentials must not be silently replaced.
            if getattr(exc, "code", None) != "nous_auth_missing":
                raise
            shared = shared_resolver(
                timeout_seconds=timeout_seconds,
                force_refresh=bool(kwargs.get("force_refresh", False)),
                auth_nous=module,
            )
            if shared:
                return shared
            raise

    setattr(resolve_shared_nous, _PATCH_MARKER, True)
    module.resolve_nous_runtime_credentials = resolve_shared_nous

    status_resolver = getattr(module, "_compute_nous_auth_status", None)
    if callable(status_resolver) and not getattr(status_resolver, _PATCH_MARKER, False):
        def shared_nous_status() -> Dict[str, Any]:
            status = status_resolver()
            if status.get("logged_in"):
                return status
            try:
                creds = shared_resolver(
                    timeout_seconds=5.0, force_refresh=False, auth_nous=module,
                )
            except Exception:
                return status
            if not creds:
                return status
            # Never expose bearer material through the account-status response.
            return {
                "logged_in": True,
                "portal_base_url": None,
                "inference_base_url": creds.get("base_url"),
                "access_expires_at": None,
                "agent_key_expires_at": creds.get("expires_at"),
                "has_refresh_token": False,
                "inference_credential_present": True,
                "credential_source": "shared_account_store",
                "source": "runtime:shared_account_store",
            }

        setattr(shared_nous_status, _PATCH_MARKER, True)
        module._compute_nous_auth_status = shared_nous_status
    return True


def _resolve_shared_nous_runtime_credentials(
    *, timeout_seconds: float, force_refresh: bool, auth_nous: Any,
) -> Dict[str, Any] | None:
    """Resolve a short-lived inference key from Hermes' shared Nous account store."""
    global _nous_cache
    try:
        store_path = auth_nous._nous_shared_store_path()
        store_path_text = str(store_path)
        mtime = store_path.stat().st_mtime
    except Exception:
        return None

    now = time.time()
    with _nous_cache_lock:
        cached = _nous_cache
        if cached and not force_refresh and cached.get("path") == store_path_text and cached.get("mtime") == mtime:
            expires_epoch = cached.get("expires_epoch")
            if isinstance(expires_epoch, (int, float)) and expires_epoch > now + 30:
                result = dict(cached["credentials"])
                result["expires_in"] = max(0, int(expires_epoch - now))
                return result

        # Hermes' shared-store importer serializes refresh-token rotation and writes
        # only to hermes/shared/nous_auth.json; it does not create profile auth.
        state = auth_nous._try_import_shared_nous_state(timeout_seconds=timeout_seconds)
        if not isinstance(state, dict):
            _nous_cache = None
            return None
        api_key = state.get("agent_key")
        if not isinstance(api_key, str) or not api_key:
            _nous_cache = None
            return None
        expires_at = state.get("agent_key_expires_at")
        auth_module = __import__("hermes_cli.auth", fromlist=["_parse_iso_timestamp"])
        expires_epoch = auth_module._parse_iso_timestamp(expires_at)
        if not isinstance(expires_epoch, (int, float)) or expires_epoch <= now:
            _nous_cache = None
            return None
        inference_url = (
            auth_nous._nous_inference_env_override()
            or auth_nous._validate_nous_inference_url_from_network(state.get("inference_base_url"))
            or auth_nous.DEFAULT_NOUS_INFERENCE_URL
        )
        credentials = {
            "provider": "nous",
            "base_url": inference_url,
            "api_key": api_key,
            "key_id": state.get("agent_key_id"),
            "expires_at": expires_at,
            "expires_in": max(0, int(expires_epoch - now)),
            "source": auth_nous.NOUS_AUTH_PATH_INVOKE_JWT,
            "auth_path": auth_nous.NOUS_AUTH_PATH_INVOKE_JWT,
            "state_path": store_path_text,
        }
        try:
            cached_mtime = store_path.stat().st_mtime
        except OSError:
            cached_mtime = None
        _nous_cache = {
            "path": store_path_text,
            "mtime": cached_mtime,
            "expires_epoch": expires_epoch,
            "credentials": credentials,
        }
        return dict(credentials)


def _patch_codex(module: Any) -> bool:
    resolver = getattr(module, "resolve_codex_runtime_credentials", None)
    importer = getattr(module, "_import_codex_cli_tokens", None)
    result_builder = getattr(module, "_codex_runtime_result", None)
    auth_error = getattr(module, "AuthError", None)
    if not callable(resolver) or not callable(importer) or not callable(result_builder) or auth_error is None:
        return False
    if getattr(resolver, _PATCH_MARKER, False):
        return True

    def resolve_shared_codex(*, read_only: bool = False, **kwargs: Any) -> Dict[str, Any]:
        try:
            return resolver(read_only=read_only, **kwargs)
        except auth_error as exc:
            # A valid account-level Codex CLI access token is shared read-only.
            # Do not adopt/copy it or consume its externally-owned refresh token.
            if getattr(exc, "code", None) not in {
                "codex_auth_missing",
                "codex_auth_missing_access_token",
                "codex_auth_invalid_shape",
            }:
                raise
            tokens = importer()
            access_token = str((tokens or {}).get("access_token") or "").strip()
            if not access_token:
                raise
            return result_builder(
                access_token,
                source="codex-cli-auth",
                last_refresh=None,
            )

    setattr(resolve_shared_codex, _PATCH_MARKER, True)
    module.resolve_codex_runtime_credentials = resolve_shared_codex
    return True
