# docs/14_DECISION_LOG.md

## Decisions made during Flo Bootstrap Pass (MiniMax Continuation)

### Onboarding: Continue button blocking rule
**Decision:** Continue blocks only when Local AI is not configured. Gmail, Drive, Zapier, Signing are nice-to-have and don't block.
**Rationale:** Ashley should be able to use Flo chat immediately after installing. Optional integrations can be completed later from Settings.
**Date:** 2026-09-17

### Gmail credential storage
**Decision:** Use Electron `safeStorage` (DPAPI on Windows, Keychain on Mac) for Gmail App Password. Never store in env vars or plaintext.
**Rationale:** Credentials must survive app restarts without being in Git or plain config files. `gmailBootstrap` IPC decrypts on Hermes backend startup and injects into the email process only.
**Date:** 2026-09-17

### Google OAuth: reuse existing setup.py
**Decision:** `googleSetup` + `googleComplete` IPC invokes the existing `google-workspace/setup.py --auth-url` and `--auth-code` rather than building a parallel OAuth flow.
**Rationale:** The existing Python script is the canonical Google auth authority. Reusing it avoids two OAuth implementations and ensures consistency.
**Date:** 2026-09-17

### Local AI default model: llama3.2:3b
**Decision:** Auto-install `llama3.2:3b` as the default local model.
**Rationale:** Small enough to run on modest hardware. Does not download a 30 GB model blindly. Falls back to cloud model from Settings → Advanced.
**Date:** 2026-09-17

### Local Signing: winget first, MSI fallback
**Decision:** Docker and Ollama auto-install uses `winget` first, falls back to direct MSI/exe download.
**Rationale:** Respects the Windows package manager. Official Docker/Ollama installers are the fallback.
**Date:** 2026-09-17

### One Google sign-in for Drive + Calendar + Gmail SMTP
**Decision:** Drive and Calendar share the same Google OAuth token. Gmail uses its own App Password flow (separate auth mechanism per Google's security model).
**Rationale:** Google's OAuth scopes cover Drive/Calendar; Gmail requires an App Password for SMTP. Combining them into one "Google Workspace" card with Drive/Calendar status is sufficient.
**Date:** 2026-09-17

### NSIS installer requires Windows host or Wine
**Decision:** Cross-compiling the NSIS installer from Mac ARM64 is not practical without Wine (and Wine install requires sudo).
**Resolution:** Portable zip is the Mac-side deliverable. NSIS installer produced on Ashley's PC or a Windows host.
**Date:** 2026-09-17
