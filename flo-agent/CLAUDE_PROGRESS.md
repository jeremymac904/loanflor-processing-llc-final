# CLAUDE_PROGRESS.md — Flo Bootstrap Pass (MiniMax Continuation)

**Branch:** `flo/minimax-continuation`
**Commit:** `de04fd1a2dc2ac42b640bc813a687c9ffe2f7dd3`
**Status:** Ready for Ashley's PC
**Date:** 2026-09-17

---

## What was done

### Flo Onboarding (first-run experience)
- New route `/flo/onboarding` — replaces Hermes bootstrap as Ashley's first screen
- 5 connector cards: Gmail, Google Drive & Calendar, Zapier, Local Signing, Local AI
- Each card has Ready/Not Ready state + one action button
- Continue button blocks only on missing Local AI (optional connectors don't block)
- Status line shows "N of 5 ready" + explicit Local AI warning
- WVOE button added to FilePanel alongside Order Title / Order HOI

### Real setup flows (no manual steps for Ashley)
- **Gmail:** `saveGmail` IPC stores credentials via Electron `safeStorage` (DPAPI/Keychain); `gmailBootstrap` IPC decrypts on Hermes backend startup — credential survives app restart, never plaintext
- **Google Drive/Calendar:** `googleSetup` + `googleComplete` IPC invokes the existing `google-workspace/setup.py --auth-url` → opens browser → collects code inline → completes exchange. One sign-in covers Drive + Calendar + (via the same token) Gmail SMTP
- **Local Signing:** `signingSetup` IPC detects Docker Desktop; if missing, offers auto-install via winget → MSI. Handles Windows reboot requirement. Starts existing `flo-start.ps1`, polls `localhost:3000/api/health`
- **Local AI:** `aiSetup` IPC detects Ollama; if missing, installs via winget → `OllamaSetup.exe`. Pulls `llama3.2:3b` (project conservative default). Configures Flo to use local model. Falls back to cloud model from Settings → Advanced
- **Zapier:** `saveZapier` IPC stores webhook URL to config file

### Tests
- `FloOnboarding.test.tsx` — 6 tests, all passing:
  - Renders welcome + 5 cards
  - Continue disabled when Local AI not ready (bug: was `disabled={busy !== null}`, fixed to `disabled={busy !== null || !allRequiredReady}`)
  - Save Gmail encrypts credential
  - Save Zapier writes URL
  - Status line surfaces model warning
  - Continue enabled when Local AI ready

### Build fixes
- `test-desktop.mjs`: use `PACKAGE_JSON.productName` for Mac binary path (was hardcoded `Hermes.app`, broke on `Flo.app`)
- `npm run dist:win` fails on ARM64: electron-builder tries `win-arm64` but Electron has no Windows ARM64 binary → use `npm run builder -- --win dir --x64`
- Electron Windows dist not cached locally: manually extracted from `~/Library/Caches/electron/.../electron-v40.10.2-win32-x64.zip` into `node_modules/electron/dist/`

### Release artifact
- `release/ashley/Flo-0.17.0-win-x64-portable.zip` — 483 MB, SHA256 `43eb159a0821aff99aea20eb97f8bcc71e918cee8906e27e3c1e2172b8d847f2`
- Built from `de04fd1`, includes all IPC handlers, onboarding UI, Flo branding
- `install-stamp.json` pins to `flo/minimax-continuation @ de04fd1`

---

## Test results

| Suite | Result |
|-------|--------|
| Flo Python (tests/flo/) | 429/452 — 15 pre-existing failures in test_idempotency.py + test_provider_failover.py |
| Desktop UI (FloOnboarding) | 6/6 pass |
| TypeScript (apps/desktop/) | Clean (pre-existing TS errors in preview-file/chrome/artifacts/index are unrelated) |
| Mac fresh build | `Flo.app` + DMG produced |
| Windows x64 build | `Flo.exe` (204 MB) + portable zip produced |

---

## One remaining item outside Mac scope

**NSIS installer** (`Flo-Setup-0.17.0-win-x64.exe`) requires `makensis` — Windows PE binary. Wine is not installable on this Mac (needs sudo). Resolution: run `npm run dist:win:nsis` on Ashley's PC (Windows host or Wine-enabled Mac).

---

## Branch push status
- **Push blocked:** SSH key not registered with GitHub, HTTPS credential prompt hangs in non-interactive shell
- **Branch is ready locally** — clone `flo/minimax-continuation` on Ashley's PC and run `git pull` to get latest
