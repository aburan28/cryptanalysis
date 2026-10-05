#!/usr/bin/env python3
"""Exhaustively derive graph edges from corrections without a recipe table."""

import hashlib
import json
from pathlib import Path

from make_tau8_orbits import unit_action
from make_tau_wide_graph import recipes
from make_tau_wide_orbits import ID_BITS, MAX_ID, WIDTHS, build, residue_key
from run import recode


def derive(atlas):
    corrections = atlas["corrections"]
    widths = atlas["width"]
    descriptors = []
    digit_scans = 0
    for a, b in corrections:
        digits = recode(a, b)
        digit_scans += len(digits)
        nonzero = [(position, digit) for position, digit in enumerate(digits)
                   if digit is not None]
        if not nonzero:
            descriptors.append((0, 0, 255))
            continue
        position, digit = nonzero[-1]
        slot = (digit[0] % 9) * 9 + digit[1] % 9
        depth = len(nonzero)
        if depth > 3 or position >= widths or slot >= 81:
            raise AssertionError("descriptor exceeds frozen width or depth")
        descriptors.append((depth, position, slot))
    old = recipes(atlas)
    tau_steps = lookups = 0
    for orbit_id, (depth, position, slot) in enumerate(descriptors):
        if depth < 2:
            expected = (0, 255, 0, 0) if depth == 0 else (0, slot, position, 1)
            if old[orbit_id] != expected:
                raise AssertionError((widths, orbit_id, expected, old[orbit_id]))
            continue
        digit = recode(*corrections[orbit_id])[position]
        term_a, term_b = digit[:2]
        for _ in range(position):
            term_a, term_b = -3 * term_b, term_a + 3 * term_b
            tau_steps += 1
        a, b = corrections[orbit_id]
        parent = a - term_a, b - term_b
        packed = atlas["packed"][residue_key(*parent, atlas["modulus"])]
        lookups += 1
        parent_id, unit = packed & (MAX_ID - 1), packed >> ID_BITS
        if (unit > 5 or unit_action(*corrections[parent_id], unit) != parent or
                descriptors[parent_id][0] != depth - 1 or
                old[orbit_id] != (packed, slot, position, depth)):
            raise AssertionError((widths, orbit_id, parent, packed))
    return {"orbits": len(corrections), "recode_calls": len(corrections) - 1,
            "digit_slots_scanned": digit_scans, "integer_tau_steps": tau_steps,
            "parent_index_lookups": lookups, "exact_parent_checks": lookups,
            "descriptor_temp_bytes": 2 * len(corrections),
            "graph_adds_per_block": lookups,
            "recipe_equivalence_checks": len(corrections)}


def main():
    root = Path(__file__).resolve().parent
    rows = {str(width): derive(build(width)) for width in WIDTHS}
    paths = [Path(__file__), root / "make_tau_wide_orbits.py",
             root / "make_tau_wide_graph.py", root / "run.py",
             root / "IMPLICIT_ORBIT_GRAPH.md",
             root.parents[1] / "src" / "generated" / "tau_wide_orbits.h",
             root.parents[1] / "src" / "generated" / "tau_wide_graph.h"]
    report = {"schema": 1, "status": "exhaustive_implicit_orbit_graph_screen",
              "widths": rows,
              "source_sha256": {str(path.relative_to(root.parents[1])):
                                hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in paths}}
    (root / "implicit-orbit-graph-screen.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "widths": rows}, sort_keys=True))


if __name__ == "__main__":
    main()
