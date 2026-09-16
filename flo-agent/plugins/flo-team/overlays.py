"""Lender / investor overlay architecture — layered ON TOP OF an agency rule, never replacing it.

No Loan Factory overlay is invented here: the store ships empty. An overlay
record is created only from an actual lender guide or approved AE guidance
(``overlay_source``) and carries:

    overlay_id, program, lender, product, overlay_source, overlay_section,
    agency_rule_ref (the agency rule it sits on, optional), text,
    effective_date, expires, exception (bool: relaxes vs tightens),
    proposed_by, approved_by (structured identity), ae_confirmation_status
    (unconfirmed | confirmed | disputed), confirmed_by, lifecycle
    (proposed | active | archived)

Sage's card presents the agency baseline and the overlay side by side
(``lender_overlay`` layer: LOADED with the overlay records, or NOT_LOADED); the
agency baseline is never overwritten. Conflicts (overlay text contradicting
the agency rule on the same topic) are surfaced as a caution, not resolved.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .store import JsonDocStore, JsonlLog, new_id, now_iso

CONFIRMATION = ("unconfirmed", "confirmed", "disputed")
LIFECYCLE = ("proposed", "active", "archived")


class OverlayError(ValueError):
    pass


class OverlayStore:
    def __init__(self, root) -> None:
        self.docs = JsonDocStore(root / "knowledge" / "overlays")
        self.log = JsonlLog(root / "activity", "activity")

    def propose(self, *, program: str, lender: str, overlay_source: str, text: str, overlay_section: Optional[str] = None,
                agency_rule_ref: Optional[str] = None, effective_date: Optional[str] = None, expires: Optional[str] = None, product: Optional[str] = None,
                exception: bool = False, proposed_by: str = "unknown", ae_confirmation_status: str = "unconfirmed", confirmed_by: Optional[str] = None) -> Dict[str, Any]:
        if not str(overlay_source or "").strip():
            raise OverlayError("overlay_source (lender guide reference or approved AE guidance reference) is required; overlays are never inferred")
        if ae_confirmation_status not in CONFIRMATION:
            raise OverlayError(f"ae_confirmation_status must be one of {CONFIRMATION}")
        text = " ".join(str(text or "").split())
        if not text:
            raise OverlayError("overlay text is required")
        row = {
            "overlay_id": new_id("ovl"), "program": (program or "").lower(), "lender": lender, "product": product, "overlay_source": overlay_source,
            "overlay_section": overlay_section, "agency_rule_ref": agency_rule_ref, "text": text[:1500], "effective_date": effective_date, "expires": expires,
            "exception": bool(exception), "proposed_by": proposed_by, "approved_by": None, "ae_confirmation_status": ae_confirmation_status,
            "confirmed_by": confirmed_by, "lifecycle": "proposed", "created_at": now_iso(),
            "history": [{"at": now_iso(), "lifecycle": "proposed", "by": proposed_by}],
            "layer": "lender_overlay", "note": "layered on top of the agency baseline; the baseline is never overwritten",
        }
        self.docs.put(row["overlay_id"], row)
        self.log.append({"event": "overlay.proposed", "actor": proposed_by, "overlay_id": row["overlay_id"], "program": row["program"], "lender": lender})
        return row

    def activate(self, overlay_id: str, *, identity: Dict[str, Any]) -> Dict[str, Any]:
        row = self.docs.get(overlay_id)
        if row is None:
            raise OverlayError(f"unknown overlay {overlay_id}")
        if identity.get("identity_source") in (None, "model") or not identity.get("approved_by_user_id"):
            raise OverlayError("only a human administrator identity may activate an overlay")
        if row.get("ae_confirmation_status") != "confirmed":
            raise OverlayError("an overlay activates only after AE confirmation (ae_confirmation_status=confirmed)")
        row["lifecycle"] = "active"
        row["approved_by"] = identity
        row["history"].append({"at": now_iso(), "lifecycle": "active", "by": identity.get("approved_by_user_id")})
        self.docs.put(overlay_id, row)
        self.log.append({"event": "overlay.active", "actor": identity.get("approved_by_user_id"), "overlay_id": overlay_id})
        return row

    def archive(self, overlay_id: str, *, identity: Dict[str, Any]) -> Dict[str, Any]:
        row = self.docs.get(overlay_id)
        if row is None:
            raise OverlayError(f"unknown overlay {overlay_id}")
        row["lifecycle"] = "archived"
        row["history"].append({"at": now_iso(), "lifecycle": "archived", "by": identity.get("approved_by_user_id")})
        self.docs.put(overlay_id, row)
        return row

    def active_for(self, program: str, lender: Optional[str], *, product: Optional[str] = None, relevant_date: Optional[str] = None) -> List[Dict[str, Any]]:
        from .sources import _parse_date

        when = _parse_date(relevant_date)
        rows = []
        for row in self.docs.all():
            if row.get("lifecycle") != "active" or row.get("program") != (program or "").lower():
                continue
            if lender and str(row.get("lender") or "").lower() != str(lender).lower():
                continue
            if product and row.get("product") and str(row["product"]).lower() != str(product).lower():
                continue
            eff = _parse_date(row.get("effective_date"))
            if when and eff and eff > when:
                continue
            rows.append(row)
        return rows

    def all(self) -> List[Dict[str, Any]]:
        return list(self.docs.all())


def overlay_layer(rows: List[Dict[str, Any]], lender: Optional[str]) -> Dict[str, Any]:
    """The ``lender_overlay`` layer for a card."""
    if not rows:
        return {"lender": lender, "state": "NOT_LOADED", "note": "no approved overlay pack; 'none loaded' never means 'no overlays exist' — confirm with AE", "overlays": []}
    return {"lender": lender, "state": "LOADED", "note": "overlays are layered on top of the agency baseline (shown separately); AE-confirmed", "overlays": [
        {k: r.get(k) for k in ("overlay_id", "lender", "product", "overlay_source", "overlay_section", "agency_rule_ref", "text", "effective_date", "exception", "ae_confirmation_status", "confirmed_by")}
        for r in rows]}


def conflicts(rows: List[Dict[str, Any]], citations: List[Dict[str, Any]]) -> List[str]:
    """Overlay records that name an agency rule present in the citations are flagged for side-by-side review (never auto-resolved)."""
    cited = {c.get("rule_id"): c for c in citations}
    out = []
    for r in rows:
        ref = r.get("agency_rule_ref")
        if ref and ref in cited:
            kind = "relaxes" if r.get("exception") else "tightens"
            out.append(f"Overlay {r['overlay_id']} ({r.get('lender')}) {kind} agency rule {ref}: apply the stricter requirement unless the AE-confirmed exception governs; both are shown, neither is overwritten.")
    return out
