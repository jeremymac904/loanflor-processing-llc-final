"""Sage's source registry, knowledge-cache lifecycle and Guideline Cards.

Builds on the prior underwriting scaffold (``.flo/underwriting/`` — source
registry, five inactive agency packs) and the pack's
``sources/official/underwriting_sources.yaml``. The plugin ships a copy of the
registry (``knowledge/registry.json``) so runtime does not depend on the repo
checkout; the installer refreshes it.

Layers are kept apart and named on every answer: ``agency_baseline``,
``lender_overlay``, ``investor_program``, ``aus_finding``, ``file_condition``.

Lifecycle of a source revision::

    detected -> pending_review -> regression -> approval -> active -> archived

Only ``active`` revisions can back a Guideline Card conclusion. A detected or
pending revision never changes an answer; it is surfaced as "new guidance
available". Because every shipped revision is ``pending_review`` (no source
bytes were ingested, no rights decision, no admin approval), every real
guideline question today yields a card whose conclusion is ``SOURCE_GAP`` with
the official link and the exact reason — that is the correct, honest output.

Non-QM / Jumbo / specialty: no card is produced without an actual
lender/investor source record; Loan Factory overlays are ``NOT_LOADED``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .store import JsonDocStore, now_iso

HERE = Path(__file__).resolve().parent
REGISTRY_PATH = HERE / "knowledge" / "registry.json"

PROGRAMS = ("fannie", "freddie", "fha", "va", "usda", "non_qm", "jumbo", "specialty")
AGENCY_PROGRAMS = ("fannie", "freddie", "fha", "va", "usda")
LAYERS = ("agency_baseline", "lender_overlay", "investor_program", "aus_finding", "file_condition")
LIFECYCLE = ("detected", "pending_review", "regression", "approval", "active", "archived", "superseded")
_LIFECYCLE_NEXT = {
    "detected": {"pending_review", "archived"},
    "pending_review": {"regression", "archived"},
    "regression": {"approval", "pending_review", "archived"},
    "approval": {"active", "pending_review", "archived"},
    "active": {"superseded", "archived"},
    "superseded": {"archived"},
    "archived": set(),
}
OVERLAY_STATES = ("NOT_LOADED", "LOADED", "NOT_APPLICABLE_WITH_EVIDENCE", "CONFLICT")
SOURCE_TIERS = {"official": 1, "organization": 2, "file_specific": 3, "informational": 4}


class KnowledgeError(ValueError):
    pass


def load_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    path = path or REGISTRY_PATH
    if not path.exists():
        return {"schema_version": 1, "sources": [], "overlays": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def sources_for(registry: Dict[str, Any], program: str) -> List[Dict[str, Any]]:
    program = (program or "").lower()
    return [s for s in registry.get("sources", []) if s.get("program") == program or s.get("agency") == program]


def active_sources(registry: Dict[str, Any], program: str) -> List[Dict[str, Any]]:
    return [s for s in sources_for(registry, program) if s.get("lifecycle") == "active"]


def overlay_state(registry: Dict[str, Any], lender: Optional[str]) -> Dict[str, Any]:
    if not lender:
        return {"lender": None, "state": "NOT_LOADED", "note": "no lender named; overlay scope unknown"}
    overlays = registry.get("overlays") or {}
    row = overlays.get(lender.lower())
    if not row:
        return {"lender": lender, "state": "NOT_LOADED", "note": f"no approved overlay pack for {lender}; 'none loaded' never means 'no overlays exist' — confirm with AE"}
    state = row.get("state", "NOT_LOADED")
    if state not in OVERLAY_STATES:
        state = "NOT_LOADED"
    return {"lender": lender, "state": state, "note": row.get("note", ""), "source_id": row.get("source_id")}


def guideline_card(
    *,
    program: str,
    topic: str,
    registry: Optional[Dict[str, Any]] = None,
    lender: Optional[str] = None,
    aus_path: Optional[str] = None,
    aus_findings: Optional[List[str]] = None,
    file_conditions: Optional[List[str]] = None,
    investor_source_id: Optional[str] = None,
    calculation_trace_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """A citation-capable Guideline Card. Conclusion is SOURCE_GAP unless an ACTIVE source backs it."""
    registry = registry or load_registry()
    program = (program or "").lower()
    if program not in PROGRAMS:
        raise KnowledgeError(f"program must be one of {PROGRAMS}")
    topic = " ".join(str(topic or "").split())
    if not topic:
        raise KnowledgeError("topic is required")

    layers: Dict[str, Any] = {layer: None for layer in LAYERS}
    cautions: List[str] = []

    if program in AGENCY_PROGRAMS:
        active = active_sources(registry, program)
        candidates = sources_for(registry, program)
        if active:
            src = active[0]
            layers["agency_baseline"] = _cite(src, topic)
            conclusion = f"See {src['title']} {src.get('section') or '(section: SOURCE_GAP)'}: rule text is in the approved cache revision {src.get('revision_id')}"
            confidence = "source-backed (active revision)"
        else:
            layers["agency_baseline"] = {"status": "SOURCE_GAP", "candidates": [_cite(s, topic) for s in candidates[:3]]}
            conclusion = "SOURCE_GAP"
            confidence = "none: no active, rights-approved source revision for this program"
            if candidates:
                cautions.append(f"{len(candidates)} official source record(s) known for {program} but none is active (lifecycle: "
                                + ", ".join(sorted({c.get('lifecycle', 'pending_review') for c in candidates})) + ").")
            else:
                cautions.append(f"no official source record registered for {program}")
    else:
        # Non-QM / Jumbo / specialty: only with a real lender/investor source.
        src = _find(registry, investor_source_id) if investor_source_id else None
        if src and src.get("lifecycle") == "active":
            layers["investor_program"] = _cite(src, topic)
            conclusion = f"Per {src['title']} (investor/program guide) {src.get('section') or ''}".strip()
            confidence = "source-backed (active investor revision)"
        else:
            layers["investor_program"] = {"status": "SOURCE_GAP", "note": "Non-QM/Jumbo/specialty rules exist only in the actual lender/investor guide; none loaded"}
            conclusion = "SOURCE_GAP"
            confidence = "none: no lender/investor guide loaded for this product"
            cautions.append("Do not infer Non-QM/Jumbo/specialty rules from agency guides or general knowledge.")

    layers["lender_overlay"] = overlay_state(registry, lender)
    if layers["lender_overlay"]["state"] == "NOT_LOADED":
        cautions.append("Overlay not loaded — confirm with AE.")
    layers["aus_finding"] = {"path": aus_path or "unknown", "findings": [str(f)[:300] for f in (aus_findings or [])][:20],
                             "note": "AUS findings are file-specific evidence, not a guideline"}
    layers["file_condition"] = {"conditions": [str(c)[:300] for c in (file_conditions or [])][:20],
                                "note": "a UW condition is a file-specific checklist entry, never a global rule"}

    return {
        "card_type": "guideline_card",
        "program": program,
        "agency_or_investor": program if program in AGENCY_PROGRAMS else (investor_source_id or "SOURCE_GAP"),
        "topic": topic,
        "aus_or_manual": aus_path or "unknown",
        "layers": layers,
        "conclusion": conclusion,
        "confidence": confidence,
        "calculation_trace": calculation_trace_ref,
        "missing_documentation": "SOURCE_GAP: documentation requirements follow the (not yet active) source" if conclusion == "SOURCE_GAP" else None,
        "conflict_or_caution": cautions,
        "best_next_move": (
            "Ask the AE/UW for the applicable rule text and effective date, or load the approved source revision through the admin review workflow."
            if conclusion == "SOURCE_GAP" else "Apply the cited section; escalate to AE/UW if overlay or AUS conflicts remain."
        ),
        "underwriting_decision": False,
        "language": "guideline-supported assessment based on the documents currently available; not a loan approval",
        "generated_at": now_iso(),
    }


def _find(registry: Dict[str, Any], source_id: Optional[str]) -> Optional[Dict[str, Any]]:
    for s in registry.get("sources", []):
        if s.get("source_id") == source_id:
            return s
    return None


def _cite(src: Dict[str, Any], topic: str) -> Dict[str, Any]:
    return {
        "source_id": src.get("source_id"),
        "title": src.get("title") or src.get("document_name"),
        "official_url": src.get("official_url") or src.get("official_source"),
        "section": src.get("section") or "SOURCE_GAP",
        "publication_date": src.get("publication_date"),
        "effective_date": src.get("effective_date"),
        "version": src.get("version"),
        "lifecycle": src.get("lifecycle", "pending_review"),
        "status": src.get("status", "unknown"),
        "tier": src.get("tier", 1),
        "topic": topic,
    }


# ---------------------------------------------------------------------------
# Knowledge freshness + lifecycle (stateful, under the shared team root)
# ---------------------------------------------------------------------------

class KnowledgeState:
    """Per-install revision lifecycle overlay on the shipped registry."""

    def __init__(self, root) -> None:
        self.docs = JsonDocStore(root / "knowledge")

    def revisions(self) -> List[Dict[str, Any]]:
        return list(self.docs.all())

    def detect(self, *, source_id: str, version: str, official_url: str, detected_by: str, checksum: Optional[str] = None,
               revision_id: Optional[str] = None) -> Dict[str, Any]:
        rev_id = revision_id or re.sub(r"[^A-Za-z0-9_.\-]", "_", f"{source_id}-{version}")[:80]
        existing = self.docs.get(rev_id) if self._safe(rev_id) else None
        if existing:
            return existing
        row = {
            "revision_id": rev_id, "source_id": source_id, "version": version, "official_url": official_url,
            "checksum": checksum, "lifecycle": "detected", "detected_by": detected_by, "detected_at": now_iso(),
            "history": [{"at": now_iso(), "lifecycle": "detected", "by": detected_by}],
            "note": "detection never activates a rule; review, regression tests and admin approval are required",
        }
        self.docs.put(rev_id, row)
        return row

    def advance(self, revision_id: str, new_state: str, *, by: str, source: str = "user", regression_receipt: Optional[str] = None) -> Dict[str, Any]:
        row = self.docs.get(revision_id)
        if row is None:
            raise KnowledgeError(f"unknown revision {revision_id}")
        current = row.get("lifecycle", "detected")
        if new_state not in LIFECYCLE or new_state not in _LIFECYCLE_NEXT.get(current, set()):
            raise KnowledgeError(f"cannot move revision from {current} to {new_state}")
        if new_state in ("approval", "active") and source != "user":
            raise KnowledgeError("only a human administrator can approve or activate a revision")
        if new_state == "approval" and not regression_receipt:
            raise KnowledgeError("approval requires a regression-test receipt")
        row["lifecycle"] = new_state
        if regression_receipt:
            row["regression_receipt"] = regression_receipt
        row.setdefault("history", []).append({"at": now_iso(), "lifecycle": new_state, "by": f"{source}:{by}"})
        self.docs.put(revision_id, row)
        return row

    def freshness(self, registry: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = []
        pending = {r["source_id"]: r for r in self.revisions() if r.get("lifecycle") in ("detected", "pending_review", "regression", "approval")}
        for src in registry.get("sources", []):
            sid = src.get("source_id")
            rows.append({
                "source_id": sid,
                "title": src.get("title"),
                "program": src.get("program"),
                "lifecycle": src.get("lifecycle", "pending_review"),
                "status": src.get("status", "unknown"),
                "checked_at": src.get("checked_at"),
                "publication_date": src.get("publication_date"),
                "official_url": src.get("official_url"),
                "new_revision_pending": pending.get(sid, {}).get("revision_id"),
                "freshness": "UNKNOWN" if not src.get("checked_at") else ("STALE_SOURCE" if src.get("lifecycle") != "active" else "current"),
            })
        return rows

    @staticmethod
    def _safe(value: str) -> bool:
        try:
            from .store import safe_id

            safe_id(value)
            return True
        except ValueError:
            return False
