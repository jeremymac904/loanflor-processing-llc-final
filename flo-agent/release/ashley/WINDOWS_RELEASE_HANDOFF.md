# Windows Release Handoff — Claude on Ashley's PC

## This document tells Claude what to do and what NOT to do.

---

## What to do

1. **Verify the portable build runs**
   - Double-click `Flo.exe` inside `Flo-0.17.0-win-x64-portable.zip`.
   - If Windows blocks it: **More info → Run anyway**.
   - Confirm Flo opens to the first-run onboarding screen.

2. **Produce the NSIS installer** *(only if the portable build works)*
   - Run: `npm run dist:win:nsis` inside `flo-agent/apps/desktop/`
   - This requires `wine-stable` or a Windows host for `makensis`.
   - If Wine is available on Mac: `brew install wine-stable && npm run dist:win:nsis`
   - If Wine is not available: run on a Windows machine or WSL.
   - Output: `Flo-Setup-0.17.0-win-x64.exe` in `release/`

3. **Complete Ashley's account connections** (authorization — NOT setup code)
   - Google: click Connect Google, complete OAuth in the browser, paste the code.
   - Gmail: enter address + App Password, click Save.
   - Zapier: paste webhook URL, click Save.
   - Local Signing: click Set Up, wait for Docker/Ollama if prompted.
   - Local AI: click Set Up, wait for Ollama to download the model.

4. **Click Continue** — enter Flo.

5. **Run the acceptance smoke test**
   - Flo opens to Today view (not Hermes bootstrap).
   - Local AI is configured (shows Ready in Settings → Advanced).
   - Gmail connector shows Connected.
   - WVOE button appears in the file panel.

6. **Report any machine-specific failures only** — e.g., a driver issue, a port conflict, a missing Windows feature. Do not try to fix architecture.

---

## What NOT to do

- Do NOT add features.
- Do NOT redesign anything.
- Do NOT rebuild profiles or agents.
- Do NOT rewrite connectors.
- Do NOT change the model architecture.
- Do NOT edit `team.yaml`, `AGENTS.md`, or plugin source unless a specific bug requires it.
- Do NOT commit secrets, tokens, or borrower data.
- Do NOT run `git push` or any destructive git operations.
- Do NOT install dependencies unless the smoke test explicitly fails due to a missing package.

---

## If code must change

That is an **unexpected bug**. Report it in full:
1. What you tried to do.
2. What happened instead.
3. The exact error message.
4. The file and line number (if available).

---

## Artifact inventory

| File | What it is |
|------|-----------|
| `Flo-0.17.0-win-x64-portable.zip` | Complete Windows portable build (Flo.exe + Chromium + all assets) |
| `Flo-Setup-0.17.0-win-x64.exe` | *(not yet produced)* NSIS installer — produces after smoke test |
| `ASHLEY_INSTALL_CHECKLIST.md` | Short card for Ashley |
| `WINDOWS_RELEASE_HANDOFF.md` | This document |

---

## Source branch

```
Branch:  flo/minimax-continuation
Commit:  a7a0c9d  (continuing — last commit pending)
Remote:  origin
```

On Ashley's PC, after cloning:
```bash
git clone --branch flo/minimax-continuation <repo-url>
cd flo-agent
git log -1 --oneline
```

Verify it says `flo/minimax-continuation` before proceeding.
