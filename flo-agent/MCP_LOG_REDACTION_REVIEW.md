# MCP URL / token log redaction review (2026-09-08)

## Root cause

Upstream `agent/redact.py::redact_sensitive_text` deliberately passes web-URL query parameters through in the default (log) pass so OAuth callbacks and magic links survive; strict query redaction exists only as an opt-in (`redact_url_credentials=True`, used at explicit egress boundaries). `RedactingFormatter` (used by every Hermes file handler) therefore left `https://mcp.zapier.com/api/v1/connect?token=…` intact in `agent.log`, `desktop.log` and profile logs whenever `httpx`/`httpx2`/`mcp.client` logged a request line, a retry, or an exception.

## Fix — lowest shared level

1. **Core patch (small, upstream-mergeable)** in `agent/redact.py`: a registry `register_credential_url_hosts(hosts)`; in the default pass, URLs whose host is registered get credential-named query params masked (`token=***`) via the existing `_redact_query_string`, without changing behaviour for any other host. Covers every path that formats through `RedactingFormatter`: connection setup, HTTP exceptions/tracebacks, debug lines, retries, the desktop log queue listener.
2. **Plugin layer** `plugins/flo-team/redaction.py::install(config)`: registers `mcp.zapier.com` plus every `mcp_servers.*.url` host from the active config, and adds a `logging.Filter` to the root logger, all root handlers and the HTTP/MCP client loggers that redacts `msg`, `args` and pre-rendered `exc_text` with the strict URL redaction. This catches handlers that were attached without the redacting formatter (bare `StreamHandler`, `basicConfig` in helper processes). Installed by the Flo Team plugin at load; the installer installs it before it logs anything; the source-fetch script does not log URLs.
3. The `httpx`/`httpx2`/`httpcore`/`mcp.client.streamable_http` loggers are raised to WARNING by the plugin (belt and braces from the previous pass).

## Test (`tests/flo/test_mcp_log_redaction.py`, synthetic fake token)

- Registry semantics: registered host masked, unregistered host untouched, userinfo/port/fragment variants masked.
- Real `hermes_logging.setup_logging` into a temporary Hermes home; the fake token logged at WARNING/ERROR/exception through six logger names plus a bare stream handler; every `*.log/*.txt/*.jsonl/*.out` under the home scanned; the test fails if the complete secret appears anywhere. Result: **no hits**; bare handler output shows `token=***`.
- Installer run with `FLO_ZAPIER_MCP_URL=<fake>`: stdout/stderr and all logs clean; the URL appears only in the installed profile `config.yaml` (its intended home).

The real token was never used in tests. The token-bearing lines written before this fix were scrubbed from this machine's logs in the previous pass.

## Residual

Processes that never load the Flo Team plugin and are started without the installer (e.g. the default profile's plain `hermes` CLI) still rely on the core patch alone, which now covers `mcp.zapier.com`; other MCP hosts are covered once any Flo process has read the config (the registry is per process). Recommend upstreaming the host registry and having `tools/mcp_tool.py` register hosts as servers are loaded.
