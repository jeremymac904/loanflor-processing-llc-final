#!/usr/bin/env python3
"""Record an official section captured from a JavaScript-rendered official site
(Freddie Mac Guide, VA KnowVA) into the private cache + sections.json.

    python scripts/flo/ingest_source_capture.py --program freddie --section 5303.1 \
        --title "Employed income" --url https://guide.freddiemac.com/app/guide/section/5303.1 \
        --from-json <tool-results json>   (or --from-text <file>)
        [--page-date 05/07/2025] [--edition "Guide as published 2026-09"]

The capture is the rendered article text of the official page (same site,
same content, retrieved through a browser because the site does not serve
static HTML). Retrieval timestamp and checksum are recorded; lifecycle stays
``detected``. Rights: the guides' own professional-use terms; private cache
only, nothing committed.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
sys.path.insert(0, str(REPO))
_DATE = re.compile(r"(\d{2}/\d{2}/\d{4})")
RIGHTS = {
    "freddie": "Freddie Mac Guide terms (freddiemac.com/terms): professional use; no redistribution; private cache only",
    "va": "U.S. Government work (VA Pamphlet 26-7); private cache; review embedded third-party content before wider reuse",
    "fha": "U.S. Government work (HUD Handbook 4000.1); private cache",
    "usda": "U.S. Government work (USDA HB-1-3555); private cache",
    "fannie": "Fannie Mae limited professional-use permission; private cache only",
}


def _load_sources():
    spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["flo_team"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return importlib.import_module("flo_team.sources")


def text_from_json(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    parts = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
    elif isinstance(data, dict):
        parts.append(str(data.get("text", "")))
    text = "\n".join(parts)
    # Strip the capture header ("Title: …\nURL: …\nSource element: …\n---\n").
    if "\n---\n" in text[:400]:
        text = text.split("\n---\n", 1)[1]
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--program", required=True)
    parser.add_argument("--section", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--from-json")
    parser.add_argument("--from-text")
    parser.add_argument("--page-date")
    parser.add_argument("--edition", default="")
    parser.add_argument("--capture-method", default="browser_rendered_article")
    parser.add_argument("--home")
    args = parser.parse_args(argv)
    if args.home:
        import os

        os.environ["HERMES_HOME"] = args.home
    sources = _load_sources()
    if args.from_json:
        text = text_from_json(Path(args.from_json))
    elif args.from_text:
        text = Path(args.from_text).read_text(encoding="utf-8")
    else:
        print("--from-json or --from-text required", file=sys.stderr)
        return 2
    if len(text.strip()) < 500:
        print(f"capture too short ({len(text.strip())} chars); refusing to record", file=sys.stderr)
        return 1
    page_date = args.page_date
    if not page_date:
        m = _DATE.search(text[:3000])
        page_date = m.group(1) if m else None
    rec = sources.record_section(program=args.program, section=args.section, title=args.title, official_url=args.url, text=text,
                                 page_date=page_date, edition=args.edition or f"{sources.program_spec(args.program)['source_title']} as published on the official site",
                                 capture_method=args.capture_method, rights=RIGHTS.get(args.program.lower(), "official source; private cache"))
    print(f"{args.program} {args.section}: {rec['title']} | {rec['text_chars']} chars | page date {rec['page_date']} | {rec['revision_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
