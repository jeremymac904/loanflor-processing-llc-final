# Windows Release Handoff — Claude on Ashley's PC

## What you do (5 steps total)

1. **Install Docker Desktop and Ollama on Ashley's PC**
   - Open `https://www.docker.com/products/docker-desktop/` in browser → Download → Run installer → Restart if asked
   - Open `https://ollama.com/download` → Download for Windows → Run installer
   - These are the ONLY manual installations Ashley needs.

2. **Unzip the release**
   - Right-click `Flo-0.17.0-win-x64-portable.zip` → Extract All → e.g. `Desktop\Flo`
   - **Important:** extract first, then double-click `Flo.exe` from inside the extracted folder. Don't run from inside the zip.

3. **Run Flo**
   - Double-click `Flo.exe`
   - If Windows SmartScreen blocks: **More info → Run anyway**
   - Flo opens to the onboarding welcome screen (NOT a developer setup)

4. **Drive the onboarding**
   - Click through each card; Flo runs the setup itself:
     - Connect Google → opens browser, Ashley signs in, pastes code
     - Connect Gmail → Ashley enters Gmail + App Password, Flo encrypts via safeStorage
     - Connect Zapier → Ashley pastes webhook URL
     - Set Up Local Signing → Flo detects Docker, brings up Documenso
     - Set Up Local AI → Flo detects Ollama, installs default model

5. **Click Continue** — Ashley is in Flo.

## Smoke test (after Continue)

- [ ] Flo opens to Today view, NOT Hermes bootstrap
- [ ] Settings → Advanced → Local AI shows the model as Ready
- [ ] Gmail connector card on Settings shows Connected
- [ ] WVOE button appears in FilePanel
- [ ] Local Signing health is green at http://localhost:3000/api/health

## What you do NOT do

- Do NOT clone the source repository.
- Do NOT run `npm install` or any build commands.
- Do NOT run install.ps1 or any PowerShell setup scripts by hand.
- Do NOT edit any code.
- Do NOT set environment variables.
- Do NOT install team profiles manually — Flo's onboarding creates them.
- Do NOT run `docker compose` by hand — Flo drives the stack.
- Do NOT install Ollama manually if Flo already handled it.

If Flo's onboarding successfully completes all five cards, the release is working.

## What to do if a card stays "Not Set Up"

1. The card shows a specific error in the UI (red banner at top).
2. Read the error to Ashley in plain language.
3. If it's a network/auth issue: walk Ashley through the failed step.
4. If it's a code issue: report the exact error text. Do not edit code to "fix" it.

## Artifact inventory

| File | What it is |
|------|-----------|
| `Flo-0.17.0-win-x64-portable.zip` | Complete Windows portable build (Flo.exe + Chromium + all assets) |
| `ASHLEY_INSTALL_CHECKLIST.md` | Card Ashley can use herself |
| `WINDOWS_RELEASE_HANDOFF.md` | This document |
| `SHA256.txt` | Checksum for the zip |

## Source branch

The release is built from `flo/minimax-continuation @ fb771df` (tagged `flo-ashley-rc1`).

Ashley does NOT need to clone this branch. The portable build is self-contained.
