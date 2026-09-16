# Open Questions

These questions do not block the first baseline/rebrand pass. Record decisions when available.

## Ownership / release
- Final reverse-DNS app ID?
- Private Git repository URL?
- Flo release/update hosting?
- macOS signing/notarization owner?
- Windows code-signing owner?

## Ashley environment
- Windows, macOS, or both?
- Google Workspace domain/account type?
- Which Drive locations must Flo search?
- Is full-Drive discovery required, or can access be file/folder-selected?
- Which LOS / lender portals are priorities later?
- Is Ashley's email Gmail only?
- Any company MDM/DLP/security requirements?

## Model/provider
- Which model provider should Flo use in production?
- Local/direct provider, API gateway, or hosted company service?
- Are model requests permitted to contain borrower NPI under the organization's agreements/policies?

## Data lifecycle
- How long should Flo retain chat/session history?
- Should closed-loan workspaces archive or purge after a defined period?
- What audit retention is required?
- What backup/encryption policy applies?

## Mortgage sources
The current source pack is intentionally sparse.

Need authoritative materials for:
- W2 income calculation;
- self-employed income calculation;
- rental income calculation;
- agency-specific rules;
- lender overlays;
- TPO workflow details;
- condition taxonomy;
- compliance-approved outbound templates.

Until supplied, Flo should refuse to invent these specifics.

## Development toolchain / baseline follow-up

- Operator: sign in to Claude Code (`claude`) and configure the chosen OpenCode provider (`opencode auth login`); then perform one bounded read-only context smoke test for each.
- Codex starts and has ChatGPT auth, but the nested read-only smoke test's PowerShell Get-Content command was rejected as "blocked by policy". Diagnose official CLI Windows sandbox/policy from an interactive developer terminal; do not bypass sandbox/approval protections. No repository comprehension pass is claimed.
- Upstream AGENTS.md exceeds Codex's default 32768-byte automatic instruction budget. Flo pointer is placed first; explicitly read applicable upstream instructions. Consider a reviewed developer-only project_doc_max_bytes setting or upstream guide restructuring later; no global config changes made here.
- Triage stock Windows Desktop baseline failures and the case-colliding contributor filenames before the Phase 1 branding gate. Python backend environment and stock app launch remain to be verified.

## Rebrand / release decisions needed — 2026-09-08 (Claude Code pass)

- **App ID**: `com.example.flo` is a placeholder (`apps/desktop/flo/brand.config.json`, `package.json build.appId`, Windows AUMID). Changing it later moves Electron userData; choose before the first install Ashley keeps.
- **Publisher identity**: `package.json` `author`, Linux `maintainer`, and the exe `CompanyName` say "Flo Agent (owner TBD - placeholder)". Supply the legal entity and contact.
- **Icons / avatar**: DONE 2026-09-08 from the owner's branding sheet (Flo badge icon, Flo face brand mark, LoanFlow logo, `flo-desktop` theme). `public/nous-girl.jpg` and `public/hermes*.png` remain in the tree unused; safe to delete in the Codex pass.
- **Publisher** is now LoanFlow Processing LLC; the reverse-DNS app ID (`com.example.flo`) still needs the company's domain.
- **Release channel**: updates are disabled. To enable, set `updates.mode: flo-release` with a Flo-owned git `source` and a `bootstrapSource` raw-content base; both are rejected if they point at upstream. Who hosts it, and is the runtime (`hermes-agent` checkout) also served from the Flo repo?
- **Should `hermes update` (Python CLI) also refuse upstream?** Currently only the desktop paths are gated. Ashley's profile has no shell, so the exposure is developer-side only.
- **Bots surface**: `src/plugins/hermes-bots` still shows a default bot named "Hermes" (`labels.ts`) and its own roster UI. ADR-004 wants one visible assistant; hide the page for the Ashley profile or rename?
- **Hermes "[a]lways" approvals**: the upstream approval prompt offers "always" which persists into `command_allowlist`. Flo scopes the rule key per capability+target, but decide whether "always" should be disabled entirely for Ashley (would need an upstream config or a Flo approval transport).
- **E2E**: Playwright e2e (title assertions updated to brand config) was not run in this environment.
- **Stock desktop launch**: not performed (no model provider configured; GUI launch is not verifiable non-interactively here). `npm run build` succeeded with Flo changes.

## Underwriting source / implementation gaps — 2026-09-08

- Approve a licensed/authorized ingestion route and permitted cache/normalized-rule use for each source, especially GSE materials. No blanket government/GSE reuse assumption. No full guides committed.
- Freddie current guide/bulletin version could not be verified from readable official content; VA handbook routes redirected to a KnowVA welcome shell. Obtain current official content through authorized access. Do not substitute old PDFs.
- HUD official index confirms August 12, 2026 publication; PDF retrieval failed. Verify section-level effective predicates and applicable Letters/INFO before activation.
- USDA portal issue date is not consolidated revision currency; reconcile HB-1-3555 chapters against applicable Procedure Notices. Fannie September 2 edition still needs rule-level effective-date review.
- Identify source-review administrator, approval expiry policy, freshness SLAs, rights evidence, private cache location/retention and rollback ownership.
- Actual Loan Factory/lender overlays and all specialty/investor guides remain absent. Ask AE/UW to resolve conflicts; never infer overlays from the supplied TPO shell.
- Confirm desired first program/income slice and program-specific loan date inputs when calculator implementation starts. Full source ingestion and positive calculation tests remain later phases; current fixtures are acceptance specs only.

## Flo Team — 2026-09-08

See `FLO_TEAM_OPEN_QUESTIONS.md` (retire `ashley`?, autonomy level, approval buttons on the Team page, production local/cloud providers and NPI policy, workspace root, Zapier action catalog, vendor directory, source rights/administrator, brand/compliance sources for Franklin).

## Reliability hardening - 2026-09-09

- Sensitive-data route: which provider is approved for real borrower files? Today every cloud route is `pii_allowed: false` and the local model is too slow, so sensitive workflows fail closed by design.
- Who is the Knowledge Center administrator (approve/activate/archive source revisions, promote guidance, activate overlays), and should the desktop expose an authenticated user id so the buttons can execute instead of copying commands?
- FHA early implementation of Update 18 before 11/10/2026: lender decision required per file; Flo labels it and never assumes it.
- Loan Factory overlays remain absent; supply them with source, section and AE confirmation before any overlay is activated.
