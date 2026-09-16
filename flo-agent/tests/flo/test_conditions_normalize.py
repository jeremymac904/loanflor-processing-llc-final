"""Conditions normalizer — owner detection, plain-English rewrite, grouping.

All synthetic fixtures. The lender phrasing in these tests mirrors what real
UW emails look like; the goal is to confirm the parser handles the common
shapes and falls back to ``Other`` when nothing aligns.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins" / "flo-team"

if "flo_team" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "flo_team", PLUGIN / "__init__.py",
        submodule_search_locations=[str(PLUGIN)],
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["flo_team"] = _module
    _spec.loader.exec_module(_module)

from flo_team import conditions_normalize as cn  # noqa: E402


# ── Owner detection ────────────────────────────────────────────────────────

class TestOwnerDetection:
    @pytest.mark.parametrize("text,expected", [
        ("Provide most recent paystub from borrower 1",            "Borrower"),
        ("Borrower to provide W-2 for 2025",                       "Borrower"),
        ("Most recent bank statement",                              "Borrower"),
        ("Updated gift letter required from family",                "Borrower"),
        ("Title company to provide updated title commitment",       "Title"),
        ("Title endorsement required",                              "Title"),
        ("Revised HOI declaration page",                            "Insurance"),
        ("Updated hazard insurance policy",                        "Insurance"),
        ("Verification of employment from employer",                "Employer"),
        ("Appraisal report required",                               "Appraiser"),
        ("Underwriter requires updated paystub",                    "Lender/UW"),
        ("Prior to doc: updated VOI",                               "Lender/UW"),
        ("PTF condition: pay off second mortgage",                  "Lender/UW"),
        ("Letter of explanation from loan officer",                 "Loan Officer"),
        ("Processor to upload final docs",                          "Processor"),
        ("Please respond to this matter",                           "Other"),
        ("Updated insurance",                                       "Insurance"),
    ])
    def test_owner(self, text, expected):
        assert cn._detect_owner(text) == expected


# ── Type detection ─────────────────────────────────────────────────────────

class TestTypeDetection:
    @pytest.mark.parametrize("text,expected_type,expected_cat", [
        ("Most recent paystub from borrower",                  "paystub",               "income"),
        ("W-2 for 2025",                                       "w2",                    "income"),
        ("1099 income",                                        "1099",                  "income"),
        ("Provide tax return for 2024",                        "tax_return",            "income"),
        ("Most recent bank statement",                         "bank_statement",        "assets"),
        ("Two months bank statements",                         "bank_statement",        "assets"),
        ("Verification of deposit required",                   "bank_statement",        "assets"),
        ("Gift letter from family member",                     "gift_letter",           "assets"),
        ("Updated HOI declaration page",                       "insurance_declaration", "insurance"),
        ("Title commitment with all endorsements",             "title_commitment",      "title_property"),
        ("Written VOE from employer",                          "wvoe",                  "other"),
        ("VOE from HR",                                        "voe",                   "other"),
        ("Letter of explanation for large deposit",             "letter_of_explanation", "other"),
        ("Appraisal required",                                 "appraisal",             "aus_findings"),
        ("DU findings to be reviewed",                         "aus_findings",          "aus_findings"),
        ("Random unrelated text",                              "other",                 "other"),
    ])
    def test_type(self, text, expected_type, expected_cat):
        assert cn._detect_type(text) == (expected_type, expected_cat)


# ── Plain-English rewrite ──────────────────────────────────────────────────

class TestPlainEnglish:
    def test_paystub_rewrites_with_borrower_subject(self):
        c = cn.parse_condition("Provide most recent paystub from borrower 1")
        assert c["plain_english"].lower().startswith("borrower")

    def test_ptd_short_form_expanded(self):
        c = cn.parse_condition("PTD condition: pay off second mortgage")
        assert "prior to doc" in c["plain_english"].lower()

    def test_hoi_capitalized_in_plain_english(self):
        c = cn.parse_condition("Provide updated HOI dec page")
        assert "HOI" in c["plain_english"]

    def test_short_form_loe_expanded(self):
        c = cn.parse_condition("LOE for large deposit")
        assert "letter of explanation" in c["plain_english"].lower()

    def test_unrelated_phrasing_keeps_meaning(self):
        c = cn.parse_condition("Updated paystub from co-borrower for current period")
        # Must keep the meaning; should mention "paystub" somewhere.
        assert "paystub" in c["plain_english"].lower()
        # Must not be empty.
        assert len(c["plain_english"]) > 0

    def test_does_not_invent_new_requirements(self):
        original = "Paystub"
        c = cn.parse_condition(original)
        # The plain English must not contradict the original by adding items.
        assert "W-2" not in c["plain_english"]
        assert "1099" not in c["plain_english"]
        assert "tax return" not in c["plain_english"]


# ── Required item ──────────────────────────────────────────────────────────

class TestRequiredItem:
    @pytest.mark.parametrize("text,expected_type,expected_phrase", [
        ("Most recent paystub from borrower",        "paystub",               "paystub"),
        ("W-2 for 2025",                             "w2",                    "w-2"),
        ("Updated HOI declaration page",             "insurance_declaration", "hoi"),
        ("Title endorsement required",               "title_commitment",      "title"),
        ("Bank statement page 4 missing",            "bank_statement",        "bank statement"),
        ("Random phrase with no type",                "other",                 ""),
    ])
    def test_required_item_phrase(self, text, expected_type, expected_phrase):
        c = cn.parse_condition(text)
        assert c["condition_type"] == expected_type
        if expected_phrase:
            assert expected_phrase.lower() in c["required_item"].lower()


# ── Sage gate ──────────────────────────────────────────────────────────────

class TestNeedsSage:
    @pytest.mark.parametrize("text,expected", [
        ("Letter of explanation for large deposit",                 True),
        ("Source of funds verification",                            True),
        ("Gift letter from family",                                 True),
        ("Appraisal review required",                               True),
        ("Per Fannie guidelines, provide …",                        True),
        ("In accordance with DU findings, …",                       True),
        ("Most recent paystub",                                     False),
        ("Bank statement page 4 missing",                           False),
        ("Updated HOI declaration page",                            False),
    ])
    def test_sage_flag(self, text, expected):
        c = cn.parse_condition(text)
        assert c["needs_sage"] is expected


# ── Multi-line ingestion ───────────────────────────────────────────────────

class TestParseBlob:
    def test_lender_email_with_three_conditions(self):
        blob = """\
Hi Ashley,

We have the following conditions on loan Johnson:
1. Provide most recent paystub from borrower 1
2. Bank statement: most recent 2 months
3. Title company to provide updated title commitment

Thank you,
Underwriter
"""
        rows = cn.parse_conditions_blob(blob, source="lender_email")
        assert len(rows) == 3
        owners = [r["owner"] for r in rows]
        assert owners == ["Borrower", "Borrower", "Title"]
        types = [r["condition_type"] for r in rows]
        assert types == ["paystub", "bank_statement", "title_commitment"]

    def test_boilerplate_lines_dropped(self):
        blob = """\
Hi Ashley,

1. Paystub from borrower

Thank you,
"""
        rows = cn.parse_conditions_blob(blob)
        # only one real condition line
        assert len(rows) == 1
        assert rows[0]["condition_type"] == "paystub"

    def test_numbered_prefixes_removed(self):
        blob = "1. Updated paystub\n2. W-2 for 2025\n3. HOI page"
        rows = cn.parse_conditions_blob(blob)
        assert len(rows) == 3
        for r in rows:
            assert not r["plain_english"].startswith(("1.", "2.", "3."))

    def test_duplicate_blob_does_not_crash(self):
        # duplicates are caller concern, not parser concern. Two parses
        # should give the same fields.
        blob = "Updated paystub"
        a = cn.parse_conditions_blob(blob)
        b = cn.parse_conditions_blob(blob)
        assert a == b


# ── Grouping ───────────────────────────────────────────────────────────────

class TestGroupByOwner:
    def test_groups_by_owner_canonical_order(self):
        rows = [
            {"owner": "Borrower", "id": "c1"},
            {"owner": "Title",    "id": "c2"},
            {"owner": "Borrower", "id": "c3"},
            {"owner": "Other",    "id": "c4"},
        ]
        grouped = cn.group_by_owner(rows)
        # Borrower first, then Title, then Other — owners without rows are dropped.
        assert list(grouped.keys()) == ["Borrower", "Title", "Other"]
        assert [c["id"] for c in grouped["Borrower"]] == ["c1", "c3"]
        assert [c["id"] for c in grouped["Title"]] == ["c2"]

    def test_unknown_owner_falls_to_other(self):
        rows = [{"owner": "Imaginary", "id": "c1"}]
        grouped = cn.group_by_owner(rows)
        assert "Other" in grouped
        assert grouped["Other"][0]["id"] == "c1"

    def test_filter_open_drops_cleared(self):
        rows = [
            {"id": "c1", "state": "open"},
            {"id": "c2", "state": "cleared"},
            {"id": "c3", "status": "Cleared"},
            {"id": "c4"},
        ]
        open_rows = cn.filter_open(rows)
        assert [r["id"] for r in open_rows] == ["c1", "c4"]


# ── Source attribution ────────────────────────────────────────────────────

class TestSourceAttribution:
    def test_manual_default_source(self):
        c = cn.parse_condition("Updated paystub")
        assert c["source"] == "manual"

    def test_lender_email_source_propagates(self):
        c = cn.parse_condition("Paystub", source="lender_email", source_date="2026-09-16")
        assert c["source"] == "lender_email"
        assert c["source_date"] == "2026-09-16"


# ── Backfill / normalization helper ────────────────────────────────────────

class TestNormalizeExisting:
    def test_backfills_missing_fields(self):
        cond = {"id": "c1", "text": "Most recent paystub from borrower", "state": "open"}
        cn.normalize_existing(cond)
        assert cond["owner"] == "Borrower"
        assert cond["condition_type"] == "paystub"
        assert cond["plain_english"]
        assert cond["required_item"]

    def test_preserves_existing_curated_fields(self):
        # If the caller already set owner to something specific, don't overwrite.
        cond = {"id": "c1", "text": "Most recent paystub",
                "owner": "Loan Officer", "plain_english": "Custom note",
                "state": "open"}
        cn.normalize_existing(cond)
        assert cond["owner"] == "Loan Officer"
        assert cond["plain_english"] == "Custom note"

    def test_skips_cleared_in_workspace(self):
        ws = {"conditions": [
            {"id": "c1", "text": "Updated paystub", "state": "cleared"},
            {"id": "c2", "text": "Most recent paystub"},
        ]}
        cn.normalize_workspace(ws)
        assert "owner" not in ws["conditions"][0]  # cleared left alone
        assert ws["conditions"][1]["owner"] == "Borrower"

    def test_skips_non_dict_entries(self):
        ws = {"conditions": ["string condition", {"id": "c1", "text": "Updated paystub"}]}
        cn.normalize_workspace(ws)
        # string entry untouched, dict gets backfill
        assert ws["conditions"][0] == "string condition"
        assert ws["conditions"][1]["owner"] == "Borrower"
