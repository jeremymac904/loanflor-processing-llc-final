"""Rule impact analysis — where each guideline is encoded, so nobody has to remember.

For every rule record (``<program>.<...>`` in ``knowledge/<program>/rules.json``)
the index resolves references to:

    calculators          formulas whose ``rule_ref`` is the rule or whose ``requires_section`` is its section
    fileprep_requirements File Prep bindings (``fileprep.BINDINGS``) that cite the rule or section
    asset_bindings       asset workbench bindings citing the section
    guideline_cards      topics the rule answers (``sources.TOPIC_WORDS`` vocabulary)
    synthetic_evals      golden-loan fixtures whose program uses the section
    tests                test files that mention the rule id or section number

``affected(program, changed_rule_ids, changed_sections)`` turns a source change
into: affected_rule → affected_calculator → affected_workflow → affected_tests,
and a one-line summary such as "FHA update affects 4 active rules and 12
regression scenarios."
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from . import assets as assets_mod
from . import calc as calc_mod
from . import fileprep as fileprep_mod
from . import sources

REPO = Path(__file__).resolve().parents[2]
TESTS_DIR = REPO / "tests" / "flo"
FIXTURES_DIR = TESTS_DIR / "fixtures" / "golden_loan"
PROGRAM_FIXTURES = {"fannie": "golden_loan.json", "freddie": "freddie_golden_loan.json", "fha": "fha_golden_loan.json", "va": "va_golden_loan.json", "usda": "usda_golden_loan.json"}


def _walk_bindings(obj: Any, out: List[Dict[str, Any]], path: str = "") -> None:
    if isinstance(obj, dict):
        if "section" in obj and ("rule" in obj or "item" in obj):
            out.append({"path": path, "section": obj.get("section"), "rule": obj.get("rule"), "large_section": obj.get("large_section"), "large_rule": obj.get("large_rule"), "item": obj.get("item")})
        for k, v in obj.items():
            _walk_bindings(v, out, f"{path}.{k}" if path else str(k))


def _test_index() -> Dict[str, Set[str]]:
    """section number / rule id → test files that mention it (text scan; cached per process)."""
    global _TEST_CACHE
    try:
        return _TEST_CACHE  # type: ignore[name-defined]
    except NameError:
        pass
    index: Dict[str, Set[str]] = {}
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"\b([A-Z]\d-\d(?:\.\d)?-\d{2}|II\.A\.\d\.[a-z](?:\.[a-z]+)?(?:\([A-Z]\)\(\d\))?|\d{4}\.\d|\d{1,2}\.\d(?:-\d{1,2}\.\d{1,2})?|9-A|Chapter 4)\b", text):
            index.setdefault(m.group(1), set()).add(path.name)
        for m in re.finditer(r"\b((?:fannie|freddie|fha|va|usda)\.[a-z0-9_.]+)\b", text):
            index.setdefault(m.group(1), set()).add(path.name)
    _TEST_CACHE = index  # type: ignore[name-defined]
    return index


def rule_references(program: str, rule: Dict[str, Any]) -> Dict[str, Any]:
    program = program.lower()
    rule_id = rule["rule_id"]
    base_id = rule_id.split("@")[0]
    number = sources.section_number(rule["section"])
    calculators = [f.formula_id for f in calc_mod.FORMULAS.values() if f.program == program and (f.rule_ref in (rule_id, base_id) or (f.requires_section and sources.section_number(f.requires_section) == number))]
    fp: List[Dict[str, Any]] = []
    _walk_bindings(fileprep_mod.BINDINGS.get(program, {}), fp)
    fileprep_refs = [b["path"] for b in fp if b.get("rule") in (rule_id, base_id) or b.get("large_rule") in (rule_id, base_id)
                     or (b.get("section") and sources.section_number(b["section"]) == number) or (b.get("large_section") and sources.section_number(b["large_section"]) == number)]
    abind = assets_mod.BINDINGS.get(program, {}).get("sections", {})
    if program == "fha":
        abind = {f"{m}.{k}": v for m, d in abind.items() for k, v in d.items()}
    asset_refs = [k for k, v in abind.items() if v and sources.section_number(v) == number]
    topics = [rule.get("topic")] if rule.get("topic") else []
    tests = sorted(_test_index().get(number, set()) | _test_index().get(base_id, set()) | _test_index().get(rule_id, set()))
    evals = [PROGRAM_FIXTURES[program]] if program in PROGRAM_FIXTURES and (calculators or fileprep_refs or asset_refs) else []
    return {"rule_id": rule_id, "section": rule["section"], "section_number": number, "version": rule.get("version"), "calculators": calculators,
            "fileprep_requirements": fileprep_refs, "asset_bindings": asset_refs, "guideline_cards": topics, "synthetic_evals": evals, "tests": tests,
            "malcolm_matrices": [fileprep_mod.BINDINGS[program]["matrix"] if program != "fha" else "fha_total_golden_loan_path/fha_manual_golden_loan_path"] if fileprep_refs else []}


def index(program: str) -> List[Dict[str, Any]]:
    return [rule_references(program, r) for r in sources.load_rules(program)]


def affected(program: str, *, changed_rule_ids: Iterable[str] = (), changed_sections: Iterable[str] = (), state=None, root=None) -> Dict[str, Any]:
    program = program.lower()
    changed_rules = set(changed_rule_ids)
    changed_secs = {sources.section_number(s) for s in changed_sections}
    rows = []
    for ref in index(program):
        if ref["rule_id"] in changed_rules or ref["section_number"] in changed_secs or ref["section"] in set(changed_sections):
            rows.append(ref)
    active_rules = 0
    for r in rows:
        try:
            if sources.section_status(program, r["section"], state, root).usable:
                active_rules += 1
        except Exception:  # noqa: BLE001
            pass
    calculators = sorted({c for r in rows for c in r["calculators"]})
    workflows = sorted({w for r in rows for w in r["fileprep_requirements"]} | {a for r in rows for a in r["asset_bindings"]})
    tests = sorted({t for r in rows for t in r["tests"]})
    evals = sorted({e for r in rows for e in r["synthetic_evals"]})
    display = sources.program_spec(program)["display"]
    scenario_count = len(tests) + len(evals)
    summary = f"{display} update affects {len(rows)} rule record(s) ({active_rules} active), {len(calculators)} calculator(s), {len(workflows)} File Prep/asset binding(s) and {scenario_count} regression scenario(s)."
    return {"program": program, "affected_rules": rows, "affected_calculators": calculators, "affected_workflows": workflows, "affected_tests": tests,
            "affected_evals": evals, "active_rule_count": active_rules, "summary": summary}
