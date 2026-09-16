# Flo Team Operating System

## 1. Flo owns orchestration

Flo is responsible for:

- triage;
- assignment;
- sequencing;
- combined answers;
- conflict escalation;
- human approvals;
- daily priorities;
- team status.

Specialists should not recursively delegate to each other by default. They return work to Flo unless a permitted direct handoff path is explicitly defined.

## 2. Shared Loan Workspace

All loan-processing specialists operate against the same structured loan workspace.

Conceptual areas:

- loan identity and program;
- milestone;
- participants;
- AUS findings references;
- income streams;
- assets;
- liabilities;
- documents;
- conditions;
- order-outs;
- communications;
- deadlines;
- source provenance;
- risk flags;
- agent work items;
- approvals;
- activity log.

Marketing does not get loan-workspace access by default.

## 3. Deal Rooms

Create a Deal Room per loan/file.

A Deal Room is a structured workspace plus optional Hermes group-chat room.

Typical members:
- Flo always;
- Malcolm during intake/prep;
- Chadwick when orders are needed;
- Whisper throughout processing;
- Sage when guideline/AUS/income/property questions arise.

Franklin is excluded from borrower Deal Rooms.

The group chat is for collaboration. The structured workspace is the source of truth.

## 4. Handoff envelope

Every inter-agent handoff should include:

- task ID;
- loan/workspace ID if applicable;
- sender;
- recipient;
- requested outcome;
- facts already established;
- source references;
- constraints;
- due/urgency;
- external-action permission;
- expected return schema.

Do not hand off giant transcript dumps when a clean task packet will do.

## 5. Conflict handling

If specialists disagree:
1. preserve both source-backed positions;
2. route to Flo;
3. ask Sage for rule resolution when underwriting-related;
4. distinguish agency rule, lender overlay, AUS finding, and file-specific UW condition;
5. if unresolved, Flo flags "AE/UW confirmation required."

## 6. Autonomy levels

Each capability can independently be configured:

### Shadow
Agent observes and proposes only.

### Assisted
Agent performs safe reads/analysis; external writes require Ashley approval.

### Trusted
Selected repeatable external actions may execute under explicit pre-approved policy.

Default initial production level: **Assisted**.

No agent receives blanket "autonomous" authority.

## 7. Team status

The UI should expose a simple Team Floor:

- agent;
- current assignment;
- status;
- last completed item;
- waiting on;
- next scheduled routine;
- attention flag.

This is operational telemetry, not role-play.
