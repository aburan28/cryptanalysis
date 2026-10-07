#!/usr/bin/env python3
"""Count exact atlas recurrence states shared by five axial neighbors."""

import hashlib
import json
import re
import struct
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ATLAS = REPO / "src/generated/tau4_residue_atlas.h"
CURVES = {
    "glv-j0-32": (23729779, 2323, -3275, 5598, 2323, 23729779),
    "j0-56": (53624256071278747, 140057, -231499057, 231639114,
              140057, 53624256071278747),
}
AXIAL = ((-1, 0), (0, -1), (0, 0), (0, 1), (1, 0))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_body(source, name):
    return source.split(name, 1)[1].split("{", 1)[1].split("};", 1)[0]


def atlas_tables():
    source = ATLAS.read_text()
    index = [int(value) for value in re.findall(
        r"\d+", array_body(source, "ca_tau4_atlas_index[6561]"))]
    patterns = [tuple(map(int, match)) for match in re.findall(
        r"\{\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\}",
        array_body(source, "ca_tau4_atlas_patterns[217]"))]
    assert len(index) == 6561 and len(patterns) == 217
    return index, patterns


def round_div(a, b):
    if b < 0:
        a, b = -a, -b
    return -((-a + b // 2) // b) if a < 0 else (a + b // 2) // b


def states(x, y, index, patterns):
    result = []
    while x or y:
        result.append((x, y))
        pattern = patterns[index[81 * (x % 81) + (y % 81)]]
        a, b = x - pattern[2], y - pattern[3]
        nx, ny = a + 3 * b, -a - 2 * b
        assert nx % 9 == ny % 9 == 0
        x, y = nx // 9, ny // 9
    return result


def main():
    index, patterns = atlas_tables()
    result = {
        "schema": 1,
        "kind": "exploratory_five_neighbor_suffix_sharing_upper_bound",
        "atlas_sha256": sha(ATLAS),
        "analyzer_sha256": sha(Path(__file__)),
        "curves": {},
    }
    for curve, (order, v1x, v1y, v2x, v2y, det) in CURVES.items():
        fixture = HERE.parent / "prime-j0-free-gauge" / f"heldout-{curve}.bin"
        raw = fixture.read_bytes()
        assert len(raw) == 1024 * 16
        total = unique = nonzero = sharing = 0
        for a, b in struct.iter_unpack("<QQ", raw):
            for scalar in (a, b):
                scalar %= order
                if scalar == 0:
                    continue
                nonzero += 1
                u0 = round_div(scalar * v2y, det)
                v0 = round_div(-scalar * v1y, det)
                sequences = []
                for du, dv in AXIAL:
                    u, v = u0 + du, v0 + dv
                    x = scalar - u * v1x - v * v2x
                    y = -u * v1y - v * v2y
                    sequences.append(states(x + y, -y, index, patterns))
                blocks = sum(map(len, sequences))
                distinct = len(set().union(*map(set, sequences)))
                total += blocks
                unique += distinct
                sharing += blocks > distinct
        result["curves"][curve] = {
            "fixture_sha256": sha(fixture),
            "nonzero_scalars": nonzero,
            "atlas_states": total,
            "distinct_states_within_scalar": unique,
            "maximum_reusable_states": total - unique,
            "scalars_with_any_reuse": sharing,
        }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
