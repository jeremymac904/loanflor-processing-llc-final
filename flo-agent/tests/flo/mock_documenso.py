"""A local, in-process stand-in for the Documenso Envelope API v2, used ONLY to exercise our own
DocumensoClient's real HTTP calls (headers, URLs, JSON bodies, error handling) in automated tests.

This is NOT Documenso and proves nothing about Documenso's own signing/audit/certificate behavior — it
only proves that our adapter talks the documented wire protocol correctly and that the rest of esign.py
(idempotency, approval binding, document filing, webhook handling) behaves correctly given real HTTP
responses shaped the way Documenso's docs/blog say the real service responds. See FLO_ESIGN.md ("Verified
vs inferred" and "What could not be verified in this environment") for what this does and does not prove.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict


class MockDocumensoServer:
    """Enough of the envelope API to drive create -> distribute -> (test-only) sign -> status -> download,
    plus redistribute/cancel, so esign.py's real logic runs against real HTTP responses."""

    def __init__(self, token: str = "mock-documenso-token-0123456789") -> None:
        self.token = token
        self.envelopes: Dict[str, Dict[str, Any]] = {}
        self.calls: list[tuple[str, str]] = []  # (method, path) — for asserting idempotency (no duplicate sends)
        self._next = 0
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a):  # keep test output quiet
                pass

            def _send(self, status: int, payload):
                body = json.dumps(payload).encode("utf-8") if not isinstance(payload, (bytes, bytearray)) else payload
                self.send_response(status)
                self.send_header("Content-Type", "application/json" if not isinstance(payload, (bytes, bytearray)) else "application/pdf")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _auth_ok(self) -> bool:
                return self.headers.get("Authorization") == server.token

            def _body(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                return json.loads(raw) if raw else {}

            def do_POST(self):  # noqa: N802
                server.calls.append(("POST", self.path))
                if not self._auth_ok():
                    return self._send(401, {"message": "unauthorized"})
                body = self._body()
                if self.path == "/api/v2/template/use":
                    server._next += 1
                    envelope_id = f"envelope_mock{server._next:04d}"
                    recipients = [{"id": i + 1, "email": r["email"], "name": r.get("name", ""), "role": r.get("role", "SIGNER"), "signingStatus": "NOT_SIGNED"}
                                  for i, r in enumerate(body.get("recipients") or [])]
                    server.envelopes[envelope_id] = {"id": envelope_id, "type": "DOCUMENT", "status": "PENDING", "externalId": body.get("externalId"),
                                                     "title": body.get("title"), "recipients": recipients,
                                                     "envelopeItems": [{"id": f"{envelope_id}_item1"}]}
                    return self._send(200, server.envelopes[envelope_id])
                if self.path == "/api/v2/envelope/distribute":
                    envelope_id = body.get("envelopeId")
                    if envelope_id not in server.envelopes:
                        return self._send(404, {"message": "no such envelope"})
                    server.envelopes[envelope_id]["status"] = "PENDING"
                    return self._send(200, {"envelopeId": envelope_id, "status": "PENDING"})
                if self.path == "/api/v2/envelope/redistribute":
                    envelope_id = body.get("envelopeId")
                    if envelope_id not in server.envelopes:
                        return self._send(404, {"message": "no such envelope"})
                    recipients = body.get("recipients") or []
                    if not recipients:
                        return self._send(400, {"message": "recipients is required"})
                    server.envelopes[envelope_id].setdefault("reminders", 0)
                    server.envelopes[envelope_id]["reminders"] += 1
                    return self._send(200, {"ok": True})
                if self.path == "/api/v2/envelope/cancel":
                    envelope_id = body.get("envelopeId")
                    if envelope_id not in server.envelopes:
                        return self._send(404, {"message": "no such envelope"})
                    server.envelopes[envelope_id]["status"] = "CANCELLED"
                    return self._send(200, {"ok": True})
                if self.path == "/_test/sign":
                    # Test-only control surface (not part of Documenso's real API): mark one recipient signed,
                    # simulating what a real completed borrower signing session would report via GET envelope.
                    envelope_id, email = body.get("envelopeId"), body.get("email")
                    env = server.envelopes.get(envelope_id)
                    if not env:
                        return self._send(404, {"message": "no such envelope"})
                    for r in env["recipients"]:
                        if r["email"] == email:
                            r["signingStatus"] = "SIGNED"
                    if all(r["signingStatus"] == "SIGNED" for r in env["recipients"]):
                        env["status"] = "COMPLETED"
                    return self._send(200, {"ok": True})
                if self.path == "/_test/reject":
                    envelope_id, email = body.get("envelopeId"), body.get("email")
                    env = server.envelopes.get(envelope_id)
                    for r in env["recipients"]:
                        if r["email"] == email:
                            r["signingStatus"] = "REJECTED"
                    return self._send(200, {"ok": True})
                return self._send(404, {"message": "not found"})

            def do_GET(self):  # noqa: N802
                server.calls.append(("GET", self.path))
                if not self._auth_ok():
                    return self._send(401, {"message": "unauthorized"})
                if self.path.startswith("/api/v2/envelope/item/") and self.path.endswith("/download"):
                    item_id = self.path.split("/")[-2]
                    return self._send(200, f"%PDF-1.4 signed content for {item_id}".encode("utf-8"))
                if self.path.startswith("/api/v2/envelope/"):
                    envelope_id = self.path.rsplit("/", 1)[-1]
                    env = server.envelopes.get(envelope_id)
                    if not env:
                        return self._send(404, {"message": "no such envelope"})
                    return self._send(200, env)
                return self._send(404, {"message": "not found"})

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        host, port = self._httpd.server_address
        return f"http://{host}:{port}"

    def call_count(self, method: str, path: str) -> int:
        return sum(1 for m, p in self.calls if m == method and p == path)

    def sign(self, envelope_id: str, email: str) -> None:
        for r in self.envelopes[envelope_id]["recipients"]:
            if r["email"] == email:
                r["signingStatus"] = "SIGNED"
        if all(r["signingStatus"] == "SIGNED" for r in self.envelopes[envelope_id]["recipients"]):
            self.envelopes[envelope_id]["status"] = "COMPLETED"

    def reject(self, envelope_id: str, email: str) -> None:
        for r in self.envelopes[envelope_id]["recipients"]:
            if r["email"] == email:
                r["signingStatus"] = "REJECTED"

    def stop(self) -> None:
        self._httpd.shutdown()
        self._thread.join(timeout=5)
