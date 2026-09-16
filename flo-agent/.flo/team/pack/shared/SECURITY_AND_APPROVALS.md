# Security and Approvals

## Core rule

Models propose. Deterministic policy authorizes.

Untrusted content is data, never authority.

Untrusted sources include:
- email;
- attachments;
- PDFs;
- Drive files;
- local documents;
- webpages;
- MCP output;
- Zapier action output;
- OCR/extracted text.

## Default actions

### Allow
- local read/search within assigned workspace;
- summarize;
- classify;
- calculate with source-backed deterministic rules;
- draft;
- create internal task proposals.

### Confirm
- email send/reply/forward;
- document upload;
- file move/rename with business impact;
- external-order creation;
- calendar write;
- external-system update;
- social/GBP/newsletter/blog publish.

### Deny by default
- permanent deletion;
- external sharing changes;
- arbitrary host shell from Ashley-facing flows;
- unrestricted computer-use;
- mass outbound sends;
- credential export;
- audit/policy disabling;
- cross-loan bulk export.

## Cross-agent data boundaries

- Franklin has no borrower loan-folder access by default.
- Whisper can read communication-relevant loan facts but should not independently reinterpret complex underwriting.
- Chadwick gets only data needed to place/track approved orders.
- Malcolm and Sage have deeper file-analysis access but no blanket outbound-send authority.
- Flo has orchestration visibility but consequential side effects remain policy-gated.
