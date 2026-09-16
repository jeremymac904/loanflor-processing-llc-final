"""Fannie Mae vertical slice — thin program binding over :mod:`sources` and :mod:`cards`.

The public API used by the Golden Loan Path (``load_sections``, ``load_rules``,
``section_status``, ``is_active``, ``regression``, ``match_rules``,
``guideline_card``) is preserved; every function delegates to the
program-agnostic layer with ``program="fannie"`` so the activated Fannie
rules keep their behaviour while the same code path serves every other
program. See ``plugins/flo-team/sources.py`` for the lifecycle contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from . import sources
from .knowledge import KnowledgeState
from .sources import SectionStatus, default_state  # noqa: F401 - re-exported

PROGRAM = "fannie"
HERE = sources.KNOWLEDGE_DIR / PROGRAM
SECTIONS_PATH = sources.sections_path(PROGRAM)
RULES_PATH = sources.rules_path(PROGRAM)


def load_sections() -> Dict[str, Dict[str, Any]]:
    return sources.load_sections(PROGRAM)


def load_rules() -> List[Dict[str, Any]]:
    return sources.load_rules(PROGRAM)


def cache_dir(root: Optional[Path] = None) -> Path:
    return sources.cache_dir(PROGRAM, root)


def cached_text(section: str, root: Optional[Path] = None) -> Optional[str]:
    return sources.cached_text(PROGRAM, section, root)


def section_status(section: str, state: Optional[KnowledgeState] = None, root: Optional[Path] = None) -> SectionStatus:
    return sources.section_status(PROGRAM, section, state, root)


def is_active(section: str, state: Optional[KnowledgeState] = None, root: Optional[Path] = None) -> bool:
    return sources.is_active(PROGRAM, section, state, root)


def regression(section: str, root: Optional[Path] = None) -> Dict[str, Any]:
    return sources.regression(PROGRAM, section, root)


def match_rules(topic: str, rules: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    return sources.match_rules(PROGRAM, topic, rules)


def guideline_card(topic: str, **kwargs: Any) -> Dict[str, Any]:
    from . import cards

    return cards.guideline_card(program=PROGRAM, topic=topic, **kwargs)
