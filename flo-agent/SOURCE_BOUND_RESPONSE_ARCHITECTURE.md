# Source-bound response architecture (2026-09-09)

Why: in the USDA live run Sage's structured Guideline Card stayed inside the activated source, but her prose stated that a dependent deduction "is not a recognized 7 CFR 3555.152(c) deduction" — a factual rule assertion the cached text does not make. This class of failure is now caught before a guideline answer can close.

## Pipeline

```
source retrieval (flo_guideline_card, flo_calc, flo_du/AUS envelope, overlays, file conditions, flo_guidance)
   → deterministic normalized rule object (cards with CURRENT/FUTURE resolution, calc traces)
   → validated Guideline Card (cards.py)
   → allowed factual claims           flo_sage_response action=build  →  SourceBoundResponse
   → model presentation layer         Sage writes/polishes the wording
   → post-generation validator        flo_sage_response action=validate | rewrite
   → flo_handoff action=complete      refuses a guideline_card task without a validated response id
```

## The intermediate object (`plugins/flo-team/sage_response.py`)

```json
{
  "response_id": "resp_…", "digest": "…",
  "supported_claims":   [{"kind": "rule|missing_documentation|overlay|file_condition|guidance", "text": "...", "ref": "rule_id", "section": "...", "version": "...", "resolution": "CURRENT"}],
  "calculation_results": [{"calc_id": "...", "formula_id": "...", "status": "SUCCESS", "result": "...", "unit": "...", "inputs": {...}, "section": "...", "version": "..."}],
  "source_refs":        [{"section": "...", "version": "...", "effective": "...", "revision_id": "...", "official_url": "...", "resolution_label": "CURRENT | FUTURE — NOT YET EFFECTIVE | SUPERSEDED"}],
  "aus":                ["GUS findings show Accept / Eligible.", "dti: 42.8", "..."],
  "warnings":           ["Overlay not loaded — confirm with AE.", "FUTURE — NOT YET EFFECTIVE: ..."],
  "source_gaps":        ["...: SOURCE_GAP (...)"],
  "allowed_facts":      {"numbers": ["29", "41", "480", "64320", ...], "claim_count": n},
  "underwriting_decision": false
}
```

Only applicable (CURRENT / early-implementation) and ACTIVE citations become supported claims. FUTURE citations are carried as warnings, and their numbers are quotable only inside that labelled caution. Calculation inputs, step values and results, AUS envelope values, overlay text, file-specific conditions and recorded guidance items are the rest of the allowed vocabulary.

## Validator (`validate`)

Material underwriting assertions are checked; conversational glue is not.

| Assertion type | Detection | Rule |
|---|---|---|
| percentages | `29%`, `29 percent` | number must be in `allowed_facts.numbers` |
| dollar amounts | `$480`, `960 dollars` | same |
| periods and counts | `two-year history`, `30 consecutive Days`, `2 months of statements`, `3 points`, `28 pay stubs` | same (unit normalized: months/years/days/weeks/statements/pages/points/paystubs) |
| ratio pairs | `31/43` | both numbers |
| rule-like sentences | contains must / required / may not / cannot / not permitted / not recognized / not eligible / minimum / maximum / at least / no more than … | must share ≥ 2 content words with a supported claim, warning, calculation or AUS line |

Violations are returned with the sentence and the reason; `rewrite` removes the offending sentences and appends a note saying how many were removed and why. Every validation is recorded on the stored response (`<team root>/responses/<id>.json`) with the text digest, so the audit trail shows what Sage sent against what the sources supported.

## Enforcement

* Sage's SOUL makes build → validate mandatory and states that underwriting facts are not hers to add.
* `flo_handoff action=complete` for a `guideline_card` task by Sage requires `validated_response_id` whose last validation is `ok`; otherwise it refuses with instructions. The response digest is written into the task result.
* The renderer (`render`) gives a deterministic, already-valid text Sage can send verbatim when in doubt.

## Regression tests (`tests/flo/test_source_bound_response.py`)

Percentages, dollar amounts, deduction amounts (the USDA $960 case), required history (two-year), statement periods (3 months), reserve requirements ($5,000 / three months), eligibility thresholds (43 percent, 31/43), rule-like assertions without support ("Gift funds are not permitted"), glue text ignored, rewrite keeps supported sentences, FUTURE rule numbers quotable only as labelled, and the handoff-close enforcement through the real tool surface.

## Limits (honest)

The validator is lexical: it cannot judge whether a supported number is used in the right sentence, only that every material number and rule sentence traces to something on record. A supported sentence copied into the wrong context still passes; that is the presentation layer's residual risk and is why the deterministic `render` output exists.
