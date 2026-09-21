# Windows Release Handoff — Ashley PC

## Release

- Branch: `flo/codex-polish`
- Commit: `9a7ae0f5332be97c87dc859417cf6d0a05c0d1be`
- Artifact: `Flo-0.17.0-win-x64-portable.zip`
- Architecture: Windows x64
- Voice status: code and hooks packaged; live Windows voice acceptance is still required.

Claude’s job is only to copy/extract the release, launch Flo, approve normal Windows/UAC prompts, connect Ashley’s real accounts, allow microphone permissions, let Flo install local dependencies, and run the smoke test below. Claude should not write code.

## Ashley-PC smoke test

A. Launch Flo.

B. Verify Today, Pipeline, Approvals, and Flo Chat.

C. Verify Flo Pet is visible and clickable, opens the Ask Flo composer, and supports popup/floating mode.

D. Verify voice: allow microphone permission; confirm local STT; ask “Flo, what should I work on?”; confirm a spoken response; verify stop/mute works.

E. Create/import one synthetic loan.

F. Drag/drop synthetic documents.

G. Ask: “Prep this file.”

H. Verify Malcolm result.

I. Click Why? and verify Sage.

J. Verify missing-document request.

K. Verify conditions.

L. Verify WVOE, Title, and HOI actions.

M. Verify local signing.

N. Restart Flo.

O. Verify everything survives.

Use no real borrower data for this smoke test.

## What is packaged

The x64 app contains the Flo renderer/plugin, onboarding and connector UI, document drop, WVOE/Title/HOI actions, profiles/skills/underwriting UI bundles, local signing and local-AI setup hooks, voice recorder/transcription/playback hooks, Petdex-compatible Flo sprites, and the existing popup Ask Flo IPC path. Model weights and local voice dependencies are not bundled; the supported runtime setup may install them on Ashley’s PC.

## Honest boundary

The Mac build cannot perform live Windows microphone, local-STT, local-TTS, account, Docker, Ollama, signing, or restart acceptance. Those are the final Ashley-PC checks.
