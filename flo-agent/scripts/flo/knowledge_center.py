#!/usr/bin/env python3
"""Knowledge Center CLI: build the review console data, show metadata/rules, compare versions, impact.

    python scripts/flo/knowledge_center.py --build                 # writes <team root>/knowledge/center.json (the desktop page reads it)
    python scripts/flo/knowledge_center.py --show fha "II.A.4.c@update-18"
    python scripts/flo/knowledge_center.py --rules freddie 5303.1
    python scripts/flo/knowledge_center.py --diff fha [--old update-17 --new update-18]
    python scripts/flo/knowledge_center.py --impact freddie freddie.base_income.calc_table
    python scripts/flo/knowledge_center.py --guidance <guidance_id> --promote|--reject --reason "<why>" [--approver-name NAME --approver-id ID]
    python scripts/flo/knowledge_center.py --overlay <overlay_id> --activate|--archive [--approver-name NAME]

Approval/activation of sections stays in scripts/flo/activate_sources.py (human boundary).
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
sys.path.insert(0, str(REPO))


def _load():
    if "flo_team" not in sys.modules:
        spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["flo_team"] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    names = ("sources", "sourcediff", "impact", "knowledge", "knowledge_center", "manifest", "identity", "guidance", "overlays")
    for name in names:
        importlib.import_module(f"flo_team.{name}")
    return {name: sys.modules[f"flo_team.{name}"] for name in names}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--build", action="store_true")
    p.add_argument("--show", nargs=2, metavar=("PROGRAM", "SECTION"))
    p.add_argument("--rules", nargs=2, metavar=("PROGRAM", "SECTION"))
    p.add_argument("--diff", metavar="PROGRAM")
    p.add_argument("--old")
    p.add_argument("--new")
    p.add_argument("--impact", nargs=2, metavar=("PROGRAM", "RULE_ID"))
    p.add_argument("--guidance")
    p.add_argument("--promote", action="store_true")
    p.add_argument("--reject", action="store_true")
    p.add_argument("--overlay")
    p.add_argument("--activate", action="store_true")
    p.add_argument("--archive", action="store_true")
    p.add_argument("--reason", default="")
    p.add_argument("--approver-name")
    p.add_argument("--approver-id")
    p.add_argument("--home")
    args = p.parse_args(argv)
    if args.home:
        import os

        os.environ["HERMES_HOME"] = args.home
    m = _load()
    root = m["manifest"].hermes_root()
    team_root = root / "flo" / "team" if root else None
    state = m["knowledge"].KnowledgeState(team_root) if team_root else None
    if args.build:
        pending = m["guidance"].GuidanceStore(team_root).pending() if team_root else []
        overlays = m["overlays"].OverlayStore(team_root).all() if team_root else []
        data = m["knowledge_center"].build(team_root, state, root, guidance_pending=pending, overlays=overlays)
        print(f"knowledge center: {len(data['rows'])} section revisions, {len(pending)} pending guidance item(s), {len(overlays)} overlay record(s) -> {team_root / 'knowledge' / 'center.json'}")
        return 0
    if args.show:
        program, section = args.show
        meta = m["sources"].load_sections(program).get(section)
        st = m["sources"].section_status(program, section, state, root)
        print(json.dumps({"metadata": meta, "status": st.to_dict()}, indent=2, default=str))
        return 0
    if args.rules:
        program, section = args.rules
        rows = [r for r in m["sources"].load_rules(program) if r["section"] == section or m["sources"].section_number(r["section"]) == section]
        print(json.dumps(rows, indent=2))
        return 0
    if args.diff:
        program = args.diff
        versions = sorted({v.get("version") for v in m["sources"].load_sections(program).values() if v.get("version")})
        if args.old and args.new or len(versions) >= 2:
            out = m["sourcediff"].compare_versions(program, args.old or versions[-2], args.new or versions[-1], root=root, state=state)
        else:
            out = m["sourcediff"].compare_with_snapshot(program, root=root, state=state) or {"summary": "no previous snapshot or second version to compare"}
        print(out["summary"])
        print(json.dumps({k: v for k, v in out.items() if k != "changed_sections"}, indent=2, default=str)[:6000])
        for c in out.get("changed_sections", []):
            td = c.get("text_diff", {})
            print(f"- {c['section']}: {c['old_key']} -> {c['new_key']} similarity {td.get('similarity')} (+{td.get('added_count')} / -{td.get('removed_count')})")
        return 0
    if args.impact:
        program, rule_id = args.impact
        out = m["impact"].affected(program, changed_rule_ids=[rule_id], state=state, root=root)
        print(out["summary"])
        print(json.dumps(out, indent=2))
        return 0
    if args.guidance:
        ident = m["identity"].current_identity(explicit_id=args.approver_id, explicit_name=args.approver_name)
        rec = m["identity"].approval_record(ident, reason=args.reason, source_revision_id=args.guidance, regression_receipt=None, checksum=None, action="guidance_decision")
        status = "promoted" if args.promote else "rejected" if args.reject else None
        if not status:
            print("--promote or --reject required", file=sys.stderr)
            return 2
        item = m["guidance"].GuidanceStore(team_root).decide(args.guidance, status=status, identity=rec, reason=args.reason)
        print(json.dumps(item, indent=2))
        return 0
    if args.overlay:
        ident = m["identity"].current_identity(explicit_id=args.approver_id, explicit_name=args.approver_name)
        rec = m["identity"].approval_record(ident, reason=args.reason, source_revision_id=args.overlay, regression_receipt=None, checksum=None, action="overlay_decision")
        store = m["overlays"].OverlayStore(team_root)
        row = store.activate(args.overlay, identity=rec) if args.activate else store.archive(args.overlay, identity=rec)
        print(json.dumps(row, indent=2))
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
