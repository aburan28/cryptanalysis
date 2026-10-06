#!/usr/bin/env python3
"""Independent checked-Sage replay of W3-root IC relations and target log."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, is_prime, matrix, vector

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/n53_w3_root_smoke_v1"
EXPORT = HERE / "runs/n53_w3_base_export_v1"
N, R, COFACTOR = 53, 21044858204113, 428
GENERATOR = (198217578752339, 7929897206038174)
FIXTURE_SCALAR_VALIDATION_ONLY = 596471236405


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def main():
    runtime = RUN / "sage_runtime_info.json"
    if not runtime.is_file():
        raise FileNotFoundError("save checked Sage runtime info before replay")
    receipt = json.loads((RUN / "receipt.json").read_text())
    output = json.loads((RUN / "ic_result.jsonl").read_text())
    reps = json.loads((EXPORT / "representatives.json").read_text())
    export = json.loads((EXPORT / "receipt.json").read_text())
    assert sha(RUN / "ic_result.jsonl") == receipt["result_sha256"]
    assert sha(EXPORT / "representatives.json") == receipt["representatives_sha256"]
    assert receipt["example_source_sha256"] == sha(HERE / "koblitz_w3_root_index.rs")
    assert receipt["output_bindings_valid"] is True
    binary = GF(2)
    ring = PolynomialRing(binary, "u")
    u = ring.gen()
    field = GF(2**N, "z", modulus=u**N + u**6 + u**2 + u + 1)
    z = field.gen()
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert is_prime(R) and curve.cardinality() == R * COFACTOR

    def element(bits):
        return sum((z**i for i in range(N) if bits >> i & 1), field(0))

    def encode(value):
        return sum(int(coefficient) << i
                   for i, coefficient in enumerate(value.polynomial().list()))

    def point(pair):
        return curve(element(pair[0]), element(pair[1]))

    generator = point(GENERATOR)
    target = point(receipt["target"])
    assert generator != curve(0) and R * generator == curve(0)
    assert target != curve(0) and R * target == curve(0)
    assert FIXTURE_SCALAR_VALIDATION_ONLY * generator == target
    assert output["target"] == receipt["target"]
    assert output["recovered_scalar"] * generator == target
    assert output["recovered_scalar"] == FIXTURE_SCALAR_VALIDATION_ONLY

    lam = reps["lambda_mod_r"]
    base = []
    labels = []
    ordered_entries = []
    for column, pair in enumerate(reps["representatives"]):
        current = point(pair)
        coefficient = 1
        assert lam * current == curve(current[0]**2, current[1]**2)
        for _ in range(N):
            for signed, label in ((current, coefficient), (-current, -coefficient % R)):
                base.append(signed)
                labels.append((column, label))
                ordered_entries.append([encode(signed[0]), encode(signed[1]), column, label])
            current = curve(current[0]**2, current[1]**2)
            coefficient = coefficient * lam % R
        assert [encode(current[0]), encode(current[1])] == pair
    assert len(base) == output["factor_base_points"] == 23426
    assert len(reps["representatives"]) == output["orbit_columns"] == 221
    assert digest(ordered_entries) == export["ordered_labeled_entries_sha256"]

    def row(indices):
        coefficients = [0] * len(reps["representatives"])
        for index in indices:
            column, coefficient = labels[index]
            coefficients[column] = (coefficients[column] + coefficient) % R
        return coefficients

    witnesses = output["rank_relation_witnesses"]
    assert len(witnesses) == output["rank_verified_relations"] == 214
    rows, scalars = [], []
    for witness in witnesses:
        indices = witness["point_indices"]
        assert len(indices) == 4 and all(0 <= index < len(base) for index in indices)
        assert sum((base[index] for index in indices), curve(0)) == \
               witness["relation_scalar"] * generator
        assert witness["x_codes"] == [encode(base[index][0]) for index in indices]
        rows.append(row(indices))
        scalars.append(witness["relation_scalar"])
    target_indices = output["target_relation_indices"]
    assert len(target_indices) == 4
    assert sum((base[index] for index in target_indices), curve(0)) == target
    target_row = row(target_indices)
    prime_field = GF(R)
    relation_matrix = matrix(prime_field, rows)
    assert relation_matrix.rank() == output["rank"] == 214
    combination = relation_matrix.transpose().solve_right(vector(prime_field, target_row))
    assert combination * relation_matrix == vector(prime_field, target_row)
    derived_log = int(sum((combination[i] * prime_field(scalars[i])
                           for i in range(len(scalars))), prime_field(0)))
    assert derived_log == output["recovered_scalar"]
    assert derived_log == output["target_span_recovered_scalar"]
    report = {"status": "PASS", "kind": "n53_w3_root_ic_sage_replay",
              "curve_cardinality": R * COFACTOR,
              "base_points": len(base), "columns": len(reps["representatives"]),
              "verified_relation_witnesses": len(witnesses),
              "independent_relation_rank": int(relation_matrix.rank()),
              "target_relation_verified": True,
              "target_row_in_relation_span": True,
              "independently_derived_scalar": derived_log,
              "scalar_replay_verified": True,
              "runtime_info_sha256": sha(runtime),
              "source_ic_result_sha256": sha(RUN / "ic_result.jsonl"),
              "source_base_export_sha256": sha(EXPORT / "receipt.json"),
              "source_sha256": sha(Path(__file__))}
    (RUN / "sage_replay.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
