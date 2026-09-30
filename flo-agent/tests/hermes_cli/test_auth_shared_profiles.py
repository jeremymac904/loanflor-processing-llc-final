"""Shared provider-account auth is inherited by every Hermes profile."""

import base64
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermes_cli import auth as auth_mod


BUNDLED_PROFILES = (
    "default",
    "flo",
    "malcolm",
    "sage",
    "chadwick",
    "whisper",
    "franklin",
    # The resolver is profile-agnostic; this guards future generated agents.
    "future-agent",
)


def _jwt_with_exp(exp_epoch: int) -> str:
    payload = {"exp": exp_epoch}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"h.{encoded}.s"


def _profile_home(root: Path, profile: str) -> Path:
    return root if profile == "default" else root / "profiles" / profile


@pytest.fixture
def isolated_profile_auth(tmp_path, monkeypatch):
    """Set a distinct empty Hermes auth scope while keeping account auth shared."""
    root = tmp_path / "hermes"
    # Keep the shared provider-account store distinct from both the default
    # profile and each named profile's private auth directory.
    shared_dir = tmp_path / "provider-account-auth"
    shared_dir.mkdir(parents=True)
    monkeypatch.setenv("HERMES_SHARED_AUTH_DIR", str(shared_dir))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setattr(auth_mod, "_nous_shared_runtime_cache", None)

    def select(profile: str) -> Path:
        home = _profile_home(root, profile)
        home.mkdir(parents=True, exist_ok=True)
        auth_path = home / "auth.json"
        auth_path.write_text(json.dumps({"version": 1, "providers": {}}), encoding="utf-8")
        monkeypatch.setenv("HERMES_HOME", str(home))
        return auth_path

    return root, shared_dir, select


@pytest.mark.parametrize("profile", BUNDLED_PROFILES)
def test_every_profile_resolves_shared_nous_account_without_profile_copy(
    profile, isolated_profile_auth, monkeypatch,
):
    """A shared Nous account works in default, bundled, and future profiles."""
    _root, shared_dir, select = isolated_profile_auth
    profile_auth = select(profile)
    shared_store = shared_dir / auth_mod.NOUS_SHARED_STORE_FILENAME
    shared_store.write_text("{}", encoding="utf-8")
    inference_jwt = _jwt_with_exp(int(time.time()) + 3600)

    monkeypatch.setattr(
        auth_mod,
        "_try_import_shared_nous_state",
        lambda **_kwargs: {
            "agent_key": inference_jwt,
            "agent_key_expires_at": datetime.fromtimestamp(
                time.time() + 3600, timezone.utc
            ).isoformat(),
            "agent_key_id": "shared-account-key",
            "inference_base_url": "https://inference.example.test/v1",
        },
    )

    credentials = auth_mod.resolve_nous_runtime_credentials()

    assert credentials["provider"] == "nous"
    assert credentials["source"] == "shared_account_store"
    assert credentials["api_key"] == inference_jwt
    assert json.loads(profile_auth.read_text(encoding="utf-8")) == {
        "version": 1,
        "providers": {},
    }


@pytest.mark.parametrize("profile", BUNDLED_PROFILES)
def test_every_profile_resolves_shared_codex_account_without_profile_copy(
    profile, isolated_profile_auth,
):
    """A machine-level Codex account session works without per-profile login."""
    root, _shared_dir, select = isolated_profile_auth
    profile_auth = select(profile)
    codex_home = root.parent / "codex"
    codex_home.mkdir(parents=True, exist_ok=True)
    access_token = _jwt_with_exp(int(time.time()) + 3600)
    codex_auth = codex_home / "auth.json"
    codex_auth.write_text(
        json.dumps({
            "tokens": {
                "access_token": access_token,
                "refresh_token": "shared-refresh-token-not-consumed",
            }
        }),
        encoding="utf-8",
    )

    credentials = auth_mod.resolve_codex_runtime_credentials()

    assert credentials["provider"] == "openai-codex"
    assert credentials["source"] == "codex-cli-auth"
    assert credentials["api_key"] == access_token
    assert json.loads(profile_auth.read_text(encoding="utf-8")) == {
        "version": 1,
        "providers": {},
    }
    assert json.loads(codex_auth.read_text(encoding="utf-8"))["tokens"]["refresh_token"] == (
        "shared-refresh-token-not-consumed"
    )
