#!/usr/bin/env python3
"""Fetch VA Pamphlet 26-7 (Lenders Handbook) chapters from VA's official KnowVA
knowledge base into the private cache and record them in
``plugins/flo-team/knowledge/va/sections.json``.

    python scripts/flo/fetch_va_sources.py                # default: Chapter 4 (Credit Underwriting)
    python scripts/flo/fetch_va_sources.py --article 554400000330850

KnowVA is a JavaScript application; the same official article content is
served to it as JSON from ``/system/ws/v11/ss/article/<id>`` (HTML ``content``
plus the article's ``lastModifiedDate``). The HTML is cached alongside the
text so tables (e.g. residual income) keep their row structure. Nothing is
committed; lifecycle stays ``detected`` until a human activates the revision.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import importlib.util
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "flo"))
BASE = "https://www.knowva.ebenefits.va.gov"
PORTAL = "554400000001018"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36", "Accept": "application/json"}
ARTICLES = {
    "554400000330850": ("Chapter 4", "Credit Underwriting"),
}
RIGHTS = "U.S. Government work (VA Pamphlet 26-7); private cache; review embedded third-party content before wider reuse"


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:  # noqa: S310 - official public URL
        return r.read()


def _load_sources():
    spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["flo_team"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return importlib.import_module("flo_team.sources")


def article_url(article_id: str) -> str:
    return (f"{BASE}/system/ws/v11/ss/article/{article_id}?$attribute=name,id,lastModifiedDate,availableEditions,"
            f"articleTypeAttributes,content,contentText&$lang=en-us&portalId={PORTAL}&usertype=customer")


def public_url(article_id: str, name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")
    return f"{BASE}/system/templates/selfservice/va_ssnew/help/customer/locale/en-US/portal/{PORTAL}/content/{article_id}/{slug}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--article", nargs="*")
    parser.add_argument("--home")
    args = parser.parse_args(argv)
    if args.home:
        import os

        os.environ["HERMES_HOME"] = args.home
    from fetch_freddie_sources import html_to_text

    sources = _load_sources()
    importlib.import_module("flo_team.sourcediff").save_snapshot("va")  # baseline for sourcediff.compare_with_snapshot
    rc = 0
    for article_id in args.article or list(ARTICLES):
        try:
            data = json.loads(_get(article_url(article_id)))
        except Exception as exc:  # noqa: BLE001
            print(f"{article_id}: fetch failed: {exc}")
            rc = 1
            continue
        article = data.get("article")
        if isinstance(article, list) and article:
            data = article[0]
        elif isinstance(article, dict):
            data = article
        name = data.get("name") or ARTICLES.get(article_id, ("", ""))[1]
        chapter = ARTICLES.get(article_id, (name, name))[0]
        markup = data.get("content") or ""
        text = html_to_text(markup) if markup else (data.get("contentText") or "")
        if len(text.strip()) < 500:
            print(f"{article_id}: body too short ({len(text.strip())} chars); keys={sorted(data)}")
            rc = 1
            continue
        modified = data.get("lastModifiedDate")
        if isinstance(modified, (int, float)):
            modified = dt.datetime.fromtimestamp(modified / 1000, dt.timezone.utc).strftime("%m/%d/%Y")
        elif isinstance(modified, str):
            try:  # "26 Aug 2026 18:03:44.000 +0000"
                modified = dt.datetime.strptime(modified.split(".")[0], "%d %b %Y %H:%M:%S").strftime("%m/%d/%Y")
            except ValueError:
                pass
        change_dates = sorted(set(re.findall(r"Change Date:\s*([A-Z][a-z]+ \d{1,2}, \d{4})", text)))
        rec = sources.record_section(
            program="va", section=chapter, title=f"{name}", official_url=public_url(article_id, name), text=text,
            page_date=str(modified) if modified else None, edition=f"KnowVA article {article_id} (updated {modified})",
            capture_method="official_json_api", raw=markup.encode("utf-8"), raw_suffix=".html", rights=RIGHTS,
            notes=f"KnowVA article {article_id} version {data.get('version')}; topic change dates in text: {', '.join(change_dates) or 'n/a'}",
            extra={"effective_date": str(modified) if modified else None, "topic_change_dates": change_dates, "article_version": data.get("version")},
        )
        print(f"{chapter}: {name} | updated {modified} | {rec['text_chars']} chars | {rec['revision_id']}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
