"""Loan documents inside Flo — records, private local copies, text extraction, deterministic checks.

The website stores the originals in private object storage and hands Flo *references*
(``documentRefs`` with an authenticated ``fetchUrl``). At intake Flo pulls each file
through that connector (bearer token, never the browser), verifies the checksum, keeps a
private copy under ``<hermes root>/flo/documents/<workspace>/<category>/[<borrower>/]``
with a clean display name, extracts the PDF text layer into a sidecar ``.txt`` (never
altering the original binary), and runs the checks that need no model:

* duplicate content (sha256) → status ``duplicate``
* "Page N of M" bookkeeping → status ``missing_pages`` with the missing page numbers
* PDF without a text layer → ``needs_review`` with a note (no OCR on this install)
* filename / text keyword classification when the LO left the subtype blank
  (``classification_source`` says who decided; Malcolm or Ashley can change it)

The document inventory compares what arrived with what the submission itself says
(LO-stated income documents) and with *activated* source rules; anything not backed by
an active rule is listed as SOURCE_GAP / needs clarification, never as required.

Statuses (Ashley sees these inside the file): received, needs_review, reviewed,
missing_pages, unreadable, duplicate, not_needed.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from .store import JsonDocStore, JsonlLog, new_id, now_iso

STATUSES = ("received", "needs_review", "reviewed", "missing_pages", "unreadable", "duplicate", "not_needed")
STATUS_LABEL = {"received": "Received", "needs_review": "Needs review", "reviewed": "Reviewed", "missing_pages": "Missing pages",
                "unreadable": "Unreadable", "duplicate": "Duplicate", "not_needed": "Not needed"}
CATEGORIES = ("loan_application", "credit_report", "aus_findings", "income", "assets", "purchase_contract", "title_property", "insurance", "identification", "other")
CATEGORY_LABEL = {"loan_application": "Application", "credit_report": "Credit", "aus_findings": "AUS", "income": "Income", "assets": "Assets",
                  "purchase_contract": "Contract", "title_property": "Title", "insurance": "Insurance", "identification": "Identification", "other": "Other"}
CATEGORY_FOLDER = {"loan_application": "application", "credit_report": "credit", "aus_findings": "aus", "income": "income", "assets": "assets",
                   "purchase_contract": "contract", "title_property": "title", "insurance": "insurance", "identification": "identification", "other": "other"}
SUBTYPES = {"income": ("paystub", "w2", "1099", "tax_return", "profit_and_loss", "k1", "other"), "assets": ("bank_statement", "retirement_statement", "gift_documentation", "other")}
SUBTYPE_LABEL = {"paystub": "Paystub", "w2": "W-2", "1099": "1099", "tax_return": "Tax return", "profit_and_loss": "P&L", "k1": "K-1", "bank_statement": "Bank statement",
                 "retirement_statement": "Retirement statement", "gift_documentation": "Gift documentation", "other": "Other"}
BORROWER_FOLDER = {"borrower": "borrower1", "co_borrower": "borrower2", "both": "joint"}
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_PAGE_RE = re.compile(r"\bpage\s+(\d{1,3})\s+of\s+(\d{1,3})\b", re.I)
# Whole-document identities first (an AUS report *mentions* paystubs; it is not one), then income/asset subtypes.
_KEYWORDS = [
    ("aus_findings", None, r"desktop underwriter|du findings|loan product advisor|lpa feedback|total scorecard|gus underwriting|findings report"),
    ("credit_report", None, r"credit report|tri-?merge|tradelines?"),
    ("loan_application", None, r"uniform residential loan application|form 1003|\b1003\b"),
    ("purchase_contract", None, r"purchase agreement|purchase contract|contract for sale"),
    ("insurance", None, r"homeowners insurance|hazard insurance|declarations page|hoi\b"),
    ("title_property", None, r"title commitment|preliminary title|appraisal report|survey"),
    ("identification", None, r"driver'?s license|passport|identification"),
    ("income", "paystub", r"earnings statement|pay ?stub|pay period|gross pay|net pay|pay date"),
    ("income", "w2", r"\bw-?2\b|wage and tax statement"),
    ("income", "1099", r"\b1099\b"),
    ("income", "tax_return", r"form 1040|tax return|schedule c|schedule e"),
    ("income", "profit_and_loss", r"profit and loss|profit & loss|p&l"),
    ("income", "k1", r"schedule k-?1"),
    ("assets", "bank_statement", r"bank statement|statement period|beginning balance|ending balance|checking|savings"),
    ("assets", "retirement_statement", r"401\(?k\)?|ira\b|retirement"),
    ("assets", "gift_documentation", r"gift letter|gift funds"),
]
TEXT_LIMIT = 200_000


def documents_root(team_root) -> Path:
    """Private local copies live beside the team state: <hermes root>/flo/documents."""
    return Path(team_root).parent / "documents"


def _slug(value: str) -> str:
    return _SAFE.sub("_", str(value or "")).strip("_") or "document"


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_text(path: Path) -> Dict[str, Any]:
    """PDF text layer via pypdf (best effort). Images: no OCR on this install — say so, do not block."""
    suffix = path.suffix.lower()
    if suffix != ".pdf":
        return {"text": "", "page_count": None, "method": "none", "note": "image / office document: no text extraction on this install"}
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(str(path))
        chunks = []
        for page in reader.pages:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001
                chunks.append("")
        text = "\n\f\n".join(chunks)[:TEXT_LIMIT]
        return {"text": text, "page_count": len(reader.pages), "method": "pdf_text_layer" if text.strip() else "none",
                "note": None if text.strip() else "PDF has no text layer (scan); OCR is not available on this install"}
    except Exception as exc:  # noqa: BLE001
        return {"text": "", "page_count": None, "method": "failed", "note": f"could not read PDF: {type(exc).__name__}"}


def missing_pages(text: str) -> Dict[str, Any]:
    """From 'Page N of M' markers: which pages are absent. {'expected': M, 'seen': [...], 'missing': [...]}."""
    seen, expected = set(), 0
    for m in _PAGE_RE.finditer(text or ""):
        n, total = int(m.group(1)), int(m.group(2))
        if total >= n:
            seen.add(n)
            expected = max(expected, total)
    if expected <= 1:
        return {"expected": expected or None, "seen": sorted(seen), "missing": []}
    return {"expected": expected, "seen": sorted(seen), "missing": [p for p in range(1, expected + 1) if p not in seen]}


def classify(filename: str, text: str, category: Optional[str], subcategory: Optional[str]) -> Dict[str, Any]:
    """Keep the LO's choice; fill blanks from filename/text keywords. Never overrides a stated subtype."""
    head = (text or "")[:600].lower()  # the first lines say what a document IS; later lines say what it mentions
    hay = f"{filename}\n{(text or '')[:4000]}".lower()
    guess_cat, guess_sub, source = None, None, None
    for scope in (f"{filename}\n{head}".lower(), hay):
        for cat, sub, pattern in _KEYWORDS:
            if re.search(pattern, scope):
                guess_cat, guess_sub = cat, sub
                source = "filename" if re.search(pattern, filename.lower()) else "text"
                break
        if guess_cat:
            break
    out = {"category": category or guess_cat or "other", "subcategory": subcategory, "classification_source": "loan_officer", "suggested": None}
    if not subcategory and guess_sub and (category in (None, guess_cat)):
        out["subcategory"] = guess_sub
        out["classification_source"] = source
    if category and guess_cat and guess_cat != category:
        out["suggested"] = {"category": guess_cat, "subcategory": guess_sub, "source": source}
    return out


class DocumentStore:
    """``<team root>/documents/<workspace_id>.json`` — one record list per file."""

    def __init__(self, root) -> None:
        self.root = Path(root)
        self.docs = JsonDocStore(self.root / "documents")
        self.log = JsonlLog(self.root / "activity", "activity")

    def list(self, workspace_id: str) -> List[Dict[str, Any]]:
        return list((self.docs.get(workspace_id) or {}).get("documents") or [])

    def get(self, workspace_id: str, document_id: str) -> Optional[Dict[str, Any]]:
        return next((d for d in self.list(workspace_id) if d.get("document_id") == document_id), None)

    def find(self, document_id: str) -> Optional[Dict[str, Any]]:
        for wid in self.docs.ids():
            rec = self.get(wid, document_id)
            if rec:
                return rec
        return None

    def _save(self, workspace_id: str, documents: List[Dict[str, Any]]) -> None:
        self.docs.put(workspace_id, {"workspace_id": workspace_id, "documents": documents, "updated_at": now_iso()})

    def add(self, workspace_id: str, record: Dict[str, Any]) -> Dict[str, Any]:
        documents = self.list(workspace_id)
        documents.append(record)
        self._save(workspace_id, documents)
        return record

    def update(self, workspace_id: str, document_id: str, fields: Dict[str, Any], *, by: str) -> Dict[str, Any]:
        documents = self.list(workspace_id)
        rec = next((d for d in documents if d.get("document_id") == document_id), None)
        if rec is None:
            raise KeyError(f"unknown document {document_id}")
        allowed = {"category", "subcategory", "borrower_ref", "status", "notes", "display_name"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"cannot set {sorted(unknown)}")
        if "status" in fields and fields["status"] not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        if "category" in fields and fields["category"] not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        if "subcategory" in fields and fields["subcategory"] and fields["subcategory"] not in SUBTYPES.get(fields.get("category") or rec.get("category"), ()) and fields["subcategory"] != "other":
            raise ValueError("subcategory does not belong to that category")
        if "display_name" in fields:
            fields["display_name"] = _slug(fields["display_name"])[:120] or rec["display_name"]
        changes = {k: v for k, v in fields.items() if rec.get(k) != v}
        rec.update(changes)
        if {"category", "subcategory", "borrower_ref"} & set(changes):
            rec["classification_source"] = by
        rec.setdefault("history", []).append({"at": now_iso(), "by": by, "changes": changes})
        self._save(workspace_id, documents)
        self.log.append({"event": "document.updated", "actor": by, "workspace_id": workspace_id, "document_id": document_id, "changes": sorted(changes)})
        return rec


def _local_path(team_root, workspace_id: str, rec: Dict[str, Any]) -> Path:
    folder = CATEGORY_FOLDER.get(rec.get("category") or "other", "other")
    parts = [documents_root(team_root), _slug(workspace_id), folder]
    if rec.get("category") in ("income", "assets") and rec.get("borrower_ref"):
        parts.append(BORROWER_FOLDER.get(rec["borrower_ref"], "joint"))
    base = Path(*parts)
    base.mkdir(parents=True, exist_ok=True)
    name = _slug(rec.get("display_name") or rec.get("original_filename") or "document.pdf")
    candidate = base / name
    n = 2
    while candidate.exists():
        candidate = base / f"{Path(name).stem}_{n}{Path(name).suffix}"
        n += 1
    return candidate


def default_fetch(token: Optional[str]) -> Callable[[Dict[str, Any]], bytes]:
    def _fetch(ref: Dict[str, Any]) -> bytes:
        url = str(ref.get("fetchUrl") or "")
        if not url.startswith(("http://", "https://")):
            raise ValueError("document has no fetch URL")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token or ''}", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 - authenticated connector to the website backend
            return resp.read()

    return _fetch


def ingest(team_root, workspace_id: str, submission_id: str, refs: Iterable[Dict[str, Any]], *, fetch: Optional[Callable[[Dict[str, Any]], bytes]] = None,
           token: Optional[str] = None, actor: str = "flo") -> Dict[str, Any]:
    """Pull every referenced document through the connector and build its record. Never raises for one bad file."""
    store = DocumentStore(team_root)
    fetch = fetch or default_fetch(token)
    existing = store.list(workspace_id)
    seen_sha = {d.get("sha256"): d for d in existing if d.get("sha256")}
    seen_ids = {d.get("website_document_id") for d in existing}
    results: List[Dict[str, Any]] = []
    for ref in refs or []:
        if not isinstance(ref, dict) or ref.get("documentId") in seen_ids:
            continue
        rec: Dict[str, Any] = {
            "document_id": new_id("doc"), "website_document_id": ref.get("documentId"), "submission_id": submission_id, "workspace_id": workspace_id,
            "category": ref.get("category") if ref.get("category") in CATEGORIES else "other", "subcategory": ref.get("subcategory") or None,
            "borrower_ref": ref.get("borrowerRef") or None, "original_filename": str(ref.get("originalFilename") or ref.get("fileName") or "document")[:160],
            "display_name": str(ref.get("displayName") or ref.get("fileName") or "document")[:160], "storage_key": ref.get("storageKey"),
            "mime_type": ref.get("mimeType"), "size_bytes": ref.get("sizeBytes"), "sha256": ref.get("sha256"), "uploaded_at": ref.get("uploadedAt"),
            "uploaded_by": ref.get("uploadedBy") or "loan_officer", "received_at": now_iso(), "status": "received", "classification_source": "loan_officer",
            "notes": "", "local_path": None, "text_path": None, "text_chars": 0, "page_count": None, "checks": {}, "history": [],
        }
        if ref.get("status") == "duplicate" or (rec["sha256"] and rec["sha256"] in seen_sha):
            twin = seen_sha.get(rec["sha256"])
            rec["status"] = "duplicate"
            rec["notes"] = f"Same content as {twin['display_name']}" if twin else "Duplicate of another upload in this submission"
            rec["local_path"] = twin.get("local_path") if twin else None
            store.add(workspace_id, rec)
            results.append(rec)
            continue
        try:
            data = fetch(ref)
        except Exception as exc:  # noqa: BLE001
            rec["status"] = "needs_review"
            rec["notes"] = f"Could not fetch from storage ({type(exc).__name__}); retry with flo_documents action=refetch"
            rec["checks"] = {"fetch_failed": True}
            store.add(workspace_id, rec)
            results.append(rec)
            continue
        digest = sha256_of(data)
        if rec["sha256"] and digest != rec["sha256"]:
            rec["notes"] = "Checksum differs from the website record; kept the fetched bytes and flagged for review"
            rec["status"] = "needs_review"
        rec["sha256"] = digest
        rec["size_bytes"] = len(data)
        path = _local_path(team_root, workspace_id, rec)
        path.write_bytes(data)
        rec["local_path"] = str(path)
        extracted = extract_text(path)
        rec["page_count"] = extracted["page_count"]
        if extracted["text"]:
            text_path = path.with_suffix(path.suffix + ".txt")
            text_path.write_text(extracted["text"], encoding="utf-8")
            rec["text_path"] = str(text_path)
            rec["text_chars"] = len(extracted["text"])
        cls = classify(rec["original_filename"], extracted["text"], rec["category"], rec["subcategory"])
        rec["subcategory"] = cls["subcategory"]
        rec["classification_source"] = cls["classification_source"]
        if cls["suggested"]:
            rec["checks"]["suggested_classification"] = cls["suggested"]
        pages = missing_pages(extracted["text"])
        rec["checks"]["pages"] = pages
        if pages["missing"]:
            rec["status"] = "missing_pages"
            rec["notes"] = f"Pages {', '.join(map(str, pages['missing']))} of {pages['expected']} not in the file"
        elif rec["status"] == "received" and extracted["method"] == "none" and path.suffix.lower() == ".pdf":
            rec["status"] = "needs_review"
            rec["notes"] = extracted["note"] or "no text layer"
        elif extracted["method"] == "failed":
            rec["status"] = "unreadable"
            rec["notes"] = extracted["note"] or "could not read"
        seen_sha[digest] = rec
        store.add(workspace_id, rec)
        results.append(rec)
    store.log.append({"event": "documents.ingested", "actor": actor, "workspace_id": workspace_id, "submission_id": submission_id, "count": len(results),
                      "statuses": {s: sum(1 for r in results if r["status"] == s) for s in STATUSES if any(r["status"] == s for r in results)}})
    return {"workspace_id": workspace_id, "documents": results, "received": sum(1 for r in results if r["status"] != "duplicate"), "duplicates": sum(1 for r in results if r["status"] == "duplicate")}


def refetch(team_root, workspace_id: str, document_id: str, *, fetch: Optional[Callable[[Dict[str, Any]], bytes]] = None, token: Optional[str] = None,
            fetch_url: Optional[str] = None, by: str = "flo") -> Dict[str, Any]:
    """Retry a document whose fetch failed at intake."""
    store = DocumentStore(team_root)
    rec = store.get(workspace_id, document_id)
    if rec is None:
        raise KeyError(document_id)
    fetch = fetch or default_fetch(token)
    data = fetch({"fetchUrl": fetch_url or rec.get("fetch_url"), "documentId": rec.get("website_document_id")})
    path = _local_path(team_root, workspace_id, rec)
    path.write_bytes(data)
    extracted = extract_text(path)
    fields = {"status": "received", "notes": ""}
    rec.update({"local_path": str(path), "sha256": sha256_of(data), "size_bytes": len(data), "page_count": extracted["page_count"], "checks": {"pages": missing_pages(extracted["text"])}})
    if extracted["text"]:
        text_path = path.with_suffix(path.suffix + ".txt")
        text_path.write_text(extracted["text"], encoding="utf-8")
        rec["text_path"], rec["text_chars"] = str(text_path), len(extracted["text"])
    if rec["checks"]["pages"]["missing"]:
        fields = {"status": "missing_pages", "notes": f"Pages {', '.join(map(str, rec['checks']['pages']['missing']))} of {rec['checks']['pages']['expected']} not in the file"}
    store._save(workspace_id, [rec if d.get("document_id") == document_id else d for d in store.list(workspace_id)])
    return store.update(workspace_id, document_id, fields, by=by)


def add_local(team_root, workspace_id: str, path: str, *, category: str, subcategory: Optional[str] = None, borrower_ref: Optional[str] = None, by: str = "ashley") -> Dict[str, Any]:
    """Ashley adds a file from her own machine (Upload Missing Doc). Copies it into the private folder; the source stays untouched."""
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(path)
    if src.suffix.lower() not in (".pdf", ".jpg", ".jpeg", ".png"):
        raise ValueError("file type not accepted")
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of {CATEGORIES}")
    data = src.read_bytes()
    store = DocumentStore(team_root)
    digest = sha256_of(data)
    twin = next((d for d in store.list(workspace_id) if d.get("sha256") == digest), None)
    rec = {"document_id": new_id("doc"), "website_document_id": None, "submission_id": None, "workspace_id": workspace_id, "category": category,
           "subcategory": subcategory, "borrower_ref": borrower_ref, "original_filename": src.name[:160],
           "display_name": f"{now_iso()[:10]}_{_slug(subcategory or CATEGORY_FOLDER[category])}_{len(store.list(workspace_id)) + 1:02d}{src.suffix.lower()}",
           "storage_key": None, "mime_type": None, "size_bytes": len(data), "sha256": digest, "uploaded_at": now_iso(), "uploaded_by": by, "received_at": now_iso(),
           "status": "duplicate" if twin else "received", "classification_source": by, "notes": f"Same content as {twin['display_name']}" if twin else "",
           "local_path": None, "text_path": None, "text_chars": 0, "page_count": None, "checks": {}, "history": []}
    if not twin:
        dest = _local_path(team_root, workspace_id, rec)
        shutil.copyfile(src, dest)
        rec["local_path"] = str(dest)
        extracted = extract_text(dest)
        rec["page_count"] = extracted["page_count"]
        if extracted["text"]:
            tp = dest.with_suffix(dest.suffix + ".txt")
            tp.write_text(extracted["text"], encoding="utf-8")
            rec["text_path"], rec["text_chars"] = str(tp), len(extracted["text"])
        cls = classify(src.name, extracted["text"], category, subcategory)
        rec["subcategory"] = cls["subcategory"]
        pages = missing_pages(extracted["text"])
        rec["checks"]["pages"] = pages
        if pages["missing"]:
            rec["status"], rec["notes"] = "missing_pages", f"Pages {', '.join(map(str, pages['missing']))} of {pages['expected']} not in the file"
    else:
        rec["local_path"] = twin.get("local_path")
    return store.add(workspace_id, rec)


# ── Inventory: what arrived vs what the submission and activated rules expect ─────────────

_RULE_BASIS = {
    # (program, expected key) -> rule id whose section must be ACTIVE for the item to count as source-backed
    ("fannie", "paystub"): "fannie.docs.paystub", ("fannie", "w2"): "fannie.docs.w2", ("fannie", "aus_findings"): "fannie.du.findings_report",
    ("fannie", "bank_statement"): "fannie.assets.statement_period",
    ("freddie", "paystub"): "freddie.docs.paystub", ("freddie", "w2"): "freddie.docs.w2", ("freddie", "bank_statement"): "freddie.assets.depository_documentation",
    ("freddie", "aus_findings"): "freddie.lpa.feedback_certificate",
    ("fha", "paystub"): "fha.total.income.traditional_documentation", ("fha", "bank_statement"): "fha.total.assets.checking_savings_documentation",
    ("va", "paystub"): "va.docs.standard_verification", ("va", "bank_statement"): "va.assets.verification",
    ("usda", "paystub"): "usda.docs.paystub_30_days", ("usda", "w2"): "usda.docs.base_wages_documentation", ("usda", "bank_statement"): "usda.assets.depository_documentation",
    ("usda", "aus_findings"): "usda.gus.recommendation",
}


def _rule_active(program: str, rule_id: str, rule_check: Optional[Callable[[str, str], bool]]) -> bool:
    if rule_check is not None:
        return bool(rule_check(program, rule_id))
    try:
        from . import sources

        rules = {r["rule_id"].split("@")[0]: r for r in sources.load_rules(program)}
        rule = rules.get(rule_id)
        return bool(rule) and sources.is_active(program, rule["section"])
    except Exception:  # noqa: BLE001
        return False


def expected_documents(submission: Dict[str, Any], *, program: Optional[str], rule_check: Optional[Callable[[str, str], bool]] = None) -> List[Dict[str, Any]]:
    """What a submission leads us to expect. ``required`` only when an ACTIVE rule backs it; otherwise SOURCE_GAP."""
    program = (program or "").lower()
    income = submission.get("lo_stated_income") or submission.get("income") or []
    purchase = (submission.get("transaction_type") or (submission.get("loan") or {}).get("transactionType")) == "purchase"
    lo_docs = {d for s in income for d in (s.get("documentsIncluded") or [])}
    wants: List[Dict[str, Any]] = [
        {"key": "loan_application", "label": "Loan application (1003)", "category": "loan_application", "subcategory": None, "basis": "submission workflow"},
        {"key": "credit_report", "label": "Credit report", "category": "credit_report", "subcategory": None, "basis": "submission workflow"},
        {"key": "aus_findings", "label": "AUS findings", "category": "aus_findings", "subcategory": None, "basis": None},
    ]
    types = {s.get("incomeType") for s in income}
    if "w2" in types or "paystubs" in lo_docs:
        wants.append({"key": "paystub", "label": "Most recent paystub(s)", "category": "income", "subcategory": "paystub", "basis": None})
    if "w2" in types or "w2s" in lo_docs:
        wants.append({"key": "w2", "label": "W-2(s)", "category": "income", "subcategory": "w2", "basis": None})
    if "1099" in types or "1099s" in lo_docs:
        wants.append({"key": "1099", "label": "1099(s)", "category": "income", "subcategory": "1099", "basis": "LO listed"})
    if types & {"self_employed"} or "tax_returns" in lo_docs:
        wants.append({"key": "tax_return", "label": "Tax returns", "category": "income", "subcategory": "tax_return", "basis": "LO listed" if "tax_returns" in lo_docs else None})
    if types & {"retirement_pension", "social_security"} or "award_letter" in lo_docs:
        wants.append({"key": "award_letter", "label": "Award letter", "category": "income", "subcategory": "other", "basis": "LO listed" if "award_letter" in lo_docs else None})
    if submission.get("funds_to_close") or submission.get("assets") or "bank_statements" in lo_docs:
        wants.append({"key": "bank_statement", "label": "Bank statement(s) for stated assets", "category": "assets", "subcategory": "bank_statement", "basis": None})
    if purchase:
        wants.append({"key": "purchase_contract", "label": "Purchase contract", "category": "purchase_contract", "subcategory": None, "basis": "submission workflow"})
    for w in wants:
        rule = _RULE_BASIS.get((program, w["key"]))
        if rule and _rule_active(program, rule, rule_check):
            w["basis"], w["required"] = rule, True
        elif w["basis"] in ("submission workflow", "LO listed"):
            w["required"] = False  # expected because the LO / the transaction says so — not a guideline requirement
        else:
            w["basis"], w["required"] = "SOURCE_GAP", False
    return wants


def _matches(doc: Dict[str, Any], want: Dict[str, Any]) -> bool:
    if doc.get("status") in ("duplicate", "not_needed"):
        return False
    if doc.get("category") != want["category"]:
        return False
    return want["subcategory"] in (None, doc.get("subcategory"))


def inventory(team_root, workspace_id: str, submission: Dict[str, Any], *, program: Optional[str], rule_check: Optional[Callable[[str, str], bool]] = None) -> Dict[str, Any]:
    """Received / missing / needs clarification, in Ashley's words, with the basis for every expectation."""
    docs = DocumentStore(team_root).list(workspace_id)
    wants = expected_documents(submission, program=program, rule_check=rule_check)
    received, missing, clarify = [], [], []
    for w in wants:
        hits = [d for d in docs if _matches(d, w)]
        if hits:
            problems = [d for d in hits if d.get("status") in ("missing_pages", "unreadable", "needs_review")]
            entry = {**w, "documents": [d["document_id"] for d in hits], "display": [d["display_name"] for d in hits]}
            if problems:
                entry["problem"] = "; ".join(f"{d['display_name']}: {STATUS_LABEL[d['status']]}" + (f" — {d['notes']}" if d.get("notes") else "") for d in problems)
                clarify.append(entry)
            else:
                received.append(entry)
        elif w["required"]:
            missing.append(w)
        else:
            clarify.append({**w, "reason": "expected from the submission, but not a source-backed requirement" if w["basis"] == "SOURCE_GAP" else f"expected ({w['basis']})"})
    unexpected = [d for d in docs if d.get("status") not in ("duplicate", "not_needed") and not any(_matches(d, w) for w in wants)]
    counts = {s: sum(1 for d in docs if d.get("status") == s) for s in STATUSES}
    return {
        "workspace_id": workspace_id, "received": received, "missing": missing, "needs_clarification": clarify,
        "other_documents": [{"document_id": d["document_id"], "display_name": d["display_name"], "category": d["category"], "status": d["status"]} for d in unexpected],
        "counts": {"documents": sum(1 for d in docs if d.get("status") != "duplicate"), **counts},
        "lines": [f"{w['label']} — {'✓ ' + ', '.join(w['display'])}" for w in received] + [f"{w['label']} — ⚠ {w['problem']}" for w in clarify if w.get("problem")]
                 + [f"{w['label']} — missing ({w['basis']})" for w in missing] + [f"{w['label']} — {w['reason']}" for w in clarify if w.get("reason")],
        "note": "Only items backed by an ACTIVE source rule are 'missing'; everything else is a clarification, never an invented requirement.",
    }


def ashley_documents(team_root, workspace_id: str) -> Dict[str, Any]:
    """Grouped, plain-English view for the file screen (no storage keys)."""
    docs = DocumentStore(team_root).list(workspace_id)
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for d in docs:
        groups.setdefault(d.get("category") or "other", []).append({
            "document_id": d["document_id"], "display_name": d["display_name"], "original_filename": d["original_filename"],
            "subcategory": SUBTYPE_LABEL.get(d.get("subcategory") or "", d.get("subcategory")), "borrower": d.get("borrower_ref"),
            "status": d["status"], "status_label": STATUS_LABEL[d["status"]], "notes": d.get("notes") or "", "received_at": d.get("received_at"),
            "pages": d.get("page_count"), "local_path": d.get("local_path"), "text_path": d.get("text_path"),
        })
    return {"groups": [{"category": c, "label": CATEGORY_LABEL[c], "documents": groups.get(c, [])} for c in CATEGORIES if groups.get(c)],
            "count": sum(1 for d in docs if d.get("status") != "duplicate")}
