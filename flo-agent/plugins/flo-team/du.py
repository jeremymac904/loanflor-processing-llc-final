"""Desktop Underwriter findings handling (Malcolm) — Fannie binding over :mod:`aus`.

Kept as the Fannie-specific entry point (``detect``/``review``) used by the
Golden Loan Path; the program-agnostic envelope and review live in
``aus.py``. Language stays "DU findings show <recommendation>." — never
"approved".
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from . import aus

DOC_KEYWORDS = aus.DOC_KEYWORDS


def detect(documents: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for doc in documents or []:
        if str(doc.get("type") or "").lower() in ("du_findings", "aus_findings"):
            return doc
    return None


def review(
    *,
    documents: List[Dict[str, Any]],
    recalculated_dti: Any = None,
    active_check: Optional[Callable[[str], bool]] = None,
    section_meta: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    out = aus.review(documents=documents, program="fannie", recalculated_dti=recalculated_dti, active_check=active_check, section_meta=section_meta)
    out["review"] = "du_findings"
    if not out["present"]:
        out["statement"] = "DU findings are not in the file."
        out["next"] = "obtain the DU Underwriting Findings report before prep can be completed"
    return out
