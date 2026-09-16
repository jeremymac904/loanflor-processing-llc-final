#!/usr/bin/env python3
"""Fetch the Freddie Mac Single-Family Seller/Servicer Guide sections used by the
Freddie Golden Loan Path into the private cache and record them in
``plugins/flo-team/knowledge/freddie/sections.json``.

    python scripts/flo/fetch_freddie_sources.py            # fetch the default slice
    python scripts/flo/fetch_freddie_sources.py --only 5303.1 5501.3

The public Guide site (guide.freddiemac.com) is a JavaScript application; the
same official content is served to that application as JSON from
``/cc/data/getAnswerById/answerId/<id>`` (section number → id from
``/cc/data/getContentLookupFor/GUIDE/SECTION_NUMBER``). Each record carries
the Guide's own ``publishedDate`` and ``version`` which are recorded as the
revision metadata. The HTML body is converted to text; both are cached
privately (Freddie's terms: professional use, no redistribution). Nothing is
committed; lifecycle stays ``detected`` until a human activates the revision.
"""

from __future__ import annotations

import argparse
import html
import importlib
import importlib.util
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
sys.path.insert(0, str(REPO))
BASE = "https://guide.freddiemac.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36", "Accept": "application/json"}

# The narrow Freddie slice: employed income, documentation, LPA, assets, DTI, age of docs.
DEFAULT_SECTIONS = [
    "5101.1", "5101.2", "5101.3", "5101.4", "5101.5", "5101.6", "5101.7", "5101.8", "5101.9",
    "5102.3", "5102.4",
    "5301.1", "5302.1", "5302.2", "5302.3", "5302.4", "5302.5", "5302.6",
    "5303.1", "5303.2", "5303.3", "5303.4",
    "5401.1", "5401.2",
    "5501.1", "5501.2", "5501.3",
]
RIGHTS = "Freddie Mac Guide terms (freddiemac.com/terms): professional use; no redistribution; private cache only"


class _Text(HTMLParser):
    BLOCK = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "table", "ul", "ol", "section", "td", "th"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        return html.unescape("".join(self.parts))


def html_to_text(markup: str) -> str:
    p = _Text()
    p.feed(markup or "")
    return re.sub(r"[ \t]+", " ", p.text())


def _get(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:  # noqa: S310 - official public URL
        return r.read()


def _load_sources():
    spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["flo_team"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return importlib.import_module("flo_team.sources")


def _field(record: dict, key: str):
    for row in record.get("data") or []:
        field = (row.get("content") or {}).get(key)
        if field and field.get("value") is not None:
            return field.get("value")
    return None


def _body(record: dict) -> str:
    """The Guide's own HTML body (``GUIDE/BODY``)."""
    return str(_field(record, "GUIDE/BODY") or "")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--home")
    parser.add_argument("--dump-keys", action="store_true", help="print the content field keys of the first record and exit")
    args = parser.parse_args(argv)
    if args.home:
        import os

        os.environ["HERMES_HOME"] = args.home
    sources = _load_sources()
    importlib.import_module("flo_team.sourcediff").save_snapshot("freddie")  # baseline for sourcediff.compare_with_snapshot
    lookup = json.loads(_get(f"{BASE}/cc/data/getContentLookupFor/GUIDE/SECTION_NUMBER"))
    wanted = args.only or DEFAULT_SECTIONS
    rc = 0
    for section in wanted:
        answer_id = lookup.get(section)
        if not answer_id:
            print(f"{section}: not in the official section index (skipped)")
            continue
        try:
            record = json.loads(_get(f"{BASE}/cc/data/getAnswerById/answerId/{answer_id}"))
        except Exception as exc:  # noqa: BLE001
            print(f"{section}: fetch failed: {exc}")
            rc = 1
            continue
        if args.dump_keys:
            for row in record.get("data") or []:
                for key, field in (row.get("content") or {}).items():
                    print(key, field.get("type"), repr(field.get("value"))[:80])
            return 0
        title = str(_field(record, "GUIDE/TITLE") or record.get("title") or "").strip()
        title = re.sub(rf"^{re.escape(section)}\s*", "", title).strip() or title
        effective = _field(record, "GUIDE/EFFECTIVE_DATE")
        markup = _body(record)
        text = html_to_text(markup)
        if len(text.strip()) < 500:
            print(f"{section}: body too short ({len(text.strip())} chars); keys: {[k for r in record.get('data') or [] for k in (r.get('content') or {})]}")
            rc = 1
            continue
        rec = sources.record_section(
            program="freddie", section=section, title=title, official_url=f"{BASE}/app/guide/section/{section}", text=text,
            page_date=record.get("publishedDate"), edition=f"Guide section version {record.get('version')} (published {record.get('publishedDate')})",
            capture_method="official_json_api", raw=markup.encode("utf-8"), raw_suffix=".html", rights=RIGHTS,
            notes=f"answerId {answer_id}; docID {record.get('docID')}; versionID {record.get('versionID')}; last modified {record.get('lastModifiedDate')}",
            extra={"effective_date": effective, "guide_version": record.get("version")},
        )
        print(f"{section}: {title} | v{record.get('version')} published {record.get('publishedDate')} effective {effective} | {rec['text_chars']} chars | {rec['revision_id']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
