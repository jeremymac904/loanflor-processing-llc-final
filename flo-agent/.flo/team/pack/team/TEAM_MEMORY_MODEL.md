# Team Memory Model

## Shared memory

Suitable:
- Ashley communication preferences;
- approved operating procedures;
- shared glossary;
- vendor/contact reference IDs;
- non-sensitive process lessons approved for reuse.

## Agent-private memory

Suitable:
- role-specific heuristics;
- tool usage notes;
- routine preferences;
- non-sensitive agent-specific working state.

## Loan workspace memory

Suitable:
- file-specific status;
- conditions;
- document references;
- calculations;
- order statuses;
- communication references;
- provenance.

## Never promote automatically

A one-off UW condition, lender exception, borrower fact, or agent guess must not become a global rule.

## Learning workflow

Agent notices pattern
-> proposes reusable lesson
-> Flo reviews
-> Ashley/admin approves when meaningful
-> store with source and scope
-> regression test if it changes underwriting behavior.
