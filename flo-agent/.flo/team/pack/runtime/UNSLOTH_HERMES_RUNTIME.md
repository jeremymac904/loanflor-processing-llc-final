# Unsloth / Hermes Local Runtime

This file records the current local-runtime findings supplied from the active build work.

## Current machine

- macOS 26.6.2
- Apple M1 Max
- 64 GB unified memory
- ~53 GB visible to Metal according to the verification report
- Python 3.12 is available via uv; Unsloth Studio uses its own Python 3.13 uv environment
- Unsloth installed at `~/.unsloth/studio`
- Unsloth CLI at `~/.local/bin/unsloth`
- Unsloth Desktop at `/Applications/Unsloth.app`
- model cache rooted under `~/Unsloth/models`
- adapters under `~/Unsloth/adapters`

## Verified runtime

The build report states:
- Metal llama.cpp inference works;
- MLX works;
- MLX LoRA training/export was verified;
- local API works on loopback `127.0.0.1:8888/v1`;
- Hermes was verified end-to-end through the local Unsloth server;
- existing primary Hermes config was left unchanged.

## Known Hermes compatibility constraints found during verification

1. Hermes v0.21 requires a model/context configuration of at least 64K for the tested path.
2. A provider-name/model-ID mismatch occurred when the provider name `unsloth` caused Hermes to strip the `unsloth/` model prefix.
3. A local wrapper at `~/Unsloth/bin/hermes-via-unsloth.sh` was created/tested to work around the naming issue.
4. The Desktop app and Unsloth Studio may contend for port 8888 depending on how they are launched; keep provider ports explicit.

Treat these as local compatibility findings, not permanent upstream assumptions. Codex should inspect the current downstream code and isolate any workaround.

## Recommended team use

Do not hard-code one model for every agent.

Use a model router:
- local fast model for classification, extraction, drafting, routine file work;
- stronger local model when context/quality is sufficient;
- approved cloud model for difficult reasoning/research where organizational policy permits;
- deterministic code for arithmetic and policy decisions.

## Candidate local model

The official Unsloth site currently lists Qwen3.8-27B at roughly 17-19 GB for its recommended 4-bit GGUF and up to 256K context, making it a candidate for the 64 GB Apple Silicon machine. Benchmark it with Flo's synthetic eval suite before assigning production roles.

Do not assume model size alone determines underwriting quality.
