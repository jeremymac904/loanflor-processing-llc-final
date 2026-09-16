"""Franklin's Marketing Content Factory — structurally separate from borrower data.

Content items (social, newsletter, gbp, blog, campaign) move ``idea`` →
``draft`` → ``review`` → ``approved`` → ``published`` (published only with an
execution_ref from the publishing tool). Every draft is scanned for claims
that need an approved source or disclosure (rates, APR, savings, guarantees,
licensing, eligibility promises, testimonials) and for NPI shapes; flagged
items cannot move past ``review`` until the flags carry a source id.

Marketing sources come from the pack's ``marketing_sources.yaml``
(platform/HUD policies) — company brand guide, disclosures, licensing display
rules etc. are ``required_future_sources`` (SOURCE_GAP).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .store import JsonDocStore, new_id, now_iso

CHANNELS = ("social", "newsletter", "gbp", "blog", "campaign")
STAGES = ("idea", "draft", "review", "approved", "published", "archived")
_NEXT = {
    "idea": {"draft", "archived"}, "draft": {"review", "archived"}, "review": {"approved", "draft", "archived"},
    "approved": {"published", "draft", "archived"}, "published": {"archived"}, "archived": set(),
}
CLAIM_PATTERNS = {
    "rate_or_apr": re.compile(r"\b(\d+(\.\d+)?\s?%|apr|interest rate|rates? (as low as|starting at|from))\b", re.I),
    "savings_or_guarantee": re.compile(r"\b(save|savings|guarantee[ds]?|lowest|best rate|no closing costs?|free)\b", re.I),
    "eligibility_promise": re.compile(r"\b(you (will|'ll) (qualify|be approved)|approved in|guaranteed approval|everyone qualifies|no credit check)\b", re.I),
    "licensing": re.compile(r"\b(nmls|license[d]?|licensing|equal housing)\b", re.I),
    "testimonial": re.compile(r"\b(testimonial|review from|client story|our client|borrower said)\b", re.I),
    "program_claim": re.compile(r"\b(fha|va|usda|conventional|jumbo|non-qm|dscr|bank statement loan)\b", re.I),
}
_NPI = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9,}\b")
_LOAN_REF = re.compile(r"\b(loan_[a-f0-9]{6,}|doc://|mail://|drive://)", re.I)


class MarketingError(ValueError):
    pass


def scan(text: str) -> List[Dict[str, Any]]:
    flags = []
    for kind, pattern in CLAIM_PATTERNS.items():
        match = pattern.search(text or "")
        if match:
            flags.append({"kind": kind, "excerpt": match.group(0)[:80], "requires": "approved source/disclosure id before publishing", "source_id": None})
    if _NPI.search(text or "") or _LOAN_REF.search(text or ""):
        flags.append({"kind": "npi_or_loan_reference", "excerpt": "[redacted]", "requires": "remove: marketing content never carries borrower data or loan references", "source_id": None, "blocking": True})
    return flags


class ContentFactory:
    def __init__(self, root) -> None:
        self.docs = JsonDocStore(root / "marketing")

    def create(self, *, channel: str, title: str, body: str = "", pillar: Optional[str] = None,
               scheduled_for: Optional[str] = None, agent: str = "franklin") -> Dict[str, Any]:
        channel = (channel or "").lower()
        if channel not in CHANNELS:
            raise MarketingError(f"channel must be one of {CHANNELS}")
        title = " ".join(str(title or "").split())
        if not title:
            raise MarketingError("title is required")
        # Idempotency: the same channel + normalized title while an item is still unpublished is one item.
        from . import intents as intents_mod

        intent = intents_mod.intent_id(kind="marketing_content", workspace_id=None, target=channel, purpose="content",
                                       material={"channel": channel, "title": intents_mod.normalize_text(title), "scheduled_for": intents_mod.normalize_text(scheduled_for)})
        for existing in self.docs.all():
            if existing.get("intent_id") == intent and existing.get("stage") not in ("published", "archived"):
                return {**existing, "deduplicated": True, "decision": "return_existing"}
        flags = scan(f"{title}\n{body}")
        item = {
            "content_id": new_id("content"), "intent_id": intent, "channel": channel, "title": title[:200], "body": str(body or "")[:8000],
            "pillar": pillar, "scheduled_for": scheduled_for, "stage": "draft" if body else "idea",
            "flags": flags, "approval_required": True, "proposal_id": None, "execution_ref": None,
            "performance_notes": [], "created_by": agent, "created_at": now_iso(),
            "history": [{"at": now_iso(), "stage": "draft" if body else "idea", "by": agent}],
        }
        self.docs.put(item["content_id"], item)
        return item

    def advance(self, content_id: str, stage: str, *, by: str, proposal_id: Optional[str] = None,
                execution_ref: Optional[str] = None, source_ids: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        item = self.docs.get(content_id)
        if item is None:
            raise MarketingError(f"unknown content {content_id}")
        current = item.get("stage", "idea")
        if stage not in STAGES or stage not in _NEXT.get(current, set()):
            raise MarketingError(f"cannot move content from {current} to {stage}")
        for flag in item.get("flags", []):
            if source_ids and flag["kind"] in source_ids:
                flag["source_id"] = source_ids[flag["kind"]]
        if stage in ("approved", "published"):
            unresolved = [f for f in item.get("flags", []) if not f.get("source_id")]
            if unresolved:
                raise MarketingError("unresolved compliance/source flags: " + ", ".join(f["kind"] for f in unresolved))
        if stage == "approved" and not proposal_id:
            raise MarketingError("approved requires the Approval Center proposal_id (Ashley's decision)")
        if stage == "published" and not execution_ref:
            raise MarketingError("published requires an execution_ref from the publishing tool; drafting is not publishing")
        item["stage"] = stage
        if proposal_id:
            item["proposal_id"] = proposal_id
        if execution_ref:
            item["execution_ref"] = execution_ref
        item.setdefault("history", []).append({"at": now_iso(), "stage": stage, "by": by})
        self.docs.put(content_id, item)
        return item

    def calendar(self) -> Dict[str, List[Dict[str, Any]]]:
        out: Dict[str, List[Dict[str, Any]]] = {c: [] for c in CHANNELS}
        for item in self.docs.all():
            out.setdefault(item.get("channel", "social"), []).append(
                {k: item.get(k) for k in ("content_id", "title", "stage", "pillar", "scheduled_for", "flags")})
        return out
