# Final GitHub Handoff

Repository: https://github.com/jeremymac904/loanflor-processing-llc-final

Final branch: `flo/codex-polish`

Final release tag: `flo-ashley-rc2`

GitHub Release URL: https://github.com/jeremymac904/loanflor-processing-llc-final/releases/tag/flo-ashley-rc2

Windows artifact: `Flo-0.17.0-win-x64-portable.zip`

SHA256: `d3a08f251377fa9428b90e09045ea7f89877f48c6a489a3b7fa4e6f381c83b49`

The final branch HEAD is the authoritative handoff commit; its exact SHA is recorded in the final remote verification report after this documentation commit is pushed.

## In Git

- Flo/Hermes source, website intake, agents, profiles, avatars, skills, underwriting metadata and tests.
- Flo UI, Petdex registration/assets/state mappings, popup Ask Flo hooks, and local voice source/configuration.
- Gmail, Google Workspace, Zapier, Documenso/local signing, local AI setup, recovery scripts, packaging scripts, and release documentation.

## Intentionally not in Git

- Secrets, OAuth tokens, API keys, private signing keys, real borrower data, runtime databases, Docker volumes, model weights, caches, `node_modules`, `.venv`, and Mac artifacts.
- The 169 MB Windows ZIP is a GitHub Release asset, not normal Git history.

## Recreated on Ashley’s PC

Extract the x64 portable ZIP, launch `Flo.exe`, complete Flo onboarding, connect Ashley’s real accounts, allow microphone access, and let the supported local voice/signing dependencies install when prompted. Use the included smoke test; use synthetic loan data only.

## Claude’s job on Ashley’s PC

Copy/extract the release, launch Flo, approve normal Windows/UAC and microphone prompts, connect Google/Gmail and Zapier, set up Local Signing and Local AI, test Pet/voice, and run the A–O smoke test in `WINDOWS_RELEASE_HANDOFF.md`. Claude should not write code.

Live Windows installation, account, Docker/Ollama, microphone, local STT/TTS, native runtime, and restart acceptance remain to be performed on Ashley’s PC.
