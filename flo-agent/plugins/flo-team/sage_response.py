"""Source-bound response architecture for Sage.

    source retrieval → deterministic normalized rule object (cards, calc traces,
    AUS envelope, overlays, file conditions, guidance) → validated Guideline Card
    → allowed factual claims → model presentation layer → post-generation validator

:func:`build` folds everything Sage retrieved into one ``SourceBoundResponse``:

    {
      "supported_claims": [...],      # rule texts from applicable, ACTIVE citations (+ overlay / condition / guidance claims)
      "calculation_results": [...],   # calc traces (formula, inputs, result)
      "source_refs": [...],           # section, version, effective date, revision, URL
      "warnings": [...],              # cautions the card carries (FUTURE, overlay not loaded, …)
      "source_gaps": [...],           # SOURCE_GAP conclusions / pending sections
      "allowed_facts": {...}          # the numeric/period vocabulary the prose may use
    }

:func:`render` is the deterministic presentation the model may polish.
:func:`validate` checks generated prose: every *material underwriting
assertion* (percentages, dollar amounts, counts of months/years/days/
statements/pages/points, ratio pairs such as 31/43, and modal rule sentences
"must / required / not permitted / not recognized …") must be traceable to a
supported claim, a calculation result, the AUS envelope, an overlay, a
file-specific condition or a recorded guidance item. Ordinary conversational
glue is ignored. :func:`rewrite` drops the unsupported sentences and says so.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .store import JsonDocStore, new_id, now_iso

RESPONSE_VERSION = "1"

_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_PERCENT = re.compile(rf"({_NUM})\s?(?:%|percent(?:age)?\b)", re.I)
_DOLLAR = re.compile(rf"\$\s?({_NUM})|({_NUM})\s?(?:dollars|usd)\b", re.I)
_PERIOD = re.compile(rf"({_NUM}|one|two|three|four|five|six|seven|eight|nine|ten|twelve|twenty-four)[- ]?(?:calendar |business |consecutive |full |monthly |bank )?"
                     r"(months?|years?|days?|weeks?|statements?|pages?|percentage points?|points?|pay ?stubs?|pay periods?)\b", re.I)
# Ratio pairs such as 31/43 or 41/45; calendar dates (11/26/2025, 04/10/2025) are not ratios.
_RATIO_PAIR = re.compile(r"(?<![\d/])\b(\d{2})\s?/\s?(\d{2})\b(?!\s?/\s?\d)")
_MODAL = re.compile(r"\b(must|required|requires|requirement|shall|may not|cannot|can't|not permitted|not allowed|not recognized|not eligible|ineligible|prohibited|only if|at least|no more than|no later than|maximum|minimum)\b", re.I)
_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10", "twelve": "12", "twenty-four": "24"}
_STOP = set("the a an and or of to in for on with by is are be as at from that this these those it its their there which when while than then into over under not no any all each per".split())
# Sentence-level glue that is never a rule assertion.
_GLUE = re.compile(r"^(hi|hello|thanks?|thank you|ash|ashley|okay|ok|sure|here is|here's|summary|conclusion|next|note)\b", re.I)


def _norm_num(text: str) -> str:
    text = _WORDS.get(text.lower(), text)
    text = text.replace(",", "")
    try:
        d = Decimal(text)
    except InvalidOperation:
        return text.lower()
    return format(d.normalize(), "f")


def _numbers_in(text: str) -> Set[str]:
    out: Set[str] = set()
    for m in re.finditer(_NUM, text or ""):
        out.add(_norm_num(m.group(0)))
    for word in _WORDS:
        if re.search(rf"\b{word}\b", text or "", re.I):
            out.add(_WORDS[word])
    return out


def _content_words(text: str) -> Set[str]:
    return {w for w in re.findall(r"[a-z][a-z\-]{2,}", (text or "").lower()) if w not in _STOP}


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+|(?<=;)\s+", text or "")
    return [p.strip(" -•*\t") for p in parts if p and p.strip(" -•*\t")]


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def build(
    *,
    cards: Optional[List[Dict[str, Any]]] = None,
    calculations: Optional[List[Dict[str, Any]]] = None,
    aus_envelope: Optional[Dict[str, Any]] = None,
    overlays: Optional[List[Dict[str, Any]]] = None,
    file_conditions: Optional[List[str]] = None,
    guidance_items: Optional[List[Dict[str, Any]]] = None,
    workspace_id: Optional[str] = None,
    program: Optional[str] = None,
) -> Dict[str, Any]:
    """Fold retrieved objects into the source-bound structure. Nothing here consults a model."""
    claims: List[Dict[str, Any]] = []
    refs: List[Dict[str, Any]] = []
    warnings: List[str] = []
    gaps: List[str] = []
    allowed_text: List[str] = []
    for card in cards or []:
        for c in card.get("citations", []):
            if c.get("usable") and c.get("resolution") in (None, "CURRENT", "EARLY_IMPLEMENTATION"):
                claims.append({"kind": "rule", "text": c["rule"], "ref": c.get("rule_id"), "section": c.get("section"), "version": c.get("version"),
                               "effective": c.get("effective"), "resolution": c.get("resolution_label") or "CURRENT"})
                allowed_text.append(c["rule"])
            elif c.get("resolution") == "FUTURE":
                warnings.append(f"FUTURE — NOT YET EFFECTIVE: {c.get('section')} effective {c.get('effective')}: {c['rule']}")
                allowed_text.append(c["rule"])  # quotable only as a labelled future rule; the caution text carries it
            refs.append({k: c.get(k) for k in ("section", "section_number", "version", "effective", "revision_id", "official_url", "resolution_label", "lifecycle", "usable")})
        for c in (card.get("details") or {}).get("future_citations", []):
            refs.append({k: c.get(k) for k in ("section", "section_number", "version", "effective", "revision_id", "official_url", "resolution_label", "lifecycle", "usable")})
            warnings.append(f"FUTURE — NOT YET EFFECTIVE: {c.get('section')} effective {c.get('effective')}: {c['rule']}")
            allowed_text.append(c["rule"])
        for w in card.get("conflict_or_caution", []):
            if w not in warnings:
                warnings.append(w)
        if card.get("conclusion") == "SOURCE_GAP" or card.get("guideline_supported_conclusion") == "SOURCE_GAP":
            gaps.append(f"{card.get('topic')}: SOURCE_GAP ({card.get('confidence')})")
        for p in (card.get("details") or {}).get("pending_revisions", []):
            gaps.append(f"{p.get('section')} is {p.get('lifecycle')} ({p.get('reason')})")
        for m in card.get("missing_documentation", []) or []:
            claims.append({"kind": "missing_documentation", "text": str(m), "ref": "card"})
            allowed_text.append(str(m))
    calc_rows: List[Dict[str, Any]] = []
    for t in calculations or []:
        if not isinstance(t, dict):
            continue
        row = {"calc_id": t.get("calc_id"), "formula_id": t.get("formula_id"), "status": t.get("status"), "result": t.get("result"), "unit": t.get("unit"),
               "period": t.get("period"), "inputs": t.get("inputs"), "section": (t.get("source") or {}).get("section"), "version": (t.get("source") or {}).get("version"),
               "warnings": list(t.get("warnings") or [])}
        calc_rows.append(row)
        allowed_text.append(json.dumps({"inputs": t.get("inputs"), "result": t.get("result"), "steps": t.get("steps")}, default=str))
        allowed_text.extend(str(w) for w in (t.get("warnings") or []))
        warnings.extend(str(w) for w in (t.get("warnings") or []) if str(w) not in warnings)
        if t.get("status") == "SOURCE_GAP":
            gaps.append(f"calculation {t.get('formula_id')}: SOURCE_GAP")
    aus_rows: List[str] = []
    if aus_envelope:
        aus_rows.append(str(aus_envelope.get("statement") or ""))
        for k in ("aus_result", "dti", "ltv", "funds_required_to_close", "reserves_required_to_be_verified", "aus_version", "findings_date"):
            if aus_envelope.get(k) is not None:
                aus_rows.append(f"{k}: {aus_envelope.get(k)}")
        for m in aus_envelope.get("messages") or []:
            aus_rows.append(str(m.get("text") if isinstance(m, dict) else m))
        allowed_text.extend(aus_rows)
    for o in overlays or []:
        claims.append({"kind": "overlay", "text": str(o.get("text") or o.get("rule") or ""), "ref": o.get("overlay_id"), "scope": o.get("scope"), "status": o.get("ae_confirmation_status")})
        allowed_text.append(str(o.get("text") or o.get("rule") or ""))
    for cnd in file_conditions or []:
        claims.append({"kind": "file_condition", "text": str(cnd), "ref": "uw_condition", "scope": "file_specific"})
        allowed_text.append(str(cnd))
    for g in guidance_items or []:
        claims.append({"kind": "guidance", "text": str(g.get("text") or ""), "ref": g.get("guidance_id"), "scope": g.get("scope"), "status": g.get("status")})
        allowed_text.append(str(g.get("text") or ""))
    allowed_numbers: Set[str] = set()
    for t in allowed_text:
        allowed_numbers |= _numbers_in(t)
    bound = {
        "response_version": RESPONSE_VERSION, "response_id": new_id("resp"), "workspace_id": workspace_id, "program": program, "generated_at": now_iso(),
        "supported_claims": claims, "calculation_results": calc_rows, "source_refs": refs, "aus": aus_rows, "warnings": warnings, "source_gaps": gaps,
        "allowed_facts": {"numbers": sorted(allowed_numbers), "claim_count": len(claims)},
        "underwriting_decision": False,
    }
    bound["digest"] = hashlib.sha256(json.dumps({k: bound[k] for k in ("supported_claims", "calculation_results", "aus", "warnings", "source_gaps")}, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    return bound


# ---------------------------------------------------------------------------
# render (deterministic presentation)
# ---------------------------------------------------------------------------

def render(bound: Dict[str, Any]) -> str:
    lines: List[str] = []
    if bound.get("source_gaps") and not bound.get("supported_claims"):
        lines.append("Conclusion: SOURCE_GAP — no activated rule in force backs this topic.")
    elif bound.get("supported_claims"):
        lines.append("Guideline-supported assessment (based on the documents currently available; not a loan approval):")
    for c in bound.get("supported_claims", []):
        tag = c.get("section") or c.get("scope") or c.get("kind")
        lines.append(f"- {c['text']} [{c['kind']}: {tag}" + (f", {c.get('resolution')}" if c.get("resolution") else "") + "]")
    for r in bound.get("calculation_results", []):
        if r.get("status") == "SUCCESS":
            lines.append(f"- Calculation {r['formula_id']} = {r['result']} {r.get('unit') or ''} ({r.get('period') or ''}; calc {r['calc_id']}; {r.get('section') or ''})".replace("  ", " "))
        else:
            lines.append(f"- Calculation {r['formula_id']}: {r.get('status')} (calc {r.get('calc_id')})")
    for a in bound.get("aus", []):
        if a:
            lines.append(f"- AUS: {a}")
    for w in bound.get("warnings", []):
        lines.append(f"- Caution: {w}")
    for g in bound.get("source_gaps", []):
        lines.append(f"- SOURCE_GAP: {g}")
    for r in bound.get("source_refs", []):
        if r.get("usable") or r.get("resolution_label"):
            lines.append(f"- Source: {r.get('section')} ({r.get('resolution_label') or r.get('lifecycle')}, effective {r.get('effective')}) {r.get('official_url') or ''}".rstrip())
    lines.append("Not an underwriting decision.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# validate / rewrite
# ---------------------------------------------------------------------------

def _support_index(bound: Dict[str, Any]) -> Tuple[Set[str], List[Set[str]]]:
    numbers = set(bound.get("allowed_facts", {}).get("numbers", []))
    bags: List[Set[str]] = []
    for c in bound.get("supported_claims", []):
        bags.append(_content_words(c.get("text", "")))
    for w in bound.get("warnings", []):
        bags.append(_content_words(w))
    for g in bound.get("source_gaps", []):
        bags.append(_content_words(g))
    for a in bound.get("aus", []):
        bags.append(_content_words(a))
    for r in bound.get("calculation_results", []):
        bags.append(_content_words(" ".join(str(x) for x in (r.get("formula_id"), r.get("section"), " ".join(r.get("warnings") or [])))))
    return numbers, bags


def _canon_period(unit: str) -> str:
    u = unit.lower().replace(" ", "")
    for base in ("month", "year", "day", "week", "statement", "page", "percentagepoint", "point", "paystub", "payperiod"):
        if u.startswith(base):
            return {"percentagepoint": "points", "paystub": "paystubs", "payperiod": "pay_periods"}.get(base, base + "s")
    return u


def _material_numbers(sentence: str) -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    for m in _PERCENT.finditer(sentence):
        found.append(("percent", _norm_num(m.group(1))))
    for m in _DOLLAR.finditer(sentence):
        found.append(("dollar", _norm_num(m.group(1) or m.group(2))))
    for m in _PERIOD.finditer(sentence):
        found.append((_canon_period(m.group(2)), _norm_num(m.group(1))))
    for m in _RATIO_PAIR.finditer(sentence):
        found.append(("ratio", _norm_num(m.group(1))))
        found.append(("ratio", _norm_num(m.group(2))))
    return found


def validate(text: str, bound: Dict[str, Any], *, min_overlap: int = 2) -> Dict[str, Any]:
    """Check generated prose against the bound object. Returns ``{"ok", "violations", "checked_sentences"}``."""
    numbers, bags = _support_index(bound)
    violations: List[Dict[str, Any]] = []
    checked = 0
    for sentence in _sentences(text):
        if _GLUE.match(sentence) and not _MODAL.search(sentence) and not _material_numbers(sentence):
            continue
        material = _material_numbers(sentence)
        modal = bool(_MODAL.search(sentence))
        if not material and not modal:
            continue
        checked += 1
        words = _content_words(sentence)
        overlap = max((len(words & bag) for bag in bags), default=0)
        for kind, value in material:
            if value not in numbers:
                violations.append({"sentence": sentence[:240], "kind": f"unsupported_{kind}", "value": value,
                                   "reason": f"{kind} value {value} does not appear in any supported claim, calculation, AUS finding, overlay or condition"})
        if modal and overlap < min_overlap and not any(v["sentence"] == sentence[:240] for v in violations):
            violations.append({"sentence": sentence[:240], "kind": "unsupported_assertion", "value": None,
                               "reason": "rule-like assertion shares fewer than two content words with any supported claim or recorded caution"})
    return {"ok": not violations, "violations": violations, "checked_sentences": checked, "response_id": bound.get("response_id"), "digest": bound.get("digest")}


def rewrite(text: str, bound: Dict[str, Any]) -> Dict[str, Any]:
    """Drop every sentence that fails validation and say what was removed."""
    result = validate(text, bound)
    if result["ok"]:
        return {"text": text, "removed": [], "ok": True, "response_id": bound.get("response_id")}
    bad = {v["sentence"] for v in result["violations"]}
    kept = [s for s in _sentences(text) if s[:240] not in bad]
    note = f"[{len(bad)} statement(s) removed by the source-bound validator: not supported by the activated rules, calculations, AUS findings, overlays or file conditions on record.]"
    return {"text": "\n".join(kept + [note]), "removed": sorted(bad), "ok": True, "response_id": bound.get("response_id"), "validated_after_rewrite": validate("\n".join(kept), bound)["ok"]}


class ResponseStore:
    """Bound responses are durable so a validation can be replayed and audited."""

    def __init__(self, root) -> None:
        self.docs = JsonDocStore(root / "responses")

    def put(self, bound: Dict[str, Any]) -> Dict[str, Any]:
        return self.docs.put(bound["response_id"], bound)

    def get(self, response_id: str) -> Optional[Dict[str, Any]]:
        return self.docs.get(response_id)

    def record_validation(self, response_id: str, result: Dict[str, Any], text_sha: str) -> None:
        def _mutate(d):
            d.setdefault("validations", []).append({"at": now_iso(), "ok": result["ok"], "violations": result["violations"], "text_sha": text_sha})

        self.docs.update(response_id, _mutate)
