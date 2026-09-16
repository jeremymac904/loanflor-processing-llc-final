# Project Charter

## Product

**Flo Agent** - a customized desktop agentic assistant for Ashley's mortgage-processing workflow.

## User

Ashley is a high-performing third-party mortgage processor. The system should help her work faster and more clearly with fewer interruptions and less decision fatigue.

## Primary outcomes

Flo should eventually:

- surface the highest-value priorities for the day;
- track files through mortgage-processing milestones;
- identify blockers and the cleanest next action;
- search and summarize approved email/document sources;
- translate lender/underwriter conditions into clear action lists;
- draft borrower, LO, lender, realtor, and portal communication in Ashley's preferred style;
- support income-evaluation workflows using source-backed rules;
- prepare morning briefs, risk checks, and end-of-day recaps;
- maintain clear provenance and an audit trail;
- require approval for consequential external actions.

## Non-goals for the initial pass

- autonomous lender-portal submission;
- unrestricted computer control;
- automatic deletion or sharing of borrower documents;
- unsupervised outbound borrower/lender communication;
- replacing underwriting or legal/compliance review;
- full replacement of every internal Hermes identifier;
- self-modifying agent code in production.

## Product identity

User-facing name: **Flo Agent**

Assistant name: **Flo**

Internal upstream lineage: **Hermes Agent**

Flo is a downstream distribution. Preserve the Hermes MIT license and attribution requirements.

## Success standard

Every Ashley-facing Flo response should answer, as appropriate:

- What matters most?
- What is the current status?
- What needs to happen next?
- How urgent is it?
- What is the cleanest action or ready-to-send draft?

The product should reduce noise, not create it.
