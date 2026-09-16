#!/usr/bin/env python3
"""Build plugins/flo-team/knowledge/registry.json from the two source-of-truth files:

* ``.flo/underwriting/source_registry.json`` — the prior underwriting scaffold
  (11 official discovery records; all pending review, none active);
* ``.flo/team/pack/sources/official/underwriting_sources.yaml`` — the team
  pack's official source list, lender overlay state and specialty products.

The result is metadata only (no source bytes). Every record keeps
``lifecycle: pending_review`` unless an administrator has activated it through
the knowledge lifecycle — this script never sets ``active``.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SRC_JSON = REPO / ".flo" / "underwriting" / "source_registry.json"
SRC_YAML = REPO / ".flo" / "team" / "pack" / "sources" / "official" / "underwriting_sources.yaml"
OUT = REPO / "plugins" / "flo-team" / "knowledge" / "registry.json"

PROGRAM_MAP = {
    "conventional_fannie": "fannie", "conventional_freddie": "freddie", "fha": "fha", "va": "va",
    "usda_guaranteed": "usda", "conventional": None,
}


def main() -> int:
    sources = {}
    prior = json.loads(SRC_JSON.read_text(encoding="utf-8")) if SRC_JSON.exists() else {"sources": []}
    for row in prior.get("sources", []):
        program = row.get("agency") or PROGRAM_MAP.get(row.get("program"))
        sources[row["source_id"]] = {
            "source_id": row["source_id"], "title": row.get("document_name"), "program": program, "agency": row.get("agency"),
            "official_url": row.get("official_source"), "section": row.get("section"), "publication_date": row.get("publication_date"),
            "effective_date": row.get("effective_date"), "version": row.get("version"), "checksum": row.get("checksum"),
            "checked_at": row.get("checked_at"), "retrieved_at": row.get("retrieved_at"), "tier": 1,
            "status": (row.get("temporal_status") or "unknown").lower(), "lifecycle": "pending_review",
            "rights_status": row.get("rights_status"), "notes": row.get("notes"), "origin": "flo/underwriting/source_registry.json",
        }
    pack = yaml.safe_load(SRC_YAML.read_text(encoding="utf-8")) if SRC_YAML.exists() else {}
    aliases = {
        "fannie_selling_guide": "fannie-selling-guide", "freddie_single_family_guide": "freddie-guide",
        "fha_handbook_4000_1": "fha-handbook", "fha_info": "fha-info", "va_pamphlet_26_7": "va-handbook",
        "usda_hb_1_3555": "usda-handbook", "usda_procedure_notices": "usda-procedure-notices",
    }
    for row in pack.get("sources", []):
        program = PROGRAM_MAP.get(row.get("program"), row.get("program"))
        sid = aliases.get(row["id"], row["id"].replace("_", "-"))
        if sid in sources:
            sources[sid].setdefault("pack_id", row["id"])
            continue
        sources[sid] = {
            "source_id": sid, "pack_id": row["id"], "title": row.get("title"), "program": program, "agency": program,
            "official_url": row.get("official_url"), "section": None,
            "publication_date": row.get("observed_published_date") or row.get("observed_update_date"), "effective_date": None,
            "version": None, "checksum": None, "checked_at": str(pack.get("reviewed") or ""), "retrieved_at": None,
            "tier": 1 if str(row.get("tier", "")).startswith("authoritative") else 4,
            "status": "unknown", "lifecycle": "pending_review", "rights_status": "REVIEW_REQUIRED",
            "notes": f"pack tier: {row.get('tier')}; ingestion: {row.get('ingestion', 'metadata_only')}", "origin": "team pack underwriting_sources.yaml",
        }
    overlays = {}
    for lender, info in (pack.get("lender_overlays") or {}).items():
        overlays[lender.replace("_", "-")] = {"state": "NOT_LOADED", "note": info.get("note", ""), "source_id": None, "pack_status": info.get("status")}
        overlays[lender] = overlays[lender.replace("_", "-")]
    specialty = {k: v for k, v in (pack.get("specialty_programs") or {}).items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema_version": 1,
        "generated_from": [str(SRC_JSON.relative_to(REPO)), str(SRC_YAML.relative_to(REPO))],
        "note": "Metadata only. No source bytes ingested. No revision is active; every guideline answer is SOURCE_GAP until admin review/approval.",
        "sources": sorted(sources.values(), key=lambda r: r["source_id"]),
        "overlays": overlays,
        "specialty_programs": specialty,
    }, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"wrote {OUT} ({len(sources)} sources, {len(overlays)//2 or len(overlays)} overlay lenders, {len(specialty)} specialty programs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
