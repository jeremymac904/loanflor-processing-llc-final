# Upstream lineage — Hermes Agent

This directory (`flo-agent/`) is a **downstream distribution** of Hermes Agent, rebranded and extended as
**Flo** for LoanFlow Processing LLC's mortgage-origination workflow. It is not an independent project.

## Upstream

- **Project:** Hermes Agent
- **Publisher:** Nous Research
- **License:** MIT (see `LICENSE` in this directory — unmodified, required attribution preserved)
- **Upstream URL:** https://github.com/NousResearch/hermes-agent
- **Original pinned tag:** `v2026.8.31`

## Flo branch state at time of migration

- **Flo branch (in the original Windows checkout):** `flo/0.21-bootstrap`
- **Flo branch HEAD commit:** `9b032fa5686256eb0f53dd67c9ba98da320fec23`
- **Commit date:** 2026-09-15 16:08:32 -0400
- **Migration date:** 2026-09-16
- **Migrated by:** Claude Code, on the owner's instruction, into the `loanflor-processing-llc-final` monorepo

## What "downstream distribution" means here

Per `CLAUDE.md` in this directory: Flo behavior is added through profiles, skills, backend plugins, desktop
plugins, theme/skin APIs, and isolated adapters — not by rewriting Hermes core. Internal Hermes names
(`hermes`, `hermes_cli`, gateway RPC names, `HERMES_*` env vars) are preserved deliberately so this tree
stays mergeable against upstream if that's ever useful. Only user-visible surfaces are rebranded to Flo.

## What did NOT come across in this migration

The original Windows checkout carried its own local `.git` history tracking `upstream` (Hermes) as a remote.
That `.git` directory was **deliberately excluded** from this migration — nesting a second Git repository
inside this monorepo would make GitHub store only a broken pointer instead of real content. This means:

- The original commit-by-commit Hermes/Flo history is **not** part of this repository's history.
- This migration is captured as a single working-tree snapshot at the commit above.
- If full history is ever needed, it exists in the original Windows checkout (not migrated) and in the
  Hermes upstream repository directly.

## Rebuilding the Hermes connection on a new machine

This monorepo does not re-establish a `git remote add upstream` relationship automatically — that's a
deliberate choice per `CLAUDE_PROGRESS.md`'s "no autonomous git operations beyond what's asked" rule. If a
future session needs to diff or pull from Hermes upstream again:

```bash
cd flo-agent
git remote add upstream https://github.com/NousResearch/hermes-agent.git
git fetch upstream
```

(This only works if `flo-agent/` is itself re-initialized as a git repo, or a separate scratch clone is used
for the diff — do not turn this directory back into a nested repo inside the monorepo.)
