"""Program-agnostic official-source layer (versioned cache, checksums, rules, lifecycle).

One code path for every agency program. A *program* is identified by a
namespace (``fannie``, ``freddie``, ``fha``, ``va``, ``usda``) and ships two
metadata files under ``plugins/flo-team/knowledge/<program>/``:

* ``sections.json`` — per-section metadata (official URL, page/revision
  date, retrieval timestamp, checksums, cache ref, capture method, shipped
  lifecycle ``detected``). Written by the fetch/ingest scripts, never by a bot.
* ``rules.json`` — paraphrased rule records with an ``anchor`` phrase that the
  regression step verifies against the privately cached official text.
  Every record carries ``program``, and for FHA also ``underwriting_method``
  (``total`` | ``manual``), so a rule can never be selected for the wrong
  program or method.

Official text lives only in the private cache
``<hermes root>/flo/sources/cache/<program>/<section>.txt`` (+ ``.html``/``.pdf``
when applicable). Per-install activation state is :class:`knowledge.KnowledgeState`.
Lifecycle: detected → pending_review → regression → approval → active, with a
human approver identity recorded at approval/activation (``identity.py``).

``fannie.py`` keeps its public API by delegating here with ``program="fannie"``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .knowledge import KnowledgeState
from .manifest import hermes_root
from .store import now_iso

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"

PROGRAMS: Dict[str, Dict[str, Any]] = {
    "fannie": {"display": "Fannie Mae Conventional", "agency": "Fannie Mae", "source_title": "Fannie Mae Selling Guide",
               "aus_systems": ["DU"], "underwriting_methods": ["du", "manual"]},
    "freddie": {"display": "Freddie Mac Conventional", "agency": "Freddie Mac", "source_title": "Freddie Mac Single-Family Seller/Servicer Guide",
                "aus_systems": ["LPA"], "underwriting_methods": ["lpa", "manual"]},
    "fha": {"display": "FHA", "agency": "HUD / FHA", "source_title": "FHA Single Family Housing Policy Handbook 4000.1",
            "aus_systems": ["TOTAL"], "underwriting_methods": ["total", "manual"]},
    "va": {"display": "VA", "agency": "U.S. Department of Veterans Affairs", "source_title": "VA Pamphlet 26-7 Lenders Handbook",
           "aus_systems": ["AUS"], "underwriting_methods": ["aus", "manual"]},
    "usda": {"display": "USDA Guaranteed (SFHGLP)", "agency": "USDA Rural Development", "source_title": "HB-1-3555 SFH Guaranteed Loan Program Technical Handbook",
             "aus_systems": ["GUS"], "underwriting_methods": ["gus", "manual"]},
}


def program_spec(program: str) -> Dict[str, Any]:
    key = (program or "").lower()
    if key not in PROGRAMS:
        raise KeyError(f"unknown program {program!r}; known: {sorted(PROGRAMS)}")
    return PROGRAMS[key]


def _safe_section(section: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", section)


def sections_path(program: str) -> Path:
    return KNOWLEDGE_DIR / program.lower() / "sections.json"


def rules_path(program: str) -> Path:
    return KNOWLEDGE_DIR / program.lower() / "rules.json"


def load_sections(program: str) -> Dict[str, Dict[str, Any]]:
    path = sections_path(program)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("sections", {})


def load_rules(program: str) -> List[Dict[str, Any]]:
    path = rules_path(program)
    if not path.exists():
        return []
    rules = json.loads(path.read_text(encoding="utf-8")).get("rules", [])
    for rule in rules:
        rule.setdefault("program", program.lower())
    return rules


def cache_dir(program: str, root: Optional[Path] = None) -> Path:
    root = root or hermes_root()
    return Path(root) / "flo" / "sources" / "cache" / program.lower()


def cached_text(program: str, section: str, root: Optional[Path] = None) -> Optional[str]:
    path = cache_dir(program, root) / f"{_safe_section(section)}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else None


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Recording a retrieved section (fetch scripts / browser captures)
# ---------------------------------------------------------------------------

def record_section(
    *,
    program: str,
    section: str,
    title: str,
    official_url: str,
    text: str,
    page_date: Optional[str],
    edition: str,
    capture_method: str,
    raw: Optional[bytes] = None,
    raw_suffix: str = ".html",
    rights: str,
    root: Optional[Path] = None,
    notes: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write the private cache files and update ``sections.json`` (lifecycle → detected on change)."""
    program = program.lower()
    spec = program_spec(program)
    cache = cache_dir(program, root)
    cache.mkdir(parents=True, exist_ok=True)
    stem = _safe_section(section)
    text = re.sub(r"\s+", " ", text).strip()
    (cache / f"{stem}.txt").write_text(text, encoding="utf-8")
    if raw is not None:
        (cache / f"{stem}{raw_suffix}").write_bytes(raw)
    path = sections_path(program)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema_version": 1, "program": program, "sections": {}}
    record = data["sections"].get(section, {})
    sha_text = sha(text)
    changed = record.get("checksum_text") not in (None, sha_text)
    now = now_iso()
    record.update({
        "program": program, "section": section, "title": title, "official_url": official_url, "source_title": spec["source_title"],
        "edition": edition, "page_date": page_date, "retrieved_at": now, "checksum_text": sha_text,
        "checksum_raw": sha(raw.decode("utf-8", "replace")) if raw is not None else None, "text_chars": len(text),
        "cache_ref": f"flo/sources/cache/{program}/{stem}.txt", "capture_method": capture_method, "rights": rights,
        "lifecycle": "detected" if (changed or "lifecycle" not in record) else record["lifecycle"],
        "revision_id": f"{program}-{stem.lower()}-{sha_text[:12]}",
    })
    if notes:
        record["notes"] = notes
    if extra:
        record.update({k: v for k, v in extra.items() if k not in record or k in ("effective_date", "underwriting_method", "version", "version_note", "mandatory_date", "issued_date", "section_number")})
    # Versioned copies of the text are kept so revisions can be diffed later (sourcediff.py).
    (cache / f"{stem}.{sha_text[:12]}.txt").write_text(text, encoding="utf-8")
    if changed and record.get("lifecycle") not in (None, "detected"):
        record["note"] = f"content changed on re-fetch; previous revision demoted to detected at {now}"
    data["sections"][section] = record
    data["generated_at"] = now
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return record


# ---------------------------------------------------------------------------
# Status / regression
# ---------------------------------------------------------------------------

@dataclass
class SectionStatus:
    program: str
    section: str
    title: str
    revision_id: Optional[str]
    lifecycle: str
    official_url: Optional[str]
    page_date: Optional[str]
    retrieved_at: Optional[str]
    checksum: Optional[str]
    usable: bool
    reason: str
    effective_date: Optional[str] = None
    in_force: Optional[bool] = None      # False when the recorded effective date is still in the future
    edition: Optional[str] = None
    underwriting_method: Optional[str] = None
    version: Optional[str] = None        # e.g. update-17 / update-18 for versioned sections
    resolution: Optional[str] = None     # CURRENT | FUTURE | SUPERSEDED | EARLY_IMPLEMENTATION (when resolved by date)
    section_number: Optional[str] = None
    mandatory_date: Optional[str] = None
    version_note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()

    @property
    def cautions(self) -> List[str]:
        out = []
        if self.resolution == "FUTURE":
            out.append(f"FUTURE — NOT YET EFFECTIVE: {program_spec(self.program)['source_title']} {self.section_number or self.section} ({self.version or 'later version'}) "
                       f"is effective {self.effective_date}" + (f"; the transmittal permits immediate implementation but mandates it by {self.mandatory_date}" if self.mandatory_date else "") + ".")
        elif self.resolution == "EARLY_IMPLEMENTATION":
            out.append(f"EARLY IMPLEMENTATION elected: {self.section_number or self.section} ({self.version}) applied before its mandatory date {self.mandatory_date}; record the lender's election.")
        elif self.resolution == "SUPERSEDED":
            out.append(f"SUPERSEDED: {self.section_number or self.section} ({self.version}) is not the version in force on the relevant date.")
        elif self.in_force is False and self.resolution is None:
            out.append(f"{program_spec(self.program)['source_title']} {self.section} as captured is effective {self.effective_date}, which is after today; "
                       "the currently in-force text of this section is not in the private cache (SOURCE_GAP for files governed by the earlier version).")
        return out


def _parse_date(value: Optional[str]):
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%y", "%m-%d-%Y"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def _in_force(effective: Optional[str]) -> Optional[bool]:
    d = _parse_date(effective)
    if d is None:
        return None
    return d <= date.today()


def _safe_id(value: str) -> bool:
    try:
        from .store import safe_id

        safe_id(value)
        return True
    except ValueError:
        return False


def section_status(program: str, section: str, state: Optional[KnowledgeState] = None, root: Optional[Path] = None, *,
                   relevant_date: Optional[Any] = None, early_implementation: bool = False) -> SectionStatus:
    """Status of one section key, or of a bare section number resolved to the version in force on ``relevant_date``."""
    program = program.lower()
    sections = load_sections(program)
    meta = sections.get(section)
    resolution = None
    if not meta:
        res = resolve_section(program, section, relevant_date=relevant_date, early_implementation=early_implementation)
        if res.get("key"):
            section, meta, resolution = res["key"], sections[res["key"]], res["resolution"]
        elif res.get("candidates"):
            # Only future versions exist for the relevant date: report the earliest as FUTURE and unusable.
            first = res["candidates"][0]
            section, meta, resolution = first["key"], sections[first["key"]], "FUTURE"
    if not meta:
        return SectionStatus(program, section, "", None, "missing", None, None, None, None, False, f"section not in the shipped {program} slice")
    if resolution is None and meta.get("version"):
        res = resolve_section(program, meta.get("section_number") or section_number(section), relevant_date=relevant_date, early_implementation=early_implementation)
        row = next((c for c in res["candidates"] if c["key"] == section), None)
        resolution = row["status"] if row else None
    rev_id = meta["revision_id"]
    lifecycle = meta.get("lifecycle", "detected")
    if state is not None:
        row = state.docs.get(rev_id) if _safe_id(rev_id) else None
        if row:
            lifecycle = row.get("lifecycle", lifecycle)
    text = cached_text(program, section, root)
    common = (program, section, meta["title"], rev_id)
    tail = (meta.get("official_url"), meta.get("page_date"), meta.get("retrieved_at"), meta.get("checksum_text"))
    extra = {"effective_date": meta.get("effective_date") or meta.get("page_date"), "in_force": _in_force(meta.get("effective_date") or meta.get("page_date")),
             "edition": meta.get("edition"), "underwriting_method": meta.get("underwriting_method") or _method_for(program, section),
             "version": meta.get("version"), "resolution": resolution, "section_number": meta.get("section_number") or section_number(section),
             "mandatory_date": meta.get("mandatory_date"), "version_note": meta.get("version_note")}
    if text is None:
        return SectionStatus(*common, lifecycle, *tail, False, "official text not in the private cache on this machine", **extra)
    if sha(text) != meta.get("checksum_text"):
        return SectionStatus(*common, "STALE_SOURCE", *tail, False, "cached text no longer matches the recorded checksum; re-fetch and re-review", **extra)
    usable = lifecycle == "active"
    if usable and resolution in ("FUTURE", "SUPERSEDED"):
        # An active revision that is not the version in force on the relevant date is citable as context only.
        return SectionStatus(*common, lifecycle, *tail, False, f"active but {resolution.lower()} for the relevant date; not applicable", **extra)
    return SectionStatus(*common, lifecycle, *tail, usable, "active" if usable else f"revision is {lifecycle}; not usable until a human activates it", **extra)


def _method_for(program: str, section: str) -> Optional[str]:
    """FHA sections are scoped to an underwriting method by their Handbook location."""
    if program == "fha":
        if section.upper().startswith("II.A.4."):
            return "total"
        if section.upper().startswith("II.A.5."):
            return "manual"
    return None


# ---------------------------------------------------------------------------
# Effective-date resolution across section versions (e.g. FHA Update 17 vs Update 18)
# ---------------------------------------------------------------------------

RESOLUTIONS = ("CURRENT", "FUTURE", "SUPERSEDED", "EARLY_IMPLEMENTATION")


def section_number(key: str) -> str:
    """``II.A.4.c@update-18`` → ``II.A.4.c``; unversioned keys are their own number."""
    return key.split("@", 1)[0]


def section_versions(program: str, number: str) -> List[Dict[str, Any]]:
    """Every recorded version of a section number, oldest effective date first."""
    rows = [dict(meta, key=key) for key, meta in load_sections(program).items() if section_number(key) == section_number(number)]
    rows.sort(key=lambda m: (_parse_date(m.get("effective_date") or m.get("page_date")) or date.min, m.get("issued_date") or ""))
    return rows


def resolve_section(program: str, number: str, *, relevant_date: Optional[Any] = None, early_implementation: bool = False) -> Dict[str, Any]:
    """Pick the version of ``number`` that governs on ``relevant_date`` (default today).

    Deterministic rule: the applicable version is the latest one whose effective date is on or
    before the relevant date. A version whose effective date is later is FUTURE — NOT YET
    EFFECTIVE. FHA nuance preserved from the Update 18 transmittal ("may be implemented
    immediately, but must be implemented no later than November 10, 2026"): when the caller
    states ``early_implementation=True`` and the relevant date is on/after the version's issued
    date, that version is selected and labelled EARLY_IMPLEMENTATION. Versions never blend.
    """
    program = program.lower()
    when = _parse_date(relevant_date) if not isinstance(relevant_date, date) else relevant_date
    when = when or date.today()
    versions = section_versions(program, number)
    if not versions:
        return {"program": program, "section_number": section_number(number), "relevant_date": when.isoformat(), "key": None, "resolution": None,
                "candidates": [], "reason": "section not recorded"}
    labelled = []
    chosen = None
    for meta in versions:
        eff = _parse_date(meta.get("effective_date") or meta.get("page_date"))
        issued = _parse_date(meta.get("issued_date"))
        if eff is not None and eff <= when:
            status = "CURRENT"
        elif early_implementation and meta.get("mandatory_date") and issued is not None and issued <= when:
            status = "EARLY_IMPLEMENTATION"
        else:
            status = "FUTURE"
        labelled.append({"key": meta["key"], "version": meta.get("version"), "effective_date": meta.get("effective_date"), "mandatory_date": meta.get("mandatory_date"),
                         "issued_date": meta.get("issued_date"), "version_note": meta.get("version_note"), "status": status})
    applicable = [row for row in labelled if row["status"] in ("CURRENT", "EARLY_IMPLEMENTATION")]
    if applicable:
        chosen = applicable[-1]  # latest effective (list is sorted by effective date)
        for row in applicable[:-1]:
            row["status"] = "SUPERSEDED"
    trigger = "case number assignment date" if program == "fha" else "relevant date"
    return {
        "program": program, "section_number": section_number(number), "relevant_date": when.isoformat(), "relevant_date_basis": trigger,
        "early_implementation": bool(early_implementation), "key": chosen["key"] if chosen else None,
        "resolution": chosen["status"] if chosen else None, "candidates": labelled,
        "reason": ("selected the latest version effective on or before the relevant date" if chosen and chosen["status"] == "CURRENT"
                   else "early implementation elected (transmittal permits immediate implementation)" if chosen
                   else "no version is effective on the relevant date"),
    }


def resolve_rule(program: str, topic: str, *, relevant_date: Optional[Any] = None, underwriting_method: Optional[str] = None,
                 early_implementation: bool = False, state: Optional[KnowledgeState] = None, root: Optional[Path] = None, limit: int = 8) -> Dict[str, Any]:
    """Topic → rule records split by effective-date resolution: ``applicable`` (the version in force
    on the relevant date, ACTIVE or not, with usability flags), ``future`` (not yet effective),
    ``superseded``. Never returns a blended answer."""
    program = program.lower()
    matched = match_rules(program, topic, underwriting_method=underwriting_method, limit=limit * 2)
    out: Dict[str, Any] = {"program": program, "topic": topic, "relevant_date": None, "applicable": [], "future": [], "superseded": [], "resolutions": {}}
    for rule in matched:
        number = section_number(rule["section"])
        res = out["resolutions"].get(number) or resolve_section(program, number, relevant_date=relevant_date, early_implementation=early_implementation)
        out["resolutions"][number] = res
        out["relevant_date"] = res["relevant_date"]
        status_row = next((c for c in res["candidates"] if c["key"] == rule["section"]), None)
        label = status_row["status"] if status_row else ("CURRENT" if res["key"] in (None, rule["section"]) else "FUTURE")
        st = section_status(program, rule["section"], state, root)
        entry = {**rule, "resolution": label, "usable": st.usable, "lifecycle": st.lifecycle, "effective_date": st.effective_date, "version": st.version}
        if label in ("CURRENT", "EARLY_IMPLEMENTATION"):
            out["applicable"].append(entry)
        elif label == "FUTURE":
            out["future"].append(entry)
        else:
            out["superseded"].append(entry)
    return out


def is_active(program: str, section: str, state: Optional[KnowledgeState] = None, root: Optional[Path] = None, *,
              relevant_date: Optional[Any] = None, early_implementation: bool = False) -> bool:
    return section_status(program, section, state, root, relevant_date=relevant_date, early_implementation=early_implementation).usable


def default_state() -> Optional[KnowledgeState]:
    root = hermes_root()
    return KnowledgeState(root / "flo" / "team") if root else None


def regression(program: str, section: str, root: Optional[Path] = None) -> Dict[str, Any]:
    text = cached_text(program, section, root)
    rules = [r for r in load_rules(program) if r["section"] == section]
    if text is None:
        return {"program": program, "section": section, "ok": False, "checked": 0, "failed": [r["rule_id"] for r in rules], "reason": "no cached text", "receipt": None}
    norm = _norm(text)
    failed = [r["rule_id"] for r in rules if _norm(r["anchor"]) not in norm]
    ok = not failed and bool(rules)
    receipt = None
    if ok:
        blob = json.dumps({"program": program, "section": section, "rules": sorted(r["rule_id"] for r in rules), "checksum": sha(text)}, sort_keys=True)
        receipt = "regr_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return {"program": program, "section": section, "ok": ok, "checked": len(rules), "failed": failed, "receipt": receipt, "at": now_iso()}


def active_sections(program: str, state: Optional[KnowledgeState] = None, root: Optional[Path] = None) -> List[str]:
    return [s for s in load_sections(program) if section_status(program, s, state, root).usable]


def all_program_statuses(state: Optional[KnowledgeState] = None, root: Optional[Path] = None) -> Dict[str, List[Dict[str, Any]]]:
    return {p: [section_status(p, s, state, root).to_dict() for s in load_sections(p)] for p in PROGRAMS}


def checks_for(program: str, state: Optional[KnowledgeState] = None, root: Optional[Path] = None, *,
               relevant_date: Optional[Any] = None, early_implementation: bool = False):
    """``(active_check, section_meta)`` callables bound to one program and one relevant date — the shape every workbench takes.

    A bare section number (``II.A.4.c``) resolves to the version in force on ``relevant_date``
    (FHA: the case number assignment date); a versioned key is checked as-is.
    """
    program = program.lower()
    kw = {"relevant_date": relevant_date, "early_implementation": early_implementation}
    return (lambda s: is_active(program, s, state, root, **kw)), (lambda s: section_status(program, s, state, root, **kw).to_dict())


# ---------------------------------------------------------------------------
# Rule matching (topic → rule records) shared by every program
# ---------------------------------------------------------------------------

TOPIC_WORDS: Dict[str, tuple] = {
    "base_income": ("base", "salary", "salaried", "hourly", "wage", "w-2", "w2", "employment income", "non-fluctuating", "fluctuating"),
    "base_income_calculation": ("calculate", "calculation", "monthly income", "average", "pay frequency", "biweekly", "bi-weekly", "weekly", "semi-monthly", "hours", "ytd", "year-to-date", "trend", "raise"),
    "employment_documentation": ("paystub", "pay stub", "voe", "verification of employment", "1005", "document", "documentation", "w-2", "w2", "wvoe", "evoe", "pcv"),
    "employment_history": ("history", "gap", "gaps", "job change", "two year", "two-year", "raise", "12 months", "less than 12"),
    "overtime_bonus": ("overtime", "bonus", "commission", "tip"),
    "assets": ("asset", "bank statement", "deposit", "checking", "savings", "vod", "1006", "funds", "statement"),
    "assets_large_deposits": ("large deposit", "deposit"),
    "reserves": ("reserve", "pitia", "piti"),
    "document_age": ("age", "four months", "120 days", "stale", "expired"),
    "du_tolerances": ("tolerance", "resubmit", "resubmission", "dti"),
    "du": ("du", "desktop underwriter", "findings", "approve/eligible", "validation service"),
    "lpa": ("lpa", "loan product advisor", "feedback certificate", "risk class", "accept", "caution", "findings"),
    "lpa_tolerances": ("tolerance", "resubmit", "resubmission", "dti"),
    "total": ("total", "scorecard", "accept", "refer", "feedback certificate", "findings", "aus"),
    "aus": ("aus", "automated underwriting", "accept", "approve", "refer", "findings"),
    "gus": ("gus", "guaranteed underwriting", "accept", "refer", "findings"),
    "manual_underwriting": ("manual", "manually", "compensating", "ratio", "31/43", "downgrade"),
    "income_general": ("continuance", "stable", "predictable", "income", "dependable", "effective income", "three years"),
    "dti": ("dti", "debt-to-income", "debt to income", "ratio", "41", "45", "29", "31", "43"),
    "residual_income": ("residual", "family size", "region", "family support", "26-6393", "loan analysis"),
    "household_income": ("household", "annual income", "adjusted annual", "income limit", "eligibility income", "$480", "student"),
    "repayment_income": ("repayment income", "repayment", "qualifying", "parties to the note"),
}


def match_rules(program: str, topic: str, rules: Optional[List[Dict[str, Any]]] = None, *, underwriting_method: Optional[str] = None, limit: int = 6) -> List[Dict[str, Any]]:
    rules = rules if rules is not None else load_rules(program)
    q = _norm(topic)
    scored = []
    for rule in rules:
        if rule.get("program", program.lower()) != program.lower():
            continue  # a rule from another program can never be selected
        if underwriting_method and rule.get("underwriting_method") and rule["underwriting_method"] != underwriting_method:
            continue  # FHA TOTAL rules never answer a manual question and vice versa
        score = 0
        for word in TOPIC_WORDS.get(rule["topic"], ()):
            if word in q:
                score += 2
        if rule["topic"].replace("_", " ") in q:
            score += 3
        if any(w in q for w in _norm(rule.get("title", "")).split()):
            score += 1
        if score:
            scored.append((score, rule))
    scored.sort(key=lambda s: -s[0])
    return [r for _, r in scored[:limit]]
