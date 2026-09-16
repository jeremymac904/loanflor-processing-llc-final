"""Keep credential-bearing MCP URLs out of every log this process writes.

Two layers, both cheap and idempotent:

1. **Shared, lowest level**: ``agent.redact.register_credential_url_hosts``
   (small core patch) marks hosts whose URLs carry credentials in the query
   string — ``mcp.zapier.com`` by default plus every ``mcp_servers.*.url``
   host in the active config. ``redact_sensitive_text`` then strips
   ``token=`` / ``key=`` / ``auth=`` … values for those hosts in the *default*
   pass, which is what upstream's ``RedactingFormatter`` runs on every file
   handler (agent.log, gateway.log, gui.log, desktop.log via the queue
   listener) and on exceptions/tracebacks formatted through it.
2. **Belt and braces**: a ``logging.Filter`` on the root logger and every
   existing handler that rewrites the record's message/args in place, so a
   handler that was attached without the redacting formatter (a plugin's own
   handler, ``logging.basicConfig`` in a helper process, stderr in a test)
   cannot print the token either.

The Flo plugin installs both on load; the installer and the source-fetch
script call :func:`install` before they log anything. Tests use a fake token.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional
from urllib.parse import urlsplit

DEFAULT_HOSTS = ("mcp.zapier.com",)
_MARK = "_flo_redaction_filter"


def _hosts_from_config(config: Optional[dict]) -> list[str]:
    hosts: list[str] = []
    servers = (config or {}).get("mcp_servers") if isinstance(config, dict) else None
    if isinstance(servers, dict):
        for entry in servers.values():
            url = entry.get("url") if isinstance(entry, dict) else None
            if isinstance(url, str) and "://" in url:
                host = urlsplit(url).hostname
                if host:
                    hosts.append(host)
    return hosts


class _RedactFilter(logging.Filter):
    """Redact the record before any handler formats it (msg + args + exc text)."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - logging API
        try:
            from agent.redact import redact_sensitive_text

            if isinstance(record.msg, str):
                record.msg = redact_sensitive_text(record.msg, redact_url_credentials=True)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: (redact_sensitive_text(v, redact_url_credentials=True) if isinstance(v, str) else v) for k, v in record.args.items()}
                else:
                    record.args = tuple(redact_sensitive_text(a, redact_url_credentials=True) if isinstance(a, str) else a for a in record.args)
            # Tracebacks: a handler without the redacting formatter renders
            # exc_info itself, so pre-render and redact it here.
            if record.exc_info and not record.exc_text:
                record.exc_text = redact_sensitive_text(logging.Formatter().formatException(record.exc_info), redact_url_credentials=True)
                record.exc_info = None
            elif record.exc_text:
                record.exc_text = redact_sensitive_text(record.exc_text, redact_url_credentials=True)
        except Exception:  # noqa: BLE001 - a broken filter must never drop or crash logging
            pass
        return True


def install(config: Optional[dict] = None, extra_hosts: Iterable[str] = ()) -> dict:
    hosts = list(DEFAULT_HOSTS) + _hosts_from_config(config) + [h for h in extra_hosts if h]
    registered = 0
    try:
        from agent.redact import register_credential_url_hosts

        registered = register_credential_url_hosts(hosts)
    except Exception:  # noqa: BLE001 - older core without the patch: the filter below still applies
        registered = -1
    root = logging.getLogger()
    targets = [root] + list(root.handlers)
    for logger_name in ("httpx", "httpx2", "httpcore", "mcp", "mcp.client", "mcp.client.streamable_http", "openai", "urllib3"):
        targets.append(logging.getLogger(logger_name))
    added = 0
    for target in targets:
        if not any(getattr(f, _MARK, False) for f in target.filters):
            flt = _RedactFilter()
            setattr(flt, _MARK, True)
            target.addFilter(flt)
            added += 1
    return {"hosts": sorted(set(hosts)), "core_registered": registered, "filters_added": added}
