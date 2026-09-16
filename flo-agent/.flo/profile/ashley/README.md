# Ashley / Flo profile distribution

Owner directive: Flo is the full, unrestricted Hermes agent with Flo's persona,
skills, skin, routines and an audit trail on top. Nothing is locked down.

| File | Role |
|---|---|
| `SOUL.md` | Flo persona (warm, concise, priority-led, neutral under friction, SOURCE_GAP-honest). |
| `config.yaml` | Stock Hermes defaults + Flo skin + Flo policy plugin. No toolset disabled. |
| `flo/policy.yaml` | Audit everything; one click before email send, mass send, permanent delete, external share. |
| `skins/flo.yaml` | Flo CLI/TUI skin (green and gold). |
| `memories/USER.md` | Ashley seed. User-owned: seeded once by the installer, never overwritten. |
| routines (created by the installer via Hermes cron) | Morning brief 7:30 weekdays, end-of-day recap 5:00 pm weekdays. |

Install for real:

```bash
python scripts/flo/install_ashley_profile.py --alias      # ~/.hermes/profiles/ashley + `ashley` command
hermes -p ashley setup                                    # pick model/provider once
hermes -p ashley                                          # chat as Flo
```

Google (Gmail/Calendar/Drive): the bundled `google-workspace` skill is already
available; ask Flo "set up Google" and follow its one-time OAuth steps.

Local models: Hermes/Flo does not download weights itself; it uses a local
runtime. Ollama is installed on Ashley's machine (`%LOCALAPPDATA%\Programs\Ollama`,
server on `http://localhost:11434`, registered as `providers.ollama` in the
profile config) with `qwen3:8b` pulled. Hermes requires a 64K context window
and Ollama reports Qwen3's default 40K, so a variant `qwen3-flo` was created
(`FROM qwen3:8b` + `PARAMETER num_ctx 65536`); use that name. Switch in the
app under Settings → Model (provider "Ollama"), or one-off from the CLI with
`hermes -p ashley --provider ollama -m qwen3-flo`. The machine has no discrete GPU, so
local models run on CPU: usable for 7–8B models, slow above that. The default
stays the ChatGPT/Codex subscription model for quality.

Zapier MCP (Gmail, Google Drive/Docs/Sheets/Tasks/Contacts/Forms via Zapier):
configured on the installed profile as `mcp_servers.zapier` (HTTP transport,
104 tools at install time). The Zapier connect URL carries an account token and
therefore lives only in the profile's local `config.yaml`, never in this
distribution or git. To re-add on a fresh machine:

```bash
hermes -p ashley mcp add zapier --url "<your Zapier MCP connect URL>"
```

The mortgage skills live in `skills/flo-mortgage/` and sync into every profile.
