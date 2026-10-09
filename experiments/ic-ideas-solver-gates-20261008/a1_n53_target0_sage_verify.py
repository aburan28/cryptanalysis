#!/usr/bin/env python3
"""Independent Sage certificate for the frozen public N53 target recovery."""
from __future__ import annotations

import hashlib
import itertools
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

from a1_n53_pair_sage_verification import CLASSES, bits, from_bits

HERE = Path(__file__).resolve().parent
GEOMETRY = HERE.parent / "ic-ideas-20261007/results/a1_n53_k600_followup_final.json"
GENERATOR_CHECK = HERE / "a1_n53_pair_sage_verification.json"
TARGET_RECEIPT = HERE / "a1_n53_target0_recovery.json"
TARGET_RAW = HERE / "a1_n53_target0_recovery_raw.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "a1_n53_target0_sage_verify.json"
    if output.exists():
        raise FileExistsError(output)
    started = time.perf_counter_ns()
    geometry = json.loads(GEOMETRY.read_text())
    prior = json.loads(GENERATOR_CHECK.read_text())
    receipt = json.loads(TARGET_RECEIPT.read_text())
    raw = json.loads(TARGET_RAW.read_text())
    assert receipt["status"] == raw["status"] == "verified_recovery"
    assert receipt["raw_sha256"] == sha(TARGET_RAW)
    assert receipt["recovered_scalar"] == raw["recovered_scalar"]
    F2 = GF(2)
    P = PolynomialRing(F2, "u")
    u = P.gen()
    modulus_bits = geometry["field_modulus_bits"]
    modulus = sum((u**i for i in range(54) if modulus_bits >> i & 1), P(0))
    K = GF(2**53, "a", modulus=modulus)
    E = EllipticCurve(K, [1, 0, 0, 0, 1])
    G = E(*(from_bits(K, value) for value in prior["generator_point"]))
    Q = E(*(from_bits(K, value) for value in raw["target_point"]))
    r = geometry["subgroup_order"]
    scalar = raw["recovered_scalar"]
    assert 0 < scalar < r
    assert r * G == E(0) and r * Q == E(0)
    assert scalar * G == Q

    seen = set()
    seed_reps = []
    scanned = 0
    raw_x = 1
    while len(seed_reps) < 60:
        scanned += 1
        for point in E.lift_x(from_bits(K, raw_x), all=True):
            candidate = geometry["cofactor"] * point
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
    assert scanned == raw["scanned_x"]
    reps = [multiplier * point for point in seed_reps
            for multiplier in CLASSES]
    x_values = []
    for index in raw["witness_indices"]:
        geometric, within = divmod(index, 106)
        shift = within // 2
        x_values.append(reps[geometric][0] ** (1 << shift))
    choices = [E.lift_x(x, all=True) for x in x_values]
    assert all(len(options) == 2 for options in choices)
    matching_sign_assignments = sum(sum(combo, E(0)) == Q
                                    for combo in itertools.product(*choices))
    assert matching_sign_assignments >= 1
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "curve_id": geometry["curve_id"],
              "field_modulus_bits": modulus_bits,
              "subgroup_order": r,
              "generator_point": prior["generator_point"],
              "target_point": raw["target_point"],
              "recovered_scalar": scalar,
              "scalar_replay_on_public_target": True,
              "witness_x_bits": [bits(x) for x in x_values],
              "matching_sign_assignments": matching_sign_assignments,
              "stage_wall_ns_exploratory": time.perf_counter_ns()-started,
              "geometry_receipt_sha256": sha(GEOMETRY),
              "generator_check_sha256": sha(GENERATOR_CHECK),
              "target_receipt_sha256": sha(TARGET_RECEIPT),
              "target_raw_sha256": sha(TARGET_RAW),
              "source_sha256": sha(Path(__file__))}
    output.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"scalar": scalar,
                      "matching_sign_assignments": matching_sign_assignments}))


if __name__ == "__main__":
    main()
