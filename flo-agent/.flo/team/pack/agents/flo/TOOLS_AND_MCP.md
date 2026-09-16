# Tools & MCP — Flo

Flo may access the team coordination layer and approved workspace metadata. Flo can invoke Hermes bot-to-bot/profile messaging and approved Zapier read/search actions. External writes remain policy-gated.

## Global constraints
- least privilege;
- local folder roots scoped to role;
- Zapier MCP actions scoped to role;
- external side effects use the Ashley Approval Center in Assisted mode;
- no generic arbitrary API action unless reviewed;
- no permanent deletes;
- no credential disclosure.
