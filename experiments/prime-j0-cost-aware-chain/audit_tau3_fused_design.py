#!/usr/bin/env python3
"""Read-only algebraic and byte-for-byte audit of the width-3 fused map."""

import hashlib
import json
from pathlib import Path

from make_tau3_fused import build, digits, omega, recode, render, tau, unit


ROOT = Path(__file__).resolve().parent
HEADER = ROOT.parents[1] / "src/generated/tau3_fused.h"
SCREEN = ROOT / "tau3-fused-screen.json"


def tau_power(a, b, exponent):
    for _ in range(exponent):
        a, b = tau(a, b)
    return a, b


def contribution(pattern_id, digit):
    if not pattern_id:
        return 0, 0
    position, digit_index = divmod(pattern_id - 1, 18)
    return tau_power(*digit[digit_index], position)


def pair_contribution(u, v, digit):
    a, b = contribution(u, digit)
    c, d = contribution(v, digit)
    c, d = tau_power(c, d, 3)
    return a + c, b + d


def main():
    data = build()
    digit, residue, pattern, ids, units, reps = data
    assert HEADER.read_text() == render(data)
    assert len(digit) == 18 and len(residue) == 27 and len(reps) == 343
    assert tau_power(1, 0, 6) == (-27, 0)
    assert tau_power(0, 1, 6) == (0, -27)
    checked = 0
    for u in range(55):
        for v in range(55):
            index = 55 * u + v
            valid = not u or not v or pattern[v][0] >= pattern[u][0]
            if not valid:
                assert ids[index] == 65535 and units[index] == 255
                continue
            rep = reps[ids[index]]
            expected = pair_contribution(u, v, digit)
            actual = unit(*pair_contribution(*rep, digit), units[index])
            assert actual == expected, (u, v, rep, units[index])
            checked += 1
    assert checked == 2053
    for a in range(-150, 151):
        for b in range(-150, 151):
            recode(a, b, digit, residue)
    screen = json.loads(SCREEN.read_text())
    assert screen["header_sha256"] == hashlib.sha256(HEADER.read_bytes()).hexdigest()
    assert screen["source_sha256"] == hashlib.sha256(
        (ROOT / "make_tau3_fused.py").read_bytes()).hexdigest()
    assert screen["status"] == "retrospective_design_screen"
    assert len(screen["rows"]) == 8
    assert all(float(row["predicted_add_saving"]) > 0 for row in screen["rows"])
    print("tau3 fused design audit: PASS (2,053 valid pair maps; 90,601 recodings)")


if __name__ == "__main__":
    main()
