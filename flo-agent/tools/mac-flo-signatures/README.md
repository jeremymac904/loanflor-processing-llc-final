# Flo Signatures — Mac launcher

This is the **macOS** equivalent of the Windows `Flo Signatures` Edge app-mode
shortcut. It's a tiny wrapper app so Ashley can launch local e-signing with a
single click — no Terminal, no `localhost`, no Docker commands.

## What it does

Double-click **Flo Signatures** in Finder (or launch from Spotlight / Launchpad
after install). The launcher:

1. Tries `http://localhost:3000` (Documenso's local signing UI).
2. If reachable, opens it in the default browser.
3. If not, shows a plain-English dialog:
   > Flo Signatures isn't running yet.
   > Start it from where you usually start Flo and try again.
4. Either way, exits — no background process, no menu bar icon.

## Install (one-time, Ashley-facing)

Copy the app bundle into her `~/Applications` (or `/Applications`):

```bash
cp -R "flo-agent/tools/mac-flo-signatures/Flo Signatures.app" ~/Applications/
```

Then launch it once from Finder / Spotlight so macOS records the bundle
identifier (`com.loanflow.flo.signatures`). After that, Spotlight will find it
by typing "Flo Signatures".

To rebuild from scratch (e.g. after changing the icon or the URL):

```bash
cd flo-agent/tools/mac-flo-signatures
./build.sh
```

The build script regenerates `Contents/Resources/flo-icon.icns` from
`apps/desktop/public/flo-badge.png` and `chmod +x`'s the launcher.

## Configuration

- **Default Documenso URL:** `http://localhost:3000` (matches `FLO_RECOVERY.md`).
- **Override:** set `DOCUMENSO_URL` before launch — the launcher reads it from
  the environment. The .app bundle doesn't expose this; if the URL changes,
  edit the script in `Contents/MacOS/flo-signatures-launcher` and re-install.

## What's *not* here

- No auto-start at login yet — the Mac equivalent of `flo-autostart.ps1`. That
  requires a `LaunchAgent` plist, which the user installs after Docker is
  installed and the Documenso stack is verified. Until then, Ashley starts
  Documenso manually before clicking Flo Signatures.
- No new installer / packaging — the .app bundle is the deliverable. The
  existing `flo-agent/deploy/documenso/` `docker-compose.yml` stays the
  authoritative way to start Documenso.
- No retries / polling — single attempt per click. Ashley clicks again if
  Documenso comes up after she starts it.

## Why this shape

Per `MAC_HANDOFF.md` and the project rules, Ashley must experience local
e-signing with one click and zero technical exposure. A minimal `.app` bundle
is the smallest thing that:

- shows up in Spotlight and Launchpad,
- displays the Flo icon,
- runs a short shell script,
- keeps Ashley out of the Terminal.

A PWA / app-mode Chrome shortcut would also work but assumes a Chrome install;
the `.app` bundle uses the system default browser so it works whether Ashley
uses Safari, Chrome, Firefox, or Arc. Electron would have been overkill for
"open a URL."
