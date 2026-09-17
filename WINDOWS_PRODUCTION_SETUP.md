# Flo Windows Production Setup

Audience: Jeremy building/releasing on the Mac; Ashley installing on her
Windows PC.

Goal: a single artifact (`Flo Setup <version>.exe`) that gives Ashley a
working Flo in five clicks and no developer exposure.

```
1. Install Flo
2. Launch Flo
3. Sign into Google
4. Connect Zapier
5. Done
```

Everything Ashley does must be in the UI. Anything Jeremy builds must
keep the Mac dev machine and Ashley's PC isolated — no shared
credentials, no shared state, no Mac-only paths leaking into the
installer.

---

## 1. What's already wired

The macOS/Linux/Windows code path is already in `flo-agent/`. Ashley's
PC doesn't need any of this source — it gets the compiled artifact.

| Piece | Path | Status |
|---|---|---|
| Electron shell + React renderer | `flo-agent/apps/desktop/` | ✅ rebranded to Flo (productName, appId `com.example.flo`, `protocols.schemes: [flo]`) |
| Flo Team profiles (Ashley + 6 specialists) | `flo-agent/.flo/profile/{ashley,flo,malcolm,sage,chadwick,whisper,franklin}` | ✅ ready to install |
| Ashley profile installer | `flo-agent/scripts/flo/install_ashley_profile.py` | ✅ works on Linux/macOS, runs on Windows via uv |
| Flo Team installer | `flo-agent/scripts/flo/install_flo_team.py` | ✅ same |
| Documenso local stack (Postgres + Documenso + maildev) | `flo-agent/deploy/documenso/docker-compose.yml` | ✅ pinned `documenso:v2.18.0` |
| Windows recovery script | `flo-agent/flo-start.ps1` + `flo-agent/flo-autostart.ps1` | ✅ already used on Ashley's Windows dev box |
| Installer pipeline | `flo-agent/scripts/install.ps1` (Windows) / `flo-agent/scripts/install.sh` (macOS/Linux) | ✅ supports `-IncludeDesktop` |
| Build commands | `npm run dist:win:nsis` | ✅ produces `release/Flo-Setup-<ver>-win-<arch>.exe` |
| First-run gate | `flo-agent/apps/desktop/electron/first-run-setup-gate.ts` | ✅ wired; needs Flo-specific cards (this milestone) |

---

## 2. What this milestone adds

| Change | Where | Why |
|---|---|---|
| `-IncludeFlo` switch | `flo-agent/scripts/install.ps1` | Opt-in flag so the Flo Stage runs only on Flo installers, never on a stock Hermes install. |
| `Stage-FloTeam` | `flo-agent/scripts/install.ps1` | Runs `install_ashley_profile.py` + `install_flo_team.py`, creates local workspace root. |
| `Install-FloTeamProfiles` | `flo-agent/scripts/install.ps1` | Worker function. |
| `Install-FloSignaturesShortcut` | `flo-agent/scripts/install.ps1` | Creates `Start Menu → Programs → Flo Signatures.lnk` → `flo-start.ps1`. |
| `WINDOWS_PRODUCTION_SETUP.md` | repo root | This document. |

The Flo Stage is **opt-in** with `-IncludeFlo`. The Flo desktop installer
always passes it; the stock Hermes CLI one-liner (`irm | iex`) does not
— that keeps Ashley's SOUL.md from accidentally landing in someone
else's checkout.

---

## 3. Installer build (Jeremy's Mac → Ashley's PC)

### One-time Mac setup

```bash
# 1. Clone the repo (already done on this Mac).
cd /Users/jeremymcdonald/Desktop

# 2. Install dependencies (already done — see repo root install steps).
cd loanflor-processing-llc-final/flo-agent/apps/desktop
npm ci

# 3. Confirm the build chain works for Windows from macOS.
#    electron-builder can target Windows from macOS via wine OR
#    via a native Windows runner. For an unsigned dev build, macOS
#    produces an NSIS installer that runs on Windows out of the box
#    (the resulting .exe does NOT need code signing for Ashley's use).
npm run dist:win:nsis
```

The output lands in `flo-agent/apps/desktop/release/`:

```
release/
  Flo-Setup-0.17.0-win-x64.exe       ← ship this to Ashley
  Flo-Setup-0.17.0-win-x64.exe.blockmap
  win-unpacked/                      ← raw files (debug only)
  ...
```

**Artifact to send Ashley:** `release/Flo-Setup-0.17.0-win-x64.exe`.

### Optional: code signing

For Ashley's day-to-day use an unsigned build is fine (Windows shows
"Unknown publisher" but installs cleanly when Ashley double-clicks →
"More info" → "Run anyway"). For a publicly distributed build, add
`CSC_LINK` + `CSC_KEY_PASSWORD` env vars before `npm run dist:win:nsis`
and electron-builder picks up the signing cert automatically. That's
not this milestone.

### Optional: Mac → Windows cross-compile

electron-builder supports `--win` from macOS but may pull a Windows
Electron binary via `@electron/get` (with `ELECTRON_MIRROR`). The
existing `apps/desktop/scripts/run-electron-builder.mjs` already handles
this case. No changes needed for this milestone.

---

## 4. What Ashley sees on her PC

### 4.1 Install (1 click)

Ashley double-clicks `Flo-Setup-0.17.0-win-x64.exe` (or right-click →
"Install" if SmartScreen blocks). NSIS wizard:

```
Welcome to the Flo Setup Wizard
[Next]

License Agreement (MIT for the Hermes engine, LoanFlow Processing LLC for Flo)
[I Agree]

Install Location: C:\Users\Ashley\AppData\Local\hermes
  (default — Ashley doesn't need to change this)
[Install]

Installation in progress...

Setup has finished installing Flo on your computer.
[Finish]
```

A `Flo` shortcut appears on the desktop and in `Start Menu → Programs →
Flo Signatures` (added by `Install-FloSignaturesShortcut` during the
Flo Stage).

### 4.2 First launch (1 click)

Ashley double-clicks the **Flo** desktop shortcut (or `Flo Signatures`
in Start Menu). The Electron app starts. Two things happen:

1. The first-run setup gate (already wired in `bootstrap-runner.ts` +
   `first-run-setup-gate.ts`) shows a "Welcome to Flo 💚" card.
2. After Ashley clicks **Continue**, the Flo Stage runs:
   - Ashley profile (SOUL.md, config.yaml, etc.) lands in
     `%LOCALAPPDATA%\hermes\profiles\ashley\`
   - The six Flo Team profiles (Flo, Malcolm, Sage, Chadwick, Whisper,
     Franklin) land in the same tree
   - Local workspace root `%LOCALAPPDATA%\hermes\flo\workspace\{intake,aus,
     income,assets,title,insurance,conditions,orders,correspondence,exports}`
     is created

Ashley never sees a terminal, never edits an `.env`, never runs
`docker compose`.

### 4.3 First-run setup (Ashley-facing cards)

The existing first-run UI needs new cards. They're not built yet —
this milestone lays the wiring so the cards can drop in.

```
Welcome to Flo 💚

Let's get you connected.

[Connect Google]              ← opens Gmail / Drive / Calendar OAuth
[Connect Zapier]              ← opens Zapier MCP sign-in
[Set Up Local Signing]        ← detects Docker, offers Documenso install
[Continue]                    ← open Today with connectors disconnected

Advanced ↓ (hidden by default)
```

Each button calls the existing Hermes connector OAuth flow with Ashley's
account. No API keys are typed. No `.env` editing. The Google Workspace
skill (`flo-agent/skills/productivity/google-workspace/`) already has the
OAuth flow; the email adapter (`flo-agent/plugins/platforms/email/`) uses
IMAP + app password (a small follow-up adds a "Connect Gmail" button
that drives the existing IMAP path).

### 4.4 Day-to-day

- Ashley launches Flo → Today loads → Pipeline loads → Approvals loads
- Local backend comes up via the existing autostart flow (Task
  Scheduler entry installed by `flo-autostart.ps1`)
- Documenso comes up via the existing `flo-start.ps1`
- After Windows reboot, Task Scheduler re-runs `flo-autostart.ps1` →
  Docker starts → Documenso containers restart (their `restart:
  unless-stopped` policy handles this) → Flo backend ready

Ashley never sees a terminal, PowerShell, Git, npm, Python, or Docker
command after install.

---

## 5. What the installer puts on Ashley's PC

| Path | What |
|---|---|
| `%LOCALAPPDATA%\hermes\Flo.exe` | The launcher (Flo.exe — formerly Hermes.exe, branded by `after-pack.mjs`) |
| `%LOCALAPPDATA%\hermes\resources\` | App data, install-stamp.json, icon.ico |
| `%LOCALAPPDATA%\hermes\hermes-agent\` | The cloned source tree (used by bootstrap to re-run install.ps1 on update) |
| `%LOCALAPPDATA%\hermes\profiles\` | All seven profiles (ashley, flo, malcolm, sage, chadwick, whisper, franklin) — written by Stage-FloTeam |
| `%LOCALAPPDATA%\hermes\flo\workspace\` | Local workspace root — created by Stage-FloTeam |
| `Start Menu\Programs\Flo Signatures.lnk` | One-click shortcut to `flo-start.ps1` |
| `Start Menu\Programs\Flo.lnk` | One-click shortcut to the Flo.exe (Flo Signatures shortcut is separate by design) |
| Task Scheduler → `FloSignatures` task | Runs `flo-autostart.ps1` at login |

### What the installer does NOT put on Ashley's PC

- The git repo (only the build artifacts; the source tree is internal)
- `.venv/`, `node_modules/`, build artifacts
- Test mailboxes, synthetic test data
- Ashley's existing accounts stay on her Mac/Ashley-signed-in-Chrome
- Any of Jeremy's dev credentials

---

## 6. Connectors

| Connector | How Ashley signs in | Source path |
|---|---|---|
| Google (Gmail / Drive / Calendar) | One OAuth flow that grants all three at once | `flo-agent/skills/productivity/google-workspace/scripts/setup.py` (existing OAuth helper) |
| Zapier | Browser OAuth to `https://nla.zapier.com/` | `flo-agent/.flo/profile/ashley/config.yaml` `mcp_servers.zapier` (existing field, populated by Ashley's OAuth callback) |
| Local Documenso | One click — installer detects Docker, runs `docker compose up -d`, writes health check | `flo-agent/deploy/documenso/docker-compose.yml` (existing) |
| Local model (optional) | Optional — installer can pull Ollama; off by default | not built in this milestone |

### What this milestone does NOT add

- A new "Connect Gmail" button that drives the IMAP app-password path.
  The IMAP connector is already wired (`flo-agent/plugins/platforms/email/`).
  A small follow-up adds a button that prompts for Ashley's Gmail + app
  password (entered via a hidden prompt, never chat / never committed).
- Cloud connectors, third-party Zapier replacements, or SaaS sign-in.

---

## 7. Local signing (Documenso on Ashley's PC)

The existing `flo-start.ps1` already does this. It's a single command:
`powershell -File flo-start.ps1`. The new `Install-FloSignaturesShortcut`
makes that one click from the Start Menu.

The first-run UI's **Set Up Local Signing** button calls into a thin
wrapper around `flo-start.ps1`. If Docker isn't installed, the wrapper:

1. Opens `https://www.docker.com/products/docker-desktop/` in
   Ashley's default browser with the Edge download link
2. Walks Ashley through "next, next, install, finish"
3. Returns to the wrapper, runs `flo-start.ps1`, shows a green check
   when the three containers are running

No terminal, no `docker compose`, no YAML editing.

---

## 8. Update / uninstall behavior

### Update

The Flo desktop app includes an auto-updater wired in `apps/desktop/electron/main.ts`
(`update:shim`, `update:repro:*` scripts in `flo-agent/scripts/desktop-update/`).
Ashley clicks **Flo → Help → Check for updates**; the app downloads
and stages a new version, prompts to restart. After restart, the
bootstrap-runner re-runs `install.ps1` to upgrade the source tree, and
the new Flo Stage re-installs profiles if they changed.

The Flo Stage is **idempotent** — `install_ashley_profile.py` and
`install_flo_team.py` both have `--update` modes that re-apply
distribution files without overwriting user-owned files
(`profiles/ashley/memories/USER.md` is never overwritten).

### Uninstall

NSIS uninstaller removes:
- `%LOCALAPPDATA%\hermes\` (Flo, hermes-agent, profiles, workspace)
- `Start Menu\Programs\Flo.lnk`, `Start Menu\Programs\Flo Signatures.lnk`
- The `FloSignatures` Task Scheduler entry (created by `flo-autostart.ps1`)
- Registry entries `Flo`, `Hermes`

It does **NOT** remove:
- Docker Desktop (Ashley may have other apps using it)
- The Documenso containers (separate uninstall path via
  `docker compose down`)
- Ashley's browser cookies (no change there)

---

## 9. What Ashley must do manually

| Step | Action | Where |
|---|---|---|
| 1 | Double-click `Flo-Setup-0.17.0-win-x64.exe` | wherever she saved the installer |
| 2 | Click "Install" in the NSIS wizard | inside the installer |
| 3 | Click "Finish" | inside the installer |
| 4 | Click the **Flo** shortcut on her desktop | desktop |
| 5 | Click **Welcome to Flo 💚 → Continue** | inside Flo |
| 6 | Click **Connect Google** → approve in Chrome | Chrome |
| 7 | Click **Connect Zapier** → approve in Chrome | Chrome |
| 8 | Click **Set Up Local Signing** → follow the Docker prompt if needed | inside Flo |

That's it. After step 8 she's done. Future launches just open Flo and
land on Today.

### What Ashley does NOT do

- No terminal, PowerShell, Git, npm, Python, Docker commands
- No `.env` editing
- No copying profile JSON files
- No manual `git clone` or `npm install`
- No restarting the PC (autostart handles it)
- No setting up the database (Documenso's compose file does it)

---

## 10. Acceptance test (clean Windows environment)

Run on a fresh Windows VM or a clean user profile:

```text
- Install Flo                       ✓ Setup completes, no terminal visible
- Launch Flo                        ✓ Today / Pipeline / Approvals all load
- Team profiles installed          ✓ ls %LOCALAPPDATA%\hermes\profiles shows all 7
- Documenso health check            ✓ http://localhost:3000 returns 200
- Connectors show "Disconnected"    ✓ Until Ashley authorizes
- No developer setup required       ✓ No npm / pip / git commands used
```

No real Ashley Gmail is connected during this test. The
"Disconnected" state is correct for a fresh install — Ashley clicks
the cards to authorize on her own.

---

## 11. What's still pending

Items still to build for this milestone to be "Ashley-ready":

1. **First-run UI cards** — the Connect Google / Zapier / Set Up Local
   Signing buttons. The wiring exists (`bootstrap-runner.ts`,
   `first-run-setup-gate.ts`); the React components don't. Build
   inside `apps/desktop/src/app/onboarding/` (new dir).
2. **Connector OAuth UI for Google Workspace** — the existing skill at
   `flo-agent/skills/productivity/google-workspace/scripts/setup.py`
   has the OAuth dance; wrap it in a card that opens Chrome.
3. **Gmail IMAP connector button** — small wrapper around the existing
   `EMAIL_ADDRESS` + `EMAIL_PASSWORD` env vars, prompted via hidden
   input. The IMAP connector is already in place.
4. **Documenso install wrapper** — small UI that calls `flo-start.ps1`
   and surfaces a green check on success.
5. **Local model install wrapper (optional)** — Ollama installer via
   winget.

These are all small React components. None require backend changes —
the production-ready backend (Stage-FloTeam + flo-start.ps1) is in
place as of this commit.

---

## 12. Commit SHAs

- `da0970f` — gmail: route connector messages into Flo condition/CTC
  handlers (the prior commit, still in place)
- (this commit) — install.ps1: opt-in Flo Stage for Ashley profile +
  Flo Team + workspace + Flo Signatures shortcut
- `WINDOWS_PRODUCTION_SETUP.md` — written

---

## 13. Build command summary

```text
Mac (Jeremy):
  cd flo-agent/apps/desktop
  npm ci
  npm run dist:win:nsis
  # → release/Flo-Setup-0.17.0-win-x64.exe (ship this to Ashley)

Windows (Ashley):
  Flo-Setup-0.17.0-win-x64.exe     # install
  Start Menu → Flo                # launch
  Welcome → Connect Google → Connect Zapier → Set Up Local Signing
  Done.
```

That's the full round trip from `npm run dist:win:nsis` on Jeremy's
Mac to Ashley using Flo on her PC with five clicks and zero developer
exposure.
