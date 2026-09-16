# Flo mortgage skills

Bundled skills for the Flo distribution (downstream of Hermes Agent). Each
skill is source-backed: it states only what the owner-supplied material in
`.flo/source_material/` supports, records provenance and a review date, and
marks everything else `SOURCE_GAP`. None of them contains an income formula,
agency rule, overlay, or compliance library — those have not been supplied.

| Skill | Source-backed content |
|---|---|
| `flo-processing-workflow` | Six milestones in order: Intake, Application, Processing, Conditional Approval, Clear to Close, Closed |
| `flo-milestones` | Processing = docs collected; CTC = ready to close |
| `flo-income-analysis` | Guide covers W2, self-employed, rental income (no rules supplied) |
| `flo-tpo-guidelines` | Follow agency rules; confirm overlays with AE |
| `flo-communication` | Ashley's communication contract (priority, status, action, urgency, next move) |
| `flo-compliance-messaging` | One approved borrower template |
| `flo-notes-and-emails` | One sample note as a tone seed |

Tests: `tests/skills/test_flo_mortgage_skills.py` (plus the repo-wide
`tests/skills/test_authoring_standards.py`). Onboarding new sources follows
`.flo/docs/09_MORTGAGE_SKILLS_PLAN.md`.
