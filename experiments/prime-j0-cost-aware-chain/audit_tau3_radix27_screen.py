#!/usr/bin/env python3
"""Read-only full replay of the radix-27 shortest-path design screen."""

import json
from pathlib import Path

from screen_tau3_radix27 import screen


ROOT = Path(__file__).resolve().parent


def main():
    path = ROOT / "tau3-radix27-screen.json"
    recorded = json.loads(path.read_text())
    assert recorded == screen()
    assert all(row["fallbacks"] == 0 and
               row["optimal_additions"] <= row["native_sparse_additions"]
               for row in recorded["rows"])
    print("tau3 radix-27 design audit: PASS (32,768 exact coefficient paths)")


if __name__ == "__main__":
    main()
