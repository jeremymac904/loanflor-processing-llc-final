# Mortgage Skills Plan

## Principle

Use skills for progressively disclosed domain knowledge. Keep skill content source-backed and version-controlled.

## Initial skill set

### `flo-processing-workflow`
Source-backed facts:
- structured workflow from intake to closing;
- milestones: Intake, Application, Processing, Conditional Approval, Clear to Close, Closed.

### `flo-milestones`
Source-backed facts:
- Processing: docs collected.
- CTC: ready to close.

Anything beyond those supplied definitions is a source gap.

### `flo-income-analysis`
Current supplied source only says the guide covers:
- W2 income;
- self-employed income;
- rental income evaluation.

Do **not** invent formulas, averaging periods, add-backs, loss treatment, agency matrices, or documentation requirements. Scaffold the skill with explicit `SOURCE_GAP` sections awaiting authoritative content.

### `flo-tpo-guidelines`
Source-backed rule:
- follow agency rules;
- confirm overlays with AE.

Flo must communicate uncertainty and avoid fabricating overlays.

### `flo-communication`
Derived from Ashley's communication profile:
- concise;
- priority/status/action/urgency;
- next-best move;
- low-noise;
- neutral under friction;
- ready-to-send drafts where useful.

### `flo-compliance-messaging`
Current supplied safe template:
- "Your loan is progressing. We will update you at next milestone."

Do not treat this single sample as a comprehensive compliance library.

### `flo-notes-and-emails`
Current supplied sample:
- file moving through processing;
- appraisal ordered.

Use as a tone/example seed only.

## Skill metadata requirements

Each Flo mortgage skill should include:
- purpose;
- scope;
- authoritative source list;
- last-reviewed date;
- source gaps;
- prohibited inference notes;
- examples;
- tests/evals where feasible.

## Provenance

For material decisions, Flo should be able to identify which approved skill/source informed the answer.

## Future source onboarding

When more guidelines are supplied:
1. store original source;
2. extract/version normalized content;
3. identify issuer/program/effective date;
4. write or update skill;
5. add evals;
6. have a human review;
7. mark previous guidance superseded rather than silently deleting historical context.

## Underwriting source onboarding correction

The first-class Underwriting Knowledge Engine in `UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md` owns guidelines/calculators. Skills are thin workflow instructions, not the rule store. The earlier source-onboarding steps do not authorize putting original guides in Git: first review rights, use an authorized private cache, record immutable revision/checksum/effectiveness, review normalized rules and regressions, then approve activation. No original guide or extracted corpus is bundled by this bootstrap.
