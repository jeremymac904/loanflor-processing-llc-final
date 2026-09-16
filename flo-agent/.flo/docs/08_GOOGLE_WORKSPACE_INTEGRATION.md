# Google Workspace Integration

## Goal

Flo should eventually connect to Ashley's approved Google Workspace account for Gmail and Drive-centered processing work.

## Do not blindly ship the stock Hermes Google Workspace setup

At the researched baseline, the stock Hermes setup script requests a broad group of scopes including Gmail read/send/modify, Calendar, full Drive, Contacts read, Sheets, and Docs.

Flo should implement a purpose-built connector with staged, least-privilege authorization.

## Recommended staged capability model

### Stage 1 - Gmail read + draft
Capabilities:
- search/read email;
- classify;
- extract requests;
- create a local Flo draft.

No external send.

### Stage 2 - Gmail send with confirmation
Add send capability. Every send remains Yellow and requires Ashley confirmation.

Only request Gmail modify if archive/label/move behavior is actually implemented and approved.

### Stage 3 - Drive read
Prefer the narrowest workable scope.

Two product modes may be needed:

**Selected-file mode**
Use a per-file/limited authorization pattern where possible. Best privacy posture.

**Workspace search mode**
If Ashley explicitly needs Flo to discover across her Drive, a broader read-only scope may be required. Keep write capabilities separate.

### Stage 4 - Document writes
Only after a concrete workflow requires it. Use explicit confirmation and restrict destination.

## Credential architecture

Electron/main or another trusted host component should own sensitive OAuth tokens.

Renderer code and ordinary plugins should receive capability results or broker handles, not raw refresh tokens.

## Connection UX

Settings -> Connections -> Google Workspace

Show:
- connected account;
- scopes/capabilities granted in plain language;
- last successful sync/use;
- Reconnect;
- Revoke/Disconnect;
- capability toggles where technically meaningful.

## Connector API shape

Prefer capability-level methods such as:
- `searchMail(query)`
- `readMail(messageId)`
- `createDraft(proposal)`
- `sendApprovedDraft(approvalId)`
- `searchDrive(query)`
- `readDriveFile(fileId)`
- `uploadApprovedFile(approvalId)`

Do not expose a generic "run arbitrary Google API request" tool to the model.

## Data handling

Cache metadata minimally.

Store provider IDs/references where possible rather than duplicating entire mailboxes or Drive contents into Flo state.
