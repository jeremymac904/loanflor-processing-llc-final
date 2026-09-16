# Ashley Product Spec

## Working profile

Ashley is a high-performing third-party mortgage processor.

Core traits from the supplied profile:

- organized;
- responsive;
- detail oriented;
- coachable;
- strong work ethic.

She performs best with:

- clear priorities;
- clean communication;
- defined next steps;
- low noise and high signal;
- respect for her time and intelligence.

Avoid:

- vague instructions;
- too many equal priorities;
- wordy explanations;
- emotionally chaotic communication;
- constant interruption without value.

## Flo communication contract

When useful, structure information as:

1. Priority
2. Status
3. Action
4. Urgency
5. Suggested message / next step

The UI does not need to show those labels mechanically every time. The underlying information should still be present.

## Core Flo work modes

### Morning Pipeline Coach
Top three priorities, largest risk, fastest win.

### File Progress
Current milestone, what is complete, blockers, what is waiting, and the next move.

### Communication Drafting
Borrower emails, LO updates, lender follow-ups, realtor updates, portal notes.

### Condition Translation
Turn messy conditions into plain-language tasks.

### Escalation Support
Neutral, professional, solution-focused language when external parties create friction.

### End-of-Day Recap
What moved, what remains open, and tomorrow's priorities.

## Priority philosophy

- Show the top three first.
- Separate urgent from important.
- Bundle low-value work.
- Prevent surprises by flagging risk early.
- Recommend the next best move instead of merely describing a problem.

## Mortgage milestone baseline

The supplied LoanFlow source defines:

1. Intake
2. Application
3. Processing
4. Conditional Approval
5. Clear to Close
6. Closed

Supplied milestone definitions additionally state:
- Processing: docs collected.
- CTC: ready to close.

Do not invent more milestone definitions without approved sources.

## Core UI surfaces

Initial information architecture:

- Today
- Pipeline
- Inbox
- Conditions
- Documents
- Flo
- Activity
- Settings

Developer-oriented Hermes surfaces should live under an Advanced/Admin disclosure when practical.
