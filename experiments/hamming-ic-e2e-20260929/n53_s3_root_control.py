#!/usr/bin/env python3
"""Exact GF(2^53) S3 root oracle and frozen planted-chain control."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random
import time

from n53_group import Curve, Field, N, normal_basis

HERE = Path(__file__).resolve().parent
PLANTED = HERE / "runs/n53_scale_v1/fc_planted/receipt.json"
ORDINARY = HERE / "runs/n53_scale_v1/fc/receipt.json"
SEED = 53010


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def s3_zero(field, a, b, c):
    ab = field.mul(a, b)
    e2 = ab ^ field.mul(a ^ b, c)
    return field.square(e2) ^ field.mul(ab, c) ^ 1 == 0


def square_root(field, value):
    for _ in range(N - 1):
        value = field.square(value)
    return value


def roots(field, a, b):
    """Solve S3(a,b,c)=0 as A*c^2+B*c+C=0, with all degeneracies."""
    ab = field.mul(a, b)
    coefficient_a = field.square(a ^ b)
    coefficient_b = ab
    constant = field.square(ab) ^ 1
    if coefficient_a == 0:
        candidates = [] if coefficient_b == 0 else [field.mul(constant, field.inv(coefficient_b))]
    elif coefficient_b == 0:
        candidates = [square_root(field, field.mul(constant, field.inv(coefficient_a)))]
    else:
        b_inverse = field.inv(coefficient_b)
        rhs = field.mul(field.mul(constant, coefficient_a), field.square(b_inverse))
        if field.trace(rhs):
            candidates = []
        else:
            z = field.half_trace(rhs)
            scale = field.mul(coefficient_b, field.inv(coefficient_a))
            candidates = [field.mul(scale, z), field.mul(scale, z ^ 1)]
    answer = tuple(sorted(set(candidates)))
    assert all(s3_zero(field, a, b, c) for c in answer)
    return answer


def chain(field, xs, target_x):
    states = [(xs[0], ())]
    counts = []
    for x in xs[1:4]:
        states = [(root, mids + (root,))
                  for prior, mids in states for root in roots(field, prior, x)]
        counts.append(len(states))
    accepted = [mids for prior, mids in states
                if s3_zero(field, prior, xs[4], target_x)]
    return counts, sorted(accepted)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("control receipt is immutable")
    out.mkdir(parents=True)
    started = time.perf_counter_ns()
    field = Field()
    curve = Curve(field)
    assert roots(field, 0, 0) == ()
    assert roots(field, 0, 1) == (1,)
    assert roots(field, 1, 1) == (0,)
    receipt = json.loads(PLANTED.read_text())
    ordinary = json.loads(ORDINARY.read_text())
    fixture = receipt["fixture"]
    xs = fixture["x"]
    target_x = fixture["target"][0]
    counts, accepted = chain(field, xs, target_x)
    expected = tuple(fixture["intermediate_x"])
    assert expected in accepted
    assert all(s3_zero(field, a, b, c) for a, b, c in
               ((xs[0], xs[1], expected[0]),
                (expected[0], xs[2], expected[1]),
                (expected[1], xs[3], expected[2]),
                (expected[2], xs[4], target_x)))

    _, conjugates = normal_basis(field)
    base = sorted(point for i, j in itertools.combinations(range(N), 2)
                  for point in curve.lift(conjugates[i] ^ conjugates[j]))
    assert len(base) == 1696
    rng = random.Random(SEED)
    pair_cases = []
    for _ in range(128):
        first, second = rng.sample(base, 2)
        total = curve.add(first, second)
        candidates = roots(field, first[0], second[0])
        if total is not None:
            assert total[0] in candidates
        pair_cases.append({"a": first[0], "b": second[0],
                           "sum_x": None if total is None else total[0],
                           "roots": list(candidates)})
    assert any(len(case["roots"]) == 2 for case in pair_cases)
    elapsed = time.perf_counter_ns() - started
    record = {
        "kind": "n53_s3_exact_root_control", "curve_id": ordinary["curve_id"],
        "candidate_id": None, "source_planted_receipt_sha256": sha(PLANTED),
        "source_ordinary_receipt_sha256": sha(ORDINARY),
        "source_sha256": {"n53_s3_root_control.py": sha(Path(__file__)),
                          "n53_group.py": sha(HERE / "n53_group.py")},
        "field_modulus": field.modulus, "seed": SEED,
        "degenerate_root_cases_checked": 3,
        "pair_cases": len(pair_cases),
        "pair_cases_sha256": hashlib.sha256(json.dumps(pair_cases, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest(),
        "pair_root_count_mix": {str(k): sum(len(case["roots"]) == k for case in pair_cases)
                                for k in (0, 1, 2)},
        "all_nonidentity_pair_sums_recovered": True,
        "planted_x": xs, "planted_target_x": target_x,
        "branch_counts_after_three_roots": counts,
        "accepted_middle_chains": [list(mids) for mids in accepted],
        "planted_middle_chain_present": True,
        "wall_ns": elapsed,
        "claim_boundary": "Exact S3 arithmetic control only; known five x values are supplied. No ordinary relation or DLP result."}
    (out / "receipt.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: record[key] for key in
                      ("pair_cases", "pair_root_count_mix", "branch_counts_after_three_roots",
                       "planted_middle_chain_present", "wall_ns")}, sort_keys=True))


if __name__ == "__main__":
    main()
