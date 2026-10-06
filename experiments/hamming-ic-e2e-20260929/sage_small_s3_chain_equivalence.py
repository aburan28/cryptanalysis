#!/usr/bin/env python3
"""Exhaustively compare the implicit S3 chain with five-point sums on a small field."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(degree: int, out: Path) -> None:
    if degree not in (3, 4):
        raise ValueError("small exhaustive control supports degree 3 or 4")
    out = out.resolve()
    if not (out / "sage_runtime_info.json").is_file():
        raise FileNotFoundError("save checked Sage --runtime-info before the control")
    if (out / "report.json").exists():
        raise FileExistsError("small-field report is immutable")
    start = time.perf_counter_ns()
    field = GF(2**degree, "w")
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    elements = list(field)

    def word(value):
        return sum(int(bit) << index for index, bit in
                   enumerate(value.polynomial().list()))

    def s3(a, b, c):
        e2 = a * b + a * c + b * c
        return e2**2 + a * b * c + field(1)

    lifts = {x: tuple(curve.lift_x(x, all=True)) for x in elements}
    rational = [x for x in elements if lifts[x]]
    roots = {(a, b): {c for c in elements if s3(a, b, c) == 0}
             for a, b in itertools.product(elements, repeat=2)}
    false_positive = false_negative = matching = identity_possible = 0
    examples = []
    for xs in itertools.product(rational, repeat=5):
        reach = roots[xs[0], xs[1]]
        for factor in xs[2:]:
            reach = {next_x for middle in reach
                     for next_x in roots[middle, factor]}
        actual = set()
        has_identity = False
        for points in itertools.product(*(lifts[x] for x in xs)):
            total = sum(points, curve(0))
            if total == curve(0):
                has_identity = True
            else:
                actual.add(total[0])
        if has_identity:
            identity_possible += 1
        extra = reach - actual
        missing = actual - reach
        false_positive += len(extra)
        false_negative += len(missing)
        matching += len(reach & actual)
        if (extra or missing) and len(examples) < 8:
            examples.append({
                "factor_x": [word(x) for x in xs],
                "spurious_target_x": sorted(word(x) for x in extra),
                "missed_target_x": sorted(word(x) for x in missing),
                "identity_sum_possible": has_identity,
            })

    report = {
        "schema_version": 1,
        "kind": "small_field_five_point_implicit_s3_chain_equivalence",
        "degree": degree,
        "field_modulus": str(field.modulus()),
        "curve_model": "y^2+xy=x^3+1",
        "curve_order": int(curve.cardinality()),
        "field_x_count": len(elements),
        "rational_factor_x_count": len(rational),
        "factor_x_tuples": len(rational)**5,
        "chain_reachable_and_group_reachable_pairs": matching,
        "chain_spurious_pairs": false_positive,
        "chain_missed_pairs": false_negative,
        "tuples_admitting_identity_sum": identity_possible,
        "first_mismatches": examples,
        "status": "PASS" if not false_positive and not false_negative else "COUNTEREXAMPLE",
        "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(out / "sage_runtime_info.json"),
        "wall_ms_exploratory": (time.perf_counter_ns() - start) / 1e6,
        "claim_boundary": "Small-field x-only algebraic control; not N83 target yield or speed.",
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("degree", "status", "factor_x_tuples",
                       "chain_spurious_pairs", "chain_missed_pairs")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("degree", type=int)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    main(args.degree, args.out)
