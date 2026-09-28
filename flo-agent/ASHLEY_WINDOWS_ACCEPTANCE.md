# Ashley Windows Acceptance

Date: 2026-09-28

## Machine

- Windows 11 Pro x64
- 31.2 GB RAM reported
- AMD Radeon(TM) Graphics reported; Ollama used CPU fallback because the installed driver is too old for the configured GPU path
- Docker Desktop installed and running
- WSL2 available
- Python 3.11 managed by Hermes
- Node.js and Git installed

## Flo build

- Branch: `flo/codex-polish`
- Source commit: `3c79522a3298819e2381f13a7e800218848db08d`
- Candidate tag: `flo-ashley-rc6`
- Packaged path: `%USERPROFILE%\\Downloads\\Flo-source-clean-20260928\\loanflor-processing-llc-final-flo-codex-polish\\flo-agent\\apps\\desktop\\release\\win-unpacked\\Flo.exe`
- User data preserved at `%APPDATA%\\Flo`
- Portable ZIP: `C:\\Users\\ashle\\Downloads\\Flo-0.17.0-win-x64-portable-rc6.zip`
- Portable ZIP SHA256: `1AD2B200F44888BCFF13B8BBCAC3F3670F4A29782444E58F2FD5810248656D2F`

## Verified

- Packaged renderer opens without the React maximum-update-depth or uncached-snapshot loop.
- Onboarding, Today, Pipeline, Approvals, and Flo Chat routes mount.
- Docker Desktop starts; Documenso and Postgres are healthy; Flo shows Local Signing Ready.
- Ollama is running locally with three models visible; direct local completion passed.
- Flo Pet canvas is mounted and labelled `Flo pet`.
- Flo exposes the voice controls.
- Gmail persistence passed with synthetic credentials: Flo wrote `%APPDATA%\\Flo\\flo-secrets.json` using Electron safeStorage, the plaintext secret was absent, and the packaged app reported Gmail configured after a full quit/relaunch.
- Local/custom Ollama endpoint was connected through Flo's provider UI; Gateway reported Ready.
- A clean RC6 packaged cold start reached a healthy gateway with no renderer-loop warning in the desktop log.

## Not completed / remaining boundaries

- Google Drive/Calendar: Flo currently requires an OAuth client secret file, and none is present on this PC. The Windows Python alias defect is fixed; no browser consent can begin until the project-owned client secret is supplied through the intended setup path.
- Zapier: no MCP URL was entered; no secret was exposed to chat or logs.
- Voice: Windows reported no microphone device. Audio endpoints present on this PC are output devices only.
- A `Johnson-Test` workspace is present in the local Flo Team workspace store, created with fake data only. The Ashley-facing creation prompt did not complete: the packaged Flo profile remained at `Waking up` with the local model session, so this is not counted as a UI workflow pass.
- Ten synthetic PDFs were created at `C:\\Users\\ashle\\Documents\\Flo-Synthetic-Johnson-Test` (1003, credit report, AUS, paystub, W-2, bank statement, purchase contract, HOI, title, and condition letter). Native Explorer drag/drop could not be verified because the available Windows UI automation surface did not expose Explorer, and the app's drop handler depends on a real native file path.
- Malcolm, Sage, conditions, missing-document requests, orders, Gmail condition/CTC routing, and end-to-end local signing were not claimed as passed because the Ashley-facing Flo session/upload path did not complete. Local Signing readiness is verified, but a signed PDF was not produced in this run.
- A Windows restart was not performed during this run.

## Runtime fix

- `apps/desktop/electron/main.ts`: Google setup now resolves the managed Hermes Python interpreter on Windows instead of invoking the Microsoft Store `python3` alias.
- `apps/desktop/electron/flo-safe-storage.ts`: packaged Windows now uses the imported Electron safeStorage service rather than assuming it exists on `globalThis`.
- `apps/desktop/electron/gmail-persistence.test.ts`: regression coverage for safeStorage resolution and unavailable encryption.
