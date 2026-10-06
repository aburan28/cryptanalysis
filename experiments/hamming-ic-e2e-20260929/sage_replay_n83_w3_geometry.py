#!/usr/bin/env python3
"""Independent Sage lift_x replay of the exact N83 W3 base geometry."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from math import comb
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector, ZZ

N = 83
R = 2417851639230796216685689
H = 4


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(points):
    return hashlib.sha256(json.dumps([list(pair) for pair in sorted(points)],
                       sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main(out):
    out = out.resolve()
    start = time.perf_counter_ns()
    record = json.loads((out / "geometry.json").read_text())
    reps = json.loads((out / "representatives.json").read_text())
    assert record["status"] == "EXACT_GEOMETRY_PASS"
    assert record["curve_id"] == reps["curve_id"] == "EC1N83Ckb1h2bcb59d56ad6"
    identity = record["curve_identity_record"]
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()
    assert record["curve_id"] == "EC1N83Ckb1h" + hashlib.sha256(encoded).hexdigest()[:12]
    assert record["source_sha256"] == sha(Path(__file__).with_name("sage_measure_n83_w3_geometry.py"))
    assert record["representatives_sha256"] == sha(out / "representatives.json")
    assert record["sage_runtime_info_sha256"] == sha(out / "sage_runtime_info.json")
    assert (out / "sage_runtime_info_replay.json").is_file()

    binary = GF(2)
    ring = PolynomialRing(binary, "v")
    v = ring.gen()
    field = GF(2**N, "w", modulus=v**N + v**7 + v**4 + v**2 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert ZZ(R).is_prime(proof=True)
    assert curve.cardinality() == R * H

    def element(code):
        return field(ring([(code >> bit) & 1 for bit in range(N)]))

    def encode(value):
        return sum(int(coefficient) << bit
                   for bit, coefficient in enumerate(value.polynomial().list()))

    generator_pair = identity["curve"]["G"]
    generator = curve(element(generator_pair[0]), element(generator_pair[1]))
    assert generator != curve(0) and R * generator == curve(0)

    alpha = element(record["normal_element_polynomial_bits"])
    conjugates = [alpha]
    for _ in range(1, N):
        conjugates.append(conjugates[-1]**2)
    columns = [vector(binary, [(encode(value) >> bit) & 1 for bit in range(N)])
               for value in conjugates]
    basis_matrix = matrix(binary, N, N, lambda row, col: columns[col][row])
    assert basis_matrix.rank() == N

    visited = set()
    canonical_reps, projected, raw = set(), set(), set()
    rational_orbits = 0
    nonrational_orbits = 0
    for mask in itertools.combinations(range(N), 3):
        if mask in visited:
            continue
        shifted = {tuple(sorted((bit + shift) % N for bit in mask))
                   for shift in range(N)}
        assert len(shifted) == N
        visited.update(shifted)
        x = sum((conjugates[bit] for bit in mask), field(0))
        lifts = list(curve.lift_x(x, all=True))
        if not lifts:
            nonrational_orbits += 1
            continue
        assert len(lifts) == 2 and lifts[0] == -lifts[1]
        rational_orbits += 1
        point = lifts[0]
        image = H * point
        assert image != curve(0) and R * image == curve(0)
        for source, destination in ((point, raw), (image, projected)):
            cx, cy = source[0], source[1]
            for _ in range(N):
                x_code, y_code = encode(cx), encode(cy)
                destination.update(((x_code, y_code), (x_code, x_code ^ y_code)))
                cx, cy = cx**2, cy**2
            assert (cx, cy) == (source[0], source[1])
        px, py = image[0], image[1]
        keys = []
        for _ in range(N):
            x_code, y_code = encode(px), encode(py)
            keys.extend(((x_code, y_code), (x_code, x_code ^ y_code)))
            px, py = px**2, py**2
        canonical_reps.add(min(keys))

    archived = {tuple(pair) for pair in reps["representatives"]}
    assert len(visited) == comb(N, 3)
    assert rational_orbits == record["rational_x_orbits"]
    assert nonrational_orbits == record["nonrational_x_orbits"]
    assert canonical_reps == archived
    assert len(raw) == record["geometric_raw_points"]
    assert len(projected) == record["actual_usable_projected_points_B"]
    assert len(canonical_reps) == record["effective_signed_frobenius_columns"]
    assert len(projected) == 2 * N * len(canonical_reps)
    assert digest(raw) == record["raw_point_set_sha256"]
    assert digest(projected) == record["projected_point_set_sha256"]
    assert int(record["four_point_multisets_with_repetition"]) == comb(len(projected) + 3, 4)
    assert comb(len(projected) + 3, 4) < R

    report = {
        "schema_version": 1, "kind": "n83_w3_four_sum_geometry_independent_replay",
        "status": "PASS", "curve_id": record["curve_id"],
        "field_degree": N, "subgroup_order": str(R),
        "normal_basis_rank": int(basis_matrix.rank()),
        "mask_orbits_replayed": rational_orbits + nonrational_orbits,
        "rational_x_orbits": rational_orbits,
        "actual_usable_projected_points_B": len(projected),
        "effective_signed_frobenius_columns": len(canonical_reps),
        "exact_representative_set_match": True,
        "raw_point_set_sha256": digest(raw),
        "projected_point_set_sha256": digest(projected),
        "four_point_multisets_with_repetition": str(comb(len(projected) + 3, 4)),
        "support_fraction_upper_bound_exact_numerator": str(comb(len(projected) + 3, 4)),
        "support_fraction_upper_bound_exact_denominator": str(R),
        "geometry_sha256": sha(out / "geometry.json"),
        "representatives_sha256": sha(out / "representatives.json"),
        "sage_runtime_info_replay_sha256": sha(out / "sage_runtime_info_replay.json"),
        "replay_source_sha256": sha(Path(__file__)),
        "replay_wall_ms": (time.perf_counter_ns() - start) / 1e6,
        "claim_boundary": "Independent exact geometry and support-bound check only; no ordinary-query PDP or DLP",
    }
    (out / "sage_replay.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in (
        "status", "mask_orbits_replayed", "actual_usable_projected_points_B",
        "effective_signed_frobenius_columns")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    main(parser.parse_args().out)
