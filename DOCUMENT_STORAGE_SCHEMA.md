# Document storage schema (2026-09-09)

Two record sets describe the same file: the website's upload record (what the LO sent) and Flo's document record (what the Deal Room holds). Both are keyed by opaque ids; neither ever carries borrower NPI in a name or key.

## Identifiers and naming

| Thing | Format | Example |
|---|---|---|
| Submission id (idempotency key) | `sub_<24 hex>` | `sub_49bfd552998c7539573f002c` |
| LO-facing reference | `LF-<first 10 hex, upper>` | `LF-49BFD55299` |
| Website document id | `doc_<24 hex>` | `doc_0eea7ff162002d86abd12a3d` |
| Flo document id | `doc_<12 hex>` | `doc_caf4ad43e24c` |
| Loan workspace id | `loan_<12 hex>` | `loan_eb74a54e9cc9` |
| Display name | `<upload date>_<slug>_<nn>.<ext>` (slug = subtype if given, else category) | `2026-09-09_bank_statement_01.pdf` |
| Website storage key | `submissions/<submission id>/documents/<document id>.<ext>` (opaque: ids only) | `submissions/sub_49bf…/documents/doc_73c8bb9c8205c3292bfeb6ff.pdf` |
| Flo private copy | `<hermes root>/flo/documents/<workspace>/<folder>/[borrower1|borrower2|joint]/<display name>` (+ `.txt` sidecar) | `…/loan_eb74a54e9cc9/assets/borrower1/2026-09-09_bank_statement_01.pdf` |

Flo's private copy is organised by category for Ashley (the website object key stays opaque). Folders: `loan_application → application`, `credit_report → credit`, `aus_findings → aus`, `income`, `assets`, `purchase_contract → contract`, `title_property → title`, `insurance`, `identification`, `other`. Borrower sub-folders only for income and assets (`borrower → borrower1`, `co_borrower → borrower2`, `both → joint`).

The original filename is kept as metadata only (sanitised to `[\w.\- ()]`, 120 chars). The stored binary is byte-for-byte what the LO uploaded (sha256 verified on both sides); display names and classifications are metadata and never rename the object.

## Categories, subtypes, borrower reference

```
category:     loan_application | credit_report | aus_findings | income | assets | purchase_contract | title_property | insurance | identification | other
income sub:   paystub | w2 | 1099 | tax_return | profit_and_loss | k1 | other
assets sub:   bank_statement | retirement_statement | gift_documentation | other
borrower_ref: borrower | co_borrower | both | null
```

## Statuses

| Status | Meaning | Set by |
|---|---|---|
| `received` | stored, checksum verified, nothing wrong found | website on upload; Flo on ingest |
| `needs_review` | stored but unreadable text (no PDF text layer / image / office file) or transfer failed (`checks.fetch_failed`, retry with `refetch`) | Flo |
| `reviewed` | Malcolm looked at it and connected it to what it proves | Malcolm |
| `missing_pages` | "Page N of M" markers show a gap (`checks.pages.missing`) | Flo (automatic) or Malcolm |
| `unreadable` | cannot be read at all | Malcolm |
| `duplicate` | same sha256 as an earlier document (`duplicate_of`); kept, never deleted, shares the stored object | website / Flo (automatic) |
| `not_needed` | Ashley/Malcolm decided it is not needed for this file | Malcolm via Flo |
| `removed` (website only) | LO removed it before submitting; object kept until cleanup | website |
| `listed` (Flo only) | the LO listed a file that was never transferred (no `fetchUrl`) | Flo |

Only these values are accepted by `flo_documents action=update`; anything else (e.g. "approved") is refused.

## Website upload record (`server/data/documents-meta/<submission id>.json`, git-ignored)

```jsonc
{
  "documentId": "doc_0eea7ff162002d86abd12a3d",
  "submissionId": "sub_49bfd552998c7539573f002c",
  "category": "income", "subcategory": "w2", "borrowerRef": "borrower",
  "originalFilename": "w2_2025.pdf",
  "displayName": "2026-09-09_w2_01.pdf",
  "storageKey": "submissions/sub_49bf…/documents/doc_0eea7ff162002d86abd12a3d.pdf",
  "mimeType": "application/pdf", "sizeBytes": 737, "sha256": "…",
  "uploadedAt": "2026-09-09T22:38:20.101Z", "uploadedBy": "loan_officer",
  "status": "received",                       // received | duplicate | removed
  "duplicateOf": null,
  "classificationSource": "loan_officer",
  "notes": ""
}
```

`publicDocument()` (what the browser sees) omits `storageKey`, `sha256`, `submissionId`. The submission payload delivered to Flo carries `documentRefs[]` built from these records **plus** `fetchUrl` (`{PUBLIC_API_BASE_URL}/api/internal/documents/<sid>/<docId>`); the browser's own list is only a hint and is discarded.

## Flo document record (`<team root>/documents/<workspace id>.json`)

```jsonc
{
  "document_id": "doc_caf4ad43e24c",
  "website_document_id": "doc_0eea7ff162002d86abd12a3d",
  "submission_id": "sub_49bf…", "workspace_id": "loan_eb74a54e9cc9",
  "category": "income", "subcategory": "w2", "borrower_ref": "borrower",
  "original_filename": "w2_2025.pdf", "display_name": "2026-09-09_w2_01.pdf",
  "storage_key": "submissions/…",              // where the website keeps it
  "local_path": "C:\\…\\flo\\documents\\loan_eb74a54e9cc9\\income\\borrower1\\2026-09-09_w2_01.pdf",
  "text_path": "…\\2026-09-09_w2_01.pdf.txt", "text_chars": 146, "page_count": 1,
  "mime_type": "application/pdf", "size_bytes": 737, "sha256": "…",
  "uploaded_at": "…", "uploaded_by": "loan_officer", "received_at": "…",
  "status": "received",
  "classification_source": "loan_officer",     // loan_officer | filename | text | malcolm | ashley | flo
  "checks": { "pages": { "expected": 4, "seen": [1, 2, 4], "missing": [3] }, "suggested_classification": null, "fetch_failed": null },
  "notes": "",
  "history": [ { "at": "…", "by": "malcolm", "changes": { "status": "reviewed" } } ]
}
```

Editable through `flo_documents action=update`: `category`, `subcategory`, `borrower_ref`, `status`, `display_name`, `notes`. Everything else (paths, hashes, sizes, ids) is fixed at ingest.

## Workspace view (Deal Room, `workspace.json`)

```jsonc
"document_refs": [ { "ref": "doc://doc_caf4ad43e24c", "document_id": "…", "category": "…", "subcategory": "…", "borrower_ref": "…",
                     "display_name": "…", "status": "…", "note": "…", "pages": 1, "local_path": "…", "text_path": "…", "added_at": "…" } ],
"documents_summary": { "received": 8, "duplicates": 2, "missing": ["…"], "needs_clarification": ["2026-09-09_bank_statement_01.pdf: Missing pages — Pages 3 of 4 not in the file"], "updated_at": "…" }
```

`missing` only ever contains items backed by an ACTIVE source rule for the file's program (`documents.py:_RULE_BASIS`); everything else the submission suggests is a clarification (basis `SOURCE_GAP`, "submission workflow" or "LO listed") and is never presented as required. The desktop plugin reads exactly these two fields; Ashley's screens show display names and plain statuses, never keys or ids.

## Limits

25 MB per file · 60 files per submission · extensions `pdf jpg jpeg png` (owner decision: the practical mortgage formats; DOCX/TIFF/HEIC/ZIP/HTML/scripts/executables refused) · magic bytes must match · HTML/script content refused whatever the extension · 300 upload requests per IP per hour · uploads closed once the submission is sent.

## Retention / deletion

Before submit: `DELETE /api/loan-submissions/:id/documents/:docId` marks the record `removed`; the object stays until cleanup because a duplicate record may share it. After submit: nothing is deleted through the API. Recommended cleanup job (not built): delete objects for submissions in status `delivered` older than N days once Flo confirms its private copy (`documents.ingest` verifies the checksum, so the website copy is not needed after delivery), and purge `removed` records whose object no other record references. Flo's private copies live under the Hermes root (never in git) and follow the loan folder's retention.
