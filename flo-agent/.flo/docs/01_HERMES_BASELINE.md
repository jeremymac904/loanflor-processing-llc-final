# Hermes Baseline - Researched 2026-09-08

## Pinned release

Start from:

- Repo: `https://github.com/NousResearch/hermes-agent.git`
- Release: Hermes Agent v0.21.0
- Tag: `v2026.8.31`
- Release date: 2026-08-31

Do not initially build from a random `main` commit.

## Architecture facts to verify in the checked-out tag

At the researched baseline:

- Native Desktop is an Electron + React application.
- Desktop launches a headless `hermes serve` process.
- Renderer/backend communication uses the Hermes gateway over JSON-RPC/WebSocket.
- Shared transport code is under `apps/shared`.
- The Desktop code is under `apps/desktop`.
- Hermes profiles provide separate config, memory, skills, credentials, sessions, cron state, and related agent state.
- Bot Mode uses profiles as the underlying primitive.
- Hermes supports backend plugins and a Desktop plugin SDK.
- Desktop plugin delivery includes bundled plugins and profile/user disk plugins.
- Desktop has packaging targets for macOS, Windows, and Linux.

Claude must inspect the exact tagged source before relying on any path or command in this document.

## Known user-visible rebrand surfaces in the tagged Desktop package

At the pinned tag, `apps/desktop/package.json` contains Hermes-specific build metadata including:

- app ID
- product name
- executable name
- custom protocol name/scheme
- artifact name
- macOS bundle display/executable/name strings
- platform permission descriptions

These are expected Flo rebrand targets.

## Important upstream behavior

Hermes' security model describes the default local terminal backend as having host-user access. Upstream documentation recommends stronger isolation when untrusted input surfaces are involved.

Flo will ingest untrusted email and documents. Therefore, do not assume Hermes' default personal-agent trust posture is sufficient for Flo's production profile.

## Licensing

Hermes Agent is MIT licensed. Keep the upstream LICENSE and required copyright/license notice in the downstream distribution.

## Reference repos

Useful reference only:

- `https://github.com/NousResearch/hermes-example-plugins.git`

Do not make the example repo a runtime dependency.

## Do not clone indiscriminately

Do not clone every Nous repository with "Hermes" in its name. Only add a repo when a concrete build or reference need is identified.
