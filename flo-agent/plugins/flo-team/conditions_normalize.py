"""Conditions normalizer.

Turns a raw lender / UW / AUS / approval-letter line into the structured shape
Flo stores on a workspace. Pure Python, no LLM — keyword and pattern matching
plus a small bank of substitutions. The output is the contract downstream
code (Ashley-facing UI, auto-clear hook, request buttons) relies on.

Output shape (one condition per raw line)::

    {
      "original_text":   "<verbatim lender line>",
      "plain_english":  "<plain-English rendering for Ashley>",
      "condition_type":  "paystub" | "w2" | "bank_statement" | ... | "other",
      "owner":           "Borrower" | "Loan Officer" | "Title" | "Insurance"
                         | "Employer" | "Appraiser" | "Lender/UW"
                         | "Processor" | "Other",
      "required_item":   "<short noun phrase Ashley sees on a card>",
      "category":        "income" | "assets" | "insurance" | ...,
      "needs_sage":      bool,   # guideline interpretation required
      "source":          "lender_email" | "aus" | "approval_letter" | "manual",
      "source_date":     "<iso or null>",
      "status":          "Open",  # Open is the only state at ingest time;
                                  # Waiting / Needs Review / Cleared come
                                  # from later workflows, not the parser
    }

The parser is deliberately conservative: when it's not sure, it produces a
useful but ``owner="Other"`` ``condition_type="other"`` row, never an
inferred-but-wrong one. Downstream code treats ``Other`` as
``needs_sage = True`` so the human path covers anything ambiguous.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ── Owner detection ─────────────────────────────────────────────────────────
#
# Order matters: more specific phrases win. We scan top-to-bottom and the
# first hit sets the owner. Anything not matched falls through to Other.

_OWNER_PATTERNS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("Title",           ("title company", "title commitment", "title policy",
                         "preliminary title", "title endorsement", "title curative",
                         "lien release", "title update")),
    ("Insurance",       ("insurance", "hazard insurance", "homeowners insurance",
                         "hoi", "policy declaration", "dwelling coverage",
                         "flood insurance", "condo insurance", "windstorm")),
    ("Employer",        ("employer", "human resources", "hr department",
                         "verifier", "verbal vvoe", "voe from employer")),
    ("Appraiser",       ("appraiser", "appraisal", "reo department",
                         "reconditioning", "1004mc")),
    ("Lender/UW",       ("underwriter", "lender", "uw condition",
                         "prior to doc", "prior to funding", "ptd ", "ptf ",
                         "clear to close", "ctc condition", "8102",
                         "conditions of approval", "approval condition",
                         "conditional approval")),
    ("Loan Officer",    ("loan officer", "loan originator", "lo to provide",
                         "lo must", "letter of explanation from lo",
                         "signed by loan officer", "lo signature")),
    ("Processor",       ("processor", "processing condition", "file condition",
                         "loan processor")),
    ("Borrower",        ("borrower", "co-borrower", "applicant", "taxpayer",
                         "from the buyer", "from the seller", "from the purchaser",
                         "consumer", "customer to provide", "client to provide",
                         "most recent paystub", "most recent pay stubs",
                         "year-to-date", "ytd earnings", "year to date",
                         "30-day", "60-day", "bank statement",
                         "w-2", "1099", "tax return", "drivers license",
                         "passport", "gift letter", "large deposit",
                         "child support", "alimony")),
)


def _detect_owner(text: str) -> str:
    t = (text or "").lower()
    for owner, patterns in _OWNER_PATTERNS:
        for p in patterns:
            if p in t:
                return owner
    return "Other"


# ── Condition type / category detection ────────────────────────────────────

_TYPE_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    # (condition_type, category, keyword list)
    ("paystub",              "income",    ("paystub", "pay stub", "pay-stub",
                                            "earnings statement", "ytd earnings",
                                            "year-to-date earnings", "30-day pay",
                                            "60-day pay")),
    ("w2",                   "income",    ("w-2", "w2", "wage and tax statement")),
    ("1099",                 "income",    ("1099", "misc income")),
    ("tax_return",           "income",    ("tax return", "1040", "4506",
                                            "transcript of tax return",
                                            "irs transcript")),
    ("profit_and_loss",      "income",    ("profit and loss", "p&l", "p & l")),
    ("k1",                   "income",    ("k-1", "k1", "schedule k-1")),
    ("bank_statement",       "assets",    ("bank statement", "bank statements",
                                            "checking statement", "savings statement",
                                            "verification of deposit",
                                            "vod ", "two months bank",
                                            "two months of bank",
                                            "two months' bank")),
    ("retirement_statement", "assets",    ("retirement statement", "401k", "ira ",
                                            "brokerage statement", "vanguard",
                                            "fidelity statement")),
    ("gift_letter",          "assets",    ("gift letter", "gift funds",
                                            "documentation of gift",
                                            "gift documentation")),
    ("insurance_declaration","insurance", ("insurance declaration", "hoi dec",
                                            "homeowners insurance declaration",
                                            "policy declarations page",
                                            "hazard insurance policy",
                                            "dwelling coverage", "windstorm",
                                            "flood insurance policy")),
    ("title_commitment",     "title_property",
                                         ("title commitment", "preliminary title",
                                          "marked up commitment", "title policy",
                                          "schedule b", "pud rider", "title endorsement")),
    ("appraisal",            "aus_findings",
                                         ("appraisal report", "1004", "appraisal",
                                          "reo", "subject to appraisal")),
    ("purchase_contract",    "purchase_contract",
                                         ("purchase contract", "sales contract",
                                          "purchase agreement", "fully executed contract")),
    ("loan_application",     "loan_application",
                                         ("1003", "loan application", "urla")),
    ("credit_report",        "credit_report",
                                         ("credit report", "tri-merge",
                                          "updated credit pull",
                                          "rescore credit")),
    ("identification",       "identification",
                                         ("drivers license", "passport",
                                          "state-issued id", "state id")),
    ("aus_findings",         "aus_findings",
                                         ("du findings", "lp findings",
                                          "aus findings", "desktop underwriter",
                                          "loan product advisor")),
    ("letter_of_explanation","other",     ("letter of explanation", "loe",
                                            "explanation letter", "lo explanation")),
    ("wvoe",                 "other",     ("written voe", "wvoe",
                                            "written verification of employment")),
    ("voe",                  "other",     ("verbal voe", "verbal vvoe",
                                            "phone verification", "verification of employment",
                                            "voe from", " voe ", "hr ")),
    ("source_of_funds",      "other",     ("source of funds", "source-of-funds",
                                            "sofs", "sofu")),
)


def _detect_type(text: str) -> Tuple[str, str]:
    """Return ``(condition_type, category)``. Falls back to ``("other", "other")``."""
    t = (text or "").lower()
    for ctype, category, kws in _TYPE_KEYWORDS:
        for kw in kws:
            if kw in t:
                return ctype, category
    return "other", "other"


# ── Plain-English rewrite ──────────────────────────────────────────────────
#
# Goal: take the lender's exact words and produce a sentence Ashley can
# understand. We do **not** paraphrase aggressively, we never change the
# meaning, and we never add conditions that weren't there. We strip
# addressee boilerplate, swap a handful of frequent shorthand, and keep
# the original sentence structure otherwise.

_REDUNDANT_LEAD = re.compile(
    r"^\s*(?:please\s+|kindly\s+|we\s+need\s+(?:you\s+to\s+|to\s+)?|"
    r"need\s+(?:you\s+to\s+|to\s+)?|provide\s+|provide\s+the\s+|"
    r"must\s+provide\s+the\s+|must\s+provide\s+)",
    re.IGNORECASE,
)

_SUBS: Tuple[Tuple[re.Pattern, str], ...] = (
    (re.compile(r"\bptd\b", re.IGNORECASE),     "prior to doc"),
    (re.compile(r"\bptf\b", re.IGNORECASE),     "prior to funding"),
    (re.compile(r"\bctc\b", re.IGNORECASE),     "clear to close"),
    (re.compile(r"\bdu\b",  re.IGNORECASE),     "DU"),
    (re.compile(r"\blpa\b", re.IGNORECASE),     "LPA"),
    (re.compile(r"\bvoa\b", re.IGNORECASE),     "VOA"),
    (re.compile(r"\bvoi\b", re.IGNORECASE),     "VOI"),
    (re.compile(r"\bhoi\b", re.IGNORECASE),     "HOI"),
    (re.compile(r"\bw-?2\b", re.IGNORECASE),    "W-2"),
    (re.compile(r"\b1099\b", re.IGNORECASE),    "1099"),
    (re.compile(r"\burla\b", re.IGNORECASE),    "URLA"),
    (re.compile(r"\bvvoe\b", re.IGNORECASE),    "Written VOE"),
    (re.compile(r"\bwvoe\b", re.IGNORECASE),    "Written VOE"),
    (re.compile(r"\bvoe\b",  re.IGNORECASE),    "VOE"),
    (re.compile(r"\bletter of exp\b", re.IGNORECASE), "letter of explanation"),
    (re.compile(r"\bLOE\b",  re.IGNORECASE),    "letter of explanation"),
    (re.compile(r"\bYTD\b",  re.IGNORECASE),    "year-to-date"),
    (re.compile(r"\bVOD\b",  re.IGNORECASE),    "verification of deposit"),
)


def _rewrite_to_plain_english(text: str, *, owner: str) -> str:
    """Light rewrite that preserves meaning. Owner is used for a single
    clarifying prefix when the original sentence has no subject."""
    s = (text or "").strip()
    if not s:
        return ""
    s = _REDUNDANT_LEAD.sub("", s, count=1)
    if not s:
        s = (text or "").strip()
    for pat, repl in _SUBS:
        s = pat.sub(repl, s)
    # Capitalize the first letter; collapse whitespace.
    s = re.sub(r"\s+", " ", s).strip()
    if s:
        s = s[0].upper() + s[1:]
    # If the sentence has no clear subject word ("Need X" / "Provide X"),
    # prefix with a plain-English subject derived from the owner.
    owner_prefixes = {
        "Borrower":    "Borrower needs to provide ",
        "Loan Officer": "Loan officer needs to provide ",
        "Title":       "Title company needs to provide ",
        "Insurance":   "Insurance agent needs to provide ",
        "Employer":    "Employer needs to provide ",
        "Appraiser":   "Appraiser needs to provide ",
        "Lender/UW":   "Lender / underwriter needs to provide ",
        "Processor":   "Processor needs to provide ",
        "Other":       "",
    }
    already_subject = re.match(
        r"^(Borrower|Loan officer|Title company|Insurance agent|Employer|"
        r"Appraiser|Lender|Underwriter|Processor)\b",
        s,
        re.IGNORECASE,
    )
    if not already_subject and owner in owner_prefixes and owner_prefixes[owner]:
        s = owner_prefixes[owner] + s[0].lower() + s[1:]
        s = re.sub(r"\s+", " ", s).strip()
        # Capitalize the very first character again.
        if s:
            s = s[0].upper() + s[1:]
    return s


# ── Required item — the noun phrase Ashley sees on the card ────────────────

def _required_item(text: str, condition_type: str) -> str:
    """Best-effort noun phrase. Falls back to the first sentence or
    a generic phrase. Never more than ~80 chars."""
    if condition_type != "other":
        # Map type → friendly noun phrase.
        friendly = {
            "paystub":              "most recent paystub",
            "w2":                   "W-2",
            "1099":                 "1099",
            "tax_return":           "tax return",
            "profit_and_loss":      "profit & loss",
            "k1":                   "K-1",
            "bank_statement":       "bank statement",
            "retirement_statement": "retirement statement",
            "gift_letter":          "gift letter",
            "insurance_declaration":"HOI declaration page",
            "title_commitment":     "updated title commitment",
            "appraisal":            "appraisal",
            "purchase_contract":    "purchase contract",
            "loan_application":     "loan application",
            "credit_report":        "updated credit report",
            "identification":       "identification",
            "aus_findings":         "AUS findings",
            "letter_of_explanation":"letter of explanation",
            "wvoe":                 "Written VOE",
            "voe":                  "verbal VOE",
            "source_of_funds":      "source-of-funds documentation",
        }
        return friendly.get(condition_type, condition_type.replace("_", " "))
    # Generic: take the first short noun phrase from the text.
    s = re.sub(r"^[^A-Za-z0-9]+", "", (text or "").strip())
    chunks = re.split(r"[.;]", s, maxsplit=1)
    head = chunks[0].strip() if chunks else s
    if len(head) > 80:
        head = head[:77].rsplit(" ", 1)[0] + "…"
    return head or "item"


# ── Guideline interpretation gate ─────────────────────────────────────────

_GUIDELINE_KINDS = {
    "letter_of_explanation",
    "source_of_funds",
    "gift_letter",
    "appraisal",
    "aus_findings",
    "title_commitment",
    "credit_report",
}

# A condition "needs Sage" when the lender phrase explicitly requires a
# guideline / interpretation judgment. Pure operational items (a missing
# paystub, a missing insurance page) don't.
_GUIDELINE_PHRASES = (
    "per guidelines", "per du guidelines", "per lp guidelines",
    "per fannie", "per freddie", "per fha", "per va", "per usda",
    "in accordance with", "acceptable per", "must meet",
    "satisfactory to", "must be acceptable",
)


def _needs_sage(text: str, condition_type: str) -> bool:
    t = (text or "").lower()
    if condition_type in _GUIDELINE_KINDS:
        # AUS findings and gift letter / SoF sometimes are mechanical,
        # but in practice a lender/UW condition in these kinds usually
        # means "explain it" or "qualify it" — keep the Sage path on.
        return True
    if any(p in t for p in _GUIDELINE_PHRASES):
        return True
    return False


# ── Public API ─────────────────────────────────────────────────────────────

def parse_condition(
    raw_text: str,
    *,
    source: str = "manual",
    source_date: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse one raw condition line. Returns the structured shape documented
    at the top of this module. ``extra`` is merged into the result for
    caller-supplied fields (``borrower_ref``, ``page_requirement`` …)."""
    condition_type, category = _detect_type(raw_text)
    owner = _detect_owner(raw_text)
    if owner == "Other":
        # Even if the phrase doesn't name an actor, prefer the type-driven
        # default so simple paystub / bank statements land on Borrower.
        if condition_type in {"paystub", "w2", "1099", "tax_return",
                              "profit_and_loss", "k1", "bank_statement",
                              "retirement_statement", "gift_letter",
                              "source_of_funds", "letter_of_explanation",
                              "identification"}:
            owner = "Borrower"
        elif condition_type == "insurance_declaration":
            owner = "Insurance"
        elif condition_type == "title_commitment":
            owner = "Title"
        elif condition_type == "appraisal":
            owner = "Appraiser"
    out: Dict[str, Any] = {
        "original_text":  (raw_text or "").strip(),
        "plain_english": _rewrite_to_plain_english(raw_text, owner=owner),
        "condition_type": condition_type,
        "owner":          owner,
        "required_item":  _required_item(raw_text, condition_type),
        "category":       category,
        "needs_sage":     _needs_sage(raw_text, condition_type),
        "source":         source,
        "source_date":    source_date,
        "status":         "Open",
        "state":          "open",   # legacy field read by today.py / auto-clear
    }
    if extra:
        # don't let extra clobber the curated fields
        for k, v in extra.items():
            if k not in out:
                out[k] = v
    return out


# ── Multi-line ingestion ───────────────────────────────────────────────────

def split_lender_lines(blob: str) -> List[str]:
    """Split a lender / approval-letter blob into individual condition lines.

    Removes empty / very-short lines, leading bullets / numbers, and lines
    that are clearly greeting / sign-off / boilerplate.
    """
    out: List[str] = []
    for raw in (blob or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        if len(s) < 8:
            continue
        # Drop bullets and numbered prefixes.
        s = re.sub(r"^[\-\*•·]\s*", "", s)
        s = re.sub(r"^\d+[\.\)]\s+", "", s)
        # Drop obvious boilerplate.
        low = s.lower().rstrip(",.")
        if low.startswith(("thank you", "thanks", "regards", "best", "sincerely",
                            "if you have any questions", "please contact",
                            "please feel free", "please let me know",
                            "best regards", "kind regards")):
            continue
        if low.startswith(("dear ", "hello", "hi,", "hi ", "to whom", "good morning",
                            "good afternoon", "team,", "thank you for")):
            continue
        # Sign-off lines that are just a name or "Underwriter".
        if low in {"underwriter", "loan officer", "processor", "uw", "lo"}:
            continue
        # Drop lines that just describe what's coming ("We have the following …").
        if low.startswith(("we have the following", "below are the",
                            "the following conditions", "please see the",
                            "see below", "see attached")):
            continue
        out.append(s)
    return out


def parse_conditions_blob(
    blob: str,
    *,
    source: str = "lender_email",
    source_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Parse a multi-line lender / approval-letter blob into a list of
    structured conditions. Skips boilerplate lines; each kept line becomes
    one condition. Use this for intake from email or uploaded PDFs."""
    return [
        parse_condition(line, source=source, source_date=source_date)
        for line in split_lender_lines(blob)
    ]


# ── Grouping by owner (UI consumers) ──────────────────────────────────────

def group_by_owner(
    conditions: Iterable[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Group open (or any) conditions by owner. Owner categories are the
    canonical short list — anything not matching one of them lands in
    ``"Other"``. Stable iteration order: Borrower, Loan Officer, Title,
    Insurance, Employer, Appraiser, Lender/UW, Processor, Other."""
    owner_order = (
        "Borrower", "Loan Officer", "Title", "Insurance", "Employer",
        "Appraiser", "Lender/UW", "Processor", "Other",
    )
    grouped: Dict[str, List[Dict[str, Any]]] = {o: [] for o in owner_order}
    for c in conditions or []:
        if not isinstance(c, dict):
            continue
        owner = c.get("owner") or "Other"
        if owner not in grouped:
            owner = "Other"
        grouped[owner].append(c)
    # Drop empty buckets for the return value
    return {o: v for o, v in grouped.items() if v}


def filter_open(conditions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return only conditions that are not cleared (state != "cleared")."""
    out: List[Dict[str, Any]] = []
    for c in conditions or []:
        if not isinstance(c, dict):
            continue
        state = (c.get("state") or c.get("status") or "open")
        if isinstance(state, str) and state.lower() == "cleared":
            continue
        out.append(c)
    return out


def normalize_existing(condition: Dict[str, Any]) -> Dict[str, Any]:
    """Back-fill owner / plain_english / required_item / category on a
    condition dict that was created before the normalizer existed (or
    that came in from a tool that wrote its own fields).

    Only fills in fields that are missing. Never overwrites a curated
    field. Never clears or changes ``id``, ``state``, ``status``,
    ``added_at``, ``added_by``, ``source``, ``cleared_*`` or any field
    the caller has already set.
    """
    if not isinstance(condition, dict):
        return condition
    text = condition.get("text") or condition.get("description") or condition.get("original_text") or ""
    parsed = parse_condition(
        text,
        source=condition.get("source") or "manual",
        source_date=condition.get("source_date"),
    )
    fill_keys = (
        "plain_english", "owner", "required_item", "condition_type",
        "category", "needs_sage", "status",
    )
    for key in fill_keys:
        if not condition.get(key):
            condition[key] = parsed.get(key)
    # Map condition_type onto the legacy ``kind`` field when missing.
    if not condition.get("kind") and parsed.get("condition_type"):
        condition["kind"] = parsed["condition_type"]
    return condition


def normalize_workspace(workspace_doc: Dict[str, Any]) -> None:
    """In-place back-fill of owner / plain_english / etc on a workspace's
    conditions list. Skips cleared conditions; preserves existing fields."""
    for cond in workspace_doc.get("conditions") or []:
        if not isinstance(cond, dict):
            continue
        if (cond.get("state") or cond.get("status") or "open") == "cleared":
            continue
        normalize_existing(cond)
