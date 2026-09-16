# Fannie Mae source activation — Golden Loan Path (2026-09-08)

## What was activated

Twelve sections of the official **Fannie Mae Selling Guide** (edition published 2026-09-02, `https://selling-guide.fanniemae.com/`), fetched directly from the official site by `scripts/flo/fetch_fannie_sources.py`. No blog, summary, or AI paraphrase is treated as authority; the WebFetch summaries used during research were only a map to the sections, and every rule record's anchor phrase was verified against the cached official text.

| Section | Title | Page date | Retrieved (UTC) | Text sha256 (12) | Revision |
|---|---|---|---|---|---|
| B3-3.1-01 | General Income Information | 03/04/2026 | 2026-09-09T02:5x | 69941a7d4648 | fannie-b3-3.1-01-69941a7d4648 |
| B3-3.2-01 | Standards for Employment and Income Documentation | 03/04/2026 | same run | 7ef253f338df | fannie-b3-3.2-01-7ef253f338df |
| B3-3.2-02 | Standards for Employment-Related Income | 03/04/2026 | same run | 9e2f20f2822e | fannie-b3-3.2-02-9e2f20f2822e |
| B3-3.3-01 | Base Income | 03/04/2026 | same run | 23295e8b3b2d | fannie-b3-3.3-01-23295e8b3b2d |
| B3-3.3-02 | Bonus, Commission, Overtime, and Tip Income | 03/04/2026 | same run | 71c0337b8a7d | fannie-b3-3.3-02-71c0337b8a7d |
| B3-3.1-04 | Verbal Verification of Employment | 03/04/2026 | same run | 850c04a51301 | fannie-b3-3.1-04-850c04a51301 |
| B3-4.2-01 | Verification of Deposits and Assets | 05/04/2022 | same run | e2bec9337187 | fannie-b3-4.2-01-e2bec9337187 |
| B3-4.2-02 | Depository Accounts | 12/14/2022 | same run | 852468d807a3 | fannie-b3-4.2-02-852468d807a3 |
| B3-4.1-01 | Minimum Reserve Requirements | 08/07/2024 | same run | a1523932fa1a | fannie-b3-4.1-01-a1523932fa1a |
| B1-1-03 | Allowable Age of Credit Documents and Federal Income Tax Returns | 04/02/2025 | same run | d19e85a799e2 | fannie-b1-1-03-d19e85a799e2 |
| B3-2-10 | Accuracy of DU Data, DU Tolerances, and Errors in the Credit Report | 12/04/2019 | same run | 45b8a014ccb7 | fannie-b3-2-10-45b8a014ccb7 |
| B3-2-11 | DU Underwriting Findings Report | 09/07/2022 | same run | dcbba1093184 | fannie-b3-2-11-dcbba1093184 |

Exact timestamps, full checksums (HTML and extracted text), official URLs, cache references and rights notes: `plugins/flo-team/knowledge/fannie/sections.json`. The page date is the guide's per-topic "(mm/dd/yyyy)" marker, which Fannie defines as the date of the most recent announcement amending the topic; the policy effective date is in that announcement (not resolved per rule in this pass, recorded as the section date).

## Where the text lives

Private cache only: `%LOCALAPPDATA%\hermes\flo\sources\cache\fannie\<section>.{html,txt}` on this machine. Nothing from the guide is committed. Rights basis: Fannie Mae's copyright-and-preface grants approved lenders and other mortgage-finance professionals limited permission to reproduce the guide for their own origination use and reserves the right to revoke it; this cache is for LoanFlow Processing's own processing work and is not redistributed. The repository carries citations and 34 paraphrased rule records (`rules.json`) with anchor phrases.

## Lifecycle record (per-install, `%LOCALAPPDATA%\hermes\flo\team\knowledge\fannie-*.json`)

1. `detected` — fetch script, checksum recorded.
2. `pending_review` → `regression` — `scripts/flo/activate_fannie_slice.py --review`: each rule's anchor phrase found in the cached official text (34 anchors, 12 receipts). One record was corrected during review: the summarizer had produced "all pages are required" for B3-4.2-02; the official text does not say that, so the rule now cites B3-4.2-01's actual content requirement ("all deposit and withdrawal transactions … ending account balance") and incomplete statements fail on that basis.
3. `approval` → `active` — `--approve --activate --approver "owner" --basis "Golden Loan Path directive 2026-09-08"`. The approver identity recorded is the owner running this build session (the directive itself instructed the activation). The sandbox policy blocked a first attempt whose approver string included the owner's email; the recorded approver is the plain word `owner`. To revoke: `--archive <section> --approver <name>`.

Activation re-hashes the cache before flipping to active; a changed cache demotes to `STALE_SOURCE` at read time (tested), and a re-fetch with new content demotes the revision to `detected`.

## What the activated set covers (and does not)

Covers: employment/base income definitions, documentation (paystub 30-day / YTD, most recent W-2, verbal VOE / Form 1005), history and continuance, the base-income calculation table by pay frequency, variable base income (average income and average hours methods, trend handling), YTD consistency, bonus/overtime/commission history and trend rules, asset verification content and statement periods, depository accounts and large deposits (50% rule, purchase vs refinance), reserves definition and DU one-unit primary rule, document age (four months), DU tolerances (DTI 45% / 3 points, reserves 90%), DU findings report usage.

Not covered (SOURCE_GAP): self-employment, rental, other income types; gifts, retirement, business funds, sale proceeds, virtual currency; liabilities beyond the DTI tolerance rule; property/appraisal; any lender overlay (Loan Factory `NOT_LOADED`); Freddie/FHA/VA/USDA.

## Reusable for other programs

The fetch → checksum → rules-with-anchors → regression → human approval → active pipeline, the per-install lifecycle state, `section_status`/`is_active` gating, and the Guideline Card renderer are program-agnostic. Only the section list, URL slugs and rule records are Fannie-specific.
