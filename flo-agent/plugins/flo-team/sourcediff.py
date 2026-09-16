"""Source-version comparison — what changed when a new guide revision is detected.

Inputs are two recorded revisions of one program (the shipped ``sections.json``
plus the versioned cache copies ``<section>.<sha12>.txt`` that
``sources.record_section`` writes). Output:

    new_sections, removed_sections, changed_sections (with normalized-text
    similarity and the changed paragraphs), unchanged_sections,
    changed_rule_records (anchors that no longer match the new text),
    affected_calculators, affected_workflows, affected_tests (via impact.py)
    and a summary sentence.

Two comparison modes:

* :func:`compare_versions` — two version tags of a versioned program
  (e.g. FHA ``update-17`` vs ``update-18``);
* :func:`compare_snapshots` — a previous ``sections.json`` snapshot (saved by
  the fetchers as ``sections.<sha>.json`` / passed in) vs the current one, for
  programs whose sections are re-fetched in place (Fannie, Freddie, VA, USDA).
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import impact, sources


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _paragraphs(text: str) -> List[str]:
    # The cache stores one normalized line; split on sentence-ish boundaries for a readable diff.
    return [p.strip() for p in re.split(r"(?<=[.;:])\s+(?=[A-Z(•])", text or "") if p.strip()]


def _cached(program: str, key: str, checksum: Optional[str], root: Optional[Path]) -> Optional[str]:
    cache = sources.cache_dir(program, root)
    stem = sources._safe_section(key)
    if checksum:
        versioned = cache / f"{stem}.{checksum[:12]}.txt"
        if versioned.exists():
            return versioned.read_text(encoding="utf-8")
    current = cache / f"{stem}.txt"
    if current.exists() and (not checksum or sources.sha(current.read_text(encoding="utf-8")) == checksum):
        return current.read_text(encoding="utf-8")
    return None


def diff_texts(old: str, new: str, *, max_items: int = 40) -> Dict[str, Any]:
    a, b = _paragraphs(_norm(old)), _paragraphs(_norm(new))
    ratio = difflib.SequenceMatcher(None, _norm(old), _norm(new), autojunk=False).quick_ratio() if old and new else 0.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    added: List[str] = []
    removed: List[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            removed.extend(a[i1:i2])
        if tag in ("replace", "insert"):
            added.extend(b[j1:j2])
    return {"similarity": round(ratio, 4), "added": added[:max_items], "removed": removed[:max_items], "added_count": len(added), "removed_count": len(removed)}


def _compare(program: str, old: Dict[str, Dict[str, Any]], new: Dict[str, Dict[str, Any]], *, root: Optional[Path], key_fn=lambda k: k, state=None) -> Dict[str, Any]:
    old_keys = {key_fn(k): k for k in old}
    new_keys = {key_fn(k): k for k in new}
    new_sections = sorted(set(new_keys) - set(old_keys))
    removed_sections = sorted(set(old_keys) - set(new_keys))
    changed: List[Dict[str, Any]] = []
    unchanged: List[str] = []
    for number in sorted(set(old_keys) & set(new_keys)):
        o, n = old[old_keys[number]], new[new_keys[number]]
        if o.get("checksum_text") == n.get("checksum_text"):
            unchanged.append(number)
            continue
        ot = _cached(program, old_keys[number], o.get("checksum_text"), root)
        nt = _cached(program, new_keys[number], n.get("checksum_text"), root)
        entry = {"section": number, "old_key": old_keys[number], "new_key": new_keys[number], "old_checksum": (o.get("checksum_text") or "")[:12], "new_checksum": (n.get("checksum_text") or "")[:12],
                 "old_effective": o.get("effective_date") or o.get("page_date"), "new_effective": n.get("effective_date") or n.get("page_date"),
                 "old_chars": o.get("text_chars"), "new_chars": n.get("text_chars")}
        entry["text_diff"] = diff_texts(ot, nt) if ot is not None and nt is not None else {"note": "cached text for one or both revisions is not on this machine"}
        changed.append(entry)
    # Rule records whose anchor no longer matches the new text.
    rules = sources.load_rules(program)
    changed_rules: List[Dict[str, Any]] = []
    for rule in rules:
        number = key_fn(rule["section"])
        if number not in new_keys:
            continue
        nt = _cached(program, new_keys[number], new[new_keys[number]].get("checksum_text"), root)
        if nt is None:
            continue
        if _norm(rule["anchor"]) not in _norm(nt):
            changed_rules.append({"rule_id": rule["rule_id"], "section": rule["section"], "anchor": rule["anchor"], "problem": "anchor not found in the new text"})
    imp = impact.affected(program, changed_rule_ids=[r["rule_id"] for r in changed_rules], changed_sections=[c["new_key"] for c in changed] + new_sections + removed_sections, state=state, root=root)
    display = sources.program_spec(program)["display"]
    summary = (f"{display} update: {len(new_sections)} new, {len(removed_sections)} removed, {len(changed)} changed section(s); "
               f"{len(changed_rules)} rule record(s) need re-anchoring; affects {imp['active_rule_count']} active rule(s), {len(imp['affected_calculators'])} calculator(s) and "
               f"{len(imp['affected_tests']) + len(imp['affected_evals'])} regression scenario(s).")
    return {"program": program, "new_sections": new_sections, "removed_sections": removed_sections, "changed_sections": changed, "unchanged_sections": unchanged,
            "changed_rule_records": changed_rules, "affected_calculators": imp["affected_calculators"], "affected_workflows": imp["affected_workflows"],
            "affected_tests": imp["affected_tests"], "affected_evals": imp["affected_evals"], "impact_summary": imp["summary"], "summary": summary}


def compare_versions(program: str, old_version: str, new_version: str, *, root: Optional[Path] = None, state=None) -> Dict[str, Any]:
    sections = sources.load_sections(program)
    old = {k: v for k, v in sections.items() if v.get("version") == old_version}
    new = {k: v for k, v in sections.items() if v.get("version") == new_version}
    if not old or not new:
        raise ValueError(f"program {program} has no recorded versions {old_version!r}/{new_version!r}")
    return {"old_version": old_version, "new_version": new_version, **_compare(program, old, new, root=root, key_fn=sources.section_number, state=state)}


def compare_snapshots(program: str, old_sections: Dict[str, Dict[str, Any]], new_sections: Optional[Dict[str, Dict[str, Any]]] = None, *,
                      root: Optional[Path] = None, state=None) -> Dict[str, Any]:
    new_sections = new_sections if new_sections is not None else sources.load_sections(program)
    return {"old_version": "snapshot", "new_version": "current", **_compare(program, old_sections, new_sections, root=root, state=state)}


def snapshot_path(program: str) -> Path:
    return sources.KNOWLEDGE_DIR / program.lower() / "sections.previous.json"


def save_snapshot(program: str) -> Path:
    """Fetchers call this before re-recording sections so compare_snapshots has a baseline."""
    path = snapshot_path(program)
    current = sources.sections_path(program)
    if current.exists():
        path.write_text(current.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def compare_with_snapshot(program: str, *, root: Optional[Path] = None, state=None) -> Optional[Dict[str, Any]]:
    path = snapshot_path(program)
    if not path.exists():
        return None
    old = json.loads(path.read_text(encoding="utf-8")).get("sections", {})
    return compare_snapshots(program, old, root=root, state=state)
