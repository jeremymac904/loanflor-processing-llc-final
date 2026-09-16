# Flo Team — security review (2026-09-08)

Scope: the six-profile team runtime added in this pass (`plugins/flo-team`, profile distributions, installer, desktop Team page). The earlier `flo-policy` review in `.flo/docs/07_SECURITY_AND_PERMISSIONS.md` and `CLAUDE_PROGRESS.md` §1.7 still applies.

## Threat model

Untrusted inputs: borrower emails and attachments, PDFs, Drive files, local documents, web pages, Zapier/MCP results, and messages from other bots. The pack's rule is enforced in code: models propose, deterministic policy authorizes, retrieved content is data.

## Controls and where they live

| Control | Enforced by | Verified by |
|---|---|---|
| Retrieved content never grants authority | no code path builds an approval from text; handoff constraints say so; injection strings stay as data | `TestHandoff::test_prompt_injection_in_facts_changes_nothing`, `TestApprovalCenter::test_only_humans_decide` |
| External side effects stop for Ashley | `flo-team` role overlay → `approve` directive → upstream human gate; `flo-policy` capability gate alongside | `TestRolePolicy`, `TestHooks`, real `PluginManager` test |
| Approval binds to the payload; edits invalidate | sha256 of material args; single decision; expiry 30 min; `edit` re-proposes | `test_binding_and_material_edit_invalidates` |
| No bot may claim sent/placed/published | handoff results downgraded without `execution_ref`; orders/drafts/marketing transitions require it; cards closed only from tool results | orders/drafts/marketing tests, `test_confirm_files_card_and_post_closes_it` |
| Franklin structurally excluded from borrower data | `loan_workspace: deny` → workspace tools blocked, `loans/**` denied, handoffs with workspace_id refused, Deal Room invite refused; Gmail/Drive/Calendar Zapier actions excluded | `test_franklin_*`, real-manager test |
| Role-scoped folders, originals protected, no permanent delete | `folders.py`: per-role subfolders, `intake/` read-only, delete denied for all; `FLO_TEAM_CONFINE_FILES=1` turns "outside workspace" into deny | `test_folder_boundaries`, `test_role_decisions` |
| Zapier availability never overrides policy | second-layer scope check on raw tool name; generic API requests excluded for every role; write-shaped actions CONFIRM/DENY by role and autonomy level | `test_zapier_scopes`, `test_zapier_availability_does_not_override_policy` |
| Recursion protection | manifest edges + `max_delegation_depth: 1`; `delegate_task` denied for specialists; `delegation.max_spawn_depth: 1` in configs | `test_max_delegation_depth`, `test_specialist_to_specialist_is_refused` |
| Secrets out of git and logs | Zapier URL injected by the installer; audit/activity rows carry tool names, hashes and ids only; card previews drop secret-shaped keys; tests scan every distribution file for token/URL shapes | `TestProfiles::test_distribution_files_and_no_secrets`, `test_no_secrets_in_card_preview` |
| Sensitive data never silently falls back to cloud | `models.route()` FAIL_CLOSED for PII tasks when no PII-approved class is healthy | `test_sensitive_never_falls_back_to_cloud` |
| Guideline authority | no active revision → SOURCE_GAP; bots cannot approve/activate revisions; Non-QM needs an investor source | knowledge tests |
| Fail closed | both hooks return `block` on internal error | `test_fail_closed` |

## Findings and residual risks

1. **Model choice is per-profile config, not per-call.** Hermes picks the profile's model at session start. The fail-closed route is applied at install time and by `flo_model_health`; a bot whose profile is on a cloud model will use it for everything. Mitigation today: local-first roles are configured local only when the health check passes, and the routing decision is visible. Proper per-call routing needs an upstream `pre_llm_call` hook implementation (available hook; not built in this pass).
2. **The Approval Center page cannot decide.** Decisions are made in the native chat prompt. The card's `session_id` is the hook's session; the upstream approval `request_id` is created after the hook returns and is not exposed to plugins. Until it is, the page deep-links to the bot's chat.
3. **`approvals.mode: smart` + "[a]lways".** Upstream's smart approver can auto-approve routine shell commands; the Flo Team `rule_key` is `flo-team:<role>:<capability>` so an "always" answer persists per role and capability, never per tool. Owner may prefer `manual` for specialists.
4. **Folder policy is path-based.** A tool that reaches files without a path argument (a shell command constructed oddly) is caught only by the delete-marker heuristic; shell remains available to team bots per the owner's least-restriction directive. `FLO_TEAM_CONFINE_FILES` is available for a stricter posture.
5. **Shared state is plain JSON on disk.** Anyone with local file access can edit cards; the installer sets no ACLs. Acceptable for a single-user desktop; not for a shared host.
6. **Bot Chat protocol roster includes `@hermes` (the default profile).** Upstream behaviour; the default profile is not a team member and `flo-team` is inert there.
7. **Zapier URL is mirrored into six profile configs** (0600 not enforceable on Windows). Rotation means re-running the installer.
8. **Team Chat "Group:" rooms are driven by the desktop**, not by policy; a group room can include Franklin if a user adds him manually. The Deal Room membership rules live in the workspace record and `flo_workspace invite`, not in upstream's group-chat UI.

9. **Found and mitigated: upstream HTTP logging wrote the Zapier MCP URL (token) into profile `logs/agent.log` and `logs/desktop.log`** at INFO level (`httpx2` request lines) during the live run. Mitigation in this pass: `plugins/flo-team` raises the `httpx`/`httpx2`/`httpcore`/`mcp.client.streamable_http` loggers to WARNING when it loads, and the token-bearing lines already on disk in this machine's Hermes logs were scrubbed to `token=[REDACTED]` (8 files). Residual: the default profile and any process that runs without the plugin still logs URLs; an upstream-level redaction (`hermes_cli` logging filter) is the proper fix and is on the top-ten list. The Flo audit log and team activity log never contained the URL.

## Not in scope / not done

- No production Google OAuth or portal automation.
- No real borrower data anywhere; all fixtures are synthetic.
- No penetration testing of upstream Hermes components.
