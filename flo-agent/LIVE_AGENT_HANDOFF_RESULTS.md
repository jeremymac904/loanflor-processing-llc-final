# Live agent handoff results (2026-09-08/09)

Model-driven, real Hermes Bot Mode transport (`message_agent` → `hermes -p <profile> chat -c "Bot Chat"`), real plugin tools, synthetic file only. Provider for every profile: **openai-codex / gpt-6-astra** (selected by provider discovery; the CPU-only Ollama model measured ~36 s per health probe and far below the 250 tok/s prompt-throughput floor, so it is marked `slow` and not used for interactive turns). Times are wall-clock from the activity log (`%LOCALAPPDATA%\hermes\flo\team\activity\activity-2026-09-09.jsonl`) and the Bot Chat transcripts.

## Blockers found and fixed before the loop closed

1. **Cloud provider "Model is unavailable"** on `opencode-free` (the model the `ashley` profile had been switched to) → provider discovery now runs a real one-line completion per cloud provider and marks it `unhealthy`; Codex passed (14–17 s round trip).
2. **CPU-only local model** (first attempt >20 min per turn) → throughput probe added; local marked `slow`; not used.
3. **`message_agent` refused to deliver**: upstream's delivery runner used the repository root as its working directory, and `terminal_tool` rejects a cwd containing an apostrophe (`…\Ashley's Pipeline\…`). Patched `tools/bot_mode_dm.py::_delivery_workdir` to fall back to the user's home / temp dir (test: `tests/flo/test_bot_mode_delivery_workdir.py`).
4. **Doubled knowledge path** in the tool surface (`<team root>/knowledge/knowledge`) meant the first live Malcolm run saw the Fannie sections as inactive (income `SOURCE_GAP`); fixed and covered by a test that goes through the tool surface.
5. Malcolm's own QC caught that the DU "all pages" message was marked satisfied despite a missing page → `du.review` now returns `needs_review` for incomplete statements.

## Run 1 — Flo → Malcolm → Flo (task_12dde1a09356)

| Step | Time (UTC) | Evidence |
|---|---|---|
| Flo model turn: `flo_handoff create` → `message_agent` to @malcolm (`status: sent`, process id) | 03:23:53 | Flo Bot Chat |
| Malcolm's Bot Chat spawned by the delivery; `flo_handoff receive` | 03:24:57 | activity `handoff.received` |
| Malcolm reads the synthetic file, runs `flo_fileprep` (readiness 68 raw), re-scores with his own QC (`flo_readiness` 20 BLOCKED), writes `exports/file_prep_report.txt`, `flo_handoff complete` | 03:25:31–03:27:28 | 19 tool calls, activity `handoff.completed` |
| Malcolm → `message_agent` to @flo (`status: sent`) | 03:27:51 | Malcolm Bot Chat |
| Flo's Bot Chat spawned; Flo relays to Ashley ("Ash, Malcolm's report is back… BLOCKED… three moves matter") | 03:27:52–03:28:0x | Flo Bot Chat |

Elapsed Flo-ask → Flo-answer: ~4 min. Malcolm's language: "DU shows verbatim 'Approve/Eligible'", "not an underwriting decision". In this run his income line was `SOURCE_GAP` (defect 4) — corrected in run 3.

## Run 2 — Flo → Sage → Flo (task_999cd683c3f1)

Flo `message_agent` → Sage received 03:33:04 → completed 03:33:53 → Flo relayed. Sage produced the real card (B3-3.3-01 Base Income, section date 03/04/2026, revision `fannie-b3-3.3-01-23295e8b3b2d`, official URL) **but concluded SOURCE_GAP on purpose**, because `flo_knowledge action=sources` still carried a hard-coded "no source is active" note that contradicted the card's active revisions; Sage refused to resolve a source-governance conflict herself and asked for an administrator. Correct behaviour; the stale note (and a matching sentence in Sage's SOUL) were fixed and the profile re-installed.

## Run 3 — Malcolm direct rerun (after the path fix)

Malcolm's Bot Chat, 03:36–03:39: `flo_fileprep` → readiness IN_PROGRESS 35/100; "DU findings show Approve/Eligible."; qualifying monthly **5,500.00** via `fannie.base_income.monthly` (calc id recorded, active source B3-3.3-01, revision id); YTD ratio 103.82%; W-2 comparison 66,000 vs 58,900 (+12.1%, verify raise); assets NEEDS_REVIEW, eligible 87,340.18, July page 5 missing, 4,000 deposit sourcing question. He messaged Flo; Flo's Bot Chat answered Ashley with three priorities and "not cleared qualifying income".

## Run 4 — Flo → Sage → Flo, second attempt (task_de11c76f2221)

| Step | Time (UTC) | Evidence |
|---|---|---|
| Flo model turn: `flo_handoff create to=sage` → `message_agent` (`status: sent`) | 03:41:09 | Flo Bot Chat |
| Sage's Bot Chat spawned; receive → `flo_knowledge sources` (now lists the 12 active sections) → `flo_guideline_card program=fannie` → complete | 03:41:2x–03:42:42 | Sage Bot Chat (28 tool calls across her two runs), activity `handoff.completed` |
| Sage → `message_agent` to @flo | 03:43:06 | Sage Bot Chat |
| Flo relays to Ashley | 03:43:1x | Flo Bot Chat |

Sage's structured result: status `GUIDELINE_SUPPORTED_ASSESSMENT`; citations `B3-3.3-01 | 03/04/2026 | fannie-b3-3.3-01-23295e8b3b2d | https://selling-guide.fanniemae.com/sel/b3-3.3-01/base-income`, `B3-3.2-01 | …/standards-employment-and-income-documentation`, `B3-3.2-02 | …/standards-employment-related-income`; findings separated into agency documentation / paystub / future-raise rules, overlay ("Overlay not loaded, confirm with AE"), AUS finding, file condition, investor program; "No qualifying amount calculated… Not an underwriting decision"; source-status conflict explicitly recorded as resolved on live recheck. Elapsed Flo-ask → Flo-answer ≈ 2.5 min.

Provider/model for every turn: openai-codex / gpt-6-astra. Per-turn wall clock ≈ 30–90 s for Flo, 2–3.5 min for Malcolm (file read + fileprep + report), ≈ 1.5 min for Sage.

## What this proves / does not prove

Proved live with model-generated replies: Flo model turn → real `message_agent` delegation → Malcolm model turn → real specialist reply → Flo receives and synthesizes; Flo → Sage → Flo. Whisper's draft step was exercised deterministically (`golden_path.run`), not in a live model turn. Every external send remains a proposal (no send tool was invoked; nothing left the machine). No borrower data: the file is synthetic. No MCP URL or token appeared in the logs written during these runs (redaction test + manual scan).

---

# Program expansion live validations (2026-09-09)

Provider for every profile: **Nous Portal (`nous`) / `openai/gpt-6-astra`**. Codex (`openai-codex / gpt-6-astra`) returned HTTP 429 `usage_limit_reached` on the first attempt (credential pool marks it exhausted; reset ≈ 3.6 h later) and `opencode-free / deepseek-v4-flash-free` returned HTTP 400 "Model is unavailable" although the discovery smoke had passed; Nous Portal passed a one-line smoke (24 s round trip; `deepseek/deepseek-v4-flash-0731` 15 s) and was configured for all six profiles (Codex config kept as `config.yaml.codex-2026-09-09.bak`). Same transport as before: Flo's Bot Chat turn → `flo_handoff create` → `message_agent` → specialist Bot Chat → reply → Flo. Times are UTC from the team activity log; synthetic files only.

## Freddie Mac — Synthetic-Bellamy (Deal Room `loan_f5d43116111d`)

Loop: Flo → Malcolm → Flo → Sage → Flo → Malcolm (second pass) → Flo → Whisper → Flo synthesis. One Flo query carried all four steps; the chain ran unattended.

| Time | Step | Evidence |
|---|---|---|
| 13:55:02 | Flo creates the Deal Room, `flo_handoff create to=malcolm` → `task_53ef37cd9741`, `message_agent` status sent | Flo Bot Chat |
| 13:55:54 | Malcolm receives; reads the intake JSON; `flo_fileprep program=freddie documentation_level=standard` | activity `handoff.received` |
| 13:56:08 | readiness IN_PROGRESS 58/100; `flo_handoff complete` 13:57:03 | activity `readiness.updated`, `handoff.completed` |
| 13:57:49 | Flo → Sage `task_13d29ccdd13e` with Malcolm's guideline questions | activity |
| 14:01:30 | Sage completes: four `flo_guideline_card program=freddie` calls + `flo_calc` | Sage Bot Chat (56 tool calls in session) |
| 14:02:28 | Flo → Malcolm second pass `task_5c426f2c65b3` with Sage's conclusions | activity |
| 14:03:46 | Malcolm re-scores: BLOCKED 17/100 ("newly explicit review duties and source gaps — not new adverse evidence"); completes 14:04:38 | activity |
| 14:05:42 | Flo → Whisper `task_83a07e6e91cd`; Whisper receives 14:06:44, `flo_draft` → `draft_39c96f1e478b` (status `draft`, `external_action_status: not_sent_not_submitted_for_execution`), completes 14:07:27 | activity `draft.added`, Whisper Bot Chat |
| ≈14:08 | Flo synthesis to Ashley: priorities (updated paystub draft, deposit sourcing vs exclusion, PCV timing), "BLOCKED, 17/100 … It is not an underwriting decision" | Flo Bot Chat |

Elapsed Flo-ask → Flo-synthesis ≈ 13 min for five model hops (Malcolm ≈ 1–2 min per pass, Sage ≈ 3.5 min, Whisper ≈ 45 s, Flo ≈ 45–60 s per turn).

What the models produced (all from tools, quoted by the bots):

* Malcolm: "LPA findings show Accept. Risk Class: Accept; Documentation Level: Standard." Stable monthly income 5,000.00 via `freddie.base_income.monthly` (calc `calc_9b15ea0597c3`, "Guide 5303.1(c)(i)"); large-deposit threshold 2,500.00 (`freddie.assets.large_deposit_threshold`, `calc_f4646f47fa90`); "Unsourced 3200.00 deposit on 2026-08-01 above 2500.00 threshold; source or reduce verified funds by 3200.00 (5501.1)"; July and August statements 6/6 pages; surplus 5,418.13; reserves 2.18 months; "The stale paystub still needs replacement"; missing 10-day PCV. Language: "Tool figures, not final eligibility."
* Sage: cards citing 5302.2 (published/effective 05/06/2026), 5303.1 (06/03/2026), 5501.1 (08/05/2026), 5102.4 (02/04/2026), each with revision id, checksum and official Guide URL, `in_force: true`; a PCV-exception question outside the slice concluded **SOURCE_GAP** with "no exception established, and no overdue finding made"; she re-ran `flo_calc freddie.base_income.monthly` herself (`calc_9ab5610adca8`, 5,000.00) and stated "Reported reconciliation ratios are not Guide tolerances." Her attempt to write an export file was refused by her role policy (read-only on loan folders) and she reported that instead of bypassing it.
* Whisper: one draft only, greeting and sign-off left as `[SOURCE_GAP]` (no approved template library), "Nothing sent or submitted for execution."

Failures/retries: two failed launch attempts before the provider switch (429, then "Model is unavailable"); no retries inside the chain.

## FHA (TOTAL) — Synthetic-Okafor (Deal Room `loan_fcf85b2c914e`)

| Time | Step |
|---|---|
| 14:11:52 | Flo creates the Deal Room; `task_ed17450a45ae` → Malcolm |
| 14:12:49 | Malcolm `flo_fileprep program=fha underwriting_method=total`; readiness IN_PROGRESS 58/100; completes 14:14:01 |
| 14:15:10 | Flo → Sage `task_05a29401fc51` |
| 14:16:54 | Sage completes (three `flo_guideline_card program=fha underwriting_method=total` calls + `flo_knowledge sources`) |
| 14:17:44 | Flo → Malcolm second pass `task_1bae3c0e79d2`; readiness BLOCKED 19/100 at 14:19:04; completes 14:19:49 |
| 14:20:38 | Flo → Whisper `task_375d3719ae71`; draft `draft_d4db4e88bf2c` at 14:21:36 (draft only, null execution/proposal refs); completes 14:21:50 |
| ≈14:22 | Flo synthesis: "BLOCKED, 19/100 … It is not an underwriting decision" |

Elapsed ≈ 10.5 min for five hops.

* Malcolm: "TOTAL Mortgage Scorecard findings show Accept."; Effective Income 4,800.00 (`fha.total.income.current_salary_monthly`, `calc_bfbfade93bb1`); "Critical limitation: cited Handbook II.A.4.c is Update 18, effective 11/10/2026—not yet in force. The captured asset, TOTAL and document-age sections have the same caution."; unsourced 3,000 deposit above the 2,400 threshold (`calc_35878b6d484e`); one statement without the prior ending balance → one more month required; missing 2024 W-2; no reverification.
* Sage: three cards citing II.A.4.c, II.A.4.d, II.A.1.a.i(A)(1) (each `effective 11/10/2026`, `in_force: false`, official hud.gov Update 18 URL, revision id) and the TOTAL findings kept in the AUS layer; her conclusion for *current-effective* authority was **SOURCE_GAP**: "Currently effective text is not cached. Manual sections cannot substitute." — the exact separation the directive asked for (TOTAL never borrows Manual text, and a future-effective section is not silently treated as in force).
* Whisper: one draft for the W-2 and deposit documentation, greeting/sign-off `[SOURCE_GAP]`, nothing sent.

Failures/retries: none.

## VA — Synthetic-Reyes (Deal Room `loan_ec9516f95fbe`)

| Time | Step |
|---|---|
| 14:25:14 | Flo creates the Deal Room; `task_82e35e1a0f17` → Malcolm |
| 14:26:38 | Malcolm `flo_fileprep program=va` with the whole fixture (family size, state, taxes, square footage, debts); readiness IN_PROGRESS 46/100; completes 14:27:50 |
| 14:28:54 | Flo → Sage `task_fbc005897e34` |
| 14:31:26 | Sage completes: two `flo_guideline_card program=va` calls and four `flo_calc program=va` runs (`va.residual_income.required`, `.monthly`, `.check` → `calc_14f7b493e272` 105.05, `va.dti.ratio`) |
| 14:32:41 | Flo → Malcolm second pass `task_387ffe0988aa`; BLOCKED 26/100 at 14:34:01; completes 14:34:54 |
| 14:35:55 | Flo → Whisper `task_946e2d910c6f`; Whisper creates an **internal HOLD** draft `draft_914a5a387ae3` (no borrower copy) at 14:36:46; completes 14:37:05 |
| ≈14:38 | Flo synthesis: "BLOCKED, 26/100 … no additional borrower document request is currently supported" |

Elapsed ≈ 13 min.

* Malcolm: "DU findings show Approve/Eligible."; residual guideline 1,003.00 ("South/Texas, family 4, loan category $80,000 and above"), balance available for family support 1,053.70 (`calc_6cf8726c9d43`), DTI 61.29%; asset workbench asked for a VOD or a second statement per Topic 4 but Malcolm flagged that the actual DU message asks for one month and routed the AUS-path question to Sage instead of requesting from the borrower.
* Sage: cards citing Chapter 4 (KnowVA article updated 08/26/2026, `in_force: true`, revision `va-chapter_4-73bc8cbb8b41`); resolved the asset route from the text ("Topic 4 standard: VOD or last two bank statements. Topic 8 assets-to-close row allows most recent one-month statement in lieu of VOD for Accept/Approve"), re-ran the residual and DTI calculators, and concluded: "Residual meets the base table on supplied inputs but not the 20%-above-guideline exception; DTI warrants close scrutiny. File remains not submission-ready." Chapter 4's "does not make a loan decision" language was carried through.
* Whisper: because Sage's AUS-path resolution removed the second-statement request, Whisper produced an internal HOLD note rather than a borrower e-mail; nothing sent.

Failures/retries: none.

## USDA Guaranteed — Synthetic-Lindqvist (Deal Room `loan_d52e3da70bb0`)

| Time | Step |
|---|---|
| 14:40:17 | Flo creates the Deal Room; `task_188d47dbb02a` → Malcolm (model `openai/gpt-6-astra`) |
| 14:41:41 | Malcolm `flo_fileprep program=usda` with the whole fixture (household block); readiness IN_PROGRESS 30/100 stored |
| 14:41:47 | **Provider failure**: Nous Portal HTTP 402 "Insufficient available credits for this inference request" on Malcolm's next model call; his turn ended without completing the task |
| 14:53 | Recovery: all six profiles switched to `nous / deepseek/deepseek-v4-flash-0731` (11.7 s smoke); Malcolm's Bot Chat given a direct continuation instruction for the same task |
| 14:54:28 | Malcolm completes `task_188d47dbb02a` from the stored result (deepseek) |
| 14:55:25 | Flo → Sage `task_abdc207d310d`; Sage completes 14:57:27 (cards for 9.3/9.5/9.7-9.8/11.2-11.3 + `flo_calc` reruns) |
| 14:58:15 | Flo → Malcolm second pass `task_17ea7d7c43d3`; BLOCKED 12/100 at 14:59:02; completes 14:59:32 |
| 15:00:11 | Flo → Whisper `task_33263da9db1b`; three drafts created (`draft_2ddb1b4c3f24`, `draft_9cc8ae1cb957`, `draft_4a7b2e8ae3df` — identical bodies); completes 15:01:25 |
| ≈15:02 | Flo synthesis: "BLOCKED … the workspace now holds three borrower drafts with identical bodies; the current one is draft_4a7b2e8ae3df, and Whisper recommends discarding the two superseded duplicates" |

Elapsed ≈ 22 min including the 12-minute provider outage and recovery.

* Malcolm: "GUS findings show Accept / Eligible."; three separate figures with calc ids — annual household income 65,280.00 (`calc_e1e934cfaa12`: applicant 46,800 + spouse 18,000 + student first 480), adjusted annual income 64,320.00 (`calc_6213d814899c`, "below the stated 110,650.00 area limit, but that limit and the deduction entries are lender-supplied; authoritative values to be confirmed"), repayment income 3,900.00 (`calc_d22ec1c54c5a`); ratios PITI 32.05% / TD 42.82% (`calc_6868c44e87e9`) "above the 29/41 thresholds — debt ratio waiver with compensating factors"; $1,500 non-recurring deposit above the $1,000 Attachment 9-A threshold; stale paystub; no VVOE.
* Sage: cards citing 9.3, 9.5, 9.7-9.8, 11.2-11.3 (revision ids, PN edition, official rd.usda.gov URLs); re-ran the calculators; kept the three incomes distinct ("Repayment income $3,900/month = note parties only; spouse and student excluded"). She also challenged the adjusted-income worksheet: "the reported $64,320 subtracts $960, which is not a valid 7 CFR 3555.152(c) deduction … Without documented deductions, adjusted = $65,280." **Finding:** the cached 9.5 text lists *dependents* as an eligible 152(c) deduction category but does not state the amount (Attachment 9-C is not cached); Sage's conclusion that no documented deduction applies is defensible, but her statement that a dependent deduction "is not recognized" overstates the cached text. Recorded as a model-overreach observation (open question #29 covers the missing amounts).
* Malcolm second pass: adopted Sage's correction (adjusted income 65,280 until deductions are documented), ratios unchanged, BLOCKED 12/100.
* Whisper: created one borrower draft three times (retry behaviour on the deepseek model) — identical bodies, all `draft`, nothing sent; Flo flagged the duplicates for discard. **Finding:** `flo_draft create` has no idempotency key; a duplicate-body guard is a cheap follow-up.

Failures/retries: one provider outage (402) mid-chain with a documented model switch; Whisper's triple draft.

## Summary across the four programs

| Program | Deal Room | Hops | Elapsed | Model(s) | Sections cited by Sage | Calculators invoked live | Result |
|---|---|---|---|---|---|---|---|
| Freddie | `loan_f5d43116111d` | 5 | ≈13 min | nous / gpt-6-astra | 5302.2, 5303.1, 5501.1, 5102.4 (+1 SOURCE_GAP card) | `freddie.base_income.monthly`, `freddie.assets.large_deposit_threshold` | BLOCKED 17/100, draft only |
| FHA TOTAL | `loan_fcf85b2c914e` | 5 | ≈10.5 min | nous / gpt-6-astra | II.A.4.c, II.A.4.d, II.A.1.a.i(A)(1) (all `in_force: false`) | `fha.total.income.current_salary_monthly`, `fha.total.assets.large_deposit_threshold` | BLOCKED 19/100; SOURCE_GAP for current-effective authority; draft only |
| VA | `loan_ec9516f95fbe` | 5 | ≈13 min | nous / gpt-6-astra | Chapter 4 (Topics 2, 4, 8, 9, 10) | `va.residual_income.required/.monthly/.check`, `va.dti.ratio` | BLOCKED 26/100; internal HOLD draft |
| USDA | `loan_d52e3da70bb0` | 5 | ≈22 min (12 min outage) | nous / gpt-6-astra → deepseek-v4-flash-0731 | 9.3, 9.5, 9.7-9.8, 11.2-11.3 | `usda.annual_income.household`, `usda.adjusted_annual_income`, `usda.repayment_income.monthly`, `usda.ratios.piti_td` | BLOCKED 12/100; three duplicate drafts |

Every loop: Flo → Malcolm → Sage → Malcolm → Flo with model-generated replies, then a live Whisper draft; no send tool invoked; no "approved" language; provider, model, handoff ids and calc ids as listed.
