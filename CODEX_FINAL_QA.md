# Codex final QA

## Handoff

- MiniMax source branch: `flo/minimax-continuation`
- MiniMax base commit: `6cbee95df09b46df3034f2e21fe4128215ba33c8`
- Final source branch: `flo/codex-polish`
- Final handoff commit: `c5e80ac3a972c5d6d97349f0bfa1e8bc53bd1da0`
- Final release tag: `flo-ashley-rc2`

## Scope

The pass is additive and preserves the existing backend authority, mortgage workflows, Petdex architecture, normal chat routing, document drop, approvals, CTC, orders, e-sign, and onboarding contracts.

## Evidence to complete before handoff

- [x] Final desktop renderer/Electron build completed; the bundle contains `flo-pet-spritesheet-B3oeUVrU.png`.
- [x] Focused desktop UI tests: 11 files, 66 tests passed.
- [x] Live Mac visual inspection completed for the rebuilt Flo onboarding surface; the screenshot is present in the task’s visual inspection trace. The backend was offline, so Today/Pipeline/File View/Approvals could not be populated honestly in the live app.
- [x] Windows x64 portable cross-build completed as `flo-agent/apps/desktop/release/Flo-0.17.0-win-x64.exe`.
- [x] The final x64 ZIP is preserved as the handoff artifact; Wine was unavailable for executable identity/icon stamping.
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
- Final ZIP: `release/ashley-final/Flo-0.17.0-win-x64-portable.zip`, 169,484,779 bytes; SHA-256 `d3a08f251377fa9428b90e09045ea7f89877f48c6a489a3b7fa4e6f381c83b49`.
- The unpacked x64 ASAR contains the Flo onboarding/connector strings, WVOE, document-drop, Documenso, Petdex spritesheet, Pet overlay IPC, profiles/skills bundles, and voice/microphone/transcription hooks.
- Packaged development `*.test.js`, `node_modules`, `.venv`, and `.git` entries are absent from the final ZIP. The portable payload was not executed on Windows in this Mac environment, so native runtime installation/terminal behavior remains an Ashley-PC acceptance item.
- No model weights, secrets, source repository, node_modules, `.venv`, or test data are included in the final release directory.
- Wine was unavailable, so Windows executable icon/identity stamping was not performed; the x64 portable executable itself was produced and inspected.
