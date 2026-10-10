#!/usr/bin/env python3
"""Exact retained-byte test for moving the nine-bit tau window earlier."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-tau-power16-20261010" / "screen.py"
spec = importlib.util.spec_from_file_location("tau_power_screen", PARENT)
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


def seed_count(width, bound):
    radix = 1 << width
    canonical = [source.EMPTY] * (radix * radix)
    nodes = []
    for residue in range(radix * radix):
        if canonical[residue] != source.EMPTY:
            continue
        orbit = [source.index(pair, radix)
                 for pair in source.units(divmod(residue, radix))]
        for item in orbit:
            canonical[item] = residue
        nodes.append(residue)
    visited = set()
    cycles = Counter()
    segments = Counter()
    max_direct_norm = 0
    for origin in nodes:
        if origin in visited:
            continue
        cycle = []
        cursor = origin
        while cursor not in visited:
            visited.add(cursor)
            cycle.append(cursor)
            digit = source.nearest_digit(divmod(cursor, radix), radix)
            max_direct_norm = max(max_direct_norm, source.norm(digit))
            cursor = canonical[source.index(source.tau(digit), radix)]
        assert cursor == origin
        cycles[len(cycle)] += 1
        allowed = [3 * source.norm(source.nearest_digit(divmod(node, radix), radix))
                   <= bound * bound for node in cycle]
        for _, length in source.cycle_plan(cycle, allowed):
            segments[length] += 1
    assert len(visited) == len(nodes)
    return {"width": width, "bound": bound, "classes": len(nodes),
            "max_direct_norm": max_direct_norm, "cycle_lengths": dict(cycles),
            "segments": dict(segments), "seeds": sum(segments.values()),
            "atlas_bytes": 8 + 4 * radix * radix + 4 * sum(segments.values())}


def termination(widths, bounds):
    prefix, sum_digits = 1, 0
    for width, bound in zip(widths, bounds):
        sum_digits += bound * prefix
        prefix *= 1 << width
    return {"product": str(prefix), "digit_sum": str(sum_digits),
            "margin": str(3 * (prefix - sum_digits) ** 2 - source.ORDER),
            "passes": prefix > sum_digits and
                      3 * (prefix - sum_digits) ** 2 > source.ORDER}


def main():
    widths = [8] * 14 + [9, 8]
    bounds = [256] * 14 + [512, 181]
    proof = termination(widths, bounds)
    assert proof["passes"] and not termination(widths, bounds[:-1] + [182])["passes"]
    final8 = seed_count(8, 181)
    middle9 = seed_count(9, 512)
    assert final8["seeds"] == 6476 and middle9["seeds"] == 21847
    parent = json.loads((HERE.parent / "prime-j0-tau-power16-20261010" /
                         "screen-result.json").read_text())
    common8 = parent["atlas8"]
    old_points = parent["point_slots"]
    old_atlases = parent["atlas8"]["atlas_bytes"] + parent["atlas9"]["atlas_bytes"]
    new_points = 14 * common8["seed_count"] + middle9["seeds"] + final8["seeds"]
    new_atlases = common8["atlas_bytes"] + middle9["atlas_bytes"] + final8["atlas_bytes"]
    result = {"schema": "prime-j0-tau-reordered16-screen-v1", "widths": widths,
              "bounds": bounds, "termination": proof,
              "raising_last_bound_fails": True,
              "common8_seeds": common8["seed_count"], "final8": final8,
              "middle9": middle9,
              "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "parent_source_sha256": sha256(PARENT.read_bytes()).hexdigest(),
              "reference": {"point_slots": old_points, "atlas_bytes": old_atlases,
                            "point_payload_bytes": 64 * old_points,
                            "retained_before_metadata": 64 * old_points + old_atlases},
              "reordered": {"point_slots": new_points, "atlas_bytes": new_atlases,
                            "point_payload_bytes": 64 * new_points,
                            "retained_before_metadata": 64 * new_points + new_atlases}}
    assert new_points == 104805
    assert result["reordered"]["retained_before_metadata"] == 8415552
    (HERE / "screen-result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
