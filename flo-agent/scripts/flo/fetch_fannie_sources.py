#!/usr/bin/env python3
"""Fetch the official Fannie Mae Selling Guide sections for the Golden Loan Path
into the PRIVATE source cache and record each as a *detected* revision.

    python scripts/flo/fetch_fannie_sources.py            # fetch + record
    python scripts/flo/fetch_fannie_sources.py --offline  # only re-hash what is cached

Cache location (outside git): ``<hermes root>/flo/sources/cache/fannie/<section>.html``
plus an extracted ``.txt``. What goes into git is metadata only:
``plugins/flo-team/knowledge/fannie/sections.json`` (title, official URL,
section id, publication date shown on the page, retrieval timestamp, sha256 of
the retrieved HTML and of the extracted text, lifecycle). The lifecycle stays
``detected`` here; review/regression/approval/activation are separate steps
(`scripts/flo/activate_fannie_slice.py`).

Rights: Fannie Mae grants mortgage-finance professionals limited permission to
reproduce the guide for their own origination use and reserves the right to
revoke it (copyright-and-preface). The cache is therefore private to the
processor's machine; the repository carries citations and paraphrased rule
records, not the guide text.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
META = REPO / "plugins" / "flo-team" / "knowledge" / "fannie" / "sections.json"
BASE = "https://selling-guide.fanniemae.com/sel/"

# The vertical slice: employment/base income, documentation standards, assets,
# document age, reserves, DU tolerances and findings. Section ids are the
# guide's current numbering (the Sept 2026 edition moved employment income to B3-3.3).
SECTIONS = [
    ("B3-3.1-01", "General Income Information", "b3-3.1-01/general-income-information"),
    ("B3-3.2-01", "Standards for Employment and Income Documentation", "b3-3.2-01/standards-employment-and-income-documentation"),
    ("B3-3.2-02", "Standards for Employment-Related Income", "b3-3.2-02/standards-employment-related-income"),
    ("B3-3.3-01", "Base Income", "b3-3.3-01/base-income"),
    ("B3-3.3-02", "Bonus, Commission, Overtime, and Tip Income", "b3-3.3-02/bonus-commission-overtime-and-tip-income"),
    ("B3-3.1-04", "Verbal Verification of Employment", "b3-3.1-04/verbal-verification-employment"),
    ("B3-4.2-01", "Verification of Deposits and Assets", "b3-4.2-01/verification-deposits-and-assets"),
    ("B3-4.2-02", "Depository Accounts", "b3-4.2-02/depository-accounts"),
    ("B3-4.1-01", "Minimum Reserve Requirements", "b3-4.1-01/minimum-reserve-requirements"),
    ("B1-1-03", "Allowable Age of Credit Documents and Federal Income Tax Returns", "b1-1-03/allowable-age-credit-documents-and-federal-income-tax-returns"),
    ("B3-2-10", "Accuracy of DU Data, DU Tolerances, and Errors in the Credit Report", "b3-2-10/accuracy-du-data-du-tolerances-and-errors-credit-report"),
    ("B3-2-11", "DU Underwriting Findings Report", "b3-2-11/du-underwriting-findings-report"),
]
_DATE = re.compile(r"(\d{2}/\d{2}/\d{4})")
_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)


def cache_dir() -> Path:
    from hermes_constants import get_default_hermes_root

    return Path(get_default_hermes_root()) / "flo" / "sources" / "cache" / "fannie"


def extract_text(raw: str) -> str:
    text = _SCRIPT.sub(" ", raw)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def page_date(text: str, section: str) -> str | None:
    """The parenthetical date next to the section heading ('(03/04/2026)')."""
    idx = text.find(section)
    window = text[idx: idx + 400] if idx >= 0 else text[:2000]
    m = _DATE.search(window)
    return m.group(1) if m else None


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Flo-Agent/0.1 (mortgage processing; source cache)"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - official public URL
        return resp.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    cache = cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    try:  # baseline for sourcediff.compare_with_snapshot (best effort; the fetch must not depend on it)
        import importlib.util as _ilu

        _plugin = Path(__file__).resolve().parents[2] / "plugins" / "flo-team"
        _spec = _ilu.spec_from_file_location("flo_team", _plugin / "__init__.py", submodule_search_locations=[str(_plugin)])
        _mod = _ilu.module_from_spec(_spec)
        sys.modules.setdefault("flo_team", _mod)
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
        importlib.import_module("flo_team.sourcediff").save_snapshot("fannie")
    except Exception as exc:  # noqa: BLE001
        print(f"snapshot skipped: {exc}")
    existing = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {"schema_version": 1, "sections": {}}
    now = datetime.now(timezone.utc).isoformat()
    for section, title, slug in SECTIONS:
        url = BASE + slug
        html_path = cache / f"{section}.html"
        txt_path = cache / f"{section}.txt"
        if not args.offline:
            try:
                raw = fetch(url)
            except Exception as exc:  # noqa: BLE001
                print(f"{section}: fetch failed: {exc}")
                continue
            html_path.write_text(raw, encoding="utf-8")
            txt_path.write_text(extract_text(raw), encoding="utf-8")
        if not html_path.exists():
            print(f"{section}: not cached")
            continue
        raw = html_path.read_text(encoding="utf-8")
        text = txt_path.read_text(encoding="utf-8") if txt_path.exists() else extract_text(raw)
        record = existing["sections"].get(section, {})
        sha_html = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        sha_text = hashlib.sha256(text.encode("utf-8")).hexdigest()
        changed = record.get("checksum_text") not in (None, sha_text)
        record.update({
            "section": section,
            "title": title,
            "official_url": url,
            "source_title": "Fannie Mae Selling Guide",
            "edition": "Published 2026-09-02",
            "page_date": page_date(text, section),
            "retrieved_at": now if not args.offline else record.get("retrieved_at"),
            "checksum_html": sha_html,
            "checksum_text": sha_text,
            "text_chars": len(text),
            "cache_ref": f"flo/sources/cache/fannie/{section}.txt",
            "rights": "Fannie Mae limited professional-use permission; private cache only",
            "lifecycle": "detected" if (changed or "lifecycle" not in record) else record["lifecycle"],
            "revision_id": f"fannie-{section.lower()}-{sha_text[:12]}",
        })
        if changed and record.get("lifecycle") not in (None, "detected"):
            record["note"] = f"content changed on re-fetch; previous revision demoted to detected at {now}"
        existing["sections"][section] = record
        print(f"{section}: {title} | page date {record['page_date']} | {len(text)} chars | {record['lifecycle']} | {record['revision_id']}")
    existing["generated_at"] = now
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {META}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
