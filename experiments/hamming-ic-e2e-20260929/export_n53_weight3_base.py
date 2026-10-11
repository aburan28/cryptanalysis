#!/usr/bin/env python3
"""Freeze the exact W3 projected base as 221 ordered signed Frobenius reps."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import time

from n53_group import COFACTOR, Curve, Field, GENERATOR, N, R, normal_basis

HERE = Path(__file__).resolve().parent
GEOMETRY = HERE / "runs/n53_weight3_geometry_v1/receipt.json"
LAMBDA = 10244141222326


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frobenius(field, point):
    return field.square(point[0]), field.square(point[1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("base export is immutable")
    out.mkdir(parents=True)
    start = time.perf_counter_ns()
    geometry = json.loads(GEOMETRY.read_text())
    field = Field()
    curve = Curve(field)
    _, conjugates = normal_basis(field)
    assert (LAMBDA * LAMBDA + LAMBDA + 2) % R == 0
    assert pow(LAMBDA, N, R) == 1
    assert curve.mul(GENERATOR, LAMBDA) == frobenius(field, GENERATOR)

    # Generate one representative per weight-three mask orbit, then expand
    # its two rational lifts and cofactor projections through Frobenius.
    visited = set()
    projected = set()
    for mask in itertools.combinations(range(N), 3):
        if mask in visited:
            continue
        orbit = {tuple(sorted((i + shift) % N for i in mask))
                 for shift in range(N)}
        assert len(orbit) == N
        visited.update(orbit)
        x = conjugates[mask[0]] ^ conjugates[mask[1]] ^ conjugates[mask[2]]
        for point in curve.lift(x):
            image = curve.mul(point, COFACTOR)
            assert image is not None and curve.mul(image, R) is None
            for _ in range(N):
                projected.add(image)
                image = frobenius(field, image)
    assert len(projected) == geometry["actual_usable_projected_points"] == 23426
    assert digest([list(p) for p in sorted(projected)]) == geometry["projected_set_sha256"]

    remaining = set(projected)
    representatives = []
    entries = []
    while remaining:
        representative = min(remaining)
        column = len(representatives)
        representatives.append(representative)
        assert curve.mul(representative, LAMBDA) == frobenius(field, representative)
        point = representative
        coefficient = 1
        for _ in range(N):
            negative = curve.neg(point)
            assert point in remaining and negative in remaining
            remaining.remove(point)
            remaining.remove(negative)
            entries.extend(([point[0], point[1], column, coefficient],
                            [negative[0], negative[1], column, (-coefficient) % R]))
            point = frobenius(field, point)
            coefficient = coefficient * LAMBDA % R
        assert point == representative and coefficient == 1
    assert len(representatives) == geometry["effective_signed_frobenius_columns"] == 221
    assert len(entries) == geometry["actual_usable_projected_points"]
    assert {tuple(row[:2]) for row in entries} == projected

    rep_record = {"schema_version": 1, "curve_id": geometry["curve_id"],
                  "factor_base_policy": "all rational x with normal-basis Hamming weight 3, cofactor projection, sorted signed-Frobenius orbit representatives",
                  "normal_element": 3, "lambda_mod_r": LAMBDA,
                  "subgroup_order": R, "cofactor": COFACTOR,
                  "representatives": [list(p) for p in representatives]}
    reps_path = out / "representatives.json"
    reps_path.write_text(json.dumps(rep_record, indent=2, sort_keys=True) + "\n")
    report = {"kind": "n53_weight3_exact_factor_base_export",
              "curve_id": geometry["curve_id"], "candidate_id": None,
              "normal_element": 3, "lambda_mod_r": LAMBDA,
              "actual_usable_points": len(entries),
              "effective_columns": len(representatives),
              "projected_set_sha256": geometry["projected_set_sha256"],
              "representatives_sha256": sha(reps_path),
              "ordered_labeled_entries_sha256": digest(entries),
              "source_geometry_receipt_sha256": sha(GEOMETRY),
              "source_sha256": {"export_n53_weight3_base.py": sha(Path(__file__)),
                                "n53_group.py": sha(HERE / "n53_group.py")},
              "wall_ns": time.perf_counter_ns() - start,
              "claim_boundary": "Exact portable factor-base input for a future root-index candidate; no complete algorithm wiring, natural relation, or DLP run."}
    (out / "receipt.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("actual_usable_points", "effective_columns",
                       "ordered_labeled_entries_sha256", "wall_ns")}, sort_keys=True))


if __name__ == "__main__":
    main()
