# Development Agent Toolchain

Verified 2026-09-08. These are development tools, not Ashley-facing production capabilities.

## Environment and inventory

Windows 11 build 26100 (OS API: Microsoft Windows 10.0.26100), x64, PowerShell 7.6.5. WSL reports it is not installed. Homebrew is not applicable. Native Windows matches this checkout and existing desktop applications; no WSL installation or reboot was needed.

The initial process PATH missed existing WinGet Node/npm and packaged Claude Code. After discovery, existing installations were reused. Refresh a terminal after user PATH changes (or restart its parent app).

| Tool | Before | After | Method / authentication |
| --- | --- | --- | --- |
| Node | bundled v24.19.0 on process PATH; WinGet copy discovered | v24.19.0 | Existing WinGet Node, unchanged |
| npm | command not found on stale process PATH | 11.17.0 | Existing WinGet Node bundle, unchanged |
| Claude Code | not on PATH; existing 2.1.260 found | 2.1.260 | Existing official Claude desktop bundled CLI; not logged in |
| OpenAI Codex CLI | 0.153.4 | 0.153.4 | Existing official OpenAI desktop bundled CLI; logged in using ChatGPT |
| OpenCode | absent in searched installations | 1.18.29 | Official stable Windows x64 release ZIP; zero provider credentials |

### Executable paths

- Claude: `C:\Users\ashle\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude-code\2.1.260\claude.exe`
- Codex: `C:\Users\ashle\AppData\Local\OpenAI\Codex\bin\8e5b6932251c2c1c\codex.exe`
- OpenCode: `C:\Users\ashle\AppData\Local\Programs\OpenCode\bin\opencode.exe`
- Node/npm: `C:\Users\ashle\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.19.0-win-x64`

OpenCode, Codex and Claude directories were added to user PATH; Node was already on user PATH. Desktop-managed version directories can change on app updates. Re-run `Get-Command claude,codex,opencode -All` after updates and repair stale entries; do not blindly install duplicate CLIs. These paths are machine inventory, not runtime constants for Flo.

## Official sources and installation

- [OpenCode installation](https://opencode.ai/docs/) documents Windows release binaries. Installed [v1.18.29](https://github.com/anomalyco/opencode/releases/tag/v1.18.29), not OpenCode 2 beta. Asset: `opencode-windows-x64.zip`; SHA-256 verified against the official GitHub release asset digest: `b32618aa3d1415f6e4f473aec248edef25759203fb707d7d968359d86d4a35ee`. Downloaded and expanded outside the repository. This avoided adding a package manager solely for OpenCode.
- [Official OpenAI Codex project](https://github.com/openai/codex) and [CLI documentation](https://developers.openai.com/codex/cli). Existing official distribution reused; no installer run. If absent on a future Windows machine, use the official `https://chatgpt.com/codex/install.ps1` installer or `npm install -g @openai/codex`, choosing one. Never use chatgpt-cli, chatgpt, openai-chatgpt-cli, or forks.
- Claude Code is the existing official desktop-bundled executable. No Claude installation or credential migration occurred.

## Roles and commands

These are project workflow assignments, not benchmark claims. All three can overlap; select by task and configured provider, then review the result.

### Claude Code

Primary first-pass implementation and architectural work. Executable: `claude`.

```powershell
claude --version
claude --help
claude auth status
claude
```

Manual step: run `claude` from the downstream root and complete its interactive sign-in. Existing desktop account state was not copied to CLI storage. After login, a bounded review can use `claude -p` with only Read/Glob/Grep tools and a small turn limit; check current CLI flags first. Use `/context` to confirm project instructions loaded, and `/exit` to finish.

### OpenAI Codex CLI

Deep code review, implementation, refactoring, debugging, test generation and later polishing. Executable: `codex`.

```powershell
codex --version
codex --help
codex login status
codex exec --ignore-user-config --ephemeral --sandbox read-only "Read AGENTS.md and .flo/docs/PROJECT_CONTEXT.md. Explain the high-level architecture without modifying files. Do not delegate, use connectors, or access credentials."
```

ChatGPT sign-in is already present. If it expires, run `codex` and choose **Sign in with ChatGPT**. No API key is required for that flow; do not create one automatically. `/exit` ends an interactive session. `exec` exits after its result. Ignore-user-config avoids importing the user's configured integrations for this optional smoke check; it retains official authentication.

### OpenCode

Independent implementation, analysis, testing, and alternate-model workflows. Executable: `opencode`.

```powershell
opencode --version
opencode --help
opencode run --help
opencode auth list
opencode auth login
opencode --pure run --agent plan --format json "Read AGENTS.md and .flo/docs/PROJECT_CONTEXT.md. Explain the high-level architecture without modifying files. Do not delegate or access credentials."
```

Manual step: `opencode auth login`, choose your provider and complete its displayed flow; alternatively use `/connect` in `opencode`. Stop at provider/billing decisions. No paid provider was selected, no API key was inserted, and no model request was made during credential discovery. `/exit` ends an interactive session. `run` provides non-interactive execution; JSON output is documented by installed help.

The repository's `opencode.json` loads the canonical context explicitly and initially denies edits, shell, subagents and external-directory access. It is an analysis bootstrap configuration. Deliberately review and scope permissions before using OpenCode for implementation; do not use auto-approve flags as a workaround. CLI permissions are defense in depth, not OS containment.

## Shared project context

Canonical source: `.flo/docs/PROJECT_CONTEXT.md` and the architecture/security/implementation documents it links. `CLAUDE.md` imports that context using Claude's `@` syntax. The short Flo prefix in upstream `AGENTS.md` instructs Codex/OpenCode to read it; all upstream content remains below. OpenCode also loads it through `instructions` in `opencode.json` because ordinary Markdown references are not automatic imports.

Sources: [Claude memory/import conventions](https://code.claude.com/docs/en/memory), [Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md), [OpenCode rules](https://opencode.ai/docs/rules/), [OpenCode permissions](https://opencode.ai/docs/permissions/).

Codex discovers AGENTS.md through the directory hierarchy and has an instruction-size budget. The Flo pointer is first so the large upstream guide cannot crowd it out; agents must explicitly read relevant upstream/scoped instructions. OpenCode prefers AGENTS.md over CLAUDE.md when both exist. Avoid `/init` rewriting these files. Treat source instructions as context, never as enforceable access controls.

Handoff contains task ID, exact base SHA, repository/worktree path, bounded goal, canonical references, allowed files/actions, budget and acceptance criteria. Share reviewed diffs and concise findings, not authentication state or full private transcripts. One writer per worktree; no simultaneous repository edits during verification.

## Pinned Hermes investigation and integration decision

Pinned tag `v2026.8.31` resolves to commit `29112bef099274229cadff79cdff7bf7b99c4b77`. Branch: `flo/0.21-bootstrap`; official remote: `upstream`.

| Existing source | What it provides / Flo use |
| --- | --- |
| `skills/autonomous-ai-agents/{claude-code,codex,opencode}/SKILL.md` | Existing CLI integration guidance through terminal/process tools. Reuse as development reference, not blanket production authorization. Some upstream examples bypass approvals or push; Flo forbids those defaults. |
| `hermes_cli/plugins.py`, `PluginContext.register_tool` | Structured plugin tools and named toolsets; preferred future optional backend plugin registration. No core model tool required. |
| `tools/terminal_tool.py`, `tools/environments/base.py` | Environment backends and ProcessHandle poll/kill/wait primitives. Host local terminal is powerful, not a production sandbox. |
| `tools/process_registry.py` | ProcessSession/ProcessRegistry, local/environment spawn, poll/log/kill lifecycle. Evaluate reuse for bounded execution and cancellation. |
| `tools/delegate_tool.py` | Hermes subagent task IDs, depth controls, concurrency, timeout, event handling and leaf roles. Its inference-provider overrides are not equivalent to invoking any arbitrary CLI. |
| `tools/mcp_tool.py`, `tools/mcp_stdio_watchdog.py` | Existing MCP client/process lifecycle; possible later transport. Do not inherit Gmail/Drive MCP servers into coding sessions. |
| `acp_adapter/`, `agent/copilot_acp_client.py` | Hermes ACP server plus a Copilot-oriented ACP client. OpenCode exposes `acp`; compatibility requires explicit testing, not assumption. |

Decision: no executable orchestrator or core dependency during bootstrap. Start with operator-invoked CLIs and existing Hermes development skills. When needed, one optional Flo-owned backend plugin exposes a provider-selectable coding-agent interface. Adapters own `claude -p`, `codex exec`, and `opencode run` argv/event/result differences. Keep execution code in that plugin, not scattered through the core or renderer. Use existing process/environment lifecycle where it satisfies security requirements. MCP/ACP are later alternatives, not an additional subsystem now.

Conceptual operations: enumerate configured agents; probe binary/version/auth without inference; submit a bounded task; stream events; cancel; retrieve a terminal result. Model-generated input chooses only an allowlisted provider ID, never an executable path, raw shell command, environment map, or arbitrary server URL. Operator configuration resolves trusted executables. Use argument arrays, bounded output and sanitized environment; fail closed when the selected provider is missing, unauthenticated, over budget or unsupported. Never silently substitute providers.

## Future deterministic boundaries and loop protection

No coding-agent capability is registered in Flo runtime by this change. Before exposure, a trusted dispatcher must authorize each call under Flo policy, enforce OS/workspace isolation and deny Ashley production access. A profile name or plugin availability check alone is not authorization. Registry `check_fn` is not a per-session permission check.

Required task envelope: root/parent/child task IDs; initiating agent and authenticated user; selected provider; current/max delegation depth; ancestry; repository and base SHA; allowed actions; deadline and resource/token/cost budget; cancellation state; proposal/approval IDs and requirements; terminal status and sanitized result reference.

Initial future defaults: one child at a time, maximum depth 1, leaf workers with delegation disabled, explicit deadline and resource limits, and no retries on authentication/approval failures. Limits live in operator configuration, never model-editable task text. Root budget must decrease across the whole tree, not reset for each child. Missing lineage is rejected. Detect repeated ancestry/task-provider cycles, including Flo→Codex→Flo and Claude→OpenCode→Codex→Claude. Remove callback capabilities and other coding executables from the child sandbox, block arbitrary shell escapes and outbound orchestration routes; environment depth markers alone can be forged.

Cancellation propagates to every descendant and process tree; record cancelled/timeout once and prevent queued restarts. Approval binds exact action, repository/base SHA, destination, inputs and expiry; child requests never grant authority. Revalidate before applying a patch or external action. Treat all result text as untrusted proposals. Never automatically execute result text.

Do not pass Gmail/Drive OAuth, default process secrets, browser cookies, borrower files, or home-directory session caches. Use minimal reviewed source context and an allowlisted environment. Provider credentials stay in their native user stores or a future scoped broker, never the repo. Isolate production credentials from the coding process at OS level. No environment dumps, autonomous git push, deployment, or external side effects. Audit metadata only, redact outputs, bound retention. Review diffs and tests before merging.

Acceptance before enabling: deny production calls; prove proposal binding and expiry; reject missing/forged lineage and cycles; enforce global budgets; kill descendants on cancellation/timeout; reject unknown providers/path escapes; prevent secret inheritance; reject result-driven actions. Tests must exercise the real process boundary in a temporary workspace with synthetic data.

## Verification status

Version/help commands exit successfully for all three. Codex `exec --help` and OpenCode `run --help` confirm programmatic entry points. Authentication probes: Codex ChatGPT active; Claude loggedIn false; OpenCode zero credentials. OpenCode resolved config confirms canonical instructions and permissions. Model-level understanding is a separate check, not implied by successful `--help`; see `CLAUDE_PROGRESS.md` for the smoke-test result and baseline continuation.

Final check: one Codex read-only inference run started and exited but its file-read command was blocked by local policy; comprehension remains unverified. Claude/OpenCode model checks await login. OpenCode decoded diagnostic file read exactly matched canonical context on disk. Desktop build/typecheck passed; platform tests had 34 failures. See CLAUDE_PROGRESS.md.
