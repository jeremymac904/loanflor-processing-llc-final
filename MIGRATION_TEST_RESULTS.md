# Migration test results

Run on the Windows dev machine immediately before pushing the migration branch (2026-09-16), from the
**original** checkouts (the migrated copy under `flo-agent/` has no `.venv`/`node_modules` — those are
gitignored and rebuilt fresh per `MAC_SETUP.md`, so tests were run against the source checkouts that fed
the copy, not the copy itself).

## Website

```
npm test
```

```
tests 19
pass 19
fail 0
duration_ms 18403.7
```

Covers: upload validation, document storage, esign webhook (secret verification, dedup, out-of-order
delivery, payload trust), loan submission normalization/validation/duplicate-protection/retry.

## Flo (Python)

```
TZ=UTC LANG=C.UTF-8 PYTHONHASHSEED=0 PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/flo -q
```

```
252 passed in 31.86s
```

## Flo Desktop

**Not re-run in this migration session** — no code under `apps/desktop/` changed since the last recorded
run (`FLO_ESIGN.md`: 28 esign-related tests passed, tsc clean, eslint clean, as of 2026-09-11/15). Re-run
`npm run typecheck && npm run lint && npm run test:ui` in `flo-agent/apps/desktop` before relying on this if
more time has passed or that area has changed.

## What this does and doesn't prove

This proves the source that was copied into the monorepo passed its own test suites immediately before the
copy. It does **not** yet prove the copy itself builds and tests cleanly from a fresh `uv sync` / `npm
install` — that's exactly what the fresh-clone verification step (see the migration report) checks
structurally (files present, no accidental omissions), and what running `MAC_SETUP.md` end-to-end on an
actual Mac will prove for real.
