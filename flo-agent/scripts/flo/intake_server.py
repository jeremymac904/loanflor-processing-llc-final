#!/usr/bin/env python3
"""Flo intake endpoint for lfprocessing.net loan submissions (private, token-protected).

    FLO_INTAKE_TOKEN=<shared secret> python scripts/flo/intake_server.py [--host 127.0.0.1] [--port 8787] [--no-spawn]

    POST /intake/loan-submissions   Authorization: Bearer <token>   body = v1.0 payload
        201 {ok, submissionId, workspaceId, taskId, status: "accepted"}
        200 {ok, submissionId, workspaceId, taskId, status: "duplicate"}   (same submissionId again)
        400 validation problem · 401 bad/missing token · 413 body too large
    POST /intake/esign-webhook      Authorization: Bearer <token>   body = {"envelopeId": "..."}
        Forwarded by the website's Documenso webhook receiver over this same private, already-authenticated
        channel (never the raw Documenso webhook itself, and Documenso credentials never touch the website).
        Only envelopeId is read; everything else in the body is ignored — status and the completed file are
        always re-fetched fresh from Documenso's own API (plugins/flo-team/esign.py), never trusted from a
        webhook payload. 200 {ok, ...} always (even "no local request matches"; nothing to retry).
    GET  /intake/health             {ok, service, pendingDispatch, esign: "configured"|"not configured"}

At startup (and every ``FLO_ESIGN_POLL_SECONDS`` — default 300 — while running, when
``DOCUMENSO_API_URL``/``DOCUMENSO_API_TOKEN`` are set) this process also sweeps every open signature
request across every loan and re-checks it, so a borrower who signs while Ashley's computer is off still
gets the completed document filed the next time Flo is running — see ``esign.poll_all``.

This is the ONLY thing the LoanFlow server talks to. It binds to localhost by
default: reach it from the website host over a private network or tunnel
(Tailscale / Cloudflare Tunnel), never by exposing it — and never expose the
Hermes gateway itself. On each accepted submission it (a) creates the Deal Room
and Malcolm's task deterministically (plugins/flo-team/intake.py) and (b)
starts one Flo turn in her Bot Chat so she sends Malcolm the packet and tells
Ashley "new loan" — unless --no-spawn (tests). Logs carry ids only.
"""

from __future__ import annotations

import argparse
import hmac
import importlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
MAX_BODY = 1_000_000


def _load_plugin():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    return importlib.import_module("flo_team.intake"), importlib.import_module("flo_team.manifest")


def _esign_module():
    _load_plugin()
    return importlib.import_module("flo_team.esign")


def esign_configured() -> bool:
    return bool(os.environ.get("DOCUMENSO_API_URL")) and bool(os.environ.get("DOCUMENSO_API_TOKEN"))


def run_esign_catchup(root: Path, *, log=None) -> None:
    """Best-effort sweep of every open signature request. Never raises — a misconfigured or unreachable
    Documenso must not take down the intake server or block loan-submission traffic."""
    log = log or _log
    if not esign_configured():
        return
    try:
        esign_mod = _esign_module()
        result = esign_mod.poll_all(root, esign_mod.default_client())
        log(f"[esign] catch-up sweep: checked {result['checked']}")
    except Exception as exc:  # noqa: BLE001
        log(f"[esign] catch-up sweep failed: {type(exc).__name__}: {exc}")


def schedule_esign_polling(root: Path, *, interval: int, log=None) -> Optional[threading.Timer]:
    log = log or _log
    if not esign_configured() or interval <= 0:
        return None

    def _tick():
        run_esign_catchup(root, log=log)
        schedule_esign_polling(root, interval=interval, log=log)

    timer = threading.Timer(interval, _tick)
    timer.daemon = True
    timer.start()
    return timer


def flo_turn_message(record: dict) -> str:
    return (f"A new loan submission arrived from the website: {record['borrower']} (submission {record['submission_id']}, Deal Room {record['workspace_id']}). "
            f"Run flo_intake action=dispatch submission_id={record['submission_id']} and send send_with.message to send_with.target with message_agent. "
            f"Then tell Ashley in one line: \"{record['ashley_line']}\" Do not wait for Malcolm.")


def spawn_flo(record: dict, *, timeout: int = 900) -> dict:
    exe = Path(sys.executable).parent / ("hermes.exe" if os.name == "nt" else "hermes")
    cmd = [str(exe), "-p", "flo", "chat", "--in", str(Path.home()), "-c", "Bot Chat", "-Q", "--oneshot", "-q", flo_turn_message(record)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(Path.home()))
        return {"ok": proc.returncode == 0, "returncode": proc.returncode, "stdout_tail": (proc.stdout or "")[-800:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Flo turn exceeded {timeout}s"}


def _log(message: str) -> None:
    print(message, flush=True)


def make_handler(root: Path, token: str, *, spawn: bool, intake_mod, log=_log):
    class Handler(BaseHTTPRequestHandler):
        server_version = "FloIntake/1.0"

        def log_message(self, fmt, *args):  # ids only, never bodies
            log(f"[intake] {self.address_string()} {fmt % args}")

        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization") or ""
            presented = header[7:] if header.startswith("Bearer ") else ""
            return bool(presented) and hmac.compare_digest(presented, token)

        def do_GET(self):  # noqa: N802
            if self.path.rstrip("/") == "/intake/health":
                pending = len(intake_mod.IntakeStore(root).pending_dispatch())
                return self._json(200, {"ok": True, "service": "Flo intake", "pendingDispatch": pending,
                                        "esign": "configured" if esign_configured() else "not configured"})
            return self._json(404, {"ok": False, "error": "not found"})

        def do_POST(self):  # noqa: N802
            if self.path.rstrip("/") == "/intake/esign-webhook":
                return self._handle_esign_webhook()
            if self.path.rstrip("/") != "/intake/loan-submissions":
                return self._json(404, {"ok": False, "error": "not found"})
            if not self._authorized():
                return self._json(401, {"ok": False, "error": "unauthorized"})
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                return self._json(413 if length > MAX_BODY else 400, {"ok": False, "error": "bad body size"})
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except ValueError:
                return self._json(400, {"ok": False, "error": "invalid JSON"})
            try:
                # Documents are pulled back from the website through the same shared token (fetchUrl in each documentRef).
                record = intake_mod.receive(root, payload, document_token=token)
            except intake_mod.IntakeError as exc:
                log(f"[intake] rejected submission: {exc}")
                return self._json(400, {"ok": False, "error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                log(f"[intake] error for {payload.get('submissionId') if isinstance(payload, dict) else '?'}: {type(exc).__name__}")
                return self._json(500, {"ok": False, "error": "intake failed"})
            duplicate = bool(record.get("duplicate"))
            log(f"[intake] {'duplicate' if duplicate else 'accepted'} {record['submission_id']} -> {record['workspace_id']} task {record['task_id']}")
            if spawn and not duplicate:
                threading.Thread(target=lambda: log(f"[intake] flo turn for {record['submission_id']}: {spawn_flo(record)}"), daemon=True).start()
            return self._json(200 if duplicate else 201, {"ok": True, "submissionId": record["submission_id"], "workspaceId": record["workspace_id"],
                                                          "taskId": record["task_id"], "status": "duplicate" if duplicate else "accepted"})

        def _handle_esign_webhook(self):
            # Same shared bearer token as the loan-submissions endpoint: this is the private forward from
            # the website's own webhook receiver (which independently verified Documenso's X-Documenso-Secret
            # before ever calling us), not the public internet.
            if not self._authorized():
                return self._json(401, {"ok": False, "error": "unauthorized"})
            length = int(self.headers.get("Content-Length") or 0)
            if length < 0 or length > MAX_BODY:
                return self._json(413, {"ok": False, "error": "bad body size"})
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            except ValueError:
                return self._json(400, {"ok": False, "error": "invalid JSON"})
            envelope_id = str((payload or {}).get("envelopeId") or "").strip()
            if not envelope_id:
                return self._json(400, {"ok": False, "error": "envelopeId is required"})
            if not esign_configured():
                log("[esign] webhook ping received but Documenso is not configured; ignored")
                return self._json(200, {"ok": True, "note": "esign not configured; ignored"})
            try:
                esign_mod = _esign_module()
                result = esign_mod.handle_webhook_ping(root, esign_mod.default_client(), envelope_id=envelope_id)
                log(f"[esign] webhook ping for {envelope_id}: {result.get('status') or result.get('note')}")
                return self._json(200, {"ok": True, "status": result.get("status"), "note": result.get("note")})
            except Exception as exc:  # noqa: BLE001 - never let a webhook hint crash the process
                log(f"[esign] webhook ping for {envelope_id} failed: {type(exc).__name__}: {exc}")
                return self._json(200, {"ok": True, "note": "re-check failed; the next catch-up sweep will retry"})

    return Handler


def serve(host: str, port: int, *, token: str, root: Path, spawn: bool = True):
    intake_mod, _ = _load_plugin()
    server = ThreadingHTTPServer((host, port), make_handler(root, token, spawn=spawn, intake_mod=intake_mod))
    return server


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=os.environ.get("FLO_INTAKE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FLO_INTAKE_PORT", "8787")))
    parser.add_argument("--no-spawn", action="store_true", help="do not start a Flo turn after accepting (tests)")
    args = parser.parse_args(argv)
    token = os.environ.get("FLO_INTAKE_TOKEN") or ""
    if len(token) < 24:
        print("FLO_INTAKE_TOKEN must be set (24+ characters); refusing to start without authentication", file=sys.stderr)
        return 2
    _, manifest = _load_plugin()
    root = manifest.team_state_root()
    if root is None:
        print("HERMES_HOME is not set; cannot locate the Flo Team state root", file=sys.stderr)
        return 2
    server = serve(args.host, args.port, token=token, root=Path(root), spawn=not args.no_spawn)
    print(f"Flo intake listening on http://{args.host}:{args.port}/intake/loan-submissions (spawn Flo: {not args.no_spawn}); team root {root}")
    print(f"e-signature (Documenso): {'configured' if esign_configured() else 'not configured (DOCUMENSO_API_URL / DOCUMENSO_API_TOKEN unset)'}")
    if not args.no_spawn:
        threading.Thread(target=lambda: run_esign_catchup(Path(root)), daemon=True).start()
        schedule_esign_polling(Path(root), interval=int(os.environ.get("FLO_ESIGN_POLL_SECONDS", "300")))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
