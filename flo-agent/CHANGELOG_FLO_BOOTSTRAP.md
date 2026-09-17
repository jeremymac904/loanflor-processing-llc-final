# CHANGELOG_FLO_BOOTSTRAP.md

## Flo Bootstrap Pass — MiniMax Continuation

**Branches:** `flo/minimax-continuation` (work), `flo/full-project-migration` (source)

---

### Added

#### Flo Onboarding (`/flo/onboarding`)
- 5-card first-run flow: Gmail, Google Drive & Calendar, Zapier, Local Signing, Local AI
- Each card: Ready/Not Ready state, one action button, inline expansion
- Continue blocks only on missing Local AI; optional connectors don't block
- Status line: "N of 5 ready" + explicit Local AI warning
- `LANDED_KEY` redirect sends returning users to Today view

#### Real IPC setup handlers (electron/main.ts)
| Handler | Behavior |
|---------|----------|
| `hermes:flo:save-gmail` | Stores credential via `safeStorage` (DPAPI/Keychain) |
| `hermes:flo:gmail-bootstrap` | Decrypts credential on Hermes startup; injected into email process |
| `hermes:flo:google-setup` | Runs `google-workspace/setup.py --auth-url`, returns auth URL |
| `hermes:flo:google-complete` | Completes OAuth exchange with auth code |
| `hermes:flo:save-zapier` | Stores webhook URL to config |
| `hermes:flo:check-documenso` | Probes `localhost:3000/api/health` |
| `hermes:flo:start-documenso` | Auto-installs Docker (winget→MSI), starts `flo-start.ps1` |
| `hermes:flo:check-local-ai` | Probes `localhost:11434/api/tags` |
| `hermes:flo:ai-setup` | Auto-installs Ollama (winget→installer), pulls `llama3.2:3b` |

#### FloOnboarding tests (6 tests)
- Welcome heading + 5 cards render
- Continue disabled when Local AI not ready
- Continue enabled when Local AI ready
- Gmail save encrypts via safeStorage
- Zapier save writes URL
- Status line surfaces model warning

#### WVOE button
- Added to FilePanel alongside "Order Title" / "Order HOI"

### Fixed

- **Continue button disabled logic:** was `disabled={busy !== null}`, ignored `allRequiredReady`. Now `disabled={busy !== null || !allRequiredReady}`
- **test-desktop.mjs Mac binary path:** was hardcoded `Hermes.app`, now uses `PACKAGE_JSON.productName`
- **Windows x64 build on Mac:** Electron Windows dist not cached; manually extracted from `~/Library/Caches/electron/`
- **`npm run dist:win` ARM64 failure:** explicit `--x64` flag required; Electron ships no Windows ARM64 binary

### Changed

- First-run redirect: `/` → `/flo/onboarding` (not Hermes bootstrap)
- Flo Python test suite: 429/452 pass (15 pre-existing failures unchanged)

### Known limitations

- NSIS installer (`Flo-Setup-0.17.0-win-x64.exe`) requires `makensis` — needs Windows host or Wine
- Branch push blocked by GitHub SSH key not registered; clone and `git pull` on Ashley's PC
