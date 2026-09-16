# Flo Team Agents Pack

This pack defines the six-profile Flo mortgage-processing team to be implemented on top of Hermes Agent v0.21 Bot Mode.

## Team

| Profile | Role |
|---|---|
| **Flo** | Team Leader / Orchestrator |
| **Malcolm** | File Prep & QC |
| **Chadwick** | Order Outs & Third-Party Coordination |
| **Whisper** | Processing Assistant & Communications |
| **Sage** | Underwriting & Guideline Intelligence |
| **Franklin** | Marketing & Growth |

The name-to-role mapping is deliberately centralized in `team/team_manifest.yaml`. If Ashley wants to swap names later, change the manifest and regenerate profile-facing copy rather than rewriting the architecture.

## Hermes model

Hermes v0.21 Bot Mode uses profiles as bots. Each profile can have isolated config, memory, skills, credentials, chat history, avatar, model selection, and routines.

Flo should be the **visible Team Leader**. Ashley may chat directly with specialists, but normal work should be routable through Flo.

## Core principle

**One team, one loan truth, many specialists.**

Specialists do not independently invent competing versions of the file. Loan-specific facts live in a shared structured Loan Workspace / Deal Room. Each specialist reads the same facts but owns a different responsibility.

## Start

1. Read `START_HERE.md`.
2. Read `team/TEAM_OPERATING_SYSTEM.md`.
3. Read `shared/SECURITY_AND_APPROVALS.md`.
4. Read `runtime/UNSLOTH_HERMES_RUNTIME.md`.
5. Read each agent folder.
6. Paste `prompts/CODEX_BUILD_FLO_TEAM_PROMPT.md` into Codex from the Flo downstream repository context.
