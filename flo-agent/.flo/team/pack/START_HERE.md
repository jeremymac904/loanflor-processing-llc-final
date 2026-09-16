# Start Here

## Mission

Build Ashley a coordinated mortgage-processing team inside the Flo-branded Hermes Desktop app.

Flo is Team Leader. Five specialist Hermes profiles act as sub-bots:

- Malcolm — File Prep & QC
- Chadwick — Order Outs
- Whisper — Processing Communications
- Sage — Underwriting
- Franklin — Marketing

## Do not build five disconnected chatbots

The product needs:

- shared structured loan workspaces;
- deterministic routing;
- structured agent handoffs;
- a Team Activity view;
- a centralized Ashley approval queue;
- shared source/version registry;
- role-specific folder/tool boundaries;
- per-agent model routing;
- per-agent Zapier MCP action scopes;
- escalation back to Flo;
- audit events for meaningful actions.

## First implementation outcome

At the end of the Codex team-build pass:

- all six profiles exist in Hermes' actual profile format;
- each has a real `SOUL.md`;
- each has title, role, description, skills, model policy, tool policy, avatar asset/placeholder, and routine definitions;
- Flo can delegate to each specialist using supported Hermes bot-to-bot mechanisms;
- specialist outputs use a common handoff envelope;
- actions with external side effects pass through the Flo approval policy;
- profile data boundaries are testable;
- no real borrower data is used in tests;
- underwriting rules remain source-backed;
- local Unsloth is available as a configurable provider without hard-coding every bot to it.
