#!/usr/bin/env python3
"""Independent checked-Sage replay of one paired W3-root IC and rho run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, is_prime, matrix, vector

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/n53_w3_root_pair_v2"
EXPORT = HERE / "runs/n53_w3_base_export_v1"
N, R, COFACTOR = 53, 21044858204113, 428
GENERATOR = (198217578752339, 7929897206038174)


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
    rho = json.loads((RUN / "rho.stdout.txt").read_text())
    candidate_file = json.loads((RUN / "candidate.json").read_text())
    workload_file = json.loads((RUN / "workload.json").read_text())
    fixture_scalar = workload_file["fixture_scalar_validation_only"]
    reps = json.loads((EXPORT / "representatives.json").read_text())
    export = json.loads((EXPORT / "receipt.json").read_text())
    assert sha(RUN / "ic_result.jsonl") == receipt["ic"]["result_sha256"]
    assert sha(RUN / "rho.stdout.txt") == receipt["rho"]["result_sha256"]
    assert sha(EXPORT / "representatives.json") == receipt["base_export_sha256"]
    assert receipt["source_sha256"]["ic_example.rs"] == sha(HERE / "koblitz_w3_root_index.rs")
    assert receipt["source_sha256"]["rho_example.rs"] == sha(HERE / "koblitz_rho_point.rs")
    assert candidate_file["candidate_id"] == receipt["candidate_id"]
    assert digest(candidate_file["record"])[:12] == receipt["candidate_id"].split("h")[-1]
    assert workload_file["workload_id"] == receipt["workload_id"] == digest(workload_file["record"])[:12]
    assert receipt["run_id"] == receipt["candidate_id"] + "W" + receipt["workload_id"] + "R2"
    assert receipt["ic"]["in_process_verified"] and receipt["rho"]["in_process_verified"]
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
    target = point(receipt["target_point"])
    assert generator != curve(0) and R * generator == curve(0)
    assert target != curve(0) and R * target == curve(0)
    assert fixture_scalar * generator == target
    assert output["target"] == receipt["target_point"]
    assert output["recovered_scalar"] * generator == target
    assert output["recovered_scalar"] == fixture_scalar
    assert rho["target_point"] == receipt["target_point"]
    assert rho["recovered_scalar"] * generator == target
    assert rho["recovered_scalar"] == fixture_scalar
    assert rho["verified"] is True

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
    assert len(witnesses) == output["rank_verified_relations"]
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
    assert relation_matrix.rank() == output["rank"]
    combination = relation_matrix.transpose().solve_right(vector(prime_field, target_row))
    assert combination * relation_matrix == vector(prime_field, target_row)
    derived_log = int(sum((combination[i] * prime_field(scalars[i])
                           for i in range(len(scalars))), prime_field(0)))
    assert derived_log == output["recovered_scalar"]
    assert derived_log == output["target_span_recovered_scalar"]
    assert derived_log == rho["recovered_scalar"]
    ic_ms = output["timing_ms"]["target_online_after_reusable_setup"]
    rho_ms = rho["online_ms"]
    phases = [output["timing_ms"][name] for name in (
        "target_query", "target_pdp_charged", "target_relation_check",
        "target_descent", "target_recovery_check")]
    assert abs(sum(phases) - ic_ms) < 1e-6
    assert abs(rho_ms / ic_ms - receipt["online_speedup_in_process_only"]) < 1e-10
    report = {"status": "PASS", "kind": "n53_w3_root_ic_vs_rho_sage_replay",
              "candidate_id": receipt["candidate_id"], "workload_id": receipt["workload_id"],
              "run_id": receipt["run_id"], "target_point": receipt["target_point"],
              "curve_cardinality": R * COFACTOR,
              "base_points": len(base), "columns": len(reps["representatives"]),
              "verified_relation_witnesses": len(witnesses),
              "independent_relation_rank": int(relation_matrix.rank()),
              "target_relation_verified": True,
              "target_row_in_relation_span": True,
              "independently_derived_scalar": derived_log,
              "ic_scalar_replay_verified": True, "rho_scalar_replay_verified": True,
              "ic_online_ms": ic_ms, "rho_online_ms": rho_ms,
              "online_speedup": rho_ms / ic_ms,
              "ic_exclusive_online_phase_ms": {
                  "target_query": phases[0], "target_pdp": phases[1],
                  "target_relation_check": phases[2], "target_descent": phases[3],
                  "target_recovery_check": phases[4]},
              "runtime_info_sha256": sha(runtime),
              "source_ic_result_sha256": sha(RUN / "ic_result.jsonl"),
              "source_base_export_sha256": sha(EXPORT / "receipt.json"),
              "source_sha256": sha(Path(__file__))}
    (RUN / "sage_replay.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
