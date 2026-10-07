#!/usr/bin/env python3
"""Read-only proof checks for the frozen six-step quotient/correction atlas."""

import hashlib
from pathlib import Path
import random

from make_tau3_atlas import ROOT, SIDE, build_atlas, render
from make_tau3_fused import UNREACHABLE, block_pattern, build, recode


def actions_from_digits(sequence, orbit_id, orbit_unit):
    result = []
    for start in range(0, len(sequence), 6):
        block = (sequence[start:start + 6] + [0] * 6)[:6]
        u = block_pattern(block[:3])
        v = block_pattern(block[3:])
        slot = 55 * u + v
        assert orbit_id[slot] != UNREACHABLE
        result.append((orbit_id[slot] << 3) | orbit_unit[slot])
    return result


def atlas_actions(a, b, entries):
    actions = []
    while a or b:
        ca, cb, action = entries[SIDE * (a % SIDE) + b % SIDE]
        assert (a - ca) % 27 == (b - cb) % 27 == 0
        actions.append(action)
        a, b = (ca - a) // 27, (cb - b) // 27
        assert len(actions) <= 16
    return actions


def main():
    path = ROOT.parents[1] / "src/generated/tau3_atlas.h"
    entries = build_atlas()
    assert path.read_text() == render(entries)
    assert len(entries) == 6561
    digits, residue, _, orbit_id, orbit_unit, _ = build()
    rng = random.Random(0xC0A17A6)
    for _ in range(100_000):
        a = rng.randrange(-(1 << 28), 1 << 28)
        b = rng.randrange(-(1 << 28), 1 << 28)
        expected = actions_from_digits(recode(a, b, digits, residue), orbit_id, orbit_unit)
        assert atlas_actions(a, b, entries) == expected
    print("tau3 atlas design audit: PASS (6,561 entries; 100,000 signed coefficient recodings; SHA-256 %s)" %
          hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
