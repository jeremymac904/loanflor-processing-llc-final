# Start Here

## Mission

Build a branded desktop application named **Flo Agent** for Ashley, a high-performing third-party mortgage processor.

Flo should feel like one calm, capable processing assistant rather than a generic multi-agent developer console. It should eventually be able to work with Ashley's email, Google Drive, documents, mortgage-processing knowledge, schedules, and approved external systems while preserving a strong human-approval boundary for consequential actions.

## Immediate objective for Claude Code

Do **not** attempt the entire product in one pass.

The first Claude Code pass should:

1. Bootstrap the official Hermes Agent repo at tag `v2026.8.31`.
2. Read upstream engineering and Desktop design instructions.
3. Prove the unmodified Desktop build/test baseline.
4. Document any environment blockers without guessing around them.
5. Establish the downstream Flo architecture and context directory.
6. Implement a conservative first-pass desktop rebrand foundation.
7. Scaffold Ashley's Flo profile/persona and mortgage skill package from the supplied source material.
8. Add policy/audit interfaces and tests as stubs/contracts before enabling any external side effects.
9. Leave a clean `CLAUDE_PROGRESS.md` with commands run, files changed, tests, blockers, and the next recommended task.

The later Codex pass will polish UI, refactor rough edges, increase test coverage, tighten accessibility, and finish integration details.

## Definition of a good first checkpoint

A good checkpoint is not "everything works."

A good checkpoint is:

- upstream baseline is reproducible;
- Flo launches under its own visible product identity;
- core upstream internals remain mergeable;
- Ashley's operating instructions are represented as versioned project context;
- mortgage skills have clear boundaries and source provenance;
- dangerous integrations are still disabled or approval-gated;
- no credentials or borrower data are committed;
- tests can distinguish Flo-specific changes from upstream behavior;
- the next agent can understand the state of the project in minutes.
