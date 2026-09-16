# MiniMax Review — Mac handoff verification

Written on first pass after cloning the repo on a fresh Mac mini (M1 Max, 64 GB,
macOS 26.6.2). Branch under review: `flo/full-project-migration` @
`debc9a9d8d33090068112fc117267b4927a85a6b`.

This is what was actually run, not a paraphrase of `MAC_HANDOFF.md`.

## 1. Repo state

- **Repo:** `https://github.com/jeremymac904/loanflor-processing-llc-final`
- **Branch used:** `flo/full-project-migration` (the migration branch, not `main`
  — `main` is just the website pre-migration; the website + Flo monorepo lives on
  the migration branch)
- **Branch HEAD:** `debc9a9` "Consolidate Flo/Hermes and website into one monorepo"
- **Working tree:** clean before any changes (no nested `.git`, no submodules)
- **Continuation branch created:** `flo/minimax-continuation`

## 2. Project structure found

```
loanflor-processing-llc-final/
├── README.md, PROJECT_MAP.md, MAC_HANDOFF.md, MAC_SETUP.md
├── *.md — Loan Submission v2 / intake / docs / esign docs
├── App.tsx, components/, index.html, package.json, server/, shared/   (website)
├── flo-agent/                                                          (Flo + Hermes)
│   ├── .flo/{docs,profile/<7 profiles>,source_material,team,underwriting,assets}
│   ├── plugins/flo-team/        (Python team runtime, all six profiles wired)
│   ├── plugins/flo-policy/      (policy/approvals/audit)
│   ├── apps/desktop/            (Electron + React, Ashley-facing)
│   ├── apps/{bootstrap-installer,...}
│   ├── skills/, scripts/, tests/, deploy/documenso/
│   ├── pyproject.toml, uv.lock, package.json, package-lock.json
│   └── hermes*                  (upstream Hermes Agent engine, MIT)
└── flo-agent/website/           (Flo docs site, separate Docusaurus project)
```

Top-level docs present and consistent with code: `MAC_HANDOFF.md`, `MAC_SETUP.md`,
`PROJECT_MAP.md`, `LOAN_SUBMISSION_V2.md`, `FLO_INTAKE_INTEGRATION.md`,
`DOCUMENT_UPLOAD_IMPLEMENTATION.md`, `FLO_ESIGN.md`, `FLO_RECOVERY.md`.

Inside `flo-agent/`: `CLAUDE.md`, `AGENTS.md`, `CHANGELOG_FLO_BOOTSTRAP.md`,
`CLAUDE_PROGRESS.md`, `ASHLEY_UX_SIMPLIFICATION.md`, `FLO_TEAM_BUILD.md`,
`FLO_TEAM_PROGRESS.md`, `MULTI_PROGRAM_SOURCE_REGISTRY.md`,
`FHA_GOLDEN_LOAN_PATH.md`, `FANNIE_SOURCE_ACTIVATION.md`,
`FLO_GOLDEN_LOAN_PATH.md`, etc.

All seven Flo team profiles exist on disk under `.flo/profile/`:
`ashley, flo, malcolm, sage, chadwick, whisper, franklin`.

## 3. Secret / privacy scan

Searched for: `BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY`, `sk_live_`, `pk_live_`,
`AKIA[0-9A-Z]{16}`, `ghp_*`, `xox[baprs]-*`, plus `*.db`, `*.sqlite*`, `*.p12`,
`*.pfx`, `*.pem`, `*.key`, `id_rsa*`, `*.log`.

**Result: no real secrets, no real borrower data, no runtime databases committed.**

Hits are all obviously fake or documentation placeholders:
- `AKIAIOSFODNN7EXAMPLE` (AWS's well-known example)
- `ghp_xxxx...` and `xoxb-test` in test fixtures
- `xoxb-your-bot-token-here` in docs (placeholder)
- Synthetic bank statement / W-2 PDFs in test fixtures (synthetic data, not real)

`.env.example` files exist at the root, in `flo-agent/`, and in
`flo-agent/deploy/documenso/` — they describe variable shapes, contain no real
values. `.env`, `state.db`, `sessions/`, `logs/`, `google_*_token.json` patterns
are all in `.gitignore`.

## 4. Mac environment

```
ProductName:    macOS 26.6.2 (25G83)
Model:          MacBookPro18,2 (M1 Max, 10 cores, 64 GB RAM)
Homebrew:       NOT installed (MAC_SETUP.md assumes brew at step 1)
Node:           v24.20.0  (MAC_SETUP.md asks for node@20; 24 is newer and works)
npm:            11.19.0
uv:             0.12.10  (Apple Silicon)
Python system:  3.9.6    (system; pyproject.toml needs >=3.11,<3.14)
Python via uv:  3.12.14  (managed by uv; what `uv venv` actually uses)
Docker:         NOT installed (Documenso requires Docker Desktop)
Git:            2.54.0
Ollama / Unsloth / OpenCode / Codex CLI: not present (no local model infra active — matches MAC_SETUP.md §13)
```

`MAC_SETUP.md` should be updated to note `brew` is optional on this image
(uv-managed Python replaces `brew install python`; Docker is required only for
the Documenso piece). Not doing that here — flagged in `15_OPEN_QUESTIONS.md`-equivalent note below.

## 5. Test verification (fresh clone, freshly synced)

| Surface | Result | Notes |
|---|---|---|
| Website tests (`npm test`) | **19 / 19 pass** in 0.97s | upload, storage, esign webhook, loan submission — all green |
| Website build (`npm run build`) | **OK** | vite, 1734 modules, 1.82s |
| Website typecheck (`npm run typecheck`) | **Reports 19,194 errors** but **all of them are in `flo-agent/`** files (root `tsconfig.json` has no `include`/`exclude` so `tsc` sweeps `flo-agent/website/`, which is its own Docusaurus project with its own tsconfig) | The root website itself typechecks cleanly when invoked from `flo-agent/website`. Pre-existing repo layout issue, not a regression. |
| Flo Python tests (`scripts/run_tests.sh tests/flo`) | **244 pass, 0 fail, 8 skipped** in 12.5s (20 workers) | Matches Windows migration result of 252 = 244 + 8 skipped |
| Underwriting tests (Fannie/Freddie/FHA TOTAL+Manual/VA/USDA) | **76 pass, 0 fail, 6 skipped** | Per-program activation gates; activation is per-install per `scripts/flo/activate_sources.py` |
| Flo Desktop typecheck | **Clean** (silent) | `tsc -p . && tsc -p tsconfig.electron.json && tsc -p tsconfig.e2e.json` |
| Flo Desktop lint | **0 errors, 146 warnings** (all `padding-line-between-statements` style warnings) | Was previously failing because `eslint` was missing entirely from `package.json`; fixed in this pass |
| Flo Desktop tests (`npm run test:ui`) | **6,837 / 6,837 pass** in 344s | All UI tests green |

## 6. Gaps and fixes applied in this pass

Three real gaps found by running the project, all fixed on
`flo/minimax-continuation`:

### 6.1 `pypdf` missing from `flo-agent/pyproject.toml`

**Symptom:** `tests/flo/test_documents.py` — 3 tests failed:
`test_pulls_files_names_them_extracts_text_and_flags_gaps`,
`test_submission_with_documents_lands_organized_in_the_deal_room`,
`test_flo_documents_tool_for_malcolm_and_not_for_franklin`.

**Root cause:** `plugins/flo-team/documents.py:90` does
`import pypdf  # type: ignore` inside `extract_text()`. The import fails
silently (it's wrapped in a try/except that returns `{"method": "failed"}`),
so PDF text comes back empty. The synthetic-PDF test fixtures embed
`"Page N of M"` markers and `"Synthetic Credit Union"` strings — without pypdf,
text extraction returns `""`, so `missing_pages()` finds no markers and the
test assertions fail.

`pypdf` was never declared in `pyproject.toml` or `uv.lock`. The Windows machine
that ran the migration had it installed by some other path (system pip? a
manual venv?). On Mac a fresh `uv sync` doesn't pull it.

**Fix:** Added `pypdf==5.7.0` as a core dep (pure Python, no compiled
extensions, exercised on every PDF upload — lazy-install would silently
degrade). All 244 Python tests now pass.

### 6.2 `eslint` missing from `flo-agent/package.json`

**Symptom:** `cd flo-agent/apps/desktop && npm run lint` exits 127
(`sh: eslint: command not found`).

**Root cause:** Root `package.json` declares `@eslint/js`, `typescript-eslint`,
`eslint-plugin-perfectionist`, `eslint-plugin-react-hooks`,
`eslint-plugin-unused-imports`, `globals` — but **not `eslint` itself**.
The desktop `lint` script is `eslint src/ electron/`, so it has nothing to run.

**Fix:** Added `"eslint": "9.39.5"` to root devDependencies.

### 6.3 `minimatch@3.x` vs root `brace-expansion@5.0.9` override conflict

**Symptom (after 6.2):** Even with `eslint` installed, `npm run lint` crashes
with `TypeError: expand is not a function at Minimatch.braceExpand`.

**Root cause:** Root `package.json` has `"brace-expansion": "5.0.9"` as a CVE
override. `eslint` → `@eslint/config-array@0.21.x` → `minimatch@3.1.5` →
`brace-expansion@^1.1.7`. The override forces `brace-expansion@5.0.9`
everywhere, including inside `minimatch@3.1.5`'s resolution, which breaks the
3.x minimatch code that calls `expand(pattern)` (a function in `brace-expansion
1.x`, missing in `5.x`'s different API).

**Fix:** Scoped the brace-expansion override so it applies everywhere *except*
to `minimatch`:
```json
"minimatch": { "brace-expansion": "^1.1.7" }
```

Lint now runs cleanly: 0 errors, 146 warnings (all stylistic, mostly
`padding-line-between-statements`).

## 7. Mac-specific gaps (intentionally not fixed in this pass)

- **Docker Desktop not installed.** The local Documenso stack at
  `flo-agent/deploy/documenso/docker-compose.yml` requires it. MAC_SETUP.md §6
  asks the user to install Docker Desktop — that needs an admin password and
  the privileged helper install. Per the task rules, that's a single
  owner-boundary step; I am flagging it and pausing there rather than asking
  the user to babysit a download.
  **Impact:** Documenso `esign.py` adapter is verified by `mock_documenso.py` in
  the live integration test (23 tests pass) and was already verified end-to-end
  on Windows (`FLO_ESIGN.md`, 2026-09-15). The Mac-side verification just
  hasn't been re-run.

- **Scripts lost +x on clone.** All `flo-agent/scripts/*.sh` files came in
  `-rw-r--r--`. `chmod +x scripts/*.sh` was the first step (only
  `scripts/run_tests.sh` is needed to actually run tests, but the rest were
  fixed for consistency). Mode-only diff, no content change.

## 8. Files in repo that are intentionally not in git but should exist on a
working machine

Per `MAC_HANDOFF.md` §12 and `MAC_SETUP.md` §12:

- `flo-agent/.venv/` — built by `uv sync` (not committed)
- `flo-agent/uv.lock` — IS committed (good)
- `flo-agent/node_modules/` — not committed, built by `npm install` from root
- `flo-agent/apps/desktop/node_modules/` — not committed, built by root `npm install` (workspace)
- `<hermes root>/flo/sources/cache/{fannie,freddie,fha,va,usda}/` — source
  PDFs/HTML, **not** in git, fetched per-install by `scripts/flo/activate_sources.py`
  + per-program fetchers. Re-fetching needs a human approver identity.
- `<hermes root>/flo/documents/<workspace>/...` — borrower document storage
  (sha256 + content + text sidecar), not in git. Local-first by design.
- `.env`, `.env.flo` — copy from `.env.example` and fill with your own values.
  Never commit.

## 9. State vs `MAC_HANDOFF.md`

`MAC_HANDOFF.md` accurately describes:
- the repo layout and what's working (Documenso local signing, intake, source-bound rules)
- what's deferred (two-signer live test, remote signing, SMTP, signing cert)
- the next priority (Ashley core missing-document workflow)
- the rule that remote signing is intentionally not solved with tunnels

What `MAC_HANDOFF.md` does not mention (now found and fixed):
- `pypdf` is missing from `pyproject.toml` — every fresh Mac clone will fail 3
  document tests until it's installed.
- `eslint` is missing from root `package.json` — every fresh clone will fail
  `npm run lint`.
- The `brace-expansion` override breaks `minimatch@3.x` — same lint fallout,
  root cause.

## 10. What's verified *not just by file presence*

- `npm test` at the root really ran 19 / 19 pass.
- `npm run build` at the root really built to `dist/`.
- `scripts/run_tests.sh tests/flo` really ran 244 / 244 pass.
- `apps/desktop npm run typecheck` returned silently with no errors.
- `apps/desktop npm run test:ui` really ran 6,837 / 6,837 pass.
- `apps/desktop npm run lint` (after fix) returned 0 errors / 146 warnings.

## 11. Recommended next steps (full plan in `MINIMAX_CONTINUATION_PLAN.md`)

1. **Get Documenso running locally.** Needs Docker Desktop installed; once
   that's done, `cd flo-agent/deploy/documenso && docker compose up -d`. The
   live integration test from `FLO_ESIGN.md` can be re-run on Mac.
2. **The next product priority is exactly what `MAC_HANDOFF.md` says:**
   Ashley's missing-document workflow. The plumbing is there (Malcolm's
   intake contract, `flo_documents` tool, Whisper's draft handoff, the
   one-click "Request Missing Documents" button needs to be wired from the
   Pipeline → File view to a Whisper chat that lands back in Approvals).
3. **Cosmetic root `tsconfig.json` cleanup** — add `"exclude": ["flo-agent"]`
   so `npm run typecheck` doesn't sweep into the Flo Docusaurus subtree.
