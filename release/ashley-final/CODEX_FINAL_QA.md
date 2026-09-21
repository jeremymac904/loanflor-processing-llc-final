# Codex final QA

## Handoff

- Source branch verified: `flo/minimax-continuation`
- Handoff commit verified: `6cbee95df09b46df3034f2e21fe4128215ba33c8`
- Release tag verified: `flo-ashley-rc1`
- Codex branch: `flo/codex-polish`

## Scope

The pass is additive and preserves the existing backend authority, mortgage workflows, Petdex architecture, normal chat routing, document drop, approvals, CTC, orders, e-sign, and onboarding contracts.

## Evidence to complete before handoff

- [x] Final desktop renderer/Electron build completed; the bundle contains `flo-pet-spritesheet-B3oeUVrU.png`.
- [x] Focused desktop UI tests: 11 files, 66 tests passed.
- [x] Live Mac visual inspection completed for the rebuilt Flo onboarding surface; the screenshot is present in the task’s visual inspection trace. The backend was offline, so Today/Pipeline/File View/Approvals could not be populated honestly in the live app.
- [x] Windows portable cross-build completed as `flo-agent/apps/desktop/release/Flo-0.17.0-win-arm64.exe` (234,630,145 bytes; SHA-256 `1bb2947fa521027f857a0a862f918627381896b7a83c319bf234638cc7ff3b2d`).
- [x] Exact packaging limitation recorded: this Mac’s installed Electron distribution is arm64, and Wine is unavailable for executable identity/icon stamping. The existing x64 ZIP was preserved and not overwritten.
- [x] Windows installation and Ashley workflow acceptance remain separate from build evidence; neither was verified on Ashley’s PC.

## Known environment boundary

The initial sandboxed baseline was affected by socket-bind and Vite cache permission restrictions; the desktop typecheck also exposed pre-existing duplicate React type declarations. Final results must record command output, not infer success from a build artifact alone.

## Final command results

- `npm run build`: passed.
- `npm run test:ui -- src/components/pet src/plugins/flo`: passed, 66/66.
- `git diff --check`: passed before commits.
- `npm run typecheck`: blocked by pre-existing duplicate `@types/react` ref incompatibilities throughout core desktop files.
- `npm run lint`: blocked before file linting by installed ESLint 9 / minimatch `expand is not a function` incompatibility.
- Full Python, website, Electron-platform, and Windows end-user checks were not represented as passing; the baseline recorded socket/cache permission failures and those results remain documented rather than being relabeled.

## Final x64 packaging audit

- `flo/minimax-continuation` is an ancestor of `flo/codex-polish` (`git merge-base --is-ancestor` passed).
- Windows x64 portable executable: `flo-agent/apps/desktop/release/Flo-0.17.0-win-x64.exe`.
- Size: 103,496,744 bytes.
- SHA-256: `39d2bc856325a1187f4491c55c8bf0f89f72abf1bb8cb0ca85fce0bf9e0fc179`.
- The unpacked x64 ASAR contains the Flo onboarding/connector strings, WVOE, document-drop, Documenso, Petdex spritesheet, Pet overlay IPC, profiles/skills bundles, and voice/microphone/transcription hooks.
- No model weights, secrets, source repository, node_modules, `.venv`, or test data are included in the final release directory.
- Wine was unavailable, so Windows executable icon/identity stamping was not performed; the x64 portable executable itself was produced and inspected.
