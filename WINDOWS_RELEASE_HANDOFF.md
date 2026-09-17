# Windows Release Handoff — for Claude on Ashley's PC

This file is specifically so Claude can spend **MINIMAL usage** on
Ashley's PC. Everything Mac-side is committed; everything below is
machine-specific.

## Release branch + commit

- **Branch:** `flo/minimax-continuation`
- **Latest commit on branch:** `3aff738` (build fixes for Mac→Windows cross-build)
- **Prior commits on the branch:**
  - `2cbd85e` ASHLEY_PRODUCTION_ACCEPTANCE.md
  - `29b03c1` desktop: drop loan documents onto the open file view
  - `d20f08e` gmail: route connector messages into Flo condition/CTC handlers
  - `61ad4f1` windows: opt-in Flo Stage in install.ps1
  - `ce8ddee` gmail: condition email → Flo proposes → Ashley confirms
  - `f3e418e` conditions: CTC readiness + lender CTC confirmation
  - `23d41ae` conditions: borrower/LO one-click request + Waiting state
  - `81bdf6d` conditions: normalize UW conditions
  - `6ff0845` conditions: auto-clear high-confidence matches
  - `5371a2b` mac-flo-signatures: minimal .app launcher for Ashley
  - `0e61c61` tsconfig: scope npm run typecheck to website only
  - `da0970f` gmail: route connector messages (prior milestone)

## Installer artifact

The Mac-side build produces the **Windows binary directly** but cannot
produce the wrapped installer without Wine (electron-builder's wix/candle
tools run as Windows executables via Wine on Mac).

Two paths from here:

### Path A — Build the installer on a Windows machine (preferred)

1. Clone the repo at the commit above on a Windows host with Node 22+ and
   Python 3.11+ installed.
2. `cd flo-agent\apps\desktop && npm ci && npm run dist:win:nsis`
3. Output: `flo-agent\apps\desktop\release\Flo-Setup-<ver>-win-x64.exe`

That's the file Ashley installs. ~85 MB.

### Path B — Install Wine on Mac and rebuild

1. `brew install --cask wine-stable` (or use CrossOver)
2. `cd flo-agent\apps\desktop && npm run dist:win:nsis`
3. Output: same file as Path A.

**Don't waste time here.** Path A is faster if you have a Windows
machine; otherwise Path B. Either way, the wrapped installer lands in
`release/Flo-Setup-<ver>-win-x64.exe`.

### What ships *inside* that installer

- `Flo.exe` (the cross-compiled Electron binary, 100+ MB unpacked)
- `Flo Signatures.lnk` Start Menu shortcut (created by
  `Install-FloSignaturesShortcut` during `Stage-FloTeam`)
- The Flo brand identity (icon, productName, appId `com.example.flo`)
- All seven profiles: `ashley`, `flo`, `malcolm`, `sage`, `chadwick`,
  `whisper`, `franklin` — placed at `%LOCALAPPDATA%\hermes\profiles\`
- The local workspace root at `%LOCALAPPDATA%\hermes\flo\workspace\`
  with subfolders for `intake / aus / income / assets / title /
  insurance / conditions / orders / correspondence / exports`
- The `Start Menu → Programs → Flo Signatures` shortcut pointing at
  `flo-start.ps1` for one-click local Documenso recovery

### What does NOT ship

- Secrets (no Ashley credentials, no app passwords)
- Borrower data
- Test databases
- The git repo (only the build artifacts)
- `node_modules`, `.venv`
- Jeremy's dev environment

## Final acceptance test Claude must run on Ashley's PC

```bash
# 1. Verify installer artifact exists & is recent
ls "$HOME/Downloads/Flo-Setup-0.17.0-win-x64.exe"
   # should be there, dated today, ~85 MB

# 2. Double-click the installer; follow the wizard.
#    Expected: NSIS finishes, desktop shortcut "Flo" appears,
#    Start Menu > Programs > Flo Signatures appears.

# 3. Launch Flo from the desktop shortcut.
#    Expected: Welcome to Flo 💚 / Connect Gmail / Drive/Calendar /
#    Zapier / Local Signing / Local AI.

# 4. Click each connector card:
#    - Gmail: enter Ashley's address + her 16-char app password
#    - Google Drive & Calendar: click the docs-link card to surface
#      the URL, run the existing google-workspace OAuth dance in Chrome
#      (her Google credentials)
#    - Zapier: enter her Zapier MCP URL
#    - Local Signing: click "Set Up" — if Docker Desktop isn't
#      installed, the card reports "Local signing isn't running"
#      and stays there; install Docker, click Re-check
#    - Local AI: click "Re-check" — Ollama probe
#    Expected: every card that succeeds shows "Ready / Connected".
#    Cards that aren't ready stay in their honest "Not running" /
#    "Not signed in" state.

# 5. Click Continue. Expected: Today loads with the standard
#    "Flo" branding — Top 3 / Fastest win / Biggest risk / Needs you
#    / Waiting counts. No Hermes chrome. No provider dropdown.

# 6. From the file browser, drag 3-5 synthetic loan PDFs onto the
#    open file view of a test loan.
#    Expected: each file shows up under "Documents" within a couple
#    of seconds. Classification / category inferred. No errors.

# 7. Click "Ask Flo" → "Prep this file." Expected: Flo returns a
#    Malcolm-style summary in plain English — readiness, missing items,
#    AUS status, income status, asset status, best next move.
#    No task IDs. No JSON.

# 8. Click "[Why?]" on any item. Expected: Sage answers with a
#    real source section; SOURCE_GAP is shown plainly when no source
#    is active.

# 9. Restart Flo. Restart Docker (if Local Signing is set up).
#    Restart the PC if practical. Expected: Flo comes back, profiles
#    and documents survive, Local Signing comes back automatically.

# 10. Run npm-installed Flo from the desktop, verify the version
#     stamp in Settings → Flo matches 0.17.0.
```

If any of steps 5–9 fail, the bug is in the Mac-side code — fix it
on the Mac (push to the branch), then `git pull` on Ashley's PC and
restart Flo. No installer rebuild needed for content fixes.

If step 4 (a connector) fails because of a machine issue (Docker not
installed, no Ollama running, Gmail OAuth not authorized), Ashley
clicks `Continue` and finishes the other cards. The disconnected card
stays in its honest state.

## Known limitations (machine-specific)

- **Docker Desktop** is required for Local Signing + (optionally) Local
  AI. If it's missing, the cards say so in plain English.
- **Ollama** is recommended for Local AI. Without it, Ashley needs to
  pick a cloud model in the Advanced provider settings — which is
  intentionally hidden by the Flo first-run flow.
- **Gmail app password** requires 2-Step Verification on Ashley's
  Google Account and a one-time 30-second setup. Ashley's account, her
  password, encrypted on her PC.

## What Claude should NOT do on Ashley's PC

- **Build the installer.** The artifact is committed; pull it from the
  Mac output, or rebuild on a Windows host. Don't waste Claude usage
  on build infrastructure on Ashley's PC.
- **Install Docker / Ollama.** Those are one-click installers that
  Ashley runs.
- **Edit Flo's code.** The Mac-side code is finished for this pass.
  Anything that needs code change means a real bug — fix it on the Mac,
  commit, pull.
- **Generate app passwords.** Only Ashley can do that — it's her
  Google account.
- **Add a feature.** This is the finish pass. New work is the next
  milestone.

## Final state

`flo/minimax-continuation` @ `3aff738` is what Ashley's PC pulls.
Everything machine-specific is in `ASHLEY_INSTALL_CHECKLIST.md`.
Everything Claude-side is in this file. Nothing else.

End of handoff.
