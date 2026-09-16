# Mac setup

Everything here assumes Apple Silicon or Intel Mac, macOS 13+. No Windows paths are hard-coded anywhere in
this repo — the Windows-specific pieces (`flo-autostart.ps1`, `flo-start.ps1`, Task Scheduler) are optional
convenience scripts for that platform only and are simply unused on Mac.

## 1. Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

## 2. Node.js

```bash
brew install node@20
echo 'export PATH="/opt/homebrew/opt/node@20/bin:$PATH"' >> ~/.zshrc
```

Used by both the website (root `package.json`) and Flo Desktop (`flo-agent/apps/desktop`).

## 3. Python + uv

```bash
brew install uv
```

`flo-agent/pyproject.toml` requires Python `>=3.11,<3.14`. `uv` manages the virtualenv and pinned
dependencies — don't `pip install` by hand.

```bash
cd flo-agent
uv venv .venv
source .venv/bin/activate
uv sync
```

## 4. Flo/Hermes dependencies

Already covered by `uv sync` above. If you hit a missing system library (some optional skills need audio
or native bindings), install only what the failing import names — don't bulk-install unrelated brew
packages speculatively.

## 5. Electron desktop dependencies

```bash
cd flo-agent/apps/desktop
npm install
```

## 6. Docker Desktop for Mac (only needed for local Documenso signing)

```bash
brew install --cask docker
open -a Docker
```

Flo Signatures (local e-signing) is optional for most development — skip this section unless you're working
on `flo-agent/plugins/flo-team/esign.py` or `flo-agent/FLO_ESIGN.md`.

## 7. Local Documenso + Postgres

```bash
cd flo-agent/deploy/documenso
cp .env.example .env.flo        # fill in your own values, never commit .env or .env.flo
docker compose up -d
```

Three containers: `postgres:15`, `documenso/documenso:v2.18.0`, `maildev/maildev:2.1.0`. Web UI on
`http://localhost:3000`, test-inbox on `http://localhost:1080`. See `flo-agent/FLO_ESIGN.md` and
`flo-agent/FLO_RECOVERY.md` for the full picture — this is intentionally local-only, no tunnels.

## 8. Flo profile installation

```bash
cd flo-agent
.venv/bin/python scripts/flo/install_ashley_profile.py
.venv/bin/python scripts/flo/install_flo_team.py
```

## 9. Desktop build / dev launch

```bash
cd flo-agent/apps/desktop
npm run dev            # renderer + electron, hot reload
# or
npm run build && npm start
```

## 10. Tests

```bash
# Website (repo root)
npm test && npm run typecheck && npm run build

# Flo Python
cd flo-agent
scripts/run_tests.sh <paths>          # e.g. scripts/run_tests.sh tests/flo

# Flo Desktop
cd flo-agent/apps/desktop
npm run typecheck && npm run lint && npm run test:ui
```

## 11. Local environment variables

Copy every `.env.example` you find and fill in your own values — never copy real values between machines
over chat, email, or an untracked file that could get committed by accident:

- `.env.example` (repo root — website)
- `flo-agent/.env.example`
- `flo-agent/deploy/documenso/.env.example`

## 12. Underwriting source caches

Full source PDFs/HTML for Fannie/Freddie/FHA/VA/USDA are **not** in Git (redistribution rights are
unclear). This repo carries the source *registry*, checksums, and normalized rule records only. Re-fetch
from approved official sources on the new machine:

```bash
cd flo-agent
.venv/bin/python scripts/flo/activate_fannie_slice.py
.venv/bin/python scripts/flo/fetch_freddie_sources.py
.venv/bin/python scripts/flo/fetch_pdf_sources.py --program fha
.venv/bin/python scripts/flo/fetch_pdf_sources.py --program usda
.venv/bin/python scripts/flo/fetch_va_sources.py
```

Each fetch script requires a human approver identity — see `flo-agent/plugins/flo-team/identity.py` and
`flo-agent/FANNIE_SOURCE_ACTIVATION.md`.

## 13. Local model / provider status

No local model weights are checked into this repo and none are required to run Flo — Hermes routes to
whatever provider credentials you configure through its normal credential pool (`flo-agent/agent/credential_pool.py`).
There is no Unsloth/local-model setup active in this codebase as of the last migration; if that changes, it
belongs in a separate, explicitly-approved setup step, not a default here.

## 14. Launching Flo

```bash
cd flo-agent
.venv/bin/hermes
```

## 15. Launching Flo Signatures (local signing)

Open `http://localhost:3000` once the Documenso containers are up (step 7). There is no Mac equivalent yet
of the Windows Task Scheduler auto-start / Edge app-mode shortcut — that's a small piece of deferred polish,
not a blocker.
