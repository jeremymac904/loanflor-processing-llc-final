IMPORTANT ADDITION TO THE FLO AGENT REQUIREMENTS:

Flo must have a first-class, source-backed **Underwriting Knowledge Engine**.

This is not optional and should be treated as a core product capability.

Do NOT attempt to encode all underwriting rules inside SOUL.md, CLAUDE.md, a giant system prompt, or model memory.

The underwriting library needs to be:

* program aware;
* source backed;
* versioned;
* effective-date aware;
* citation capable;
* updateable;
* lender-overlay aware;
* calculation traceable.

# PRIMARY LOAN PROGRAMS

At minimum, establish underwriting knowledge packs for:

## Conventional — Fannie Mae

Authoritative baseline:

Fannie Mae Selling Guide

Include relevant originating/underwriting guidance for:

* borrower eligibility;
* employment;
* income;
* self-employment;
* rental income;
* assets;
* reserves;
* liabilities;
* debt-to-income;
* credit;
* derogatory credit;
* property;
* appraisal;
* occupancy;
* transaction type;
* LTV/CLTV;
* gifts;
* interested party contributions;
* documentation requirements;
* verification/reverification;
* Desktop Underwriter considerations where applicable.

Treat Fannie/DU rules as Fannie rules.

Do not silently apply them to Freddie loans.

---

## Conventional — Freddie Mac

Authoritative baseline:

Freddie Mac Single-Family Seller/Servicer Guide

Include the same relevant underwriting domains, including:

* employed income;
* additional/variable income;
* self-employed income;
* rental income;
* assets;
* liabilities;
* reserves;
* credit;
* property;
* eligibility;
* documentation;
* Loan Product Advisor considerations where applicable.

Treat Freddie/LPA rules separately from Fannie/DU rules.

Do not create a fake generic "Conventional" calculation when the agencies differ.

---

## FHA

Authoritative baseline:

HUD/FHA Single Family Housing Policy Handbook 4000.1

Account for distinctions such as:

* TOTAL Mortgage Scorecard;
* manual underwriting;
* employment-related income;
* self-employed income;
* rental income;
* assets;
* liabilities;
* credit;
* compensating factors where applicable;
* property requirements;
* appraisal;
* borrower eligibility;
* occupancy;
* source of funds;
* gifts;
* reserves;
* documentation and reverification;
* FHA program-specific requirements.

Monitor Handbook updates, Mortgagee Letters, FHA INFO announcements, supplemental documents, and applicable effective dates.

Do not assume an old Handbook extract is still current.

---

## VA

Authoritative baseline:

VA Pamphlet 26-7 — Lenders Handbook

Track applicable VA Circulars and other current VA Loan Guaranty guidance in addition to the handbook.

Include:

* credit underwriting;
* effective income;
* military income;
* employment;
* self-employment;
* other income;
* assets;
* debts and obligations;
* credit;
* residual income;
* DTI analysis;
* compensating factors;
* occupancy;
* entitlement-related processing information where relevant to Ashley's job;
* property/MPR requirements;
* appraisal;
* documentation.

VA residual-income analysis must remain VA-specific.

Do not reduce VA underwriting to a conventional DTI calculation.

---

## USDA Guaranteed

Authoritative baseline:

USDA Rural Development HB-1-3555
Single Family Housing Guaranteed Loan Program Technical Handbook

Track related Procedure Notices and current USDA guidance.

Include:

* household eligibility income;
* adjusted annual income;
* repayment income;
* stable and dependable income;
* assets;
* credit;
* ratio analysis;
* GUS;
* manual underwriting;
* property/appraisal;
* eligible property;
* occupancy;
* documentation;
* program eligibility.

USDA has different income concepts.

Do not collapse:

* annual household income;
* adjusted annual income;
* repayment income

into one generic "qualifying income" field.

---

# SPECIAL / INVESTOR LOAN TYPES

Prepare the architecture for:

* Jumbo
* Non-QM
* DSCR
* Bank Statement
* Asset Depletion
* Investor Cash Flow
* Foreign National
* ITIN
* alternative documentation programs
* lender-specific specialty products

BUT DO NOT CREATE UNIVERSAL RULES FOR THESE.

These products generally depend on the actual lender/investor program guide.

Create a structure such as:

underwriting/
agency/
fannie/
freddie/
fha/
va/
usda/
lenders/ <lender>/
overlays/
programs/
investor/ <investor>/ <program>/

If Ashley or the project owner later supplies:

* Loan Factory overlays;
* lender matrices;
* AE guidance;
* non-QM matrices;
* Jumbo guides;
* investor guides;

Flo should ingest those separately.

The currently supplied Loan Factory TPO material only tells us to follow agency guidelines and confirm overlays with the AE.

Do not invent missing Loan Factory overlays.

---

# SOURCE HIERARCHY

Design a deterministic source-resolution system.

Conceptually, a loan should have:

Loan Program
+
Agency/GSE
+
Underwriting Method / AUS
+
Applicable Current Agency Guidance
+
Applicable Lender Overlay
+
Applicable Investor/Product Guide
+
Loan-Specific Underwriter Conditions

Do not blend these layers invisibly.

Flo needs to be able to explain:

"Agency baseline says X."

"Lender overlay adds Y."

"Underwriter requested Z on this specific file."

Loan-specific underwriter conditions must NOT automatically become global underwriting rules.

---

# UNDERWRITING SOURCE REGISTRY

Create a structured source registry.

Each source should track fields similar to:

source_id
source_type
agency
program
document_name
section
official_source
publication_date
effective_date
retrieved_at
version
checksum
supersedes
superseded_by
active
notes

The exact schema may differ based on Hermes/Flo architecture.

What matters is that Flo knows which version a rule came from.

Never silently replace a guide without recording the change.

---

# CURRENT VS ARCHIVED GUIDANCE

The knowledge system should distinguish:

CURRENT

FUTURE / ANNOUNCED BUT NOT YET EFFECTIVE

SUPERSEDED

ARCHIVED

UNKNOWN

A rule must not become active merely because a newer document exists.

Use the rule's effective date.

If a guideline applies based on application date, note date, case assignment date, AUS submission date, or another program-specific trigger, preserve that distinction when supported by the source.

---

# CITATION REQUIREMENT

When Flo gives Ashley an underwriting answer, it should be capable of returning something like:

Program:
Fannie Mae Conventional

Topic:
Rental Income

Source:
Fannie Mae Selling Guide

Section:
B3-3.8-02

Effective/Published:
specific date

Conclusion:
concise answer

Calculation:
if applicable

Overlay:
none loaded / specific lender overlay

Confidence:
source-backed

Flo should not force Ashley to read a huge citation block every time.

The UI can show a concise result with:

"View guideline"

or:

"Source"

for progressive disclosure.

But the underlying source reference must exist.

---

# INCOME CALCULATION ENGINE

Income calculation needs its own structured subsystem.

Do not treat it as an LLM arithmetic prompt.

Design an Income Calculation Engine where deterministic code performs arithmetic and the model helps:

* identify income type;
* identify relevant documents;
* interpret context;
* explain the result;
* identify missing documentation;
* identify conflicting evidence.

The calculation engine must be PROGRAM AWARE.

Example:

calculate_income(
program,
agency,
income_type,
documentation,
dates,
history,
applicable_overlay
)

Exact API is flexible.

---

# INCOME TYPES

Prepare source-backed support for common categories including:

## Employment

* salary;
* fixed hourly;
* variable hourly;
* overtime;
* bonus;
* commission;
* tips;
* shift differential;
* secondary employment;
* seasonal employment;
* temporary employment;
* union employment where applicable.

## Self-Employment

* sole proprietor / Schedule C;
* partnership;
* S corporation;
* corporation;
* LLC treatment where applicable;
* K-1;
* business tax returns;
* personal tax returns;
* YTD profit and loss;
* balance sheet where required;
* business liquidity;
* declining income;
* business-use-of-home adjustments where supported;
* depreciation/depletion/amortization adjustments only when source-backed;
* recurring vs nonrecurring income/expense treatment only when source-backed.

## Rental Income

* subject property;
* non-subject property;
* departing residence;
* investment property;
* multi-unit primary residence;
* leases;
* appraisal rent schedules;
* Schedule E;
* PITIA treatment;
* rental losses;
* newly acquired rentals;
* short-term rental rules when applicable.

## Other Income

Prepare source categories for, where supported by the applicable guide:

* Social Security;
* pension;
* retirement;
* annuity;
* disability;
* alimony;
* child support;
* separate maintenance;
* trust income;
* note receivable;
* interest/dividend income;
* capital gains;
* stock/RSU income;
* restricted stock;
* foster care;
* unemployment;
* public assistance;
* military pay;
* military allowances;
* VA benefits;
* boarder income;
* royalty income;
* foreign income;
* miscellaneous recurring income.

Do not assume every source is acceptable under every loan program.

---

# CALCULATION TRACE

Every calculated income result should be capable of producing a trace.

For example:

Income Type:
Overtime

Documents:
2024 W-2
2025 W-2
2026 YTD paystub through 08/31/26

Program:
Freddie Mac

Rule Source:
Guide section X

History Used:
24 months + YTD

Calculation:
show actual deterministic arithmetic

Trend:
increasing / stable / declining

Qualifying Monthly Income:
$X

Documentation Missing:
none / list

Caution:
specific source-backed issue

Overlay:
specific lender rule or none loaded

Do not expose chain-of-thought.

Show the calculation inputs, formula, arithmetic, and source-supported conclusion.

---

# INCOME WORKSHEET UI

Eventually Ashley should have an Income Analysis workspace.

Conceptual flow:

Upload / select docs

→ Flo identifies documents

→ Flo identifies borrower/employer/business/income streams

→ Ashley confirms classification if necessary

→ Flo determines applicable program rules

→ deterministic calculator runs

→ Flo presents:

Income Stream
Documentation
Calculation
Monthly Qualifying Income
Trend
Missing Items
Guideline Source
Warnings

→ Ashley can save/export a clean processing worksheet.

Keep calculations auditable.

---

# TAX RETURN ANALYSIS

Prepare the architecture for tax-return analysis but do not overbuild unsupported formulas.

Eventually Flo should understand common mortgage documentation including:

* Form 1040;
* Schedule 1;
* Schedule B;
* Schedule C;
* Schedule D;
* Schedule E;
* Schedule F;
* Form 1065;
* Form 1120;
* Form 1120-S;
* Schedule K-1;
* W-2;
* 1099s;
* business P&L;
* balance sheet.

But adjustment logic must come from the applicable approved underwriting source.

Do not allow the model to invent tax-return add-backs.

---

# DOCUMENT REQUIREMENT ENGINE

Underwriting knowledge should also support a question such as:

"What do I still need for this income?"

Return:

Available documentation

Missing documentation

Reason required

Program

Guideline citation

Lender overlay if applicable

This should integrate with Flo's Conditions/File Progress functionality.

---

# RULE CONFLICT HANDLING

If sources conflict:

DO NOT silently choose one.

Determine whether the difference is caused by:

* different agency;
* different loan program;
* different AUS/manual method;
* different effective dates;
* lender overlay;
* investor overlay;
* superseded guidance;
* loan-specific underwriter condition.

If still unresolved, tell Ashley:

"Guideline conflict — needs AE/UW confirmation."

That is preferable to hallucinating certainty.

---

# KNOWLEDGE UPDATE SYSTEM

Design the system so approved underwriting sources can be refreshed later.

At minimum provide a manual/admin workflow:

Check official source

→ detect version/date change

→ retrieve/index new version

→ compare metadata

→ mark source pending review

→ run regression tests

→ human/admin approval

→ activate new version

→ archive old version

Do NOT allow an unattended web scrape to silently rewrite production underwriting logic.

Eventually we may automate monitoring, but activation should remain controlled.

---

# REGRESSION TESTS / EVALS

Build a suite of synthetic mortgage scenarios.

Do not use real borrower data.

Examples should cover:

* salaried income;
* fixed hourly;
* variable hourly;
* overtime;
* bonus;
* commission;
* declining income;
* self-employed Schedule C;
* partnership/K-1;
* S corporation;
* rental income;
* rental loss;
* military income;
* Social Security;
* USDA household vs repayment income;
* VA residual income;
* Fannie vs Freddie rule differences;
* FHA TOTAL vs manual differences;
* lender overlay conflicts;
* superseded guideline versions.

Each test should assert:

program selected correctly;
source selected correctly;
effective version selected correctly;
math correct;
citation correct;
missing docs recognized;
unsupported inference rejected.

---

# VERY IMPORTANT PRODUCT BEHAVIOR

Flo is Ashley's processing assistant.

Flo can say:

"Using the current Fannie guideline, here is the qualifying calculation."

Flo should NOT say:

"I approved this income."

or:

"This loan is approved."

or imply it is acting as the lender/underwriter when it is not.

Preferred language:

"Guideline-supported calculation"

"Based on the documents currently available"

"Potential issue to confirm with UW"

"Loan Factory overlay not loaded — confirm with AE"

"Current source supports..."

---

# INITIAL AUTHORITATIVE SOURCE SET

Research and establish the source registry using the CURRENT official versions available today for:

1. Fannie Mae Selling Guide
2. Freddie Mac Single-Family Seller/Servicer Guide
3. FHA Single Family Housing Policy Handbook 4000.1
4. VA Pamphlet 26-7 / current VA Loan Guaranty guidance and Circulars
5. USDA HB-1-3555 / applicable Procedure Notices

Use official agency/GSE/government sources.

Do not use:

* mortgage blogs;
* random lender blogs;
* SEO summaries;
* Reddit;
* training-company summaries;

as the authoritative rule source.

Third-party content can potentially aid research, but production underwriting rules must trace back to an approved authoritative source.

---

# COPYRIGHT / DISTRIBUTION

Before committing full copies of third-party/GSE documents into the Flo repository or distributing them inside the application, check the applicable usage/licensing terms.

If redistribution is not appropriate:

* maintain source metadata;
* maintain official source references;
* use an approved private/local ingestion cache;
* store normalized rule representations where permitted;
* avoid publicly redistributing copyrighted guide PDFs.

Government and GSE materials should not automatically be assumed to have identical redistribution terms.

Document the chosen approach.

---

# DELIVERABLE

Add an:

UNDERWRITING_KNOWLEDGE_ARCHITECTURE.md

or equivalent canonical document to the Flo project.

Also update:

* architecture decisions;
* implementation plan;
* data model;
* testing plan;
* open questions;
* Claude/Codex progress documentation.

I want the project architecture established NOW even if full guideline ingestion and calculation implementation occurs over several later phases.

Do not derail the current bootstrap/rebrand work.

Incorporate this cleanly into the existing Flo architecture and then continue your current assigned work.
