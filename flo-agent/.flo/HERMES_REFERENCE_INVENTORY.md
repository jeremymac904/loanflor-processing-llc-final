# Hermes reference inventory (Flo downstream)

Classification of every class of remaining "Hermes" reference after the
bootstrap rebrand. Rule (`.flo/docs/06_REBRAND_CHECKLIST.md`): rebrand visible
product identity aggressively, keep internal upstream machinery conservatively.

Categories: **1 Rebrand** (done or must be done) · **2 Internal compatibility, keep** ·
**3 Upstream attribution/license, keep** · **4 Developer-only, keep or annotate** · **5 Needs decision**.

## What the bootstrap rebranded (category 1, done)

| Surface | Where | How |
|---|---|---|
| Product / executable / artifact names, protocol name+scheme, app ID (placeholder), macOS bundle strings and 10 permission descriptions, DMG title, NSIS shortcut/uninstall names, Windows trademark, Linux synopsis/category | `apps/desktop/package.json` | Literal edits; invariant test `apps/desktop/electron/flo-brand.test.ts` ties them to `apps/desktop/flo/brand.config.json` |
| Windows exe ProductName / FileDescription / CompanyName / Copyright | `apps/desktop/scripts/set-exe-identity.mjs` | Reads `flo/brand.config.json` |
| App name, About panel copyright, four `BrowserWindow` titles, native-notification fallback title, Windows AUMID | `apps/desktop/electron/main.ts` | `APP_NAME` now defaults to `FLO_BRAND.productName`; AUMID = `FLO_BRAND.appId` |
| Deep-link scheme registered with the OS (`flo://`, `flo-dev://` in dev) | `apps/desktop/electron/main.ts` (`HERMES_PROTOCOL`, `DEEPLINK_SCHEMES`) | Constant names kept for mergeability; values from brand config |
| Renderer deep-link acceptance | `apps/desktop/src/lib/hermes-open-target.ts` | Accepts `flo://` and, as an internal alias, `hermes://` |
| Window/document title, HUD title | `apps/desktop/index.html`, `apps/desktop/src/main.tsx` | Literal / brand constant |
| Empty-state wordmark ("FLO AGENT") | `apps/desktop/src/components/chat/intro.tsx` | `FLO_BRAND.displayName` |
| Every i18n string in all five locales, plus plugin locale bundles | `apps/desktop/src/i18n/flo-rebrand.ts`, `catalog.ts`, `runtime.ts` | Rebranded at the resolution boundary; the upstream catalog files are untouched. Test: `src/i18n/flo-rebrand.test.ts` asserts no bare "Hermes" remains in any catalog |
| E2E title expectations | `apps/desktop/e2e/boot.spec.ts`, `launch-packaged-app.spec.ts` | Use brand config (not run in this environment) |
| Upstream renderer tests asserting literal screen text | `src/components/desktop-install-overlay.test.tsx`, `src/app/updates-overlay.blockers.test.tsx`, `src/app/settings/gateway-settings.test.tsx`, `src/components/assistant-ui/thread/streaming.test.tsx`, `status-tail-only.test.tsx`, `src/i18n/runtime.test.ts` | Expected literals kept upstream-identical and wrapped in `rebrandText(...)` (31 assertion lines); `runtime.test.ts` has two rebranded literals |

## Category 2 — internal compatibility, keep

- Package/workspace names: `"name": "hermes"` (desktop), `@hermes/shared`, `@hermes/plugin-sdk`, `hermes-agent` (pyproject), `hermes_cli`, all Python module names.
- CLI and runtime commands: `hermes serve`, `hermes update`, `hermes desktop`, `hermes -p <profile>`; the `hermes` venv shim; `HERMES_HOME` layout (`~/.hermes`, `%LOCALAPPDATA%\hermes`).
- Environment variables: every `HERMES_*` (`HERMES_HOME`, `HERMES_DESKTOP_*`, `HERMES_UPDATE_*`, `HERMES_SERVE_HEADLESS`, …).
- IPC channel names `hermes:*`, gateway JSON-RPC method names, `X-Hermes-Session-Token`, `/api/hermes/*` endpoints, `ui_meta['hermes-bots']`.
- Internal privileged schemes `hermes-media`; renderer alias acceptance of `hermes://`.
- Type/module names (`src/types/hermes.ts`, `HermesPlugin`, `hermes-open-target.ts`, `src/plugins/hermes-bots/`).
- Plugin loader namespace `hermes_plugins.*`; skill frontmatter `metadata.hermes.*`; config keys.
- Upstream tests that use "Hermes" as arbitrary fixture data (e.g. `agent-message.test.tsx`, path-shaped fixtures `Hermes.app` in `app-icon.test.ts`, `spawn-helper-perms.test.ts`).

## Category 3 — upstream attribution / license, keep

- Root `LICENSE` (MIT, Nous Research) and `apps/desktop/README.md` license section.
- `plugins/security-guidance/LICENSE`, `NOTICE` (Apache-2.0 patterns).
- `flo/brand.config.json` `copyright` and `upstream` fields explicitly credit Hermes Agent / Nous Research; About panel shows that string.
- Upstream docs under `website/`, `README*.md`, `CONTRIBUTING*.md`, `SECURITY*.md`, `AGENTS.md`.

## Category 4 — developer-only, keep or annotate

- Upstream `README.md`, `apps/desktop/README.md`, `AGENTS.md`, `DESIGN.md`, `website/docs/**` (developer documentation; annotate rather than rewrite).
- `hermes_cli/banner.py`, `debug.py` (CLI banner/support links are developer surfaces; Ashley's profile uses the `flo` CLI skin for branding text).
- Dev-sandbox tooling honouring `HERMES_DESKTOP_APP_NAME`.

## Category 5 — needs decision (owner)

| Item | Current state | Decision needed |
|---|---|---|
| Reverse-DNS app ID | `com.example.flo` placeholder (`appIdIsPlaceholder: true`) | Real ID before any signed build; changing it changes userData/AUMID |
| Publisher / maintainer identity | `Flo Agent (owner TBD - placeholder)` in `package.json` author, linux maintainer, exe CompanyName | Legal entity name and contact |
| Icons | `apps/desktop/assets/icon.*`, `public/apple-touch-icon.png`, `public/nous-girl.jpg` (BrandMark) still the upstream art | Produce Flo avatar/icon set per `.flo/docs/04_FLO_PERSONA_AND_BEHAVIOR.md`; then swap files and `brand-mark.tsx` |
| Bots surface (`src/plugins/hermes-bots/*`) incl. its default display name `'Hermes'` in `labels.ts` and plugin-local catalog | Plugin catalog strings are rebranded via the runtime transform; the `labels.ts` literal and two tests are untouched | ADR-004 says Ashley sees one assistant: decide whether to hide the Bots page in the Flo profile or rename the default bot |
| `Hermes Cloud`, `Hermes Skills Hub` | Preserved verbatim by `PRESERVED_UPSTREAM_TERMS` | Confirm these Nous services are out of scope for Flo (recommended) |
| Upstream install-script URL in copy (`hermes-agent.nousresearch.com/install.sh`) | Text rebranded around it; URL unchanged | Replace when a Flo installer exists |
| `hermes-bots` and other plugin-local i18n literals not routed through the runtime translator | Covered where `translatePlugin` is used | Codex: verify no plugin renders catalog objects directly |
| Python-side `hermes update` CLI | Not gated (developer tool). Desktop app paths are gated by `flo/release-channel.ts` | Decide whether Ashley's install should also refuse `hermes update` against upstream (see progress doc) |

## Verification commands

```bash
cd apps/desktop && npx vitest run --project electron electron/flo-brand.test.ts electron/flo-release-channel.test.ts
cd apps/desktop && npx vitest run --project ui src/i18n
```
