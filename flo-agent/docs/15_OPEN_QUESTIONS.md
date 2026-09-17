# docs/15_OPEN_QUESTIONS.md

## Open questions from Flo Bootstrap Pass

### 1. NSIS installer production
**Q:** How should `Flo-Setup-0.17.0-win-x64.exe` be produced on Ashley's PC?
**Options:**
- (A) Ashley's PC has PowerShell — run `npm run dist:win:nsis` there (requires Node.js)
- (B) Provide the installer as a separate one-time task for the Windows host
- (C) Document the portable zip as sufficient; NSIS installer is cosmetic
**Status:** Open — needs Jeremy's decision

### 2. GitHub push from Mac
**Q:** SSH key not registered with GitHub, HTTPS credential prompt hangs. How to push `flo/minimax-continuation`?
**Options:**
- (A) Jeremy runs `gh auth login` once on Mac, then push works
- (B) Clone on Ashley's PC instead
- (C) Jeremy adds SSH key to GitHub account
**Status:** Open — needs Jeremy's action

### 3. Flo Signatures Mac launcher
**Q:** The Mac `Flo Signatures.app` launcher was committed in a previous pass. Should it be bundled into the Windows release? (Windows uses `flo-start.ps1` Docker compose, so N/A for Windows.)
**Status:** Resolved — Mac launcher stays Mac-only

### 4. Flo onboarding route registration
**Q:** The `/flo/onboarding` route is registered in the Flo plugin. Should it also be added to the Hermes router as a first-class route?
**Status:** Open — currently works via plugin registration; consider canonicalizing

### 5. Google OAuth: Gmail SMTP token
**Q:** Gmail uses App Password (not OAuth) for SMTP. The `gmailBootstrap` IPC decrypts and injects the App Password. Should we also support OAuth2 for Gmail read (Gmail API) in a future pass?
**Status:** Future pass — App Password is sufficient for Phase 1

### 6. Local AI: hardware detection
**Q:** `llama3.2:3b` is the conservative default. Should we detect available VRAM/RAM and suggest a larger model if hardware allows?
**Status:** Future pass — conservative default is correct for bootstrap

### 7. Test coverage: IPC handlers
**Q:** The FloOnboarding tests stub the IPC calls. Should there be Electron-level IPC tests (in `electron/**/*.test.ts`) that verify the actual safeStorage/writeFile/winget behavior?
**Status:** Future pass — stubs are sufficient for UI smoke tests; IPC integration tests need mock-free environment
