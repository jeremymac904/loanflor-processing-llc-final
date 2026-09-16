# AUS normalization (2026-09-09)

`plugins/flo-team/aus.py` turns any findings document (DU, LPA, TOTAL Mortgage Scorecard, VA-approved AUS, GUS) into one envelope without changing the system's wording. `du.py` remains the Fannie entry point and delegates to it.

## Envelope

| Field | Meaning |
|---|---|
| `aus_system` | `DU` \| `LPA` \| `TOTAL` \| `VA_AUS` \| `GUS` (from the document's `aus_system`, or its `type`) |
| `aus_result` | the result exactly as printed (`Approve/Eligible`, `Accept`, `Accept / Eligible`, `Refer`, …); never mapped |
| `aus_version` | system/scorecard version string when the report carries one |
| `findings_ref`, `findings_date`, `casefile_id`, `submission_number` | file-specific identifiers |
| `program`, `underwriting_method` | the file's program (and FHA total/manual) the envelope was built for |
| `messages[]` | `{id, text, category}` verification messages, verbatim |
| `source_document` | `{type, ref}` |
| `statement` | `"<System> findings show <result>."` — the only sentence the bots may repeat |
| `mismatch` | set when the system does not belong to the program (`EXPECTED_SYSTEMS`) |
| `dti`, `ltv`, `funds_required_to_close`, `reserves_required_to_be_verified` | figures the report states, when present |

Expected systems: fannie → DU; freddie → LPA; fha → TOTAL (through DU or LPA); va → DU/LPA (VA-approved AUS); usda → GUS. A DU report on a Freddie file, or GUS findings on a Fannie file, produce `status: mismatch`, no requirements list and a File Prep item in `needs_review` — never a normalized result.

## What is deliberately not done

* No universal "approved"/"denied" enum. `Approve/Eligible` (DU), `Accept` (LPA Risk Class, TOTAL), `Accept / Eligible` (GUS) stay different strings because the guides treat them differently (LPA Caution → manual underwriting per 5101.2; TOTAL Refer → manual per II.A.4.a; GUS Refer → lender manual underwriting per 5.3; VA AUS classifications only reduce documentation per Chapter 4 Topic 8).
* No inference of a result from messages.
* No cross-program tolerance: the DTI resubmission check runs `fannie.du.dti_resubmission_check` (B3-2-10) for Fannie and `freddie.lpa.dti_resubmission_check` (5101.3(b), > 3 points or > 45%) for Freddie; FHA/VA/USDA report `SOURCE_GAP` for a tolerance rule because none is in the activated slices.

## Review output (`aus.review`)

Envelope + message-vs-inventory (`satisfied` / `missing` / `unknown` / `needs_review` for incomplete statements) + tolerance check + guide-vs-findings conflicts routed to Sage (e.g. findings that do not mention the employment verification the program's activated section requires: B3-3.3-01, 5302.2(d), II.A.4.c reverification, Chapter 4 telephone contact, 9.3 VVOE).

## Language check

Every program's live and deterministic runs assert the statement starts with the system's name and ends with the result as printed, and that the word "approved" never appears in the statement or the synthesis status line.
