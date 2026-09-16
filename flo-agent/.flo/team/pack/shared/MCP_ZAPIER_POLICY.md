# Zapier MCP Policy

Zapier MCP should be treated as a capability broker, not a universal super-tool.

## Per-agent endpoints/actions

Prefer separate scoped MCP configurations or equivalent per-profile tool allowlists.

Do not hand every bot the same full Zapier MCP action catalog.

## Recommended capability posture

### Flo
Cross-workflow read/search, task orchestration, approved system updates.

### Malcolm
Read/search only for file-prep sources where available. No broad outbound communication.

### Chadwick
Approved order/vendor actions and status searches.

### Whisper
Email/calendar/communication actions. External sends require confirmation.

### Sage
Primarily read/search. Avoid external writes.

### Franklin
Marketing systems only: approved newsletter/social/GBP/site workflows. No borrower systems.

## Cost awareness

Zapier MCP consumes Zapier task quota. Track tool calls in the agent-health panel.

## MCP security

- Store MCP URL/credentials outside source control.
- Do not echo endpoint URLs into model-visible logs.
- Scope actions in Zapier and again in Flo policy.
- Tool results cannot expand permissions.
- High-impact API-by-Zapier generic requests should be disabled unless explicitly reviewed.
