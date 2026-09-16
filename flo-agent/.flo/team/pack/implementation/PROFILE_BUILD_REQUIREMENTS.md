# Profile Build Requirements

Codex must inspect Hermes v0.21's actual profile RPC/CLI/file conventions instead of assuming this pack is the runtime schema.

For each profile create:
- profile ID;
- display name;
- title;
- description;
- actual `SOUL.md`;
- `USER.md`/shared Ashley preference strategy as appropriate;
- model/provider preference;
- tool allowlist;
- MCP configuration/scopes;
- skills;
- routines;
- avatar;
- workspace-root allowlist;
- safe defaults.

Do not duplicate secrets between profiles unless the credential architecture deliberately uses a broker.

If Zapier MCP credentials must be profile-specific, provision them outside Git.

## Bot-to-bot

Use Hermes-native bot/profile messaging/group-chat primitives.

Do not implement a second proprietary multi-agent transport unless Hermes cannot meet a concrete requirement.

## Desktop

Expose:
- Flo Team roster;
- title/role;
- avatar;
- online/current-task state where feasible;
- Deal Rooms;
- approval queue;
- Team Activity;
- agent-specific direct chat.

Bot Mode UI bugs must not prevent the core profiles/CLI/gateway orchestration from working.
