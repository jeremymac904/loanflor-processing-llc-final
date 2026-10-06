# Flo current handoff

## Source of truth

- Repository: https://github.com/jeremymac904/loanflor-processing-llc-final
- Canonical branch: `flo/codex-polish`
- Desktop version line: `0.18.0` (release is not published by this change)
- The source checkout must be clean and at the intended canonical commit before packaging. The exact current SHA is the Git HEAD shown by `git rev-parse HEAD` and Settings → About in a package. Build provenance is embedded at `resources/install-stamp.json` and includes commit, branch, build time, dirty state, version, platform, and architecture.

## Build and test

From a fresh clone, use Node 22.22 and run `npm ci` in `flo-agent`. Build the Windows x64 NSIS installer with `npm run dist:win:nsis --workspace apps/desktop`; build macOS DMG/ZIP with `npm run dist:mac --workspace apps/desktop` on an Apple Silicon Mac. The Windows local deploy wrapper verifies the current source stamp and canonical branch before replacing app files. Never deploy a cached `release/win-unpacked` folder.

For local Mac testing, the app uses the current macOS account's own data at `~/Library/Application Support/Flo`; Ashley's Windows data is not copied or synchronized. Windows user data stays under `%APPDATA%\Flo`. Application updates replace the installed app bundle/files and do not target either user-data directory.

## Updates and releases

The packaged app uses electron-updater with the public GitHub Releases feed for this repository. No update server or embedded GitHub token is used. Create a semantic-version tag from a commit already contained in `flo/codex-polish`; `.github/workflows/release-desktop.yml` builds Windows x64 NSIS and macOS arm64 DMG/ZIP, creates SHA256 manifests, and publishes updater metadata with the GitHub Release. NSIS is the Windows auto-update format. Update behavior must be acceptance-tested on Windows before calling a release production-ready.

The About page exposes the build stamp and a manual update check. The updater downloads only after Ashley chooses Update Now, and installs/restarts only after the download completes. If GitHub is unreachable, the existing app remains running. Public releases are required for anonymous update discovery; a private repository would require a separately designed authenticated distribution path, not a shipped PAT.

## Mac distribution boundary

Local development builds can be made without Apple signing credentials. The release workflow requires GitHub Actions secrets `MACOS_CERT_P12_BASE64`, `MACOS_CERT_PASSWORD`, `APPLE_API_KEY_P8`, `APPLE_API_KEY_ID`, and `APPLE_API_ISSUER` before it will publish Mac artifacts. Public Mac distribution/update requires an Apple Developer ID Application certificate, hardened runtime, suitable entitlements, and notarization. Microphone permission text is present in the app bundle configuration; real microphone/STT/TTS acceptance must still be performed on Jeremy's Mac. No Apple credentials are committed.

Windows builds are currently unsigned unless a signing certificate is configured in CI. Broader distribution may show SmartScreen warnings until the publisher uses a trusted code-signing certificate and establishes reputation. No signing secret belongs in Git or the app.

## Secrets, data, and services

- Borrower documents, Customer Files, chats, contacts, reactions, preferences, and local signing settings stay in OS-specific user data, not GitHub.
- Provider, Gmail, and Twilio credentials stay in local secure storage/configuration; never commit them or add them to build artifacts.
- GitHub Actions receives only its short-lived repository `GITHUB_TOKEN` for release upload. The installed app needs no GitHub token for public releases.
- Ollama and local signing remain local services when configured. Cloud model, Gmail, Twilio, and other connectors are intentional external services used only according to their in-app configuration and policies.

## Jeremy's Mac maintenance loop

1. Clone or fetch this repository and check out `flo/codex-polish`.
2. Create a focused feature/fix branch; make the change and run its tests on Mac.
3. Push the branch and merge the reviewed change into `flo/codex-polish`.
4. Build/test the Mac app locally. Add Ashley-friendly notes at `release-notes/vX.Y.Z.md`, then tag the canonical commit with that semantic version and push the tag.
5. GitHub Actions builds Windows x64 and macOS arm64 artifacts, checksums, and updater metadata, then publishes the GitHub Release.
6. Ashley's packaged Flo can check that public release in Settings → About and choose when to install it.

CI artifacts are not proof of Windows UI acceptance. A Windows release still needs a real Windows install/update test; a Mac voice test likewise requires Jeremy's physical Mac and microphone permission.
