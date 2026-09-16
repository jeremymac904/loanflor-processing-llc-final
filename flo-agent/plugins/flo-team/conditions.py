"""Conditions auto-clear.

When a new document arrives in a workspace, the existing open conditions on
that workspace are evaluated. High-confidence matches clear the condition;
ambiguous matches mark it ``needs_review`` so a human decides; everything
else is left alone.

Why a separate module: keeping the matching rules here means the desktop
screens and the backend ``documents.ingest()``/``add_local()`` paths agree,
and the rules can be exercised directly from tests with synthetic data.

Conservative on purpose. Per project rules:

    Conditions that require underwriting judgment, explanation sufficiency,
    source-of-funds analysis, guideline interpretation, lender acceptance,
    appraisal review, or legal/title judgment do not auto-clear.

Confidence model
----------------

    high    category matches AND subcategory matches AND (borrower_ref matches
            OR condition has no borrower) AND period/page checks satisfied
            -> clear

    medium  category matches AND subcategory matches BUT borrower_ref differs
            OR period is ambiguous / missing
            -> needs_review

    low     only category matches, no subcategory alignment
            -> leave open (the document might be unrelated)

    skip    condition flags ``judgment_required`` (true for LOE, source-of-funds,
            appraisal review, etc.)
            -> leave open

How a document is matched
-------------------------

Documents expose:
    category           e.g. ``income``
    subcategory        e.g. ``paystub``
    borrower_ref       ``borrower`` / ``co_borrower`` / ``both`` / None
    status             ``received`` / ``missing_pages`` / ``needs_review`` ...
    pages (checks)     dict with ``expected`` and ``missing`` from text layer
    statement_period   parsed from text when available (or None)

Conditions expose whatever structure the creator wrote. The matcher reads:
    category           ``income`` / ``assets`` / ``insurance`` (from ``category``
                       field, or inferred from text)
    kind               ``paystub`` / ``w2`` / ``bank_statement`` /
                       ``insurance_declaration`` / ... (from ``kind`` or
                       ``subcategory`` field, or text)
    borrower_ref       when set on the condition
    statement_period   when set on the condition
    page_requirement   ``int`` or ``list[int]`` of page numbers required
    judgment_required  bool, defaults to True if ``kind`` is in the explicit
                       blocklist (LOE, source-of-funds, appraisal, etc.)
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .documents import SUBTYPES


# Conditions of these kinds require human judgment — never auto-clear.
JUDGMENT_KINDS = frozenset({
    "letter_of_explanation",
    "source_of_funds",
    "gift_letter",
    "appraisal_review",
    "title_judgment",
    "title_curative",
    "underwriting_decision",
    "guideline_interpretation",
    "lender_acceptance",
    "explanation",
    "amendatory",
    "8102",
})


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _borrower_match(cond_ref: Optional[str], doc_ref: Optional[str]) -> bool:
    """True when the condition's borrower constraint is satisfied by the doc."""
    cond_ref = _norm(cond_ref)
    doc_ref = _norm(doc_ref)
    if not cond_ref or cond_ref in {"both", "any", "joint", "either"}:
        return True  # condition doesn't pin a specific borrower
    if not doc_ref:
        return False  # condition pinned to a borrower, doc unattributed
    if cond_ref == doc_ref:
        return True
    if cond_ref in {"borrower1", "borrower"} and doc_ref in {"borrower", "borrower1"}:
        return True
    if cond_ref in {"co_borrower", "borrower2"} and doc_ref in {"co_borrower", "borrower2"}:
        return True
    return False


def _category_for_kind(kind: str) -> Optional[str]:
    """Map a doc subcategory/kind to its parent document category."""
    if not kind:
        return None
    for cat, kinds in SUBTYPES.items():
        if kind in kinds:
            return cat
    # Direct category strings pass through.
    if kind in {"loan_application", "credit_report", "aus_findings", "income",
                "assets", "purchase_contract", "title_property", "insurance",
                "identification"}:
        return kind
    return None


def _category_for_text(text: str) -> Optional[str]:
    """Infer a category from the free-text of a condition when its structured
    fields are blank. Returns the first category whose keywords match the text;
    ``None`` when nothing aligns."""
    t = _norm(text)
    if not t:
        return None
    # order matters: more specific patterns first
    category_keywords = (
        ("insurance", ("insurance", "hoi", "homeowners", "hazard", "dwelling", "policy declarations")),
        ("assets", ("bank statement", "statements", "checking", "savings", "asset", "retirement", "401k", "ira",
                    "gift letter", "gift funds", "source of funds", "source-of-funds")),
        ("income", ("paystub", "pay stub", "earnings statement", "w-2", "w2", "wage and tax",
                    "1099", "tax return", "1040", "4506", "profit and loss", "k-1", "k1",
                    "letter of explanation", "letter of explanations")),
        ("aus_findings", ("du findings", "lp findings", "aus findings", "desktop underwriter", "loan product advisor")),
        ("credit_report", ("credit report", "tri-merge", "tri merge", "credit pull")),
        ("purchase_contract", ("purchase contract", "sales contract", "purchase agreement")),
        ("title_property", ("title commitment", "title policy", "preliminary title")),
        ("identification", ("driver", "drivers license", "passport", "id card")),
        ("loan_application", ("1003", "urla", "loan application")),
    )
    for cat, kws in category_keywords:
        if any(kw in t for kw in kws):
            return cat
    return None


def _looks_like_kind(text: str, kind: str) -> bool:
    """Heuristic fallback: does the condition text talk about a doc kind?"""
    t = _norm(text)
    if not t:
        return False
    synonyms = {
        "paystub": ("paystub", "pay stub", "pay-stub", "earnings statement", "recent pay"),
        "w2": ("w-2", "w2", "wage and tax"),
        "1099": ("1099", "misc income"),
        "tax_return": ("tax return", "1040", "4506"),
        "profit_and_loss": ("profit and loss", "p&l", "p & l"),
        "k1": ("k-1", "k1", "schedule k"),
        "bank_statement": ("bank statement", "bank statements", "account statement", "checking statement", "savings statement"),
        "retirement_statement": ("retirement", "401k", "ira statement", "vanguard", "fidelity"),
        "gift_documentation": ("gift letter", "gift funds", "gift documentation"),
        "insurance_declaration": ("insurance dec", "hoi dec", "homeowners insurance", "hazard insurance", "policy declarations", "dwelling coverage"),
        "loan_application": ("1003", "loan application", "urla"),
        "credit_report": ("credit report", "tri-merge", "tri merge"),
        "aus_findings": ("du findings", "lp findings", "aus findings", "desktop underwriter"),
        "purchase_contract": ("purchase contract", "sales contract", "purchase agreement"),
        "title_property": ("title commitment", "title policy", "preliminary title"),
        "identification": ("driver", "drivers license", "passport", "id card"),
    }
    for needle in synonyms.get(kind, (kind.replace("_", " "),)):
        if needle in t:
            return True
    return False


def _extract_period(text: str) -> Optional[Tuple[date, date]]:
    """Pull a (start, end) date range from a condition's or document's free text.

    Supports patterns like "for 2025", "2024-2025", "covering 03/2024 through
    02/2025", and bare 4-digit years embedded in filenames or notes
    (``stmt_2025_03.pdf``). Conservative — returns None rather than guess
    when no year marker can be found.

    Note: Python's ``\\b`` treats ``_`` as a word character, so patterns that
    rely on ``\\b`` would miss a year embedded in a snake_case filename.
    Filename-friendly matches don't use ``\\b``; sentence-friendly matches do.
    """
    t = _norm(text)
    # "covering 03/2024 through 02/2025" (explicit month range, prefer it)
    m = re.search(r"\b(\d{1,2})/(\d{4})\s*(?:through|to|thru|-)\s*(\d{1,2})/(\d{4})\b", t)
    if m:
        m1, y1, m2, y2 = (int(x) for x in m.groups())
        try:
            return date(y1, m1, 1), date(y2, m2, 1)
        except ValueError:
            return None
    # "2024-2025" / "2024 - 2025" (year range, sentence-friendly)
    m = re.search(r"\b(20\d{2})\s*[-–]\s*(20\d{2})\b", t)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        return date(y1, 1, 1), date(y2, 12, 31)
    # "for 2025" / "in 2025" / "for tax year 2025" (sentence-friendly)
    m = re.search(r"\b(?:for|in|tax year|year of)\s+(20\d{2})\b", t)
    if m:
        y = int(m.group(1))
        return date(y, 1, 1), date(y, 12, 31)
    # Bare 4-digit year — filename-friendly (no \b because _ is a word char).
    m = re.findall(r"(?<!\d)(20\d{2})(?!\d)", t)
    if m:
        y = int(m[-1])
        return date(y, 1, 1), date(y, 12, 31)
    return None


def _doc_period(document: Dict[str, Any]) -> Optional[Tuple[date, date]]:
    """Pull a date range from a doc's text, filename, or notes."""
    haystack = " ".join(filter(None, [
        str(document.get("display_name") or ""),
        str(document.get("original_filename") or ""),
        str(document.get("notes") or ""),
    ]))
    period = _extract_period(haystack)
    if period:
        return period
    text = ""
    text_path = document.get("text_path")
    if text_path:
        try:
            from pathlib import Path
            text = Path(text_path).read_text(encoding="utf-8", errors="ignore")[:4000]
        except OSError:
            text = ""
    return _extract_period(text)


def _periods_overlap(a: Optional[Tuple[date, date]], b: Optional[Tuple[date, date]]) -> Optional[bool]:
    """None = unknown (don't punish); True = overlap; False = disjoint."""
    if not a or not b:
        return None
    return not (a[1] < b[0] or b[1] < a[0])


def _required_pages(condition: Dict[str, Any]) -> Optional[List[int]]:
    """Pull 'page N' / 'pages N, M' out of the condition text."""
    raw = condition.get("text") or condition.get("description") or ""
    text = _norm(" ".join(str(raw).split()))
    if not text:
        return None
    m = re.findall(r"page(?:s)?\s+(\d+(?:\s*,\s*\d+)*)", text)
    if not m:
        return None
    out: List[int] = []
    for group in m:
        for tok in group.split(","):
            tok = tok.strip()
            if tok.isdigit():
                out.append(int(tok))
    return sorted(set(out)) or None


def _missing_pages(document: Dict[str, Any]) -> List[int]:
    pages = (document.get("checks") or {}).get("pages") or {}
    return list(pages.get("missing") or [])


def _category_match(cond_cat: Optional[str], doc_cat: Optional[str]) -> bool:
    if not cond_cat or not doc_cat:
        return False
    return _norm(cond_cat) == _norm(doc_cat)


def _kind_match(cond_kind: Optional[str], doc_kind: Optional[str], cond_text: str, doc: Optional[Dict[str, Any]] = None) -> bool:
    """True when the condition's kind aligns with the document's kind.

    Fallback paths (in priority order):

      1. both kinds are set and equal
      2. condition has no kind but the document's kind matches a name in the
         condition text (e.g. condition text says "the bank statement is missing"
         and the doc is a ``bank_statement``)
      3. condition has a kind but the doc has no subcategory — accept if the
         doc's filename or text-sidecar looks like that kind
    """
    cond_kind = _norm(cond_kind)
    doc_kind = _norm(doc_kind)
    if cond_kind and doc_kind and cond_kind == doc_kind:
        return True
    if not cond_kind and doc_kind and _looks_like_kind(cond_text, doc_kind):
        return True
    if cond_kind and not doc_kind and doc is not None:
        # Doc is uncategorised. Look for the kind's vocabulary in the doc.
        haystack = " ".join(filter(None, [
            str(doc.get("display_name") or ""),
            str(doc.get("original_filename") or ""),
            str(doc.get("notes") or ""),
        ]))
        return _looks_like_kind(haystack, cond_kind) or _looks_like_kind(cond_text, cond_kind) and _looks_like_kind(doc.get("text_path", "") or "", cond_kind)
    return False


def _judgment_required(condition: Dict[str, Any]) -> bool:
    """Conditions that need a human are explicitly tagged or carry a
    judgment-required kind."""
    if condition.get("judgment_required") is True:
        return True
    kind = _norm(condition.get("kind") or condition.get("subcategory"))
    if kind in JUDGMENT_KINDS:
        return True
    text = _norm(condition.get("text") or condition.get("description") or "")
    # Specific phrases that always mean a human has to decide.
    judgment_phrases = (
        "letter of explanation",
        "source of funds",
        "source-of-funds",
        "gift letter",
        "gift funds",
        "large deposit",
        "appraisal",
        "title curative",
        "title judgment",
        "underwriting decision",
        "underwriter review",
        "lender acceptance",
        "guideline interpretation",
        "8102",
        "amendatory",
    )
    if any(phrase in text for phrase in judgment_phrases):
        return True
    return False


def _kind_for_text(text: str) -> Optional[str]:
    """Infer a doc kind from the condition text by walking the kind synonym table."""
    for kind in (
        "paystub", "w2", "1099", "tax_return", "profit_and_loss", "k1",
        "bank_statement", "retirement_statement", "gift_documentation",
        "insurance_declaration",
        "loan_application", "credit_report", "aus_findings",
        "purchase_contract", "title_property", "identification",
    ):
        if _looks_like_kind(text, kind):
            return kind
    return None


def _condition_payload(condition: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a condition dict into the fields the matcher consumes."""
    text = str(condition.get("text") or condition.get("description") or condition.get("title") or "")
    explicit_kind = condition.get("kind") or condition.get("subcategory")
    inferred_kind = explicit_kind or _kind_for_text(text)
    inferred_category = (
        condition.get("category")
        or _category_for_kind(_norm(inferred_kind))
        or _category_for_text(text)
    )
    return {
        "id": condition.get("id"),
        "text": text,
        "category": inferred_category,
        "kind": inferred_kind,
        "borrower_ref": condition.get("borrower_ref"),
        "period": _extract_period(text) if text else condition.get("period"),
        "page_requirement": _required_pages(condition),
        "judgment_required": _judgment_required(condition),
    }


def _doc_payload(document: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "document_id": document.get("document_id"),
        "category": document.get("category"),
        "subcategory": document.get("subcategory"),
        "borrower_ref": document.get("borrower_ref"),
        "status": document.get("status"),
        "page_count": document.get("page_count"),
        "missing_pages": _missing_pages(document),
        "period": _doc_period(document),
    }


def _evaluate_one(condition_payload: Dict[str, Any], document: Dict[str, Any]) -> Tuple[str, str]:
    """Return (decision, reason) for one condition/document pair.

    decision ∈ {"clear", "needs_review", "skip"}
    """
    document_payload = _doc_payload(document)
    if condition_payload["judgment_required"]:
        return "skip", "condition requires underwriting or legal judgment"

    cond_cat = condition_payload["category"]
    doc_cat = document_payload["category"]
    cond_kind = condition_payload["kind"]
    doc_kind = document_payload["subcategory"]

    if not _category_match(cond_cat, doc_cat):
        return "skip", f"category mismatch (condition {cond_cat}, document {doc_cat})"

    kind_ok = _kind_match(cond_kind, doc_kind, condition_payload["text"], doc=document)
    if not kind_ok:
        # Low confidence — leave open. The document might be unrelated.
        return "skip", "subcategory / kind does not align"

    if not _borrower_match(condition_payload["borrower_ref"], document_payload["borrower_ref"]):
        return "needs_review", (
            f"borrower mismatch: condition expects {condition_payload['borrower_ref']!r}, "
            f"document is {document_payload['borrower_ref']!r}"
        )

    if document_payload["status"] in {"missing_pages", "unreadable", "needs_review"}:
        # Don't try to satisfy a pages-required condition with a doc that's still missing pages.
        if condition_payload["page_requirement"]:
            missing = set(document_payload["missing_pages"])
            still_missing = [p for p in condition_payload["page_requirement"] if p in missing]
            if still_missing:
                return "needs_review", f"document still missing pages {still_missing}"
        if document_payload["status"] == "unreadable":
            return "needs_review", "document is unreadable; needs human review"

    if condition_payload["page_requirement"]:
        missing = set(document_payload["missing_pages"])
        if missing and any(p in missing for p in condition_payload["page_requirement"]):
            return "needs_review", f"required page(s) still missing: {condition_payload['page_requirement']}"

    # Period matching only applies to kinds that carry a date range. W-2, 1099,
    # tax returns, K-1s, loan applications, credit reports, AUS findings,
    # gift letters, and IDs are intrinsic-period (the year is *part of* the
    # doc, not a window the doc covers); skip the overlap check for them.
    PERIOD_CHECK_KINDS = {
        "paystub", "bank_statement", "retirement_statement",
        "profit_and_loss", "insurance_declaration",
    }
    check_period = (
        _norm(condition_payload["kind"]) in PERIOD_CHECK_KINDS
        or _norm(document_payload["subcategory"]) in PERIOD_CHECK_KINDS
    )
    if check_period:
        overlap = _periods_overlap(condition_payload["period"], document_payload["period"])
        if overlap is False:
            return "needs_review", "document's period does not overlap the requested period"
        if condition_payload["period"] and overlap is None and document_payload["period"] is None:
            # Condition asks for a specific period but the doc doesn't expose one.
            return "needs_review", "document doesn't expose a statement period; verify period manually"

    return "clear", "category, kind, borrower, and period all match"


def evaluate_document_for_conditions(
    conditions: Iterable[Dict[str, Any]],
    document: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Decide what happens to each open condition when a document arrives.

    Returns a list of decisions, one per non-cleared condition::

        [{"condition_id": "cond_abc", "decision": "clear"|"needs_review"|"skip",
          "reason": "..."}]

    The caller (``documents.ingest`` / ``add_local`` / the website intake
    flow) is responsible for applying the decisions to the workspace.
    """
    doc_payload = _doc_payload(document)
    out: List[Dict[str, Any]] = []
    for condition in conditions or []:
        if not isinstance(condition, dict):
            continue
        state = _norm(condition.get("state") or "open")
        if state == "cleared":
            continue  # already cleared — leave it alone (the duplicate-doc rule)
        payload = _condition_payload(condition)
        decision, reason = _evaluate_one(payload, document)
        out.append({
            "condition_id": payload["id"],
            "decision": decision,
            "reason": reason,
            "document_id": doc_payload["document_id"],
        })
    return out


def apply_decisions(workspace_doc: Dict[str, Any], decisions: List[Dict[str, Any]],
                    *, actor: str = "malcolm") -> List[Dict[str, Any]]:
    """Apply decisions to the workspace's conditions list. Returns a summary.

    The shape of a cleared condition::

        {"...existing fields...", "state": "cleared",
         "cleared_at": <iso>, "cleared_by": "malcolm",
         "cleared_by_document_id": <doc id>, "cleared_reason": "..."}

    A condition in ``needs_review`` keeps ``state == "open"`` but gets::

        {"...existing fields...", "needs_review": True,
         "needs_review_reason": "...", "needs_review_at": <iso>}
    """
    by_id = {str(d.get("condition_id")): d for d in decisions if d.get("decision") in {"clear", "needs_review"}}
    applied: List[Dict[str, Any]] = []
    for cond in workspace_doc.get("conditions") or []:
        if not isinstance(cond, dict):
            continue
        cid = str(cond.get("id"))
        dec = by_id.get(cid)
        if not dec:
            continue
        if dec["decision"] == "clear" and _norm(cond.get("state") or "open") != "cleared":
            cond["state"] = "cleared"
            cond["cleared_at"] = datetime.utcnow().isoformat() + "Z"
            cond["cleared_by"] = actor
            cond["cleared_by_document_id"] = dec.get("document_id")
            cond["cleared_reason"] = dec.get("reason")
            cond.pop("needs_review", None)
            cond.pop("needs_review_reason", None)
            cond.pop("needs_review_at", None)
            applied.append({"condition_id": cid, "decision": "clear", "reason": dec["reason"]})
        elif dec["decision"] == "needs_review":
            cond["needs_review"] = True
            cond["needs_review_reason"] = dec.get("reason")
            cond["needs_review_at"] = datetime.utcnow().isoformat() + "Z"
            applied.append({"condition_id": cid, "decision": "needs_review", "reason": dec["reason"]})
    return applied


def recompute_next_action(workspace_doc: Dict[str, Any], applied: List[Dict[str, Any]]) -> Optional[str]:
    """Update ``workspace_doc["next_action"]`` so Today/Pipeline reflects the change.

    Called after ``apply_decisions`` when at least one decision changed state.
    Conservative: only touches the ``next_action`` string. The cached
    ``readiness.best_next_move`` is intentionally left alone — Malcolm's
    next call recomputes it through the normal path.
    """
    if not applied:
        return None
    cleared = sum(1 for a in applied if a["decision"] == "clear")
    review = sum(1 for a in applied if a["decision"] == "needs_review")
    if not cleared and not review:
        return None
    open_remaining = [
        c for c in (workspace_doc.get("conditions") or [])
        if isinstance(c, dict) and _norm(c.get("state") or "open") != "cleared"
    ]
    needs_review_count = sum(1 for c in open_remaining if c.get("needs_review"))
    fresh_open = len(open_remaining) - needs_review_count

    bits = []
    if cleared == 1:
        bits.append(f"Cleared 1 condition")
    elif cleared > 1:
        bits.append(f"Cleared {cleared} conditions")
    if review == 1:
        bits.append("1 needs your review")
    elif review > 1:
        bits.append(f"{review} need your review")
    if not bits:
        return None
    summary = "; ".join(bits)
    if fresh_open == 0 and needs_review_count == 0:
        summary += ". Nothing left to clear here."
    elif fresh_open == 0 and needs_review_count == 1:
        summary += ". 1 still needs your review."
    elif fresh_open == 0:
        summary += f". {needs_review_count} still need your review."
    elif fresh_open == 1:
        summary += ". 1 still open."
    else:
        summary += f". {fresh_open} still open."
    workspace_doc["next_action"] = summary
    return summary
