#!/usr/bin/env sage -python
"""Run ``explore_sage.py`` with an explicitly enlarged PARI stack."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from sage.all import pari
except ImportError as exc:  # pragma: no cover - executed only outside Sage
    raise SystemExit("This program must run under `sage -python`.") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import explore_sage  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--pari-stack-gib", type=int, default=4)
    known, remaining = parser.parse_known_args()
    if known.pari_stack_gib < 1:
        raise SystemExit("--pari-stack-gib must be positive")
    pari.allocatemem(known.pari_stack_gib * 1024**3, silent=True)
    sys.argv = [sys.argv[0], *remaining]
    explore_sage.main()


if __name__ == "__main__":
    main()
