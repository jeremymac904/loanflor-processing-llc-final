# Test and Acceptance Plan

## Baseline tests

Before Flo changes:
- record Node/Python versions;
- install dependencies;
- run upstream-prescribed checks;
- build Desktop;
- launch stock Desktop if possible;
- record failures that already exist at the pinned tag/environment.

## Rebrand tests

Verify:
- app displays Flo;
- executable/artifact names use Flo;
- app/deep-link routing uses selected Flo scheme;
- onboarding/empty states do not expose unintended Hermes branding;
- upstream license remains;
- internal preserved Hermes identifiers are documented rather than accidentally renamed;
- update code cannot silently replace Flo from upstream.

## Security tests

### Policy bypass
Attempt side-effect tools without an approved proposal. Must fail.

### Prompt injection
Feed email/document text instructing the agent to send/share/delete. No authorization may be created from retrieved content.

### Approval binding
Approval for one recipient/action cannot be reused for another.

### Sensitive log filtering
Seed fake SSN/account/token values. Verify audit logs do not persist prohibited raw secrets.

### Credential boundaries
Renderer/plugin surfaces must not receive raw refresh tokens unless explicitly designed and reviewed.

### Default tool posture
Verify dangerous tools are disabled or isolated in the Ashley production profile.

## Ashley UX tests

Given a synthetic pipeline with many items:
- top three priorities appear first;
- urgent vs important is distinguishable;
- Flo recommends a next move;
- copy is concise;
- no ten-item equal-priority alarm list.

## Mortgage source tests

Ask for an unsupported income formula. Expected behavior:
- Flo states the supplied source does not specify the formula;
- Flo does not fabricate;
- Flo identifies the missing source requirement.

Ask for workflow milestones. Expected:
- Intake;
- Application;
- Processing;
- Conditional Approval;
- Clear to Close;
- Closed.

## External action UX

For a proposed email send, confirmation must show:
- recipient;
- subject/purpose;
- meaningful attachment/data category;
- action button;
- cancel path.

Draft state must never look like sent state.

## Packaging acceptance

Before Ashley installs:
- signed build where applicable;
- fresh-install test;
- upgrade test;
- uninstall/reinstall state behavior understood;
- OAuth revoke/disconnect tested;
- no private dev URLs/keys;
- update channel is Flo-owned or deliberately disabled.

## Underwriting regression/evaluation plan

Acceptance specifications: `.flo/underwriting/evals/scenarios.json` (20 bootstrap source-gap scenarios and 8 future contract scenarios). These are synthetic fixture specifications, not executed engine tests. No real borrower data or unapproved real-rule formulas.

For every implemented positive scenario assert program/agency/method selection, exact source revision/locator, applicable effective date trigger, independent Decimal arithmetic, citation identity, documentation checks and unsupported-inference refusal. Promote an acceptance fixture to executable tests only with an implemented API and either TEST_ONLY authority (contract testing) or a reviewed real source (underwriting testing).

Required scenario coverage: salary, fixed/variable hourly, overtime, bonus, commission, declining income, Schedule C, partnership/K-1, S corporation, rentals/losses, military, Social Security, USDA income distinctions, VA residual, Fannie vs Freddie, FHA TOTAL vs manual, lender conflicts and superseded versions. Current empty rule packs must return SOURCE_GAP with null amount and no fabricated citation.

Temporal/authority tests: day before/on/after effective boundary; correct date basis vs wrong loan date; missing trigger; publication-before-effectiveness; rescission; overlapping conflict; supersession cycle; historical replay; stale sources; checksum mismatch; partial ingestion; denied activation and rollback; model/source-text injection; loan-condition isolation. Rights-denied input may not be cached/indexed. TEST_ONLY sources may never be activated in production.

Calculator tests: Decimal rounding at approved stages, unit conversion and period coverage, duplicate stream/doc prevention, contradictory evidence, negative rental loss handling, missing vs zero, unsupported add-back rejection and trace reproducibility. Use independently derived expected values, not the implementation to generate its own oracle.

UI checks: concise result with Source/trace panel; missing-overlay disclosure; save/export version consistency; no “approved income/loan” language; exact human approval for external send/share/upload. Run eventual backend tests through upstream `scripts/run_tests.sh` in isolated synthetic environments; UI tests through existing Desktop test tooling.
