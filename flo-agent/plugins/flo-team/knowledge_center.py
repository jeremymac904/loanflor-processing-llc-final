"""Knowledge Center (Sage Library) — the administrator's view of the source lifecycle.

Builds ``<team root>/knowledge/center.json`` for the desktop page and returns
the same rows for ``flo_knowledge action=center``. One row per recorded
section revision:

    program, source, section, version, current_version (the version in force
    today), published, effective, status (lifecycle / resolution), checksum,
    rules_extracted, regression (ok/failed/receipt), human_approval (structured
    identity), supersedes, pending_update (a later version or a diff snapshot),
    impact (calculators / bindings / tests), actions (the exact commands an
    administrator runs — activation is never exposed in ordinary chat).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import impact, sourcediff, sources
from .store import now_iso

ACTIONS = ("view_source_metadata", "view_extracted_rules", "compare_versions", "run_regression", "approve", "reject", "activate", "archive")


def _cmd(program: str, action: str, section: str) -> str:
    base = f"python scripts/flo/activate_sources.py --program {program}"
    only = f' --only "{section}"'
    return {
        "run_regression": f"{base} --review{only}",
        "approve": f'{base} --approve --reason "<why>"{only}',
        "reject": f'{base} --archive "{section}" --approver-name <admin>',
        "activate": f"{base} --activate{only}",
        "archive": f'{base} --archive "{section}" --approver-name <admin>',
        "compare_versions": f"python scripts/flo/knowledge_center.py --diff {program}",
        "view_source_metadata": f"python scripts/flo/knowledge_center.py --show {program} \"{section}\"",
        "view_extracted_rules": f"python scripts/flo/knowledge_center.py --rules {program} \"{section}\"",
    }[action]


def rows(state=None, root: Optional[Path] = None, *, programs: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for program in programs or list(sources.PROGRAMS):
        spec = sources.program_spec(program)
        sections = sources.load_sections(program)
        rules = sources.load_rules(program)
        by_section: Dict[str, List[Dict[str, Any]]] = {}
        for r in rules:
            by_section.setdefault(r["section"], []).append(r)
        for key, meta in sections.items():
            st = sources.section_status(program, key, state, root)
            number = meta.get("section_number") or sources.section_number(key)
            versions = sources.section_versions(program, number) if meta.get("version") else []
            resolved = sources.resolve_section(program, number) if versions else None
            regression = sources.regression(program, key, root) if by_section.get(key) else {"ok": None, "checked": 0, "failed": [], "receipt": None}
            approval = None
            if state is not None:
                doc = state.docs.get(meta["revision_id"]) if state._safe(meta["revision_id"]) else None
                approval = (doc or {}).get("approval")
            later = [v for v in versions if v["key"] != key and (sources._parse_date(v.get("effective_date")) or sources.date.min) > (sources._parse_date(meta.get("effective_date")) or sources.date.min)]
            earlier = [v for v in versions if v["key"] != key and (sources._parse_date(v.get("effective_date")) or sources.date.min) < (sources._parse_date(meta.get("effective_date")) or sources.date.min)]
            imp = impact.affected(program, changed_sections=[key], state=state, root=root)
            out.append({
                "program": program, "program_display": spec["display"], "source": spec["source_title"], "section": key, "section_number": number, "title": meta.get("title"),
                "version": meta.get("version"), "current_version": (resolved or {}).get("key"), "resolution": st.resolution,
                "published": meta.get("page_date"), "effective": meta.get("effective_date") or meta.get("page_date"), "mandatory_date": meta.get("mandatory_date"),
                "status": st.lifecycle, "usable": st.usable, "checksum": (meta.get("checksum_text") or "")[:12], "revision_id": meta["revision_id"], "official_url": meta.get("official_url"),
                "rules_extracted": len(by_section.get(key, [])), "regression": {"ok": regression.get("ok"), "checked": regression.get("checked"), "failed": regression.get("failed"), "receipt": regression.get("receipt")},
                "human_approval": ({k: approval.get(k) for k in ("approved_by_user_id", "approved_by_display_name", "approved_at", "approval_reason", "environment", "identity_source")} if approval else None),
                "supersedes": [v["key"] for v in earlier], "pending_update": ([{"key": v["key"], "effective": v.get("effective_date"), "status": "FUTURE — NOT YET EFFECTIVE"} for v in later]
                                                                             + ([{"key": "snapshot", "status": "previous snapshot on disk"}] if sourcediff.snapshot_path(program).exists() and not versions else [])),
                "impact": {"calculators": imp["affected_calculators"], "workflows": imp["affected_workflows"], "tests": imp["affected_tests"], "summary": imp["summary"]},
                "actions": {a: _cmd(program, a, key) for a in ACTIONS},
                "capture_method": meta.get("capture_method"), "retrieved_at": meta.get("retrieved_at"),
            })
    return out


def build(root_team: Path, state=None, root: Optional[Path] = None, *, programs: Optional[List[str]] = None, guidance_pending: Optional[List[Dict[str, Any]]] = None,
          overlays: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    data = {"generated_at": now_iso(), "rows": rows(state, root, programs=programs), "guidance_pending": guidance_pending or [], "overlays": overlays or [],
            "note": "Administrator / knowledge-maintenance view. Approve/activate run through scripts/flo/activate_sources.py with a structured approver identity; nothing here is exposed in ordinary Ashley chat."}
    path = Path(root_team) / "knowledge" / "center.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return data
