#!/usr/bin/env bash
# Mac setup for the Flo / LoanFlow Processing monorepo.
# See MAC_SETUP.md for the explanation of each step — this script just runs them.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Checking Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Install it first: https://brew.sh" >&2
  exit 1
fi

echo "==> Node.js"
if ! command -v node >/dev/null 2>&1; then
  brew install node@20
fi
node --version

echo "==> uv (Python)"
if ! command -v uv >/dev/null 2>&1; then
  brew install uv
fi

echo "==> Website dependencies"
npm install

echo "==> Flo (Python) environment"
cd "$ROOT_DIR/flo-agent"
uv venv .venv
source .venv/bin/activate
uv sync
deactivate

echo "==> Flo Desktop dependencies"
cd "$ROOT_DIR/flo-agent/apps/desktop"
npm install

cd "$ROOT_DIR"
echo ""
echo "Base setup complete. Still manual (see MAC_SETUP.md):"
echo "  - copy the .env.example files and fill in your own values"
echo "  - Docker Desktop + local Documenso, only if you're working on e-signing"
echo "  - install the Flo/Ashley profile (flo-agent/scripts/flo/install_ashley_profile.py)"
echo "  - re-fetch underwriting source caches (flo-agent/scripts/flo/fetch_*.py)"
