#!/usr/bin/env python3
"""Solve and independently replay multiplier-weighted N53 relation rows."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector

from a1_n53_pair_sage_verification import CLASSES, bits, from_bits

HERE = Path(__file__).resolve().parent
GEOMETRY = HERE.parent / "ic-ideas-20261007/results/a1_n53_k600_followup_final.json"
GENERATOR_CHECK = HERE / "a1_n53_pair_sage_verification.json"
RAW = HERE / "a1_n53_pair_closure_k600_q128_raw.json"
RECEIPT = HERE / "a1_n53_pair_closure_k600_q128.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "a1_n53_rank_replay.json"
    if output.exists():
        raise FileExistsError(output)
    started = time.perf_counter_ns()
    geometry = json.loads(GEOMETRY.read_text())
    prior = json.loads(GENERATOR_CHECK.read_text())
    raw = json.loads(RAW.read_text())
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["status"] == "completed_verified"
    assert receipt["raw_sha256"] == sha(RAW)
    assert raw["policy"] == "closure"
    assert raw["independent_log_columns"] == 60
    assert raw["geometric_columns"] == 600
    assert raw["query_count"] == 128
    r = geometry["subgroup_order"]
    lam = geometry["frobenius_scalar"]
    assert r == raw["subgroup_order"]
    rows = []
    rhs = []
    for query in raw["rows"]:
        if not query["hit"]:
            continue
        coefficients = [0] * 60
        for point_index in query["witness_indices"]:
            geometric, within = divmod(point_index, 106)
            column, multiplier_index = divmod(geometric, 10)
            frobenius_shift, sign_index = divmod(within, 2)
            coefficient = CLASSES[multiplier_index] * pow(lam, frobenius_shift, r) % r
            if sign_index:
                coefficient = (-coefficient) % r
            coefficients[column] = (coefficients[column] + coefficient) % r
        rows.append(coefficients)
        rhs.append(query["scalar"])
    assert len(rows) == raw["verified_hits"]
    scalar_field = GF(r)
    A = matrix(scalar_field, rows)
    b = vector(scalar_field, rhs)
    rank = int(A.rank())
    assert rank == raw["rank"]
    full_rank = rank == 60
    seed_log_x_replays = None
    logs = None
    if full_rank:
        solution = A.solve_right(b)
        assert A * solution == b
        logs = [int(value) for value in solution]
        F2 = GF(2)
        P = PolynomialRing(F2, "u")
        u = P.gen()
        modulus_bits = geometry["field_modulus_bits"]
        modulus = sum((u**i for i in range(54) if modulus_bits >> i & 1), P(0))
        K = GF(2**53, "a", modulus=modulus)
        E = EllipticCurve(K, [1, 0, 0, 0, 1])
        generator_bits = prior["generator_point"]
        G = E(from_bits(K, generator_bits[0]), from_bits(K, generator_bits[1]))
        assert r * G == E(0)
        assert raw["rows"][0]["scalar"] * G == E(
            from_bits(K, raw["rows"][0]["target_point"][0]),
            from_bits(K, raw["rows"][0]["target_point"][1]))
        seen = set()
        seed_reps = []
        scanned_x = 0
        raw_x = 1
        while len(seed_reps) < 60:
            scanned_x += 1
            for P in E.lift_x(from_bits(K, raw_x), all=True):
                candidate = geometry["cofactor"] * P
                if not candidate or bits(candidate[0]) <= 1:
                    continue
                x = candidate[0]
                key = bits(x)
                for _ in range(1, 53):
                    x *= x
                    key = min(key, bits(x))
                if key in seen:
                    continue
                seen.add(key)
                seed_reps.append(candidate)
                if len(seed_reps) == 60:
                    break
            raw_x += 1
        assert scanned_x == raw["scanned_x"]
        seed_log_x_replays = [bits((value * G)[0]) == bits(P[0])
                              for value, P in zip(logs, seed_reps)]
        assert all(seed_log_x_replays)
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "field_degree": 53, "curve_id": geometry["curve_id"],
              "query_count": raw["query_count"],
              "verified_relations": len(rows),
              "weighted_relation_rank": rank,
              "independent_seed_log_columns": 60,
              "full_rank": full_rank,
              "solved_seed_logs": logs,
              "sage_seed_log_x_replays": seed_log_x_replays,
              "stage_wall_ns_exploratory": time.perf_counter_ns() - started,
              "geometry_receipt_sha256": sha(GEOMETRY),
              "generator_check_sha256": sha(GENERATOR_CHECK),
              "raw_sha256": sha(RAW),
              "receipt_sha256": sha(RECEIPT),
              "source_sha256": sha(Path(__file__))}
    output.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"relations": len(rows), "rank": rank,
                      "full_rank": full_rank,
                      "seed_log_replays": sum(seed_log_x_replays)
                          if seed_log_x_replays is not None else None}))


if __name__ == "__main__":
    main()
