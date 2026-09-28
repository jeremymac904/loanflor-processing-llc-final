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
- Source commit: `62108b86ac1f797a95b2fd2d6c8863917162024c`
- Candidate tag: `flo-ashley-rc5`
- Packaged path: `%USERPROFILE%\\Downloads\\Flo-source-clean-20260928\\loanflor-processing-llc-final-flo-codex-polish\\flo-agent\\apps\\desktop\\release\\win-unpacked\\Flo.exe`
- User data preserved at `%APPDATA%\\Flo`

## Verified

- Packaged renderer opens without the React maximum-update-depth or uncached-snapshot loop.
- Onboarding, Today, Pipeline, Approvals, and Flo Chat routes mount.
- Docker Desktop starts; Documenso and Postgres are healthy; Flo shows Local Signing Ready.
- Ollama is running locally with three models visible; direct local completion passed.
- Flo Pet canvas is mounted and labelled `Flo pet`.
- Flo exposes the voice controls.
- Gmail remains Connected and stored credentials remain encrypted by Electron safeStorage.
- Local/custom Ollama endpoint was connected through Flo's provider UI; Gateway reported Ready.

## Not completed / remaining boundaries

- Google Drive/Calendar: Flo currently requires an OAuth client secret file, and none is present on this PC. The Windows Python alias defect is fixed; no browser consent can begin until the project-owned client secret is supplied through the intended setup path.
- Zapier: no MCP URL was entered; no secret was exposed to chat or logs.
- Voice: Windows reported no microphone device. Audio endpoints present on this PC are output devices only.
- A real local Flo UI completion did return after connecting the local Ollama endpoint and restarting. Synthetic loan creation, drag/drop documents, Malcolm, Sage, conditions, orders, Gmail condition/CTC email flows, and local signing workflow were not claimed as passed because the loan workflow was not completed end-to-end during this run.
- A Windows restart was not performed during this run.

## Runtime fix

- `apps/desktop/electron/main.ts`: Google setup now resolves the managed Hermes Python interpreter on Windows instead of invoking the Microsoft Store `python3` alias.
