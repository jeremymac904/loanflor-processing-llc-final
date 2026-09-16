"""Standard Guideline Card — one renderer for every program.

Fields (the standard): Program, Agency, Underwriting Method, Topic, Source,
Section, Published, Effective, Revision, AUS, Lender Overlay, Investor
Overlay, Guideline-Supported Conclusion, Calculation Trace, Missing
Documentation, Conflict/Caution, Best Next Move.

Rendering is concise with progressive disclosure: ``summary`` carries the
one-screen answer (conclusion, primary citation, next move); ``details``
carries every citation, layer and status. Legacy keys used by the Golden
Loan Path (``conclusion``, ``citations``, ``layers``, ``confidence``) are kept
so existing callers and tests keep working.

A conclusion is guideline-supported only when every matched rule's section
is ACTIVE and unchanged on this install; otherwise it is SOURCE_GAP naming
the pending revisions. Rules from another program can never be matched
(``sources.match_rules`` filters by program and, for FHA, by underwriting
method).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from . import sources
from .knowledge import KnowledgeState
from .store import now_iso

STANDARD_FIELDS = ("program", "agency", "underwriting_method", "topic", "source", "section", "published", "effective", "revision", "aus",
                   "lender_overlay", "investor_overlay", "guideline_supported_conclusion", "calculation_trace", "missing_documentation",
                   "conflict_or_caution", "best_next_move")
RESOLUTION_LABEL = {"CURRENT": "CURRENT", "FUTURE": "FUTURE — NOT YET EFFECTIVE", "SUPERSEDED": "SUPERSEDED", "EARLY_IMPLEMENTATION": "CURRENT (early implementation elected)"}


def _overlay(lender: Optional[str]) -> Dict[str, Any]:
    return {"lender": lender, "state": "NOT_LOADED", "note": "no approved overlay pack; 'none loaded' never means 'no overlays exist' — confirm with AE"}


def guideline_card(
    *,
    program: str,
    topic: str,
    state: Optional[KnowledgeState] = None,
    root: Optional[Path] = None,
    underwriting_method: Optional[str] = None,
    lender: Optional[str] = None,
    aus_path: Optional[str] = None,
    aus_findings: Optional[List[str]] = None,
    aus_envelope: Optional[Dict[str, Any]] = None,
    file_conditions: Optional[List[str]] = None,
    calculation_trace_ref: Optional[str] = None,
    documentation: Optional[Dict[str, str]] = None,
    missing_documentation: Optional[List[str]] = None,
    relevant_date: Optional[Any] = None,
    early_implementation: bool = False,
    team_root: Optional[Path] = None,
    workspace_id: Optional[str] = None,
    product: Optional[str] = None,
) -> Dict[str, Any]:
    program = (program or "").lower()
    spec = sources.program_spec(program)
    overlay_rows: List[Dict[str, Any]] = []
    guidance_rows: List[Dict[str, Any]] = []
    if team_root is not None:
        try:
            from . import overlays as overlays_mod

            overlay_rows = overlays_mod.OverlayStore(team_root).active_for(program, lender, product=product, relevant_date=relevant_date)
        except Exception:  # noqa: BLE001 - overlay store absent
            overlay_rows = []
        if workspace_id:
            try:
                from . import guidance as guidance_mod

                guidance_rows = guidance_mod.GuidanceStore(team_root).for_workspace(workspace_id)
            except Exception:  # noqa: BLE001
                guidance_rows = []
    state = state if state is not None else sources.default_state()
    method = (underwriting_method or "").lower() or None
    if program == "fha" and method not in (None, "total", "manual"):
        raise ValueError("fha underwriting_method must be 'total' or 'manual'")
    resolved = sources.resolve_rule(program, topic, relevant_date=relevant_date, underwriting_method=method, early_implementation=early_implementation,
                                    state=state, root=root, limit=6)
    matched = resolved["applicable"][:6]
    future_rules = resolved["future"]
    superseded_rules = resolved["superseded"]
    sections = sorted({r["section"] for r in matched})
    kw = {"relevant_date": relevant_date, "early_implementation": early_implementation}
    statuses = {s: sources.section_status(program, s, state, root, **kw) for s in sections}
    active_rules = [r for r in matched if statuses[r["section"]].usable]
    pending = [statuses[s].to_dict() for s in sections if not statuses[s].usable]
    from . import overlays as overlays_mod

    overlay_block = overlays_mod.overlay_layer(overlay_rows, lender)
    cautions: List[str] = [] if overlay_rows else ["Overlay not loaded — confirm with AE."]
    for st in statuses.values():
        cautions.extend(st.cautions)
    for fr in future_rules:
        st = sources.section_status(program, fr["section"], state, root, **kw)
        for c in st.cautions:
            if c not in cautions:
                cautions.append(c)
    if any(r.get("resolution") == "EARLY_IMPLEMENTATION" for r in matched):
        cautions.append("Early implementation elected for a future-dated version; the lender's election must be on file.")
    if aus_envelope and aus_envelope.get("mismatch"):
        cautions.append(aus_envelope["mismatch"])
    methods = {r.get("underwriting_method") for r in matched if r.get("underwriting_method")}
    if program == "fha" and not method:
        cautions.append("FHA underwriting method not stated; TOTAL and Manual rules are shown side by side and must not be mixed on one file.")

    def _cite(rule, st, label):
        return {
            "rule_id": rule["rule_id"], "section": rule["section"], "section_number": st.section_number, "version": st.version,
            "resolution": label, "resolution_label": RESOLUTION_LABEL.get(label, label),
            "section_title": st.title, "official_url": st.official_url,
            "source_version": f"{spec['source_title']}; {st.edition or ''}; section date {st.page_date}".strip("; "),
            "published": st.page_date, "effective": st.effective_date, "mandatory_date": st.mandatory_date, "in_force": st.in_force, "revision_id": st.revision_id,
            "retrieved_at": st.retrieved_at, "checksum": (st.checksum or "")[:12], "lifecycle": st.lifecycle, "usable": st.usable,
            "underwriting_method": rule.get("underwriting_method"), "rule": rule["text"], "kind": rule["kind"],
        }

    citations = [_cite(rule, statuses[rule["section"]], rule.get("resolution") or "CURRENT") for rule in matched]
    cautions.extend(overlays_mod.conflicts(overlay_rows, citations))
    conditions_all = [str(c)[:300] for c in (file_conditions or [])][:20] + [f"{g['label']}: {g['text']} (source {g['source_ref']})" for g in guidance_rows]
    future_citations = [_cite(rule, sources.section_status(program, rule["section"], state, root, **kw), "FUTURE") for rule in future_rules]
    superseded_citations = [_cite(rule, sources.section_status(program, rule["section"], state, root, **kw), "SUPERSEDED") for rule in superseded_rules]

    lead = active_rules[0] if active_rules else None
    if not matched and future_rules:
        conclusion, confidence, status = "SOURCE_GAP", "none: the only matching rules are FUTURE — NOT YET EFFECTIVE on the relevant date", "SOURCE_GAP"
        next_move = "The in-force version of this section is not recorded; ask the AE/UW, or capture and activate the current version."
    elif not matched:
        conclusion, confidence, status = "SOURCE_GAP", f"none: no rule in the activated {spec['display']} slice matches this topic", "SOURCE_GAP"
        next_move = f"Ask the AE/UW, or extend the {spec['display']} slice with the applicable {spec['source_title']} section through the activation workflow."
    elif active_rules and not pending:
        conclusion = f"{lead['text']} ({spec['source_title']} {lead['section']}, {statuses[lead['section']].title})"
        confidence, status = f"source-backed: {len(active_rules)} active rule(s) across {', '.join(sections)}", "active"
        next_move = "Apply the cited section; escalate to AE/UW if a lender overlay or AUS finding conflicts."
    elif active_rules:
        conclusion = f"{lead['text']} ({spec['source_title']} {lead['section']})"
        confidence, status = f"partial: {len(active_rules)} active rule(s); {len(pending)} section(s) not yet active", "partial"
        cautions.append("Some matched sections are not active; those rules are shown as citations only.")
        next_move = "Use the active sections; complete review/activation for the pending ones."
    else:
        conclusion, confidence, status = "SOURCE_GAP", "none: matched sections are not active on this install", "SOURCE_GAP"
        next_move = "Run the activation workflow (fetch → review → regression → admin approval → active) for " + ", ".join(sections)

    primary = citations[0] if citations else None
    aus_block = {
        "system": (aus_envelope or {}).get("aus_system_display") or aus_path or "unknown",
        "result_as_shown": (aus_envelope or {}).get("aus_result"),
        "statement": (aus_envelope or {}).get("statement"),
        "findings": [str(f)[:300] for f in (aus_findings or [])][:20],
        "note": "AUS findings are file-specific evidence, not a guideline",
    }
    card: Dict[str, Any] = {
        "card_type": "guideline_card",
        "card_version": "2",
        # --- standard fields ---
        "program": spec["display"],
        "program_key": program,
        "agency": spec["agency"],
        "underwriting_method": method or (", ".join(sorted(methods)) if methods else (aus_path or "unknown")),
        "topic": topic,
        "source": spec["source_title"],
        "section": ", ".join(sections) if sections else None,
        "published": primary["published"] if primary else None,
        "effective": primary["effective"] if primary else None,
        "effective_status": primary["resolution_label"] if primary else None,
        "relevant_date": resolved.get("relevant_date"),
        "relevant_date_basis": next((r.get("relevant_date_basis") for r in resolved.get("resolutions", {}).values()), None),
        "revision": primary["revision_id"] if primary else None,
        "version": primary["version"] if primary else None,
        "aus": aus_block,
        "lender_overlay": overlay_block,
        "guidance": guidance_rows,
        "investor_overlay": {"state": "NOT_APPLICABLE", "note": "agency baseline card; no investor program loaded"},
        "guideline_supported_conclusion": conclusion,
        "calculation_trace": calculation_trace_ref,
        "missing_documentation": list(missing_documentation or []),
        "conflict_or_caution": cautions,
        "best_next_move": next_move,
        # --- progressive disclosure ---
        "summary": {
            "headline": conclusion if conclusion == "SOURCE_GAP" else (lead["text"] if lead else conclusion),
            "cite": (f"{spec['source_title']} {primary['section_number'] or primary['section']}" + (f" ({primary['version']})" if primary.get("version") else "")
                     + f" — {primary['resolution_label']}, effective {primary['effective']}" if primary else None),
            "status": status, "next": next_move,
            "future_versions": [f"{c['section_number'] or c['section']} ({c['version']}) effective {c['effective']}" + (f", mandatory {c['mandatory_date']}" if c.get('mandatory_date') else "") for c in future_citations],
        },
        "details": {"citations": citations, "future_citations": future_citations, "superseded_citations": superseded_citations,
                    "pending_revisions": pending, "documentation": documentation or {},
                    "file_conditions": conditions_all},
        # --- legacy keys (Golden Loan Path callers) ---
        "agency_or_investor": program,
        "aus_or_manual": method or aus_path or "unknown",
        "layers": {
            "agency_baseline": ({"status": status, "sections": sections, **({"pending": pending} if pending else {})} if matched else None),
            "lender_overlay": overlay_block,
            "investor_program": None,
            "aus_finding": {"path": aus_block["system"], "findings": aus_block["findings"], "note": aus_block["note"]},
            "file_condition": {"conditions": conditions_all, "note": "a UW condition or AE/UW guidance is a file-specific entry, never a global rule"},
        },
        "citations": citations,
        "documentation": documentation or {},
        "conclusion": conclusion,
        "confidence": confidence,
        "underwriting_decision": False,
        "language": "guideline-supported assessment based on the documents currently available; not a loan approval",
        "generated_at": now_iso(),
    }
    return card


def render_text(card: Dict[str, Any], *, expanded: bool = False) -> str:
    """Concise text rendering (summary first; citations only when expanded)."""
    s = card["summary"]
    lines = [f"[{card['program']} | {card['underwriting_method']}] {card['topic']}", f"Conclusion: {s['headline']}"]
    if s.get("cite"):
        lines.append(f"Source: {s['cite']}")
    for fv in s.get("future_versions", []):
        lines.append(f"FUTURE — NOT YET EFFECTIVE: {fv}")
    if card["aus"].get("statement"):
        lines.append(f"AUS: {card['aus']['statement']}")
    if card["missing_documentation"]:
        lines.append("Missing: " + "; ".join(card["missing_documentation"]))
    if card["conflict_or_caution"]:
        lines.append("Caution: " + " | ".join(card["conflict_or_caution"]))
    lines.append(f"Next: {s['next']}")
    if expanded:
        for c in card["details"]["citations"]:
            lines.append(f"  - {c['section']} ({c['lifecycle']}, effective {c['effective']}): {c['rule']}")
    return "\n".join(lines)
