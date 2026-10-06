"""Hermes account-auth discovery used by the Flo desktop entry point."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


COMPAT_PATH = (
    Path(__file__).parents[2]
    / "apps"
    / "desktop"
    / "scripts"
    / "flo-auth-runtime"
    / "flo_auth_runtime_compat.py"
)
SPEC = importlib.util.spec_from_file_location("flo_auth_runtime_compat_test", COMPAT_PATH)
assert SPEC and SPEC.loader
COMPAT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPAT)


class AuthError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def test_nous_profile_missing_resolves_shared_account_without_profile_copy():
    def profile_resolver(**_kwargs):
        raise AuthError("nous_auth_missing")

    shared = {"provider": "nous", "source": "shared_account_store", "api_key": "not-asserted"}
    calls = []
    module = SimpleNamespace(
        AuthError=AuthError,
        resolve_nous_runtime_credentials=profile_resolver,
        _resolve_shared_nous_runtime_credentials=lambda **kwargs: calls.append(kwargs) or shared,
    )

    assert COMPAT._patch_nous(module)
    assert module.resolve_nous_runtime_credentials(timeout_seconds=3) is shared
    assert calls == [{"timeout_seconds": 3, "force_refresh": False, "auth_nous": module}]


def test_nous_does_not_override_an_invalid_existing_profile_credential():
    def profile_resolver(**_kwargs):
        raise AuthError("nous_auth_refresh_failed")

    shared_calls = []
    module = SimpleNamespace(
        AuthError=AuthError,
        resolve_nous_runtime_credentials=profile_resolver,
        _resolve_shared_nous_runtime_credentials=lambda **kwargs: shared_calls.append(kwargs),
    )
    COMPAT._patch_nous(module)

    try:
        module.resolve_nous_runtime_credentials()
    except AuthError as error:
        assert error.code == "nous_auth_refresh_failed"
    else:
        raise AssertionError("invalid profile auth should not be silently replaced")
    assert shared_calls == []


def test_nous_status_reports_shared_runtime_auth_without_bearer_fields():
    module = SimpleNamespace(
        AuthError=AuthError,
        resolve_nous_runtime_credentials=lambda **_kwargs: (_ for _ in ()).throw(
            AuthError("nous_auth_missing")),
        _resolve_shared_nous_runtime_credentials=lambda **_kwargs: {
            "provider": "nous", "base_url": "https://inference.example", "api_key": "never-return",
            "expires_at": "2099-01-01T00:00:00Z",
        },
        _compute_nous_auth_status=lambda: {"logged_in": False},
    )
    COMPAT._patch_nous(module)

    status = module._compute_nous_auth_status()
    assert status["logged_in"] is True
    assert status["source"] == "runtime:shared_account_store"
    assert "api_key" not in status
    assert "access_token" not in status


def test_codex_status_and_runtime_can_use_shared_cli_access_token_read_only():
    def profile_resolver(**_kwargs):
        raise AuthError("codex_auth_missing")

    built = []
    module = SimpleNamespace(
        AuthError=AuthError,
        resolve_codex_runtime_credentials=profile_resolver,
        _import_codex_cli_tokens=lambda: {"access_token": "redacted-test-token", "refresh_token": "unused"},
        _codex_runtime_result=lambda token, **kwargs: built.append((token, kwargs)) or {
            "provider": "openai-codex", "source": kwargs["source"], "api_key": token,
        },
    )

    assert COMPAT._patch_codex(module)
    result = module.resolve_codex_runtime_credentials(read_only=True)
    assert result["provider"] == "openai-codex"
    assert result["source"] == "codex-cli-auth"
    assert built == [("redacted-test-token", {"source": "codex-cli-auth", "last_refresh": None})]


def test_codex_missing_or_expired_external_session_stays_unconnected():
    def profile_resolver(**_kwargs):
        raise AuthError("codex_auth_missing")

    module = SimpleNamespace(
        AuthError=AuthError,
        resolve_codex_runtime_credentials=profile_resolver,
        _import_codex_cli_tokens=lambda: None,
        _codex_runtime_result=lambda *_args, **_kwargs: {},
    )
    COMPAT._patch_codex(module)

    try:
        module.resolve_codex_runtime_credentials(read_only=True)
    except AuthError as error:
        assert error.code == "codex_auth_missing"
    else:
        raise AssertionError("missing shared credentials must remain disconnected")
