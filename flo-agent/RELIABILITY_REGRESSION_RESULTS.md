# Reliability regression results (2026-09-09)

Suite: `tests/flo` + `tests/plugins/test_flo_policy_plugin.py` + `tests/skills/test_flo_mortgage_skills.py`
(`TZ=UTC PYTHONUTF8=1 PYTHONHASHSEED=0`, `-p no:cacheprovider`): **309 passed** on this Windows host.
Desktop: `npm run typecheck`, `npm run lint`, `npx vitest run src/plugins/flo-team` — all green (8 plugin tests).

## The 14 reliability scenarios

| # | Scenario | Test(s) | Result |
|---|---|---|---|
| 1 | FHA file with case number assigned before 11/10/2026 selects the CURRENT (Update 17) version | `test_fha_effective_dates.py::test_date_selects_exactly_one_version[2026-08-25…]`, `::test_before_mandatory_date_is_not_update_18_unless_early_implementation`, `::test_card_shows_current_and_future_labels`; `test_program_expansion.py::test_golden_loan_path_per_program[fha]` (fixture 2026-08-25) | pass |
| 2 | FHA file with case number assigned on/after 11/10/2026 selects Update 18 | `::test_date_selects_exactly_one_version[2026-11-10…]`, `[2027-01-15…]` | pass |
| 1b | Early implementation before the mandatory date is labelled, never silent | `::test_early_implementation_is_labelled`; `::test_active_future_version_is_not_usable_before_its_date` | pass |
| 3 | Unsupported USDA deduction dollar amount in prose | `test_source_bound_response.py::test_unsupported_deduction_amount_fails` (reproduces the $960 sentence seen live) | caught |
| 4 | Sage states a percentage / period / ratio / rule not in an activated source | `::test_material_assertions_outside_the_source_fail[…]`, `::test_rule_like_assertion_without_support_fails_but_glue_is_ignored`, `::test_sage_cannot_close_a_guideline_card_without_a_validated_response`, `::test_calendar_dates_and_revision_ids_are_not_ratios` (false positive seen live, fixed) | caught / no false positive |
| 5 | Whisper duplicate draft retry (identical handoff, wording retry, task resubmission, duplicate delivery) | `test_idempotency.py::test_repeated_identical_handoff_returns_the_same_draft`, `::test_retry_with_different_wording_is_still_one_draft`, `::test_resubmitted_task_and_duplicate_delivery_do_not_multiply`, `::test_materially_different_request_is_a_new_draft`, `::test_sent_or_rejected_draft_allows_a_fresh_one` | one active draft |
| 6 | Duplicate title-order retry; executed side effect retried after a provider timeout; marketing double-publish | `::test_duplicate_title_order_retry_returns_existing`, `::test_executed_side_effect_is_blocked_on_retry`, `::test_marketing_content_is_deduplicated_until_published` | blocked |
| 7 | 429 between Malcolm and Sage | `test_provider_failover.py::test_429_between_malcolm_and_sage_resumes_sage_on_another_provider` | Sage resumed on another provider; Malcolm's result and Deal Room refs kept; transition recorded |
| 8 | 402 between Sage and Whisper | `::test_402_between_sage_and_whisper_uses_check_and_failover` | resumed |
| 9 | Model unavailable on the selected route | `::test_model_unavailable_and_too_slow_routes_are_skipped`, `::test_classify_error[…]` | route skipped with cooldown |
| 10 | Local model too slow | same + `::test_board_and_estimates` | TOO_SLOW, replaced before start |
| 11 | Sensitive workflow with only unapproved cloud fallback | `::test_sensitive_data_fails_closed_without_an_approved_route`, `::test_unusable_provider_is_replaced_before_starting_and_sensitive_blocks`, `::test_sensitive_workflow_with_only_cloud_fallback_fails_closed`; `test_flo_team.py::test_sensitive_never_falls_back_to_cloud` | fails closed: "AI provider unavailable — your work is saved." |
| 12 | Source revision changed after activation | `test_reliability_regression.py::test_changed_cache_locks_calculator_and_card`, `::test_snapshot_diff_detects_changed_text`, `test_golden_loan.py::test_cache_tampering_demotes_to_stale` | STALE → calculators and cards lock, diff lists the change |
| 13 | Overlay conflicts with the agency baseline | `::test_overlay_layers_on_baseline_and_conflict_is_flagged_not_resolved` | conflict flagged, both cited, nothing resolved |
| 14 | File-specific UW condition promoted globally | `::test_guidance_stays_loan_specific_until_an_admin_promotes` | stays loan-specific; promotion yields a pending overlay proposal, not a rule |
| — | Source diff / impact / audit identity | `::test_fha_version_diff_lists_changes_and_impact`, `::test_impact_index_links_rules_to_calculators_workflows_and_tests`, `::test_approval_records_use_the_structured_identity` | pass |

## Live validation (Nous Portal + Codex, 2026-09-09 17:46–17:51 UTC)

Flo → Sage on the synthetic FHA file (Deal Room `loan_fcf85b2c914e`, TOTAL, case number assigned 2026-08-25):

* Flo ran `flo_workflow preflight` (board: Team AI Ready, Cloud Reasoning Healthy, Fallback Available, Local Fast/Reasoning Offline) and created `task_d9093ac30b05`; `message_agent` status `sent`. Flo's "Bot Chat" session re-used its saved model (gpt-6-astra on openai-codex); elapsed 150 s.
* Sage (deepseek-v4-flash on nous) ran `flo_guideline_card program=fha underwriting_method=total case_number_assignment_date=2026-08-25`, then `flo_sage_response build` (digest `5218cd213824b932`, 4 supported claims), then `validate` on her first draft: **failed** (the validator read the calendar dates 11/26/2025 and 04/10/2025 as qualifying-ratio pairs). She used `rewrite` (`resp_e8f2975d7e1d`), validated **ok**, and `flo_handoff complete` accepted the task only with that validated id.
* Her answer: CURRENT = Handbook 4000.1 II.A.4.c Update 17 (revision `fha-ii.a.4.c_update-17-104476516c85`); Update 18 II.A.4.c = "FUTURE — NOT YET EFFECTIVE (effective/mandatory 11/10/2026)". Flo relayed it verbatim into Ashley's Bot Chat.
* Follow-up fix from the run: `_RATIO_PAIR` in `sage_response.py` now ignores dates (`test_calendar_dates_and_revision_ids_are_not_ratios`). The gate held before the fix (a false reject, never a false accept).

## Real-install state after the run

* Preflight with discovery: nous_portal HEALTHY (~24 s smoke), openai_codex HEALTHY (~14 s; had a 429 earlier in the day, cooldown expired), opencode_free HEALTHY (smoke only), ollama_local TOO_SLOW, lmstudio/unsloth OFFLINE; Sensitive-data route: "Fails closed (no approved route)". `stalled` = [].
* Knowledge Center built from the install: 57 section revisions across five programs; all ACTIVE revisions carry schema-2 approval records.
* Whisper's SOUL had picked up a UTF-8 BOM during the profile sync; stripped (repo + installed copy) and the profile-invariant test passes again.
