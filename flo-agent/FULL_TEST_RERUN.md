# Full test rerun (2026-09-09, idle machine)

Run after all model-intensive work had stopped (no Ollama inference, no live Hermes turns, no other suites in parallel).

## Desktop (`apps/desktop`)

| Check | Result |
|---|---|
| `npm run typecheck` (renderer, electron, e2e) | PASS |
| `npm run lint` | 0 errors, 127 pre-existing warnings (none in `src/plugins/flo*`) |
| `npx vitest run --project ui` (full) | **691 files: 690 passed, 1 failed · 6819 tests: 6818 passed, 1 failed · 262 s** |
| `npx vitest run --project electron electron/flo-*.test.ts` | 13/13 passed |
| `npm run build` | PASS (`assert-dist-built` OK) |

### Classification of the previous run's 20 failures

| Class | Count | Detail |
|---|---|---|
| (a) Flo regression | **0** | none reproduced |
| (b) pre-existing upstream failure on Windows | **1** | `src/plugins/hermes-bots/cron-prompt.test.ts › delegated arguments stay literal shell values › passes substitutions, backticks and quotes through as text` — the same case recorded at baseline (`CLAUDE_PROGRESS.md` §1.3) before any Flo code existed; it also fails in isolation |
| (c) load/timing | **19** | every other failure from the run that overlapped CPU-bound local inference (setup/environment time was ~5× normal then: 637 s vs 262 s now) did not reproduce; the `src/app/skills/index.test.tsx` cases were already shown passing in isolation |

Result: the UI suite is back to the baseline shape (6818/6819 vs 6810/6811 before the team plugin; the difference is the new plugin tests).

## Python

`pytest tests/flo tests/plugins/test_flo_policy_plugin.py tests/skills/test_flo_mortgage_skills.py tests/skills/test_authoring_standards.py tests/agent/test_redact.py tests/test_redaction_registry.py tests/hermes_cli/test_redact_config_bridge.py` → **1592 passed, 0 failed** (59 s). Includes the golden-loan suite (23), MCP redaction (3), delivery workdir (2), team (67), and the upstream redaction tests that exercise the patched `agent/redact.py` (121).

The stock Python files that fail on native Windows (symlink privilege / POSIX-only wrappers, documented at baseline) were not part of this run and are unchanged.
