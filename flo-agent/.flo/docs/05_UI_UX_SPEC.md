# UI / UX Spec

## Experience target

Flo should feel like a focused mortgage-processing command center, not a general-purpose developer agent console.

## Navigation

### Today
Default landing surface.

Show:
- greeting;
- top three moves;
- biggest risk;
- fastest win;
- waiting items;
- approvals needing Ashley;
- optional routine summary.

### Pipeline
Loan/file list grouped or filterable by milestone.

Each row should make it easy to see:
- file/loan display name;
- milestone;
- next action;
- blocker;
- urgency;
- waiting-on party;
- last meaningful update.

### Inbox
Flo-assisted work queue for approved email sources.

Prioritize:
- needs reply;
- new condition/request;
- borrower document received;
- lender decision/status;
- informational/no action.

Never auto-send from the queue in the initial release.

### Conditions
Normalize conditions into:
- request;
- plain-English meaning;
- source;
- required documents/actions;
- owner;
- due/urgency;
- status.

### Documents
Show approved document references and review status. Prefer linking to the system of record rather than duplicating sensitive files.

### Flo
Primary conversational workspace.

### Activity
Human-readable audit of meaningful agent/tool actions and approval decisions.

### Settings
Connections, model/provider, workspace permissions, routines, Flo appearance, and Advanced/Admin.

## Interaction rules

- Top priorities above comprehensive lists.
- No dashboard that shows ten equal red alerts.
- Use progressive disclosure.
- Keep confirmations specific: what will happen, to whom/where, and what data is involved.
- Show source/provenance for important extracted facts.
- Make "Draft" visually distinct from "Sent".
- Make "Proposed action" visually distinct from "Executed action".
- When Flo is uncertain, expose the uncertainty and source gap.

## Flo presence

Use the Flo avatar at:
- onboarding;
- assistant header;
- empty state;
- approval dialogs;
- compact activity indicators where clarity benefits.

Do not wallpaper the application with the character.

## Initial rebrand targets

At minimum:
- product name;
- window title;
- app/executable name;
- installer artifact name;
- deep-link protocol;
- icons;
- onboarding copy;
- empty-state wordmark;
- notifications;
- macOS/Windows metadata;
- update copy;
- help/about labels.

Keep an explicit allowlist of remaining internal "Hermes" references that are not user-visible and are preserved for upstream compatibility.
