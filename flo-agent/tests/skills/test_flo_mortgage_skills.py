"""Tests for the Flo mortgage skill set (``skills/flo-mortgage/``).

Beyond the repo-wide authoring standards, these skills must:

* declare purpose, scope, provenance, a source review date, a SOURCE_GAP
  section and prohibited-inference notes;
* state ONLY what the owner-supplied source material supports — the
  milestone list and the two milestone definitions verbatim, the single
  compliance template verbatim;
* never contain fabricated income formulas, agency rules, or overlays
  (tripwire vocabulary below).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO / "skills" / "flo-mortgage"
DISTILLED = REPO / ".flo" / "source_material" / "distilled"

SKILL_NAMES = [
    "flo-processing-workflow",
    "flo-milestones",
    "flo-income-analysis",
    "flo-tpo-guidelines",
    "flo-communication",
    "flo-compliance-messaging",
    "flo-notes-and-emails",
]

REQUIRED_SECTIONS = [
    "## When to Use",
    "## Prerequisites",
    "## How to Run",
    "## Quick Reference",
    "## Procedure",
    "## Sources",
    "## SOURCE_GAP",
    "## Prohibited Inference",
    "## Pitfalls",
    "## Verification",
]

MILESTONES = ["Intake", "Application", "Processing", "Conditional Approval", "Clear to Close", "Closed"]
COMPLIANCE_TEMPLATE = "Your loan is progressing. We will update you at next milestone."
SAMPLE_NOTE = "File is moving through processing, appraisal ordered."

# Vocabulary that would only appear if a rule had been invented. The supplied
# sources contain none of it.
INCOME_TRIPWIRES = [
    r"\b24[- ]month",
    r"\btwo[- ]year",
    r"\b2[- ]year",
    r"\bschedule [cek]\b",
    r"\b1084\b",
    r"\b1005\b",
    r"\b1040\b",
    r"\b1120",
    r"\bk-1\b",
    r"\badd[- ]?backs?\b",
    r"\bdepreciation\b",
    r"\b\d{1,3}\s?%",
    r"\bytd\b",
    r"\byear[- ]to[- ]date\b",
    r"\bdti\b",
    r"\bdebt[- ]to[- ]income\b",
    r"\bltv\b",
    r"\bfico\b",
    r"\bfannie\b",
    r"\bfreddie\b",
    r"\bfha\b",
    r"\bva\b",
    r"\busda\b",
    r"\bvvoe\b",
    r"\bvoe\b",
]


def _skill(name: str) -> tuple[dict, str, str]:
    path = SKILLS_DIR / name / "SKILL.md"
    assert path.exists(), path
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---")
    m = re.search(r"\n---\s*\n", content[3:])
    fm = yaml.safe_load(content[3 : m.start() + 3])
    body = content[m.end() + 3 :]
    return fm, body, content


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_frontmatter_and_metadata(name):
    fm, _, _ = _skill(name)
    assert fm["name"] == name
    for field in ("description", "version", "author", "license", "platforms"):
        assert field in fm, field
    assert len(fm["description"]) <= 60 and fm["description"].endswith(".")
    hermes = fm["metadata"]["hermes"]
    assert hermes["category"] == "flo-mortgage"
    assert "Flo" in hermes["tags"]
    for related in hermes["related_skills"]:
        assert (SKILLS_DIR / related / "SKILL.md").exists(), f"dangling related skill {related}"


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_required_sections_and_provenance(name):
    _, body, _ = _skill(name)
    for section in REQUIRED_SECTIONS:
        assert section in body, f"{name}: missing {section}"
    assert "Source review date: 2026-09-08" in body
    assert ".flo/source_material/" in body, f"{name}: no provenance path"
    # Provenance must point at files that exist in the repo.
    for rel in re.findall(r"`(\.flo/source_material/[^`]+)`", body):
        assert (REPO / rel).exists(), f"{name}: provenance path missing: {rel}"


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_tool_references_are_native_hermes_tools(name):
    _, body, _ = _skill(name)
    for shell_tool in ("`grep`", "`cat`", "`sed`", "`find`", "`ls`"):
        assert shell_tool not in body, f"{name}: shell tool named in prose"
    assert "`read_file`" in body


def test_workflow_milestones_match_source_exactly():
    _, body, _ = _skill("flo-processing-workflow")
    distilled = (DISTILLED / "01_LoanFlow_OS_Processing_Workflow.md").read_text(encoding="utf-8")
    for milestone in MILESTONES:
        assert milestone in distilled, "test fixture drifted from distilled source"
    positions = [body.index(f"{i + 1}. {m}") for i, m in enumerate(MILESTONES)]
    assert positions == sorted(positions), "milestones out of order"
    assert "Underwriting" not in re.sub(r"\(for example.*?\)", "", body).split("## SOURCE_GAP")[0].replace(
        '"Underwriting" is not one of the six', ""
    )


def test_milestone_definitions_are_verbatim_and_no_more():
    _, body, _ = _skill("flo-milestones")
    distilled = (DISTILLED / "04_Milestone_Definitions.md").read_text(encoding="utf-8")
    assert "Processing: Docs collected" in distilled and "CTC: Ready to close" in distilled
    assert "| Processing | Docs collected |" in body
    assert "| CTC | Ready to close |" in body
    # The four undefined milestones are named as gaps, not defined.
    gap = body.split("## SOURCE_GAP")[1].split("## Prohibited Inference")[0]
    for undefined in ("Intake", "Application", "Conditional Approval", "Closed"):
        assert undefined in gap


def test_income_skill_contains_no_fabricated_rules():
    _, body, _ = _skill("flo-income-analysis")
    lowered = body.lower()
    for pattern in INCOME_TRIPWIRES:
        assert not re.search(pattern, lowered), f"income skill contains rule vocabulary: {pattern}"
    assert "W2, self-employed, and rental income" in body
    assert "SOURCE_GAP" in body
    # The only numbers permitted are dates, versions, and section ordinals.
    stray = [n for n in re.findall(r"\b\d+(?:\.\d+)?\b", body) if n not in {"2026", "09", "08", "1", "2", "3", "4", "5", "6", "7", "0"}]
    assert stray == [], f"unexpected numbers in income skill: {stray}"


def test_tpo_skill_states_only_the_supplied_rule():
    _, body, _ = _skill("flo-tpo-guidelines")
    assert "Follow agency rules." in body and "Confirm overlays with AE." in body
    lowered = body.lower()
    for pattern in INCOME_TRIPWIRES:
        assert not re.search(pattern, lowered), f"tpo skill contains rule vocabulary: {pattern}"


def test_compliance_template_is_verbatim_and_singular():
    _, body, _ = _skill("flo-compliance-messaging")
    distilled = (DISTILLED / "07_Compliance_Safe_Templates.md").read_text(encoding="utf-8")
    assert COMPLIANCE_TEMPLATE in distilled
    assert COMPLIANCE_TEMPLATE in body
    assert "not a template library" in body
    assert "DRAFT" in body


def test_notes_skill_uses_sample_as_seed_only():
    _, body, _ = _skill("flo-notes-and-emails")
    distilled = (DISTILLED / "06_Sample_Notes_and_Emails.md").read_text(encoding="utf-8")
    assert SAMPLE_NOTE in distilled and SAMPLE_NOTE in body
    assert "tone seed only" in body
    assert "DRAFT" in body


def test_communication_skill_carries_ashleys_contract():
    _, body, _ = _skill("flo-communication")
    for phrase in ("Priority, Status, Action, Urgency", "top three", "best next move", "only blocker right now"):
        assert phrase in body, phrase
    for avoided in ("check this", "handle this", "you may want to review", "several items need attention"):
        assert avoided in body  # listed as phrases to avoid
    assert "neutral" in body and "never inflame" in body.lower()


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_no_sensitive_data_or_machine_paths(name):
    _, _, content = _skill(name)
    assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", content), "SSN-shaped value in skill"
    assert not re.search(r"C:\\Users|/home/[a-z]", content)
