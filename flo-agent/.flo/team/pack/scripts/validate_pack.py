from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
agents = ["flo", "malcolm", "chadwick", "whisper", "sage", "franklin"]
required = [
    "ROLE.md", "SOUL_SEED.md", "KNOWLEDGE.md", "TOOLS_AND_MCP.md",
    "ROUTINES.md", "AVATAR_BRIEF.md", "ACCEPTANCE_TESTS.md"
]

errors = []
for agent in agents:
    for name in required:
        p = root / "agents" / agent / name
        if not p.exists() or not p.read_text(encoding="utf-8").strip():
            errors.append(f"Missing/empty: {p.relative_to(root)}")

for p in [
    root / "team" / "team_manifest.yaml",
    root / "prompts" / "CODEX_BUILD_FLO_TEAM_PROMPT.md",
    root / "sources" / "official" / "underwriting_sources.yaml",
    root / "runtime" / "MODEL_ROUTING.yaml",
]:
    if not p.exists():
        errors.append(f"Missing: {p.relative_to(root)}")

if errors:
    print("\n".join(errors))
    sys.exit(1)

print("Flo Team Agents Pack validation passed.")
