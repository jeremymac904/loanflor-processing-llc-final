# Flo Team — open questions (2026-09-08)

Decisions only the owner can make, plus source gaps that block real content. Earlier questions in `.flo/docs/15_OPEN_QUESTIONS.md` still stand.

## Team and approvals

1. Keep the `ashley` profile as Ashley's personal Flo chat, or retire it now that `flo` is the team leader? (Both currently share credentials via the installer's mirror.)
2. Autonomy level: stay in Assisted (every external action confirms), or promote specific capabilities to Trusted (`trusted_capabilities` in `plugins/flo-team/team.yaml`)? Candidates: Zapier read/search is already allow; nothing external is proposed for Trusted.
3. Approval expiry (30 minutes today) and whether an "[a]lways" answer should be allowed for team bots at all (`approvals.mode: smart` vs `manual`).
4. Should the Approval Center get its own Approve/Reject buttons? Needs the upstream approval `request_id` exposed to plugins or a small core patch (`tools/approval.py` list by session) — a core edit was avoided in this pass.

## Runtime

5. Local model: `qwen3-flo` (Ollama, 64K) passes the health check; Unsloth Studio on the Mac (`127.0.0.1:8888/v1`) is not present on this Windows machine. Which local endpoint is production, and which cloud provider is approved for non-sensitive reasoning (today: whatever `ashley` uses, `opencode-free`)?
6. Are model requests permitted to contain borrower NPI under the organization's provider agreements? `cloud_reasoning.pii_allowed` is `false` until answered.
7. Workspace root: `~/FloWorkspace` by default (`FLO_WORKSPACE_ROOT`). Confirm the location and whether Drive should mirror it.
8. Should team bots be confined to the workspace for file tools (`FLO_TEAM_CONFINE_FILES=1`)? Default is off per the least-restriction directive.

## Zapier

9. Which Zapier actions are actually enabled on the connected account for orders (title/HOI/VOE vendors) and marketing (Mailchimp/Buffer/GBP/WordPress)? The role globs are best-effort until the action catalog is reviewed; unknown actions fall to CONFIRM (writes) or DENY (out of scope).
10. Vendor directory and SLAs for Chadwick; without them every order proposal carries `vendor: SOURCE_GAP`.

## Sources (SOURCE_GAP)

11. Rights and ingestion route for each official guide (Fannie, Freddie, FHA, VA, USDA) and who the source-review administrator is. Nothing can leave `pending_review` without them.
12. Loan Factory overlays and any investor/Non-QM guides.
13. Approved minimum-document matrix, document taxonomy and age rules for Malcolm.
14. Approved template library, greeting/sign-off, recipient channel preferences for Whisper.
15. Brand guide, disclosures, licensing/NMLS display rules, approved product claims, social/email/testimonial policies and content pillars for Franklin.

## Golden Loan Path (added 2026-09-08, second pass)

18. **Source activation approver.** The 12 Fannie sections are active on this machine with approver `owner` and basis "Golden Loan Path directive 2026-09-08". Confirm that identity is the one you want on the record (`--archive` then re-approve with a named administrator if not), and who the standing source-review administrator is.
19. **Rights.** The private cache relies on Fannie Mae's limited professional-use permission. Confirm LoanFlow's approved-lender/professional status covers it, and whether a written note from Fannie is wanted before any wider rollout.
20. **Cloud + borrower data.** Because the CPU-only local model is too slow for interactive turns, all six profiles currently run on `openai-codex` (`gpt-6-astra`). `cloud_reasoning.pii_allowed` is still `false` in the manifest, so sensitive routing fails closed in `flo_model_health`, but Hermes will send whatever a chat contains to the configured provider. Decide: (a) approve Codex for borrower data under the provider agreement, (b) put a GPU-backed local endpoint on this machine (`min_prompt_tps` ≥ 250), or (c) keep synthetic data only until then.
21. **Effective dates.** Rule records carry the section's "(mm/dd/yyyy)" marker; the announcement-level policy effective date is not resolved per rule. Want that resolved before production use?
22. **Internal document requirements.** The supplied LoanFlow workflow source defines milestones only; identity/1003, property and disclosure rows are `source_gap`. Supply the company's minimum-file list so Malcolm's matrix can cite it as `ashley`/company provenance.
23. **YTD review tolerance.** 5% is an internal review threshold (the guide requires "consistency" without a number). Keep, change, or remove?
24. **Repository path.** The checkout lives under a folder with an apostrophe; upstream's delivery runner rejected that cwd (patched to fall back). Consider relocating the repo to a plain path before packaging.

## Program expansion (added 2026-09-09)

25. **FHA effective date.** Every Handbook 4000.1 section captured comes from Update 18 and is effective 11/10/2026. The sections are active with a not-yet-in-force caution; the currently effective text is not cached. Do you want the prior Handbook version fetched and activated as a second revision for case numbers assigned before 11/10/2026, or is the caution enough until then?
26. **Approver identity.** The four new slices (Freddie, FHA, VA, USDA) were approved and activated with the explicit display name `owner` (user id `explicit:owner`, reason "Program expansion directive 2026-09-09"), and the Fannie records were migrated to `legacy:owner`. When authentication exposes user ids, re-approve under the real administrator id or confirm these stand.
27. **Provider.** Codex is usage-limited (429) and opencode-free's model was unavailable; the team now runs on Nous Portal (`openai/gpt-6-astra`). Confirm this provider (and its data terms) is acceptable, or restore Codex when its limit resets (`config.yaml.codex-2026-09-09.bak`). Borrower data still must not go to any cloud route (question 20 stands).
28. **VA inputs.** Federal/state income tax and social security deductions on Form 26-6393 are lender inputs from IRS/state tables (Topic 3); the calculator does not compute them. Supply the tax-table source you want cited, or keep them as processor inputs.
29. **USDA limits and deductions.** Area income limits and the 7 CFR 3555.152(c) deduction amounts are not in the cached Handbook text; they are entered on the lender's worksheet/GUS. Supply the source to cite (Agency income-limit table, Attachment 9-C) if you want them activated.
30. **Freddie Documentation Level.** The asset workbench assumes Standard Documentation when the Feedback Certificate's level is not supplied. Should Malcolm be required to read it from the LPA feedback before any asset conclusion?
31. **Draft idempotency.** In the USDA live run Whisper created the same borrower draft three times on the deepseek model (retries); `flo_draft action=create` has no duplicate-body guard. Add one, or accept manual discard in the Approval Center?
32. **Sage overreach on deduction amounts.** Sage stated a dependent deduction is "not a recognized 7 CFR 3555.152(c) deduction"; the cached 9.5 text lists dependents as an eligible category but no amounts are cached. Supplying Attachment 9-C / the CFR text as an activated source would remove the ambiguity.
33. **Nous Portal credits.** The Nous account ran out of credits for a gpt-6-astra request mid-run (HTTP 402); the team finished on `deepseek/deepseek-v4-flash-0731`. Decide which cloud model class is funded for the team, and whether Codex should be restored when its usage window resets (17:24 UTC on 2026-09-09).

## Assets

16. macOS `.icns` was packed by Pillow from the 1024 master; if a macOS build shows icon differences, regenerate with `iconutil -c icns .flo/assets/team/app_icon/flo.iconset`.
17. `public/hermes.png`, `public/hermes-sprite.png`, `public/nous-girl.jpg` remain unused upstream files; delete in a cleanup pass?

## Reliability hardening - 2026-09-09 (resolutions and new items)

- #31 resolved: `flo_draft action=create` now derives a `draft_intent_id` from audience, purpose, requested items and source task; repeats return the existing draft (`ACTION_IDEMPOTENCY.md`).
- #32 mitigated: Sage's prose is validated against the bound source object; an unsupported deduction amount is rejected before the handoff can close (`SOURCE_BOUND_RESPONSE_ARCHITECTURE.md`). The Attachment 9-C / CFR source question stands.
- #33 partially resolved: provider health is now persisted (`provider_state.py`) and preflight shows the readiness board; Codex recovered after its window reset and Flo's "Bot Chat" session still pins gpt-6-astra on openai-codex while the profile default is deepseek on nous. Decide the funded cloud class.
34. **Sensitive-data route.** Every cloud route is `pii_allowed: false` and the local model is TOO_SLOW, so any real borrower workflow fails closed. Approve a route (GPU-backed local endpoint or a contracted cloud provider) before Ashley uses the team on live files.
35. **Knowledge Center administrator.** Name the person who approves/activates/archives source revisions, promotes guidance and activates overlays; decide whether the desktop should carry an authenticated user id so the tab's actions execute instead of copying commands.
