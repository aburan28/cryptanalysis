#!/usr/bin/env python3
"""Exhaustive n=23 query-pair orbit indexing and target-key identity control."""

import hashlib
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
INPUT = HERE / "runs" / "n23_one_target.json"
OUTPUT = HERE / "runs" / "n23_query_orbit_reuse_control.json"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from orbit_key import OrbitKey


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lift_within(within, k, negative, n):
    sign = (within // n) ^ int(negative)
    return sign * n + (within % n + k) % n


def main():
    receipt = json.loads(INPUT.read_text())
    n = 23
    L = 2 * n
    reps = [tuple(point) for point in receipt["representatives"]]
    K = len(reps)
    B = K * L
    assert receipt["curve_id"] == "EC1N23Ckb1haed91d8afed0"
    assert B == receipt["factor_base"][
        "actual_usable_points_B_before_folding"] == 322
    assert K == receipt["factor_base"]["signed_frobenius_columns"] == 7
    curve = curves.Curve(field.Onb(n))
    orbit = OrbitKey(curve.f)
    target = tuple(receipt["workload"]["target"])
    assert curve.onCurve(target)
    base = []
    for rep in reps:
        positives = [curve.frob(rep, k) for k in range(n)]
        base.extend(positives)
        base.extend(curve.neg(point) for point in positives)
    assert len(base) == B and len(set(base)) == B
    cross_seen = set()
    identity_checks = 0
    rng = random.Random(230929)
    for i in range(K):
        for j in range(i + 1, K):
            for relative in range(L):
                first = i * L
                second = j * L + relative
                for negative in (False, True):
                    for k in range(n):
                        a = i * L + lift_within(0, k, negative, n)
                        b = j * L + lift_within(relative, k, negative, n)
                        assert a < b
                        pair = (a, b)
                        assert pair not in cross_seen
                        cross_seen.add(pair)
                # The group/key identity is tested on selected classes,
                # while pair-index coverage above is exhaustive.
                if rng.randrange(8):
                    continue
                z = curve.add(base[first], base[second])
                assert z is not None
                for _ in range(8):
                    k = rng.randrange(n)
                    negative = bool(rng.randrange(2))
                    a = i * L + lift_within(0, k, negative, n)
                    b = j * L + lift_within(relative, k, negative, n)
                    transformed = curve.frob(z, k)
                    if negative:
                        transformed = curve.neg(transformed)
                    assert curve.add(base[a], base[b]) == transformed
                    direct = curve.add(target, curve.neg(transformed))
                    q_conjugate = curve.frob(target, (-k) % n)
                    reused = curve.add(
                        q_conjugate, z if negative else curve.neg(z))
                    direct_xkey = orbit.canonical(direct)[0] >> n
                    reused_xkey = orbit.canonical(reused)[0] >> n
                    assert direct_xkey == reused_xkey
                    identity_checks += 1
    cross_pairs = math.comb(K, 2) * L * L
    within_pairs = K * L * (L + 1) // 2
    assert len(cross_seen) == cross_pairs
    assert cross_pairs + within_pairs == B * (B + 1) // 2
    report = {
        "kind": "n23_signed_frobenius_query_pair_orbit_reuse_control",
        "scope": "exhaustive cross-orbit pair indexing; sampled group and canonical-x identities; no natural target relation",
        "proposal_id": "Q1050", "candidate_id": None,
        "curve_id": receipt["curve_id"],
        "curve_identity_record": receipt["curve_identity_record"],
        "isogeny": "none",
        "actual_usable_points_B_before_folding": B,
        "signed_frobenius_columns": K,
        "factor_base_enumerated_set_sha256": receipt[
            "factor_base"]["enumerated_set_sha256"],
        "signed_frobenius_orbit_size": L,
        "cross_orbit_pair_representatives": math.comb(K, 2) * L,
        "cross_orbit_lifted_unordered_pairs": cross_pairs,
        "cross_orbit_unique_pairs_checked": len(cross_seen),
        "within_orbit_unordered_pairs_outside_this_control": within_pairs,
        "sampled_group_and_canonical_x_identities_checked":
            identity_checks,
        "all_checks_passed": True,
        "identity": "can_x(Q - epsilon*Frob^k(Z)) = can_x(Frob^(-k)(Q) - epsilon*Z), where epsilon is +1 or -1 and Z is a cross-orbit pair sum",
        "natural_relation_yield": None,
        "complete_solve_work_log2": None,
        "input_receipt_sha256": sha(INPUT),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "cross_pairs": cross_pairs,
        "representatives": report["cross_orbit_pair_representatives"],
        "group_and_key_checks": identity_checks,
        "all_checks_passed": True,
    }))


if __name__ == "__main__":
    main()
