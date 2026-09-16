# Flo Recovery Guide

**Last verified:** 2026-09-15 (power outage recovery + local signing milestone)

## Quick recovery — one command

Open PowerShell in the `flo-agent` directory and run:

```powershell
.\flo-start.ps1
```

This handles everything: socket cleanup, Docker Desktop, container health, API verification, and Hermes launch. Safe to run repeatedly.

Options:
- `.\flo-start.ps1 -SkipDocker` — Docker already running, just verify and launch Hermes
- `.\flo-start.ps1 -HermesOnly` — skip Docker entirely, launch Hermes only
- `.\flo-start.ps1 -TestOnly` — run the 23 esign tests and exit

## What happens during a power outage

Three things stop and need recovery:

| Component | What stops | Auto-recovers? | Manual step |
|-----------|-----------|----------------|-------------|
| Docker Desktop | Process terminates, WSL `docker-desktop` distro goes to `Stopped` | Partially — Docker Desktop is in the Windows Run registry key so it starts at login, but **WSL may not start** and **stale Unix socket files** can crash the backend | Run `flo-start.ps1` |
| Documenso stack | All three containers stop (documenso, postgres, maildev) | Yes — `restart: unless-stopped` brings them back once Docker daemon is running | None needed if Docker starts |
| Hermes Agent | CLI process terminates, no session state persists | No — it's an interactive CLI, not a background service | `flo-start.ps1` or `hermes.exe` |

## Known post-outage issue: stale Unix sockets

**Symptom:** Docker Desktop process starts but daemon never comes up. Docker Desktop may show an error dialog: "Docker Desktop encountered an unexpected error."

**Root cause:** Power loss leaves Unix-domain socket files (`.sock`) in:
- `%LOCALAPPDATA%\Docker\run\`
- `%LOCALAPPDATA%\docker-secrets-engine\`

Docker tries to rename them to `.stale` but Windows won't allow it. The backend crashes in a loop.

**Fix (automated by `flo-start.ps1`):**
1. Kill all Docker processes
2. Shut down WSL: `wsl --shutdown`
3. Rename stale directories:
   ```powershell
   Rename-Item "$env:LOCALAPPDATA\Docker\run" "$env:LOCALAPPDATA\Docker\run.bak"
   New-Item -ItemType Directory "$env:LOCALAPPDATA\Docker\run"
   Rename-Item "$env:LOCALAPPDATA\docker-secrets-engine" "$env:LOCALAPPDATA\docker-secrets-engine.bak"
   New-Item -ItemType Directory "$env:LOCALAPPDATA\docker-secrets-engine"
   ```
4. Restart Docker Desktop
5. Manually kick WSL if needed: `wsl -d docker-desktop -- echo started`

## Component inventory

| Component | Version | Location |
|-----------|---------|----------|
| Docker Desktop | v4.90.0 | `C:\Program Files\Docker\Docker\` |
| Documenso | v2.18.0 | Docker container `flo-documenso-documenso-1` |
| PostgreSQL | 15 | Docker container `flo-documenso-database-1` |
| maildev | 2.1.0 | Docker container `flo-documenso-mail-1` |
| Hermes Agent | v0.21.0 | `.venv\Scripts\hermes.exe` |
| Python | 3.11.9 | `.venv\Scripts\python.exe` |
| uv | WinGet package | `C:\Users\ashle\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_*\uv.exe` |

## Ports

| Port | Service | Purpose |
|------|---------|---------|
| 3000 | Documenso | Signing web UI + API |
| 1080 | maildev | Test email web inbox |
| 1025 | maildev (SMTP) | Test email delivery (internal) |
| 5432 | PostgreSQL | Database (Docker internal, not exposed to host) |

## Credentials

Stored in `deploy/documenso/.env.flo` (gitignored):
- `DOCUMENSO_API_URL` — `http://localhost:3000`
- `DOCUMENSO_API_TOKEN` — API token (no "Bearer " prefix)
- `DOCUMENSO_LOE_TEMPLATE_ID` — Template ID 1

Admin login: `ashley@lfprocessing.net` at `http://localhost:3000`

## Auto-start at boot

Two layers ensure Flo Signatures starts after login:

1. **Docker Desktop** — registered in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, starts
   automatically at Windows login. The three Documenso containers have `restart: unless-stopped` and start
   once Docker daemon is ready.

2. **"Flo Signatures Autostart" Task Scheduler task** — runs `flo-autostart.ps1` hidden at login. This
   script cleans stale sockets, waits for Docker Desktop (starts it if missing), kicks WSL if stuck, and
   verifies all three containers are running. Logs to `flo-autostart.log` in the project directory.

**Hermes does not auto-start** — it's an interactive CLI. Run `.\flo-start.ps1` or `.\.venv\Scripts\hermes.exe` when needed.

## Programmatic health check (esign adapter)

`plugins/flo-team/esign.py` includes `check_health()` and `ensure_healthy()` for automated recovery.
When called, these functions:

1. Check if the Documenso API is reachable at the configured URL
2. If not, attempt auto-recovery (Windows only): clean stale sockets → start Docker Desktop → kick WSL → `docker compose up -d` → wait for API
3. Return a result with `healthy` (bool), `message` (Ashley-facing, no Docker jargon), and `recovered` (bool)

**Tested live (2026-09-15):** Stopped the Documenso container, called `check_health()` — it detected the
failure, ran auto-recovery, and the API was back in 15.6 seconds. The Ashley-facing message on recovery:
*"Flo Signatures wasn't running. It's been started."* On failure: *"Flo Signatures isn't responding. Try
opening it from the Start Menu."*

`ensure_healthy()` wraps `check_health()` and raises `EsignError` if recovery fails — use it as a guard
before any signing operation.

## Data persistence

- **PostgreSQL data**: Docker named volume `flo-documenso_database` — survives container restarts and Docker Desktop restarts. The underlying disk image is at `%LOCALAPPDATA%\Docker\wsl\disk\docker_data.vhdx`.
- **Documenso config**: Templates, API tokens, user accounts — all in PostgreSQL, all survive restarts.
- **Hermes state**: Local to `.flo/` directory in the project — profiles, config, knowledge, team data.
- **Plugin code**: `plugins/flo-team/` — source files, not affected by power outages.

## Verification after recovery

Run the test suite to confirm nothing was corrupted:

```powershell
.\flo-start.ps1 -TestOnly
```

Expected: 23 tests pass in ~11 seconds.

For a live API check:

```powershell
$env = Get-Content deploy\documenso\.env.flo
$token = ($env | Select-String "DOCUMENSO_API_TOKEN=").Line -replace "DOCUMENSO_API_TOKEN=",""
Invoke-RestMethod -Uri "http://localhost:3000/api/v2/template/1" -Headers @{"Authorization"=$token}
```

## Cleanup

The `.bak.*` directories created during socket cleanup can be safely deleted once Docker is running:

```powershell
Get-ChildItem "$env:LOCALAPPDATA\Docker" -Directory -Filter "run.bak.*" | Remove-Item -Recurse -Force
Get-ChildItem "$env:LOCALAPPDATA" -Directory -Filter "docker-secrets-engine.bak.*" | Remove-Item -Recurse -Force
```
