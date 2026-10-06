#!/usr/bin/env python3
"""Screen a sound linear-span relaxation of a fixed-intermediate S3 pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402

PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "result.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def s3(onb, a: int, b: int, m: int) -> int:
    ab = onb.mul(a, b)
    am = onb.mul(a, m)
    bm = onb.mul(b, m)
    return onb.sqr(ab ^ am ^ bm) ^ onb.mul(ab, m) ^ onb.one()


def insert(basis: list[int], value: int) -> int:
    while value:
        pivot = value.bit_length() - 1
        if basis[pivot]:
            value ^= basis[pivot]
        else:
            basis[pivot] = value
            return 1
    return 0


def contains(basis: list[int], value: int) -> bool:
    while value:
        pivot = value.bit_length() - 1
        if not basis[pivot]:
            return False
        value ^= basis[pivot]
    return True


def coefficients(onb, basis: list[int], a0: int, b0: int,
                 m: int, free_a: list[int], free_b: list[int]):
    """Return constant, linear columns, and a lazy bilinear-column maker.

    S3(a0+sum(u_i e_i), b0+sum(v_j e_j), m) is
    c + sum(u_i alpha_i) + sum(v_j beta_j) + sum(u_i v_j gamma_ij).
    Its F2-linear span is a necessary feasibility test only: independent
    monomial choices need not correspond to any actual u, v assignment.
    """
    m2, a2, b2 = onb.sqr(m), onb.sqr(a0), onb.sqr(b0)
    bm, am = onb.mul(b0, m), onb.mul(a0, m)
    linear = []
    for i in free_a:
        e = basis[i]
        linear.append(onb.toCoords(onb.mul(onb.sqr(e), b2 ^ m2) ^
                                   onb.mul(e, bm)))
    for j in free_b:
        e = basis[j]
        linear.append(onb.toCoords(onb.mul(onb.sqr(e), a2 ^ m2) ^
                                   onb.mul(e, am)))

    def cross(i: int, j: int) -> int:
        product = onb.mul(basis[i], basis[j])
        return onb.toCoords(onb.sqr(product) ^ onb.mul(product, m))

    return onb.toCoords(s3(onb, a0, b0, m)), linear, cross


def relaxed_feasible(onb, basis: list[int], a0: int, b0: int,
                     m: int, free_a: list[int], free_b: list[int]) -> dict:
    constant, linear, cross = coefficients(
        onb, basis, a0, b0, m, free_a, free_b)
    pivots = [0] * onb.m
    rank = 0
    for column in linear:
        rank += insert(pivots, column)
    cross_tested = 0
    if rank < onb.m:
        for i in free_a:
            for j in free_b:
                rank += insert(pivots, cross(i, j))
                cross_tested += 1
                if rank == onb.m:
                    break
            if rank == onb.m:
                break
    return {"rank": rank, "constant_in_span": contains(pivots, constant),
            "cross_columns_tested": cross_tested}


def self_test() -> int:
    rejected_states = 0
    for n in (3, 5):
        onb = field.Onb(n)
        basis = [onb.fromCoords(1 << i) for i in range(n)]
        for m_coords in range(1, 1 << n):
            m = onb.fromCoords(m_coords)
            for split in range(n + 1):
                free = list(range(split, n))
                fixed_mask = (1 << split) - 1
                for a_coords in range(1 << split):
                    for b_coords in range(1 << split):
                        a0 = onb.fromCoords(a_coords & fixed_mask)
                        b0 = onb.fromCoords(b_coords & fixed_mask)
                        check = relaxed_feasible(
                            onb, basis, a0, b0, m, free, free)
                        rejected_states += not check["constant_in_span"]
                        constant, linear, cross = coefficients(
                            onb, basis, a0, b0, m, free, free)
                        for ua in range(1 << len(free)):
                            a = a0 ^ onb.fromCoords(ua << split)
                            for vb in range(1 << len(free)):
                                b = b0 ^ onb.fromCoords(vb << split)
                                predicted = constant
                                for i in range(len(free)):
                                    if ua >> i & 1:
                                        predicted ^= linear[i]
                                    if vb >> i & 1:
                                        predicted ^= linear[len(free) + i]
                                for i, left in enumerate(free):
                                    if not (ua >> i & 1):
                                        continue
                                    for j, right in enumerate(free):
                                        if vb >> j & 1:
                                            predicted ^= cross(left, right)
                                actual = onb.toCoords(s3(onb, a, b, m))
                                assert predicted == actual
                                if not check["constant_in_span"]:
                                    assert actual != 0
    assert rejected_states > 0
    return rejected_states


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        rejects = self_test()
        print(json.dumps({"status": "PASS", "degrees": [3, 5],
                          "rejected_partial_states": rejects}))
        return
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1428"
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert protocol["q1427_protocol_sha256"] == sha(
        PARENT / "q1427_interleaved_pair/protocol.json")
    q1427 = json.loads((PARENT / "q1427_interleaved_pair/protocol.json").read_text())
    rows = []
    for item in protocol["degrees"]:
        n, w = item["degree_n"], item["weight_bound"]
        archived = q1427["workloads"][f"n{n}_ordinary"]
        for key in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                    "factor_base_enumerated_set_sha256"):
            assert archived[key] == item[key]
        onb = field.Onb(n)
        basis = [onb.fromCoords(1 << i) for i in range(n)]
        for k in item["free_suffix_sizes"]:
            rng = random.Random(protocol["seed"] + 1000 * n + k)
            ranks, rejects, cross_counts = [], 0, []
            for _ in range(protocol["samples_per_cell"]):
                m = onb.fromCoords(rng.randrange(1, 1 << n))
                fixed = list(range(n - k))
                count = min(w, len(fixed))
                a_bits = rng.sample(fixed, count)
                b_bits = rng.sample(fixed, count)
                a0 = onb.fromCoords(sum(1 << i for i in a_bits))
                b0 = onb.fromCoords(sum(1 << i for i in b_bits))
                free = list(range(n - k, n))
                check = relaxed_feasible(
                    onb, basis, a0, b0, m, free, free)
                ranks.append(check["rank"])
                rejects += not check["constant_in_span"]
                cross_counts.append(check["cross_columns_tested"])
            rows.append({
                "degree_n": n, "curve_id": item["curve_id"],
                "free_suffix_size_each_leaf": k,
                "fixed_one_count_each_leaf": count,
                "samples": protocol["samples_per_cell"],
                "minimum_rank": min(ranks), "maximum_rank": max(ranks),
                "full_rank_count": sum(rank == n for rank in ranks),
                "linear_relaxation_reject_count": rejects,
                "maximum_cross_columns_tested": max(cross_counts),
            })
    result = {
        "kind": "q1428_bilinear_s3_partial_pair_span_screen",
        "proposal_id": "Q1428", "candidate_id": None,
        "isogeny": "none", "rows": rows,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "is_empirical_solver_measurement": False,
        "is_natural_relation_yield_measurement": False,
        "complete_solve_work_log2": None,
        "scope": (
            "The span test is sound but only necessary. Synthetic partial "
            "assignments use the same free coordinate suffix on both "
            "leaves, random nonzero intermediates, and random fixed one "
            "positions; they are not solver trails or ordinary queries. "
            "Rank and rejection rates cannot be extrapolated to an N131 "
            "point-decomposition or complete IC work estimate."),
    }
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.check:
        assert OUTPUT.read_text() == content
    else:
        assert not OUTPUT.exists()
        OUTPUT.write_text(content)
    print(json.dumps({"status": "PASS", "rows": len(rows),
                      "rejections": sum(row[
                          "linear_relaxation_reject_count"] for row in rows)}))


if __name__ == "__main__":
    main()
