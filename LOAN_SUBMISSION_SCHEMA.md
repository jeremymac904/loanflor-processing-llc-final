# Loan Submission payload — schemaVersion 1.0

The event the website backend delivers to Flo. Produced by `toPayload()` in `shared/loanSubmission.js` from the validated form state; consumed by `plugins/flo-team/intake.py` in the Flo repo. Bump `schemaVersion` for any breaking change and keep both sides' validators in step.

Conventions: camelCase keys; enums are lowercase snake_case strings; money and percentages are numbers (`null` when not given); dates are `YYYY-MM-DD`; phones are `(904) 555-0102`; emails lowercase; empty strings mean "not provided".

```jsonc
{
  "schemaVersion": "1.0",
  "submissionId": "sub_0694e236a2c5d51a5fe30301",   // sub_ + 24 hex, minted by the form, idempotency key everywhere
  "submittedAt": "2026-09-09T21:24:12.113Z",
  "source": "lfprocessing.net",

  "loanOfficer": { "name": "Matt Combs", "email": "matt@…", "phone": "(904) 555-0101", "company": "Synthetic Mortgage Group", "nmls": "123456", "dateSubmitted": "2026-09-09" },

  "borrowers": [                                     // 1 or 2 entries
    { "role": "borrower",    "name": "Ariana Justinvil-Synthetic", "email": "…", "phone": "(904) 555-0102" },
    { "role": "co_borrower", "name": "Sam Synthetic",              "email": "…", "phone": "(904) 555-0105" }
  ],

  "loan": {
    "investor": "PRMG", "propertyAddress": "123 Synthetic Way, Jacksonville, FL 32256",
    "expectedClosingDate": "2026-09-23", "loanAmount": 314000, "interestRate": 6.25, "ltv": 95.15, "cltv": null,
    "occupancy": "primary | second_home | investment",
    "transactionType": "purchase | refinance_rate_term | refinance_cash_out",
    "program": "conventional | fha | va | usda | jumbo | non_qm | other",
    "conventionalAgency": "fannie_mae | freddie_mac | not_sure | null",   // only for conventional
    "programOther": "",                                                   // only for other
    "aus": "du | lpa | total | gus | va_aus | manual | other | null",      // validated against the program
    "refinanceType": "fha_streamline | va_irrrl | standard | other | null", // only for refinances
    "homeType": "single_family | condo | pud | two_to_four_unit | manufactured | other | null",
    "homeTypeOther": ""
  },

  "fees": {
    "channel": "brokered | correspondent | null",
    "compensation": "lender_paid | borrower_paid | null",                 // brokered only
    "originationFees": { "lpCompPercent": 2.75, "box1": null, "discountPoints": null, "credits": null },
    "thirdPartyFees": { "creditReportFee": 152, "processingFee": 995 },
    "lenderBuyingOutFee": "yes | no | null",
    "buyoutNotes": ""                                                     // only when yes
  },

  "appraisal": { "orderTiming": "prior_to_inspection | after_inspection | null", "notes": "" },

  "parties": {
    "nonOccupantCoBorrower": "yes | no | null",
    "nonBorrowingTitleParty": { "applies": false, "name": "", "email": "", "phone": "", "willBeOnTitle": "yes | no | null" }
  },

  "setup": { "pmi": "yes | no | not_applicable | null", "subordinationRequired": "yes | no | null", "loanLocked": "yes | no | null", "escrowWaiver": "yes | no | null" },
  "communicationPreferences": ["realtor_voice", "realtor_email_cc_lo", "borrower_voice", "borrower_email_cc_lo"],

  "hoa": { "present": "yes | no | unknown | null", "company": "", "phone": "", "contact": "", "email": "",
           "condoQuestionnaireStatus": "completed | requested | order_on_disclosure | not_applicable | null" },

  "income": [                                        // LO-stated; Flo/Malcolm/Sage compute the verified figure
    { "borrower": "borrower | co_borrower", "incomeType": "w2 | 1099 | self_employed | rental | retirement_pension | social_security | military | other",
      "employerOrSource": "Synthetic Health System", "loStatedMonthlyIncome": 7842,
      "calculationBasis": "two_year_average | latest_year | current_income | other_unknown | null",
      "documentsIncluded": ["paystubs", "w2s", "tax_returns", "1099s", "award_letter", "bank_statements", "lease", "voe"],
      "notes": "", "verified": false }
  ],

  "credit": {
    "borrower":   { "status": ["as_per_credit_pull | rescore_or_supplement | tradeline_omitted | other_issue"], "omittedDebtsNotes": "" },
    "coBorrower": { "status": [], "omittedDebtsNotes": "" }
  },

  "assets": [                                        // funds to close; accountReference is last-4 / nickname only
    { "sourceType": "gift_from_relative | borrower_bank_account | retirement_withdrawal | lender_credits | other",
      "nameOrInstitution": "Synthetic Credit Union", "accountReference": "checking ••1234", "amount": 18500, "notes": "" }
  ],

  "title":     { "selected": true,  "company": "Hawes Law Firm (synthetic)", "contact": "", "phone": "(678) 555-0103", "email": "…" },
  "insurance": { "selected": false, "company": "", "contact": "", "phone": "", "email": "" },

  "agents": {                                        // both null for refinances
    "listing": { "name": "", "license": "", "phone": "", "email": "", "brokerage": "", "brokerageLicense": "" },
    "buyer":   { "name": "", "license": "", "phone": "", "email": "", "brokerage": "", "brokerageLicense": "" }
  },

  "notes": "This is a rush file, closing in 2 weeks.",

  "documentRefs": [                                  // built by the SERVER from its upload records (the browser list is only a hint)
    { "documentId": "doc_<24 hex>",
      "category": "loan_application | credit_report | aus_findings | income | assets | purchase_contract | title_property | insurance | identification | other",
      "subcategory": "paystub | w2 | 1099 | tax_return | profit_and_loss | k1 | bank_statement | retirement_statement | gift_documentation | other | null",
      "borrowerRef": "borrower | co_borrower | both | null",
      "originalFilename": "scan0042.pdf", "displayName": "2026-09-09_paystub_01.pdf",
      "storageKey": "submissions/<sid>/documents/<documentId>.pdf",   // opaque
      "mimeType": "application/pdf", "sizeBytes": 752, "sha256": "<64 hex>",
      "uploadedAt": "2026-09-09T22:38:20.101Z", "uploadedBy": "loan_officer",
      "status": "received | duplicate", "classificationSource": "loan_officer",
      "fetchUrl": "{PUBLIC_API_BASE_URL}/api/internal/documents/<sid>/<documentId>"   // Flo pulls the bytes with the shared bearer token
    }
  ]
}
```

## Validation (same rules in the browser and on the server — `validateSubmission()`)

Required: loan officer name/email/phone/company; borrower name; co-borrower name when `hasCoBorrower = yes`; property address; loan amount; occupancy; transaction type; program (+ `programOther` for other, `homeTypeOther` for other); title-party name and will-be-on-title when the section applies; an explanation when a tradeline is omitted or "other issue" is selected.

Format: emails; 10-digit phones; non-negative numbers (rates ≤ 30 %, LTV/CLTV ≤ 200 %); ISO dates; enum membership; AUS must apply to the program; refinance type must apply to the program; text ≤ 200 chars (notes ≤ 4,000); ≤ 12 income streams, ≤ 12 fund sources, ≤ 60 documents (≤ 25 MB, accepted extensions only; a submission is refused while any file is still `uploading` or `failed`).

Refused anywhere in the payload: SSN-shaped values (`###-##-####`), contiguous digit runs of 8+ that are not phone-shaped (10–11), and 12+ digits joined by spaces/dashes. Account references may contain at most 4 consecutive digits. The Flo intake repeats the sensitive-data scan and the workspace store rejects NPI a third time.

Recommended (highlighted on the review screen, never blocking): borrower email or phone, investor, expected closing, AUS, home type, channel, lender buyout answer, appraisal timing, loan locked, communication preferences, HOA company (when HOA = yes), at least one income stream, borrower credit status, a funds source on purchases, title/insurance company (when selected), agents on purchases, documents.

## Mapping into the Flo Loan Workspace (`plugins/flo-team/intake.py`)

| Payload | Workspace |
|---|---|
| `borrowers[0].name` (last word) | `display_name` |
| `loan.program` | `program`; `agency` = fannie / freddie (from `conventionalAgency`) or fha / va / usda |
| `loan.aus` | `aus` (label, e.g. "TOTAL") |
| whole payload (normalized keys) | `submission` block (`loan_officer`, `borrowers`, `transaction_label`, `program_label`, `expected_closing_date`, `lo_stated_income`, `funds_to_close`, `credit`, `hoa`, `title`, `insurance`, `agents`, `notes`, `review_status: pending`) |
| `documentRefs[]` | pulled into the Deal Room: `document_refs[]` (`doc://<id>`, category, subtype, borrower, display name, status, note, pages, private path) + `documents_summary` (received, duplicates, missing, needs_clarification); a ref without `fetchUrl` stays `listed` — see `DOCUMENT_STORAGE_SCHEMA.md` |
| `notes`, loan officer contact | `communication_refs[]` (`submission://<id>#notes`, `submission://<id>`) |
| — | `milestone: Intake`, `status_summary`, `next_action: "Malcolm is reviewing the new submission."` |
| summary facts | one `flo_handoff` task to Malcolm, `return_format: file_prep_report`, urgency from the expected closing (≤ 14 days → today) |
