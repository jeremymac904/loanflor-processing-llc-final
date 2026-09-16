"""Human guidance capture — AE/UW clarifications become *proposed* knowledge, never rules.

Ashley: "AE confirmed Loan Factory requires X for this product." Flo/Sage
records a guidance item with an explicit scope and the communication it came
from. Scopes:

    loan_specific      applies to one Deal Room only (a file-specific condition)
    product_specific   candidate for one product/program
    lender_specific    candidate for one lender (overlay candidate)
    reusable_overlay   candidate reusable overlay (needs the overlay workflow)

Status starts at ``pending_review``. Only an administrator promotes an item
(``promoted``) — through ``scripts/flo/activate_sources.py --program overlays``
or the Knowledge Center — and promotion of a non-loan-specific item creates an
overlay record in ``overlays.py`` (never an agency rule). Until then the item
reaches Sage only for the workspace it was recorded on, in the
``file_condition`` layer, labelled as pending human review. A chat or e-mail
never becomes a global rule by itself.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .store import JsonDocStore, JsonlLog, new_id, now_iso

SCOPES = ("loan_specific", "product_specific", "lender_specific", "reusable_overlay")
STATUSES = ("pending_review", "promoted", "rejected", "expired")


class GuidanceError(ValueError):
    pass


class GuidanceStore:
    def __init__(self, root) -> None:
        self.docs = JsonDocStore(root / "knowledge" / "guidance")
        self.log = JsonlLog(root / "activity", "activity")

    def propose(self, *, text: str, scope: str, source_ref: str, recorded_by: str, workspace_id: Optional[str] = None,
                program: Optional[str] = None, product: Optional[str] = None, lender: Optional[str] = None,
                confirmed_by: Optional[str] = None, effective_date: Optional[str] = None) -> Dict[str, Any]:
        text = " ".join(str(text or "").split())
        if not text:
            raise GuidanceError("guidance text is required")
        if scope not in SCOPES:
            raise GuidanceError(f"scope must be one of {SCOPES}")
        if not str(source_ref or "").strip():
            raise GuidanceError("source_ref (communication reference: mail://, note://, call://…) is required")
        if scope == "loan_specific" and not workspace_id:
            raise GuidanceError("loan_specific guidance needs a workspace_id")
        item = {
            "guidance_id": new_id("guide"), "text": text[:1200], "scope": scope, "workspace_id": workspace_id, "program": (program or "").lower() or None,
            "product": product, "lender": lender, "source_ref": str(source_ref)[:300], "confirmed_by": confirmed_by, "effective_date": effective_date,
            "recorded_by": recorded_by, "status": "pending_review", "global": False, "created_at": now_iso(),
            "history": [{"at": now_iso(), "status": "pending_review", "by": recorded_by}],
            "note": "proposed knowledge from a communication; not a rule until an administrator promotes it, and never a global rule from chat alone",
        }
        self.docs.put(item["guidance_id"], item)
        self.log.append({"event": "guidance.proposed", "actor": recorded_by, "guidance_id": item["guidance_id"], "scope": scope, "workspace_id": workspace_id})
        return item

    def decide(self, guidance_id: str, *, status: str, identity: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
        """Administrator decision. ``identity`` is an identity.approval_record-style dict (structured, no e-mail needed)."""
        if status not in ("promoted", "rejected", "expired"):
            raise GuidanceError("status must be promoted | rejected | expired")
        item = self.docs.get(guidance_id)
        if item is None:
            raise GuidanceError(f"unknown guidance {guidance_id}")
        if item.get("status") != "pending_review":
            raise GuidanceError(f"guidance is {item.get('status')}, not pending_review")
        if identity.get("identity_source") in (None, "model") or not identity.get("approved_by_user_id"):
            raise GuidanceError("only a human administrator identity may promote or reject guidance")
        item["status"] = status
        item["decision"] = {**identity, "reason": reason, "at": now_iso()}
        item["history"].append({"at": now_iso(), "status": status, "by": identity.get("approved_by_user_id")})
        overlay = None
        if status == "promoted" and item["scope"] != "loan_specific":
            from . import overlays as overlays_mod

            overlay = overlays_mod.OverlayStore(self.docs.directory.parent.parent).propose(
                program=item.get("program") or "unknown", lender=item.get("lender") or "unknown", overlay_source=f"guidance:{guidance_id} ({item['source_ref']})",
                overlay_section=None, text=item["text"], effective_date=item.get("effective_date"), product=item.get("product"), exception=False,
                proposed_by=identity.get("approved_by_user_id"), ae_confirmation_status="confirmed" if item.get("confirmed_by") else "unconfirmed",
                confirmed_by=item.get("confirmed_by"))
            item["overlay_id"] = overlay["overlay_id"]
        self.docs.put(guidance_id, item)
        self.log.append({"event": f"guidance.{status}", "actor": identity.get("approved_by_user_id"), "guidance_id": guidance_id, "overlay_id": item.get("overlay_id")})
        return item

    def for_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Items Sage may show for one Deal Room: loan-specific items for that room (pending or promoted), labelled."""
        rows = []
        for item in self.docs.all():
            if item.get("workspace_id") == workspace_id and item.get("status") in ("pending_review", "promoted"):
                rows.append({"guidance_id": item["guidance_id"], "text": item["text"], "scope": item["scope"], "status": item["status"],
                             "source_ref": item["source_ref"], "layer": "file_condition", "label": f"AE/UW guidance ({item['status']}, {item['scope']})"})
        return rows

    def pending(self) -> List[Dict[str, Any]]:
        return [i for i in self.docs.all() if i.get("status") == "pending_review"]
