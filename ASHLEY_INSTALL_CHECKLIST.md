# Ashley Install Checklist

The ONLY checklist Jeremy needs when he gets to Ashley's PC.

```
1. Run Flo Setup
2. Launch Flo
3. Welcome → Connect Gmail → Connect Google Drive → Connect Zapier
4. Set Up Local Signing
5. Set Up Local AI
6. Done
```

That's it. Eight clicks total.

---

## What Ashley actually has to do

1. **Double-click `Flo-Setup-0.17.0-win-x64.exe`** (the file Jeremy shipped her). NSIS walks her through `Next → I Agree → Install → Finish`. The installer puts Flo at `%LOCALAPPDATA%\hermes\` and creates a desktop shortcut + a `Start Menu → Programs → Flo Signatures` shortcut.

2. **Double-click the `Flo` desktop shortcut** (or `Flo Signatures` to launch signing only). First launch lands on `Welcome to Flo 💚`.

3. **Connect the five cards.** Each card has plain-English labels — `Gmail`, `Google Drive & Calendar`, `Zapier`, `Local Signing`, `Local AI`:
   - **Gmail:** Type her Gmail address + the 16-character app password from `myaccount.google.com/apppasswords`. Saved encrypted on her PC.
   - **Google Drive & Calendar:** Click → docs link copies to clipboard → she runs the OAuth dance once in a browser → returns. Status flips to Connected.
   - **Zapier:** Type her Zapier MCP URL → save.
   - **Local Signing:** Click → Docker detection → runs `flo-start.ps1` → Documenso + Postgres + maildev come up. Status flips to Ready.
   - **Local AI:** Click → Ollama detected → model count shows. (If Ollama isn't installed yet, the card says "Not running" and stays there until she runs the Ollama installer.)
4. **Continue.** Ashley lands on Today.

That's it. Zero terminal. Zero env files. Zero `npm install`. Zero git. Zero Claude Code.

If a card can't be set up right now (no Gmail password yet, no Ollama installed), she clicks Continue anyway — the card stays in `Not Connected` / `Not Running` state and re-appears in Settings whenever she opens it.

---

## What Ashley does NOT do

- No PowerShell.
- No `docker compose`.
- No environment variables.
- No JSON editing.
- No OAuth token copy-paste (the OAuth flow runs in her default browser).
- No model picking — Ollama defaults are picked automatically.

---

## What Jeremy still needs to do on Ashley's PC (machine-specific)

1. **Install Docker Desktop** — Ashley's PC may not have it. One-click from `https://www.docker.com/products/docker-desktop/`. Required for Local Signing + (optional) Local AI.
2. **Install Ollama** — for Local AI. One-click from `https://ollama.com/`. After install, Flo's Local AI card flips to Ready within a few seconds.
3. **Generate the Gmail app password** on Ashley's Google Account (one-time, 30 seconds). Ashley has to do this — it's her account. URL: `https://myaccount.google.com/apppasswords`. Sign-in + 2FA + create → 16-character password.
4. **Drop the synthetic loan package** into Flo for the smoke test (one-time). PDFs / JPGs on her Desktop → drag onto the open file view.

All four are explained in the in-app cards. None require terminal.

---

## If anything goes wrong

Each connector card has a `[Re-check]` button that re-probes the connection state. Ashley clicks it; Flo retries; if it's still broken the card shows the reason in plain English ("Email isn't connected yet." / "Local signing isn't running. I'm trying to start it." / "Flo's local AI isn't ready yet.").

For deeper issues: **Settings → Flo → Advanced**. That surface is for Claude Code / Jeremy only — Ashley never needs it.
