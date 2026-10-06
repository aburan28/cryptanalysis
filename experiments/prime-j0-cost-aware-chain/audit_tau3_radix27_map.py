#!/usr/bin/env python3
"""Read-only regeneration audit of the packed radix-27 action pool."""

import json
from pathlib import Path

from make_tau3_radix27_map import build_arrays, render, report


ROOT = Path(__file__).resolve().parent


def main():
    offsets, entries = build_arrays()
    expected = render(offsets, entries)
    header = ROOT.parents[1] / "src/generated/tau3_radix27.h"
    assert header.read_text() == expected
    actual = json.loads((ROOT / "tau3-radix27-map.json").read_text())
    assert actual == report(offsets, entries, expected)
    assert offsets[0] == 0 and offsets[-1] == 2053
    assert max(offsets[i + 1] - offsets[i] for i in range(729)) == 9
    print("tau3 radix-27 map audit: PASS (729 residues, 2053 valid actions)")


if __name__ == "__main__":
    main()
