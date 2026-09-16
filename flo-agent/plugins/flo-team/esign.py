"""Electronic signatures via Documenso (self-hosted Community Edition) — Ashley's "Send for Signature".

Product decision (owner, 2026-09-10): Documenso, self-hosted. This module is the one small adapter that
talks to it; Documenso itself stays a separate service reached over its own API. Nothing here re-implements
signing, PDF editing, or an approval system — every side effect (send / remind / cancel) is a normal
``flo_*`` tool call, so the existing flo-team role policy (``roles.py`` ``EXTERNAL_TOOLS``), the existing
Approval Center (``approvals_center.py``) and the existing tool-call idempotency (``__init__.py``
``pre_tool_call`` + ``intents.py``) gate it exactly like every other outbound action. See ``FLO_ESIGN.md``
for what was verified against Documenso's current docs/blog vs inferred from naming convention, and for
what could not be verified against a live instance in this environment (no Docker/Postgres available).

API surface used (Envelope API v2 — verified against live Documenso v2.18.0 OpenAPI spec):

    POST /api/v2/template/use               create an envelope from a template (DEPRECATED upstream,
                                             removal 2027-03-01; migrate to /api/v2/envelope/use)
    POST /api/v2/envelope/distribute         send the created envelope to its recipients
    GET  /api/v2/envelope/{envelopeId}       authoritative status + recipient signing status + item ids
    GET  /api/v2/envelope/item/{envelopeItemId}/download   completed PDF bytes (version: signed|original|pending)
    POST /api/v2/envelope/redistribute       resend to unsigned recipients (requires recipient id array)
    POST /api/v2/envelope/cancel             cancel a pending envelope (takes envelopeId + optional reason)
    GET  /api/v2/envelope/{envelopeId}/audit-log            audit log entries
    GET  /api/v2/envelope/{envelopeId}/audit-log/download   audit log as PDF
    GET  /api/v2/envelope/{envelopeId}/certificate/download signing certificate as PDF

All endpoints verified against live v2.18.0 OpenAPI at /api/v2/openapi.json on 2026-09-11.

Webhook events (``DOCUMENT_COMPLETED`` etc.) never carry a download URL or file bytes — only status. A
webhook is therefore only ever a *hint to re-check*; the authoritative source is always a fresh
authenticated GET against the API above (see ``handle_webhook_ping``).

Signature request statuses (Ashley's Documents section shows these in plain words — ``ashley.ts``
``ESIGN_STATUS_LABEL`` mirrors this list):

    draft              prepared, not yet approved/sent
    sent               distributed; no signer has completed yet
    partially_signed   at least one required signer has completed, not all
    signed             every required signer has completed (Documenso says COMPLETED)
    retrieved          the completed PDF + evidence have been downloaded and filed as a document
    declined           a recipient rejected the envelope
    cancelled          Ashley (via Flo) voided the envelope before completion
    needs_attention    an ambiguous failure (timeout, fetch/download error) that must not be silently retried
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .store import JsonDocStore, JsonlLog, new_id, now_iso

STATUSES = ("draft", "sent", "partially_signed", "signed", "retrieved", "declined", "cancelled", "needs_attention")
STATUS_LABEL = {
    "draft": "Ready to send", "sent": "Waiting for signature", "partially_signed": "Waiting for signature",
    "signed": "Signed", "retrieved": "Signed", "declined": "Needs attention", "cancelled": "Needs attention",
    "needs_attention": "Needs attention",
}
ACTIVE_STATUSES = ("sent", "partially_signed", "signed")  # still needs polling for a result
_TERMINAL = ("retrieved", "declined", "cancelled")
TEMPLATE_REGISTRY_FILENAME = "esign_templates.json"


class EsignError(ValueError):
    pass


# ── Documenso API client ──────────────────────────────────────────────────────

class DocumensoClient:
    """Thin HTTP wrapper over the Documenso Envelope API v2. No retries, no magic: one call in, one
    parsed result out. Retry/idempotency policy lives in this module's request-level functions, not here,
    so it stays visible and testable."""

    def __init__(self, base_url: str, token: str, *, timeout: int = 30, opener: Optional[Callable] = None) -> None:
        if not base_url or not base_url.startswith(("http://", "https://")):
            raise EsignError("DOCUMENSO_API_URL must be an absolute http(s) URL")
        if not token or len(token) < 8:
            raise EsignError("DOCUMENSO_API_TOKEN is not configured")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        # Injectable for tests (a callable taking a urllib.request.Request and returning a response-like
        # object with .status/.read()); defaults to the real network call.
        self._open = opener or (lambda req, timeout: urllib.request.urlopen(req, timeout=timeout))  # noqa: S310

    def _request(self, method: str, path: str, *, json_body: Optional[Dict[str, Any]] = None) -> Tuple[int, bytes]:
        url = f"{self.base_url}{path}"
        data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        headers = {"Accept": "application/json"}
        # Documenso's own docs/blog examples show the raw token in the Authorization header with no
        # "Bearer " prefix (curl -H "Authorization: <YOUR_TOKEN>"); kept exactly as documented.
        headers["Authorization"] = self.token
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._open(req, self.timeout) as resp:  # noqa: S310 - self-hosted, operator-configured URL
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def _json(self, method: str, path: str, *, json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        status, body = self._request(method, path, json_body=json_body)
        try:
            parsed = json.loads(body.decode("utf-8")) if body else {}
        except ValueError:
            parsed = {"raw": body[:500].decode("utf-8", "replace")}
        if status >= 400:
            raise EsignError(f"Documenso {method} {path} -> HTTP {status}: {parsed.get('message') or parsed.get('error') or parsed}")
        return parsed

    def create_from_template(self, template_id: str, recipients: List[Dict[str, str]], *, external_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        """POST /api/v2/template/use — recipients substitute the template's placeholder signers by position (id).
        This endpoint is deprecated upstream (removal 2027-03-01); migrate to /api/v2/envelope/use when needed."""
        payload = {"templateId": template_id, "recipients": recipients, "distributeDocument": False, "externalId": external_id}
        if title:
            payload["title"] = title
        return self._json("POST", "/api/v2/template/use", json_body=payload)

    def distribute(self, envelope_id: str) -> Dict[str, Any]:
        return self._json("POST", "/api/v2/envelope/distribute", json_body={"envelopeId": envelope_id})

    def get_envelope(self, envelope_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/api/v2/envelope/{envelope_id}")

    def download_item(self, item_id: str) -> bytes:
        status, body = self._request("GET", f"/api/v2/envelope/item/{item_id}/download")
        if status >= 400:
            raise EsignError(f"Documenso download {item_id} -> HTTP {status}")
        return body

    def redistribute(self, envelope_id: str, recipient_ids: List[int]) -> Dict[str, Any]:
        """POST /api/v2/envelope/redistribute — resend to recipients who have not yet signed.
        ``recipient_ids`` is required and must contain at least one numeric recipient ID."""
        if not recipient_ids:
            raise EsignError("redistribute requires at least one recipient id")
        return self._json("POST", "/api/v2/envelope/redistribute", json_body={"envelopeId": envelope_id, "recipients": recipient_ids})

    def cancel(self, envelope_id: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
        """POST /api/v2/envelope/cancel — cancel a pending envelope."""
        return self._json("POST", "/api/v2/envelope/cancel", json_body={"envelopeId": envelope_id, "reason": reason or ""})


def default_client(*, env: Optional[Dict[str, str]] = None) -> DocumensoClient:
    env = env if env is not None else os.environ
    base_url = env.get("DOCUMENSO_API_URL") or ""
    token = env.get("DOCUMENSO_API_TOKEN") or ""
    if not base_url or not token:
        raise EsignError("DOCUMENSO_API_URL and DOCUMENSO_API_TOKEN must be configured (see FLO_ESIGN.md)")
    return DocumensoClient(base_url, token)


# ── Health check & auto-recovery ─────────────────────────────────────────────

_AGENT_ROOT = Path(__file__).resolve().parent.parent.parent


def _find_docker() -> Optional[str]:
    known = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
    if known.exists():
        return str(known)
    import shutil
    return shutil.which("docker")


def _api_reachable(base_url: str, *, timeout: int = 5) -> bool:
    try:
        req = urllib.request.Request(f"{base_url}/api/v2/openapi.json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        return False


def _clean_stale_sockets() -> None:
    if sys.platform != "win32":
        return
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return
    for name in ("Docker\\run", "docker-secrets-engine"):
        d = os.path.join(local, name)
        if not os.path.isdir(d):
            continue
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        if not entries:
            continue
        ts = now_iso().replace(":", "").replace("-", "").replace("T", "")[:14]
        bak = f"{d}.bak.{ts}"
        try:
            os.rename(d, bak)
            os.makedirs(d)
        except OSError:
            pass


def _start_docker_desktop() -> None:
    if sys.platform != "win32":
        return
    exe = Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe")
    if exe.exists():
        try:
            flags = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            subprocess.Popen([str(exe)], creationflags=flags)
        except OSError:
            pass
    try:
        subprocess.run(["wsl", "-d", "docker-desktop", "--", "echo", "started"],
                       capture_output=True, timeout=15)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass


def _auto_recover(env: Dict[str, str]) -> bool:
    """Bring Documenso back up without launching Hermes. Returns True if API responds after recovery."""
    docker_cli = _find_docker()
    if not docker_cli:
        return False

    base_url = (env.get("DOCUMENSO_API_URL") or "http://localhost:3000").rstrip("/")
    compose_dir = _AGENT_ROOT / "deploy" / "documenso"

    _clean_stale_sockets()

    try:
        result = subprocess.run([docker_cli, "info"], capture_output=True, timeout=10)
        docker_ready = result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        docker_ready = False

    if not docker_ready:
        _start_docker_desktop()
        for _ in range(24):
            time.sleep(5)
            try:
                r = subprocess.run([docker_cli, "info"], capture_output=True, timeout=10)
                if r.returncode == 0:
                    docker_ready = True
                    break
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

    if not docker_ready:
        return False

    if compose_dir.exists():
        try:
            subprocess.run([docker_cli, "compose", "up", "-d"],
                           cwd=str(compose_dir), capture_output=True, timeout=60)
        except (subprocess.TimeoutExpired, OSError):
            pass

    for _ in range(12):
        time.sleep(5)
        if _api_reachable(base_url):
            return True
    return False


def check_health(*, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Quiet pre-flight check. Returns ``{healthy, message, recovered}``.

    When healthy: ``message`` is ``None``, no output needed.
    When recovered: Documenso was down, auto-recovery succeeded, ``message`` has a simple note.
    When unhealthy: auto-recovery failed (or not on Windows), ``message`` tells Ashley what to do."""
    env = env if env is not None else os.environ
    base_url = (env.get("DOCUMENSO_API_URL") or "http://localhost:3000").rstrip("/")

    if _api_reachable(base_url):
        token = env.get("DOCUMENSO_API_TOKEN") or ""
        if not token:
            return {"healthy": False, "message": "Flo Signatures needs its credentials configured.", "recovered": False}
        return {"healthy": True, "message": None, "recovered": False}

    if sys.platform != "win32":
        return {"healthy": False, "message": "Flo Signatures isn't responding.", "recovered": False}

    recovered = _auto_recover(env)
    if recovered:
        return {"healthy": True, "message": "Flo Signatures wasn't running. It's been started.", "recovered": True}
    return {"healthy": False,
            "message": "Flo Signatures isn't responding. Try opening it from the Start Menu.",
            "recovered": False}


def ensure_healthy(*, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Call before any e-sign operation. Raises ``EsignError`` if Documenso is unreachable after recovery."""
    result = check_health(env=env)
    if not result["healthy"]:
        raise EsignError(result["message"])
    return result


# ── Template registry (start with exactly one: the approved LOE) ─────────────

def load_templates(team_root, *, env: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, Any]]:
    """``<flo-team>/knowledge/esign_templates.json`` describes each approved template's expected shape
    (category, page count, signer roles); the actual Documenso ``templateId`` comes from an environment
    variable named in the registry entry, never hardcoded, since it is only known once someone has built
    the template in the Documenso editor for a real self-hosted instance."""
    env = env if env is not None else os.environ
    path = Path(__file__).with_name("knowledge") / TEMPLATE_REGISTRY_FILENAME
    if not path.exists():
        return {}
    registry = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, Dict[str, Any]] = {}
    for key, spec in registry.items():
        spec = dict(spec)
        spec["documenso_template_id"] = env.get(spec.get("template_id_env") or "") or None
        out[key] = spec
    return out


def eligible_templates(team_root, document: Dict[str, Any], *, env: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Which configured templates this document could be sent through — matched on category and, when the
    template specifies one, exact page count. An empty list means "This document needs signing setup."."""
    out = []
    for key, spec in load_templates(team_root, env=env).items():
        if not spec.get("documenso_template_id"):
            continue
        if spec.get("category") and document.get("category") != spec["category"]:
            continue
        expected_pages = spec.get("expected_page_count")
        if expected_pages is not None and document.get("page_count") not in (None, expected_pages):
            continue
        out.append({"template_key": key, **spec})
    return out


# ── Signature request store (one JSON record per request, keyed by workspace) ─

class SignatureRequestStore:
    def __init__(self, root) -> None:
        self.docs = JsonDocStore(root / "esign")
        self.log = JsonlLog(root / "activity", "activity")

    def list(self, workspace_id: str) -> List[Dict[str, Any]]:
        return list((self.docs.get(workspace_id) or {}).get("requests") or [])

    def get(self, workspace_id: str, request_id: str) -> Optional[Dict[str, Any]]:
        return next((r for r in self.list(workspace_id) if r.get("request_id") == request_id), None)

    def _save(self, workspace_id: str, requests: List[Dict[str, Any]]) -> None:
        self.docs.put(workspace_id, {"workspace_id": workspace_id, "requests": requests})

    def add(self, workspace_id: str, record: Dict[str, Any]) -> Dict[str, Any]:
        rows = self.list(workspace_id)
        rows.append(record)
        self._save(workspace_id, rows)
        return record

    def update(self, workspace_id: str, request_id: str, fields: Dict[str, Any], *, by: str) -> Dict[str, Any]:
        rows = self.list(workspace_id)
        rec = next((r for r in rows if r.get("request_id") == request_id), None)
        if rec is None:
            raise EsignError(f"unknown signature request {request_id}")
        rec.update(fields)
        rec.setdefault("history", []).append({"at": now_iso(), "by": by, "fields": sorted(fields)})
        self._save(workspace_id, rows)
        self.log.append({"event": "esign.updated", "actor": by, "workspace_id": workspace_id, "request_id": request_id, "fields": sorted(fields)})
        return rec

    def find_active_for_document(self, workspace_id: str, document_id: str) -> Optional[Dict[str, Any]]:
        """A live (not cancelled/declined) request already covering this exact document — used so a
        double-click or a re-run of ``prepare``/``send`` reuses it instead of creating a duplicate."""
        for r in self.list(workspace_id):
            if r.get("source_document_id") == document_id and r.get("status") not in ("cancelled", "declined"):
                return r
        return None

    def all_active(self) -> List[Dict[str, Any]]:
        """Every request across every workspace still worth polling (catch-up sweep)."""
        out = []
        for wid in self.docs.ids():
            for r in self.list(wid):
                if r.get("status") in ACTIVE_STATUSES:
                    out.append(r)
        return out


def material_key(*, workspace_id: str, document_id: str, document_checksum: str, template_key: str,
                  recipients: List[Dict[str, str]], message: str) -> str:
    """What Ashley's approval is actually about: this exact document version, these exact recipients, this
    exact template and message. Any change here means a fresh approval, never a silent reuse."""
    blob = json.dumps({
        "workspace_id": workspace_id, "document_id": document_id, "document_checksum": document_checksum,
        "template_key": template_key, "message": message,
        "recipients": sorted([{"name": r.get("name", ""), "email": r.get("email", "").lower(), "role": r.get("role", "SIGNER")} for r in recipients], key=lambda r: r["email"]),
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── prepare / send / status / retrieve / remind / cancel ─────────────────────

def prepare(team_root, *, workspace_id: str, document: Dict[str, Any], template_key: str, recipients: List[Dict[str, str]],
            message: str, by: str, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Build (never send) the request Ashley reviews. Raises with the exact wording the UI shows verbatim
    when the document does not match a configured template."""
    if document.get("workspace_id") and document["workspace_id"] != workspace_id:
        raise EsignError("that document does not belong to this loan")
    templates = eligible_templates(team_root, document, env=env)
    match = next((t for t in templates if t["template_key"] == template_key), None)
    if match is None:
        raise EsignError("This document needs signing setup.")
    if not recipients:
        raise EsignError("at least one recipient is required")
    for r in recipients:
        if not r.get("email") or "@" not in r["email"]:
            raise EsignError(f"recipient {r.get('name') or '(unnamed)'} needs a valid email address")
    message = str(message or "").strip()[:2000]
    key = material_key(workspace_id=workspace_id, document_id=document["document_id"], document_checksum=document.get("sha256") or "",
                        template_key=template_key, recipients=recipients, message=message)
    existing = SignatureRequestStore(team_root).find_active_for_document(workspace_id, document["document_id"])
    return {
        "workspace_id": workspace_id, "document_id": document["document_id"], "document_display_name": document.get("display_name"),
        "template_key": template_key, "template_label": match.get("label"), "recipients": recipients, "message": message,
        "material_key": key, "existing_request": existing, "next": "sending is a Yellow action: it stops at Ashley's approval prompt",
    }


def create_and_send(team_root, client: DocumensoClient, *, workspace_id: str, document: Dict[str, Any], template_key: str,
                     recipients: List[Dict[str, str]], message: str, by: str, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Runs only after Ashley's approval has already been verified by the generic flo-team tool-call gate
    (``roles.EXTERNAL_TOOLS`` + the pre_tool_call hook). Idempotent: a retry — double click, provider
    timeout, duplicate tool call — reuses the existing request rather than creating a second envelope."""
    store = SignatureRequestStore(team_root)
    prepared = prepare(team_root, workspace_id=workspace_id, document=document, template_key=template_key,
                        recipients=recipients, message=message, by=by, env=env)
    existing = prepared["existing_request"]
    if existing is not None and existing.get("material_key") == prepared["material_key"] and existing.get("status") != "needs_attention":
        return existing  # identical payload already active or done: never send twice
    match = next(t for t in eligible_templates(team_root, document, env=env) if t["template_key"] == template_key)
    request_id = new_id("esign")
    record = {
        "request_id": request_id, "workspace_id": workspace_id, "source_document_id": document["document_id"],
        "source_document_checksum": document.get("sha256"), "template_key": template_key, "recipients": recipients,
        "message": message, "material_key": prepared["material_key"], "documenso_envelope_id": None, "status": "draft",
        "created_by": by, "created_at": now_iso(), "history": [{"at": now_iso(), "by": by, "fields": ["created"]}],
        "signed_document_id": None, "evidence_path": None,
    }
    store.add(workspace_id, record)
    try:
        created = client.create_from_template(match["documenso_template_id"], recipients, external_id=request_id,
                                              title=document.get("display_name"))
        envelope_id = created.get("envelopeId") or created.get("id")
        if not envelope_id:
            raise EsignError("Documenso did not return an envelope id")
        store.update(workspace_id, request_id, {"documenso_envelope_id": envelope_id}, by=by)
        client.distribute(envelope_id)
    except Exception as exc:  # noqa: BLE001 - the outcome is genuinely ambiguous; never silently retry
        return store.update(workspace_id, request_id, {"status": "needs_attention",
                            "notes": f"send did not complete cleanly ({type(exc).__name__}: {exc}); check status before retrying — do not send again blindly"}, by=by)
    return store.update(workspace_id, request_id, {"status": "sent", "sent_at": now_iso()}, by=by)


def _recipient_status(envelope: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    recipients = envelope.get("recipients") or []
    signed = [r for r in recipients if r.get("signingStatus") == "SIGNED"]
    rejected = [r for r in recipients if r.get("signingStatus") == "REJECTED"]
    if rejected:
        return "declined", recipients
    if envelope.get("status") == "COMPLETED" or (recipients and len(signed) == len(recipients)):
        return "signed", recipients
    if signed:
        return "partially_signed", recipients
    return "sent", recipients


def refresh_status(team_root, client: DocumensoClient, *, workspace_id: str, request_id: str, by: str = "flo") -> Dict[str, Any]:
    """Authenticated status check — the only source of truth. Never trusts anything but the API response."""
    store = SignatureRequestStore(team_root)
    rec = store.get(workspace_id, request_id)
    if rec is None:
        raise EsignError(f"unknown signature request {request_id}")
    if not rec.get("documenso_envelope_id"):
        return rec  # nothing to check yet (still needs_attention from an ambiguous send)
    envelope = client.get_envelope(rec["documenso_envelope_id"])
    status, recipients = _recipient_status(envelope)
    fields = {"status": status, "recipient_status": [{"email": r.get("email"), "name": r.get("name"), "signing_status": r.get("signingStatus")} for r in recipients],
              "envelope_items": envelope.get("envelopeItems") or envelope.get("items") or [], "last_checked_at": now_iso()}
    if rec.get("status") in _TERMINAL:
        fields.pop("status", None)  # a terminal local state (retrieved/cancelled/declined) is not overwritten by a stale poll
    return store.update(workspace_id, request_id, fields, by=by)


def retrieve_completed(team_root, client: DocumensoClient, *, workspace_id: str, request_id: str, by: str = "flo") -> Dict[str, Any]:
    """Download the completed PDF(s) + evidence once, file them as a document, never re-download once
    filed. Preserves the signed bytes exactly — no flattening, recompression or watermarking."""
    from . import documents as documents_mod

    store = SignatureRequestStore(team_root)
    rec = refresh_status(team_root, client, workspace_id=workspace_id, request_id=request_id, by=by)
    if rec.get("signed_document_id"):
        return rec  # already retrieved and filed
    if rec.get("status") != "signed":
        return rec  # not ready; caller should show "Waiting for signature" / the specific sub-status
    items = rec.get("envelope_items") or []
    if not items:
        return store.update(workspace_id, request_id, {"status": "needs_attention",
                            "notes": "Documenso reports this signed but listed no downloadable item; retry retrieval, not the send"}, by=by)
    source_doc = documents_mod.DocumentStore(team_root).get(workspace_id, rec["source_document_id"]) or {}
    saved = []
    try:
        for item in items:
            item_id = item.get("id") or item.get("envelopeItemId")
            data = client.download_item(item_id)
            digest = hashlib.sha256(data).hexdigest()
            display_name = f"{now_iso()[:10]}_signed_{documents_mod._slug(source_doc.get('display_name') or 'document')}"
            path = documents_mod.documents_root(team_root) / documents_mod._slug(workspace_id) / "signed"
            path.mkdir(parents=True, exist_ok=True)
            dest = path / (display_name if display_name.lower().endswith(".pdf") else display_name + ".pdf")
            n = 2
            while dest.exists():
                dest = path / f"{dest.stem}_{n}{dest.suffix}"
                n += 1
            dest.write_bytes(data)
            saved.append({"path": str(dest), "sha256": digest, "size_bytes": len(data), "item_id": item_id})
    except Exception as exc:  # noqa: BLE001 - retry retrieval only, never re-send
        return store.update(workspace_id, request_id, {"status": "needs_attention",
                            "notes": f"signed but the completed file could not be downloaded yet ({type(exc).__name__}); retry retrieval"}, by=by)
    doc_store = documents_mod.DocumentStore(team_root)
    new_doc = {
        "document_id": new_id("doc"), "website_document_id": None, "submission_id": None, "workspace_id": workspace_id,
        "category": source_doc.get("category") or "other", "subcategory": source_doc.get("subcategory"),
        "borrower_ref": source_doc.get("borrower_ref"), "original_filename": Path(saved[0]["path"]).name,
        "display_name": Path(saved[0]["path"]).name, "storage_key": None, "mime_type": "application/pdf",
        "size_bytes": saved[0]["size_bytes"], "sha256": saved[0]["sha256"], "uploaded_at": now_iso(), "uploaded_by": "documenso",
        "received_at": now_iso(), "status": "received", "classification_source": "flo",
        "notes": f"Signed copy of {source_doc.get('display_name') or 'the document'} via Documenso", "local_path": saved[0]["path"],
        "text_path": None, "text_chars": 0, "page_count": None, "checks": {}, "history": [],
        "esign_request_id": request_id, "documenso_envelope_id": rec.get("documenso_envelope_id"),
    }
    doc_store.add(workspace_id, new_doc)
    evidence_path = saved[1]["path"] if len(saved) > 1 else None
    return store.update(workspace_id, request_id, {"status": "retrieved", "signed_document_id": new_doc["document_id"],
                        "evidence_path": evidence_path, "retrieved_at": now_iso()}, by=by)


def remind(team_root, client: DocumensoClient, *, workspace_id: str, request_id: str, by: str) -> Dict[str, Any]:
    """Operates on the existing request only — never creates a new envelope."""
    store = SignatureRequestStore(team_root)
    rec = store.get(workspace_id, request_id)
    if rec is None:
        raise EsignError(f"unknown signature request {request_id}")
    if rec.get("status") not in ("sent", "partially_signed"):
        raise EsignError(f"cannot remind a request that is {rec.get('status')}")
    envelope = client.get_envelope(rec["documenso_envelope_id"])
    unsigned = [r for r in (envelope.get("recipients") or []) if r.get("signingStatus") != "SIGNED"]
    if not unsigned:
        raise EsignError("all recipients have already signed")
    unsigned_ids = [r["id"] for r in unsigned if "id" in r]
    if not unsigned_ids:
        raise EsignError("could not determine recipient IDs for unsigned signers")
    client.redistribute(rec["documenso_envelope_id"], unsigned_ids)
    return store.update(workspace_id, request_id, {"last_reminded_at": now_iso()}, by=by)


def cancel(team_root, client: DocumensoClient, *, workspace_id: str, request_id: str, reason: str, by: str) -> Dict[str, Any]:
    """A changed document requires a fresh request (via ``prepare``/``create_and_send``), never editing a
    cancelled or signed one in place."""
    store = SignatureRequestStore(team_root)
    rec = store.get(workspace_id, request_id)
    if rec is None:
        raise EsignError(f"unknown signature request {request_id}")
    if rec.get("status") in _TERMINAL:
        raise EsignError(f"cannot cancel a request that is already {rec.get('status')}")
    if rec.get("documenso_envelope_id"):
        client.cancel(rec["documenso_envelope_id"], reason=reason)
    return store.update(workspace_id, request_id, {"status": "cancelled", "cancel_reason": str(reason or "")[:400]}, by=by)


def poll_all(team_root, client: DocumensoClient, *, by: str = "flo") -> Dict[str, Any]:
    """Catch-up sweep: run at Flo startup (and safe to re-run any time — e.g. a light periodic timer) so a
    borrower who signed while Ashley's computer was off still gets filed the next time Flo is running."""
    store = SignatureRequestStore(team_root)
    results = []
    for rec in store.all_active():
        try:
            updated = refresh_status(team_root, client, workspace_id=rec["workspace_id"], request_id=rec["request_id"], by=by)
            if updated.get("status") == "signed":
                updated = retrieve_completed(team_root, client, workspace_id=rec["workspace_id"], request_id=rec["request_id"], by=by)
            results.append({"workspace_id": rec["workspace_id"], "request_id": rec["request_id"], "status": updated.get("status")})
        except Exception as exc:  # noqa: BLE001 - one bad record must not stop the sweep
            results.append({"workspace_id": rec["workspace_id"], "request_id": rec["request_id"], "status": "needs_attention", "error": str(exc)})
    return {"checked": len(results), "results": results}


def handle_webhook_ping(team_root, client: DocumensoClient, *, envelope_id: str, by: str = "flo-webhook") -> Dict[str, Any]:
    """A webhook is only ever a hint to re-check *this* envelope — it never carries a download URL or a
    loan mapping we trust. Find the local request by envelope id and re-fetch authoritative status/files."""
    store = SignatureRequestStore(team_root)
    for wid in store.docs.ids():
        for rec in store.list(wid):
            if rec.get("documenso_envelope_id") == envelope_id:
                updated = refresh_status(team_root, client, workspace_id=wid, request_id=rec["request_id"], by=by)
                if updated.get("status") == "signed":
                    updated = retrieve_completed(team_root, client, workspace_id=wid, request_id=rec["request_id"], by=by)
                return updated
    return {"note": "no local signature request matches this envelope id; ignored"}


# ── Ashley's plain-English board (Documents section; no new dashboard) ────────

def board(workspace: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for r in workspace.get("esign_requests") or []:
        status = r.get("status", "draft")
        explanation = None
        if status == "partially_signed":
            names = [rs.get("name") or rs.get("email") for rs in (r.get("recipient_status") or []) if rs.get("signing_status") != "SIGNED"]
            explanation = f"Waiting on {', '.join(n for n in names if n)}." if names else "Waiting on the other signer."
        elif status == "signed":
            explanation = "Signed — retrieving the completed copy."
        elif status == "declined":
            explanation = "Recipient declined."
        elif status == "needs_attention":
            explanation = r.get("notes")
        rows.append({"request_id": r.get("request_id"), "document_id": r.get("source_document_id"),
                     "status": status, "status_label": STATUS_LABEL.get(status, "Needs attention"), "explanation": explanation,
                     "recipients": r.get("recipients"), "signed_document_id": r.get("signed_document_id")})
    return rows
