#!/usr/bin/env python3
"""Move a program's recorded official sections through the source lifecycle.

    python scripts/flo/activate_sources.py --program freddie --status
    python scripts/flo/activate_sources.py --program freddie --review           # detected -> pending_review -> regression
    python scripts/flo/activate_sources.py --program freddie --approve --reason "<why>" [--approver-id ID --approver-name NAME]
    python scripts/flo/activate_sources.py --program freddie --activate
    python scripts/flo/activate_sources.py --program fannie --migrate-identity  # upgrade v1 approval records
    python scripts/flo/activate_sources.py --program freddie --archive 5303.1

Lifecycle per section revision: detected → pending_review → regression →
approval → active. ``--review`` is mechanical (anchors are verified against
the privately cached official text and a regression receipt is recorded).
``--approve`` and ``--activate`` are the human boundary: they record a
structured approval identity (``plugins/flo-team/identity.py``:
approved_by_user_id, approved_by_display_name, approved_at, approval_reason,
source_revision_id, environment). No e-mail address is required; without
auth-provided ids the local development identity (OS account) is used, or
``--approver-id/--approver-name`` / ``FLO_APPROVER_ID/NAME``. Nothing here is
callable from a bot tool. Re-fetching a changed section demotes it to
``detected`` again. ``--approver`` is kept for compatibility with the
Fannie-era wrapper and maps to ``--approver-name``.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
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
    for name in ("sources", "knowledge", "manifest", "identity"):
        importlib.import_module(f"flo_team.{name}")
    return (sys.modules["flo_team.sources"], sys.modules["flo_team.knowledge"], sys.modules["flo_team.manifest"], sys.modules["flo_team.identity"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--program", required=True)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--review", action="store_true", help="detected -> pending_review -> regression (mechanical)")
    parser.add_argument("--approve", action="store_true", help="regression -> approval (human)")
    parser.add_argument("--activate", action="store_true", help="approval -> active (human)")
    parser.add_argument("--archive", metavar="SECTION", help="archive one section revision (human)")
    parser.add_argument("--migrate-identity", action="store_true", help="upgrade legacy approval records to the structured identity schema")
    parser.add_argument("--approver-id", help="stable approver user id (auth subject when available)")
    parser.add_argument("--approver-name", help="approver display name")
    parser.add_argument("--approver", help="compatibility alias for --approver-name")
    parser.add_argument("--reason", "--basis", dest="reason", default="", help="why the approval is granted (instruction, ticket, review note)")
    parser.add_argument("--home", help="HERMES root override (tests)")
    parser.add_argument("--only", nargs="*", help="subset of section ids")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.home:
        import os

        os.environ["HERMES_HOME"] = args.home
    sources, knowledge, manifest, identity = _load()
    program = args.program.lower()
    try:
        sources.program_spec(program)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    root = manifest.hermes_root()
    if root is None:
        print("HERMES_HOME not set", file=sys.stderr)
        return 2
    state = knowledge.KnowledgeState(root / "flo" / "team")
    sections = sources.load_sections(program)
    ids = [s for s in sections if not args.only or s in args.only]
    if not ids:
        print(f"no sections recorded for {program}; run the fetch script first")
        return 2

    if args.status or not any((args.review, args.approve, args.activate, args.archive, args.migrate_identity)):
        for sid in ids:
            st = sources.section_status(program, sid, state, root)
            force = "" if st.in_force in (None, True) else "  NOT YET IN FORCE"
            print(f"{sid:12} {st.lifecycle:15} usable={st.usable!s:5} {st.title[:60]} | eff {st.effective_date} | {st.revision_id}{force}")
        return 0

    human = args.approve or args.activate or args.archive
    ident = identity.current_identity(explicit_id=args.approver_id, explicit_name=args.approver_name or args.approver) if human else None
    if human and not args.reason and args.approve:
        print("--reason is required for approval (audit record)", file=sys.stderr)
        return 2

    rc = 0
    for sid in ids:
        meta = sections[sid]
        rev = meta["revision_id"]
        row = state.docs.get(rev)
        if row is None:
            row = state.detect(source_id=f"{program}-{sid.lower()}", version=f"{meta.get('page_date')} / {meta.get('edition')}",
                               official_url=meta["official_url"], detected_by=f"fetch_{program}_sources", checksum=meta.get("checksum_text"), revision_id=rev)
        current = row.get("lifecycle", "detected")
        if args.migrate_identity:
            doc = state.docs.get(rev)
            if doc.get("approval") and doc["approval"].get("schema_version") != 2:
                doc["approval"] = identity.migrate_legacy_approval(doc["approval"], source_revision_id=rev)
                state.docs.put(rev, doc)
                print(f"{sid}: approval record migrated ({doc['approval']['approved_by_user_id']})")
            else:
                print(f"{sid}: nothing to migrate")
            continue
        if args.review:
            if current == "detected":
                state.advance(rev, "pending_review", by="activate_sources", source="model")
                current = "pending_review"
            if current == "pending_review":
                result = sources.regression(program, sid, root)
                if not result["ok"]:
                    print(f"{sid}: regression FAILED {result['failed'] or result.get('reason')}")
                    rc = 1
                    continue
                state.advance(rev, "regression", by="activate_sources", source="model")
                doc = state.docs.get(rev)
                doc["regression_receipt"] = result["receipt"]
                doc["regression_checked"] = result["checked"]
                doc["regression_at"] = result["at"]
                state.docs.put(rev, doc)
                print(f"{sid}: regression ok ({result['checked']} anchors) receipt {result['receipt']}")
            else:
                print(f"{sid}: {current} (no review step needed)")
        if args.approve:
            doc = state.docs.get(rev)
            if doc.get("lifecycle") == "regression":
                state.advance(rev, "approval", by=ident.user_id, source="user", regression_receipt=doc.get("regression_receipt"))
                doc = state.docs.get(rev)
                doc["approval"] = identity.approval_record(ident, reason=args.reason, source_revision_id=rev, regression_receipt=doc.get("regression_receipt"),
                                                           checksum=meta.get("checksum_text"))
                state.docs.put(rev, doc)
                print(f"{sid}: approved by {ident.display_name} ({ident.user_id}, {ident.source})")
            else:
                print(f"{sid}: cannot approve from {doc.get('lifecycle')}")
                rc = 1
        if args.activate:
            doc = state.docs.get(rev)
            if doc.get("lifecycle") == "approval":
                st = sources.section_status(program, sid, None, root)
                if st.lifecycle == "STALE_SOURCE" or not st.checksum == meta.get("checksum_text"):
                    print(f"{sid}: cache changed since approval; refusing to activate")
                    rc = 1
                    continue
                state.advance(rev, "active", by=ident.user_id, source="user")
                doc = state.docs.get(rev)
                doc["activation"] = identity.approval_record(ident, reason=args.reason or doc.get("approval", {}).get("approval_reason", ""), source_revision_id=rev,
                                                             regression_receipt=doc.get("regression_receipt"), checksum=meta.get("checksum_text"), action="activation")
                state.docs.put(rev, doc)
                flag = "" if st.in_force in (None, True) else f"  (effective {st.effective_date}: not yet in force — cards will carry a caution)"
                print(f"{sid}: ACTIVE{flag}")
            else:
                print(f"{sid}: cannot activate from {doc.get('lifecycle')}")
                rc = 1
        if args.archive and sid == args.archive:
            state.advance(rev, "archived", by=ident.user_id, source="user")
            print(f"{sid}: archived")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
