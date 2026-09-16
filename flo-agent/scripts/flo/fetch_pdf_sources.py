#!/usr/bin/env python3
"""Fetch official PDF handbooks (FHA 4000.1, USDA HB-1-3555 chapters) into the private
cache, extract text per page, and record *section slices* with checksums.

    python scripts/flo/fetch_pdf_sources.py --program fha
    python scripts/flo/fetch_pdf_sources.py --program usda
    python scripts/flo/fetch_pdf_sources.py --program fha --offline   # re-slice from the cached PDF

The whole PDF is cached once (``<program>/<document>.pdf`` + ``.pages.json`` with
per-page text). Each slice in SLICES is located by its heading text in the page
stream; the slice text (from the heading to the next slice heading / end
marker) is recorded as a section with its own checksum. Nothing is committed.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"
sys.path.insert(0, str(REPO))
# rd.usda.gov sits behind an edge that rejects bare clients; a full browser-style header set is accepted.
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.rd.usda.gov/resources/directives/handbooks",
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "same-origin", "Upgrade-Insecure-Requests": "1",
}

DOCS = {
    # Two Handbook versions are kept side by side: Update 17 (issued 11/26/2025, the text in force
    # today) and Update 18 (issued 08/12/2026; "may be implemented immediately, but must be
    # implemented no later than November 10, 2026"). Neither overwrites the other: section keys are
    # version-qualified (``II.A.4.c@update-17`` / ``II.A.4.c@update-18``) and the effective-date
    # resolver in plugins/flo-team/sources.py picks the applicable one.
    "fha": [
        {"doc": "4000.1-update-17", "url": "https://www.hud.gov/sites/default/files/OCHCO/documents/40001-hsgh-Update-17.pdf",
         "edition": "Handbook 4000.1, Update 17 (issued 11/26/2025)", "page_date": "11/26/2025", "version": "update-17",
         "version_note": "currently published version in force before 11/10/2026", "mandatory_date": None},
        {"doc": "4000.1-update-18", "url": "https://www.hud.gov/sites/default/files/Housing/documents/40001-hsgh-Update-18.pdf",
         "edition": "Handbook 4000.1, Update 18 (issued 08/12/2026)", "page_date": "08/12/2026", "version": "update-18",
         "version_note": "may be implemented immediately, but must be implemented no later than November 10, 2026 (transmittal §3)", "mandatory_date": "11/10/2026"},
    ],
    "usda": [
        {"doc": "hb-1-3555-ch09", "url": "https://www.rd.usda.gov/sites/default/files/3555-1chapter09.pdf", "edition": "HB-1-3555 Chapter 9 (03-09-16) SPECIAL PN, Revised (08-05-25) PN 649", "page_date": "08/05/2025"},
        {"doc": "hb-1-3555-ch05", "url": "https://www.rd.usda.gov/files/3555-1chapter05.pdf", "edition": "HB-1-3555 Chapter 5", "page_date": None},
        {"doc": "hb-1-3555-ch11", "url": "https://www.rd.usda.gov/files/3555-1chapter11.pdf", "edition": "HB-1-3555 Chapter 11", "page_date": None},
    ],
}

# Slices: (program, section id, title, start regex, end regex, doc). Start/end are matched on the
# concatenated page text (case-insensitive); the slice is the text between them.
SLICES = {
    # Handbook 4000.1 body headings look like "c. Income Requirements (TOTAL) (11/10/2026)"; the
    # trailing date is the section's effective date and is recorded as ``effective_date``.
    "fha": [
        ("II.A.4.a", "TOTAL Mortgage Scorecard: Underwriting with an Automated Underwriting System", r"^\s*a\.\s+Underwriting with an Automated Underwriting System \(\d{2}/\d{2}/\d{4}\)", r"^\s*b\.\s+Credit Requirements \(TOTAL\)", "*"),
        ("II.A.4.c", "TOTAL: Income Requirements", r"^\s*c\.\s+Income Requirements \(TOTAL\) \(\d{2}/\d{2}/\d{4}\)", r"^\s*d\.\s+Asset Requirements \(TOTAL\)", "*"),
        ("II.A.4.d", "TOTAL: Asset Requirements", r"^\s*d\.\s+Asset Requirements \(TOTAL\) \(\d{2}/\d{2}/\d{4}\)", r"^\s*e\.\s+Final Underwriting Decision \(TOTAL\)", "*"),
        ("II.A.4.e", "TOTAL: Final Underwriting Decision", r"^\s*e\.\s+Final Underwriting Decision \(TOTAL\) \(\d{2}/\d{2}/\d{4}\)", r"^\s*a\.\s+Credit Requirements \(Manual\)", "*"),
        ("II.A.5.b", "Manual: Income Requirements", r"^\s*b\.\s+Income Requirements \(Manual\) \(\d{2}/\d{2}/\d{4}\)", r"^\s*c\.\s+Asset Requirements \(Manual\)", "*"),
        ("II.A.5.c", "Manual: Asset Requirements", r"^\s*c\.\s+Asset Requirements \(Manual\) \(\d{2}/\d{2}/\d{4}\)", r"^\s*d\.\s+Final Underwriting Decision \(Manual\)", "*"),
        ("II.A.5.d", "Manual: Final Underwriting Decision", r"^\s*d\.\s+Final Underwriting Decision \(Manual\) \(\d{2}/\d{2}/\d{4}\)", r"^\s*6\.\s+|^\s*B\.\s+Title II Insured Housing Programs|^\s*a\.\s+Origination", "*"),
        # II.A.1.a.i(A)(1) sits under "a. Applications and Disclosures (<date>)"; the slice itself has no date line,
        # so the parent heading's date is read from the page stream by _parent_heading_date().
        ("II.A.1.a.i(A)(1)", "Maximum Age of Mortgage Documents (Applications and Disclosures, general requirements)", r"^\s*\(1\)\s+Maximum Age of Mortgage Documents", r"^\s*\(2\)\s+Handling of Documents", "*", "parent:a. Applications and Disclosures"),
    ],
    # HB-1-3555 body headings are upper-case ("9.3 ANNUAL INCOME [7 CFR 3555.152(b)]"); running page
    # headers read "Paragraph 9.3 Annual Income" and never match a line-start pattern.
    "usda": [
        ("9.3", "Annual income (household income eligibility)", r"^\s*9\.3\s+ANNUAL INCOME", r"^\s*9\.4\s+CALCULATING INCOME FROM ASSETS", "hb-1-3555-ch09"),
        ("9.4", "Calculating income from assets", r"^\s*9\.4\s+CALCULATING INCOME FROM ASSETS", r"^\s*9\.5\s+ADJUSTED ANNUAL INCOME", "hb-1-3555-ch09"),
        ("9.5", "Adjusted annual income", r"^\s*9\.5\s+ADJUSTED ANNUAL INCOME", r"^\s*9\.6\s+AGENCY REVIEW OF HOUSEHOLD INCOME", "hb-1-3555-ch09"),
        ("9.7-9.8", "Repayment income: overview, stable and dependable income", r"^\s*9\.7\s+OVERVIEW", r"^\s*9\.9\s+AGENCY REVIEW OF REPAYMENT INCOME", "hb-1-3555-ch09"),
        ("9.9-9.12", "Agency review of repayment income, documentation forms, education, other", r"^\s*9\.9\s+AGENCY REVIEW OF REPAYMENT INCOME", r"^\s*ATTACHMENT 9-A", "hb-1-3555-ch09"),
        ("9-A", "Attachment 9-A income and documentation matrix", r"^\s*ATTACHMENT 9-A", r"^\s*ATTACHMENT 9-B|\Z", "hb-1-3555-ch09"),
        ("5.3", "Utilizing the Guaranteed Underwriting System (GUS)", r"^\s*5\.3\s+UTILIZING THE GUARANTEED UNDERWRITING SYSTEM", r"^\s*5\.4\s+|\Z", "hb-1-3555-ch05"),
        ("11.2-11.3", "Ratio analysis: the ratios, debt ratio waivers and compensating factors", r"^\s*11\.2\s+THE RATIOS", r"^\s*11\.4\s+MORTGAGE CREDIT CERTIFICATES", "hb-1-3555-ch11"),
    ],
}


def _load_sources():
    spec = importlib.util.spec_from_file_location("flo_team", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["flo_team"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return importlib.import_module("flo_team.sources")


def fetch_pdf(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:  # noqa: S310 - official public URL
        return r.read()


def extract_pages(pdf_bytes: bytes):
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return [(p.extract_text() or "") for p in reader.pages]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--program", required=True, choices=sorted(DOCS))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--home")
    args = parser.parse_args(argv)
    if args.home:
        import os

        os.environ["HERMES_HOME"] = args.home
    sources = _load_sources()
    importlib.import_module("flo_team.sourcediff").save_snapshot(args.program)  # baseline for sourcediff.compare_with_snapshot
    cache = sources.cache_dir(args.program)
    cache.mkdir(parents=True, exist_ok=True)
    pages_by_doc = {}
    rc = 0
    for doc in DOCS[args.program]:
        pdf_path = cache / f"{doc['doc']}.pdf"
        pages_path = cache / f"{doc['doc']}.pages.json"
        if not args.offline and not pdf_path.exists():
            try:
                pdf_path.write_bytes(fetch_pdf(doc["url"]))
                print(f"{doc['doc']}: downloaded {pdf_path.stat().st_size} bytes")
            except Exception as exc:  # noqa: BLE001
                print(f"{doc['doc']}: download failed: {exc}")
                rc = 1
                continue
        if not pdf_path.exists():
            print(f"{doc['doc']}: not cached")
            rc = 1
            continue
        if not pages_path.exists():
            pages = extract_pages(pdf_path.read_bytes())
            pages_path.write_text(json.dumps(pages), encoding="utf-8")
            print(f"{doc['doc']}: extracted {len(pages)} pages")
        pages_by_doc[doc["doc"]] = (doc, json.loads(pages_path.read_text(encoding="utf-8")))
    expanded = []
    for entry in SLICES[args.program]:
        if entry[4] == "*":  # one slice per document version, version-qualified keys
            for doc in DOCS[args.program]:
                expanded.append((f"{entry[0]}@{doc['version']}",) + tuple(entry[1:4]) + (doc["doc"],) + tuple(entry[5:]))
        else:
            expanded.append(entry)
    for entry in expanded:
        section, title, start, end, docname = entry[:5]
        forced_effective = entry[5] if len(entry) > 5 else None
        if docname not in pages_by_doc:
            print(f"{section}: document {docname} unavailable")
            continue
        doc, pages = pages_by_doc[docname]
        full = "\n".join(pages)
        # A heading can appear in the table of contents as well as in the body; keep the
        # candidate that yields the longest slice (the body), never the TOC entry.
        candidates = []
        for ms in re.finditer(start, full, re.I | re.M):
            me = re.search(end, full[ms.end():], re.I | re.M)
            candidates.append((ms.start(), full[ms.start(): ms.end() + (me.start() if me else len(full) - ms.end())]))
        if not candidates:
            print(f"{section}: start heading not found ({start})")
            rc = 1
            continue
        slice_start, text = max(candidates, key=lambda c: len(c[1]))
        if isinstance(forced_effective, str) and forced_effective.startswith("parent:"):
            forced_effective = _parent_heading_date(full[:slice_start], forced_effective[len("parent:"):])
        if len(text) < 500:
            print(f"{section}: slice too short ({len(text)} chars)")
            rc = 1
            continue
        effective = forced_effective or _heading_date(text)
        extra = {"effective_date": effective} if effective else {}
        if doc.get("version"):
            extra.update({"section_number": section.split("@")[0], "version": doc["version"], "version_note": doc.get("version_note"),
                          "mandatory_date": doc.get("mandatory_date"), "issued_date": doc.get("page_date")})
        rec = sources.record_section(program=args.program, section=section, title=title, official_url=doc["url"], text=text,
                                     page_date=doc.get("page_date") or _first_date(text), edition=doc["edition"], capture_method="official_pdf_slice",
                                     rights="U.S. Government work; private cache", notes=f"slice of {docname} located by heading regex",
                                     extra=extra or None)
        print(f"{section}: {title} | {rec['text_chars']} chars | effective {effective} | {rec['revision_id']}")
    return rc


def _parent_heading_date(full: str, heading: str):
    """Effective date printed on a parent heading, e.g. 'a. Applications and Disclosures (11/10/2026)' (last body occurrence)."""
    dates = re.findall(r"(?m)^\s*" + re.escape(heading) + r"\s*\((\d{2}/\d{2}/\d{4})\)", full)
    return dates[-1] if dates else None


def _heading_date(text: str):
    """Effective date printed in the section heading, e.g. 'c. Income Requirements (TOTAL) (11/10/2026)'."""
    m = re.search(r"\((\d{2}/\d{2}/\d{4})\)", text[:200])
    return m.group(1) if m else None


def _first_date(text: str):
    m = re.search(r"\((\d{2}-\d{2}-\d{2})\)", text[:600])
    return m.group(1) if m else None


if __name__ == "__main__":
    raise SystemExit(main())
