#!/usr/bin/env python3
"""Compatibility wrapper: the Fannie Golden-Loan-Path activation commands now run
through the program-agnostic ``scripts/flo/activate_sources.py --program fannie``.

    python scripts/flo/activate_fannie_slice.py --status
    python scripts/flo/activate_fannie_slice.py --review
    python scripts/flo/activate_fannie_slice.py --approve --approver "<name>" --basis "<why>"
    python scripts/flo/activate_fannie_slice.py --activate --approver "<name>"

``--approver`` maps to ``--approver-name`` and ``--basis`` to ``--reason``; the
approval record is the structured identity record (see identity.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from activate_sources import main as _main  # noqa: E402


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--program" not in argv:
        argv = ["--program", "fannie"] + argv
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
