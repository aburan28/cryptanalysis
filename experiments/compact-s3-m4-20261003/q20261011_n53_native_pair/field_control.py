#!/usr/bin/env python3
"""Cross-check frozen native N53 field, group, and quotient-key arithmetic."""
from __future__ import annotations
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
import field  # noqa: E402
import curves  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402

BINARY = Path("/private/tmp/q1454_field_control")
OUT = HERE / "native_field_control.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not OUT.exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    header = HERE / "native_field53.hpp"
    assert frozen["sources_sha256"][str(header.relative_to(ROOT))] == sha(header)
    command = ["/usr/bin/clang++", "-O3", "-std=c++17", "-o", str(BINARY),
               str(HERE / "field_control.cpp")]
    subprocess.run(command, check=True)
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    quotient = OrbitKey(onb)
    rng = random.Random(1454)
    field_rows = [(onb.fromCoords(rng.randrange(1, 1 << 53)),
                   onb.fromCoords(rng.randrange(1, 1 << 53))) for _ in range(1000)]
    prior = json.loads((HERE.parent / "q20261011_n53_table2m/measurement.json").read_text())
    seed_points = [tuple(point) for point in prior["first_verified_relation"]["points"]]
    points = []
    for seed in seed_points:
        point = seed
        for _ in range(53):
            points.append(point)
            point = curve.frob(point)
    group_pairs = [(points[rng.randrange(len(points))],
                    points[rng.randrange(len(points))]) for _ in range(200)]
    group_pairs += [(point, point) for point in seed_points]
    group_pairs += [(point, curve.neg(point)) for point in seed_points]
    rows = [(a, b, a, b) for a, b in field_rows]
    rows += [(*p, *q) for p, q in group_pairs]
    input_text = "".join(" ".join(format(value, "x") for value in row) + "\n"
                         for row in rows)
    result = subprocess.run([str(BINARY)], input=input_text, text=True,
                            capture_output=True, check=True)
    lines = result.stdout.splitlines()
    assert len(lines) == len(rows)
    for (a, b), line in zip(field_rows, lines):
        product, square, inverse, *_ = line.split()
        assert int(product, 16) == onb.mul(a, b)
        assert int(square, 16) == onb.sqr(a)
        assert int(inverse, 16) == onb.inv(a)
    for (p, q), line in zip(group_pairs, lines[len(field_rows):]):
        tokens = line.split()
        sum_point = curve.add(p, q)
        if sum_point is None:
            assert tokens[3:6] == ["I", "I", "I"]
        else:
            assert (int(tokens[3], 16), int(tokens[4], 16)) == sum_point
            assert (int(tokens[5], 16), int(tokens[6]), int(tokens[7])) == quotient.canonical(sum_point)
    receipt = {"status": "PASS", "proposal_id": "Q1454", "field_cases": len(field_rows),
               "group_key_cases": len(group_pairs), "seed": 1454,
               "header_sha256": sha(header),
               "control_source_sha256": sha(HERE / "field_control.cpp"),
               "control_script_sha256": sha(Path(__file__)),
               "binary_sha256": sha(BINARY),
               "prior_relation_sha256": sha(HERE.parent / "q20261011_n53_table2m/measurement.json"),
               "freeze_sha256": sha(HERE / "freeze.json")}
    OUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print("PASS Q1454 native field", len(field_rows), "group/key", len(group_pairs))


if __name__ == "__main__":
    main()
