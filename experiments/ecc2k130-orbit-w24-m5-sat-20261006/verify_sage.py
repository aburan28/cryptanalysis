#!/usr/bin/env sage -python
"""Independent Sage replay of the planted m5 group target and any SAT model."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import resource
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    check(not args.out.exists(), "refusing to overwrite Sage replay")
    config_path = HERE / "CONFIG.json"
    config = json.loads(config_path.read_text())
    result_path = args.run_dir / "receipt.json"
    result = json.loads(result_path.read_text())
    runtime_path = args.run_dir / "runtime-info.json"
    runtime = json.loads(runtime_path.read_text())
    check(runtime["status"] == "verified", "checked Sage runtime absent")
    check(result["config_sha256"] == digest(config_path), "config hash mismatch")
    check(result["sage_runtime_info_sha256"] == digest(runtime_path),
          "Sage runtime receipt mismatch")
    check(result["candidate_id"] is None, "stage is not a complete IC candidate")
    for name, expected in result["source_sha256"].items():
        check(digest(HERE / name) == expected, f"source changed: {name}")
    seed_path = EXPERIMENTS / "ecc2k130-orbit-closed-w24-seed-20261006/runs/R1/result.json"
    normal_path = EXPERIMENTS / "ecc2k130-w24-normal-barrel-20261006/runs/R2/result.json"
    check(digest(seed_path) == config["parent_seed_result_sha256"], "seed result changed")
    check(digest(normal_path) == config["parent_normal_result_sha256"],
          "normal result changed")
    seed = json.loads(seed_path.read_text())
    normal = json.loads(normal_path.read_text())
    started = time.monotonic()
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131 + t**13 + t**2 + t + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    order = int(config["subgroup_order"])

    def decode(word):
        word = int(word)
        check(0 <= word < (1 << 131), "field word outside representation")
        return field(sum(t**i for i in range(131) if (word >> i) & 1))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def half_trace(value):
        term = value
        total = value
        for _ in range(65):
            term = term**4
            total += term
        check(total**2 + total == value, "Sage half trace failed")
        return total

    basis = [field.gen()**j + (field.gen()**j).trace() for j in range(1, 25)]
    check(all(int(value.trace()) == 0 for value in basis), "W24 basis trace")

    def raw_lifts(mask, exponent):
        check(0 < mask < (1 << 24) and 0 <= exponent <= 130,
              "mask/exponent outside policy")
        seed_word = sum(basis[j] for j in range(24) if (mask >> j) & 1)
        word = seed_word ** (1 << exponent)
        check(word != 0 and int((1 / word).trace()) == 0,
              "seed does not define rational base point")
        u = half_trace(word)
        check(u not in (0, 1), "exceptional quotient u")
        x = 1 + 1 / u
        lifts = curve.lift_x(x, all=True)
        check(len(lifts) == 2, "expected two raw curve lifts")
        return sorted(lifts, key=lambda point: encode(point[1])), word, u

    observed_controls = result["planted_controls"]
    check(len(observed_controls) == 5, "five planted group controls missing")
    selected = []
    for place, index in enumerate(config["planted_group_control_indices"]):
        source = seed["group"][index]
        row = observed_controls[place]
        check(row["index"] == index == source["control_index"],
              "planted group control order")
        check(row["mask"] == source["mask"] and
              row["exponent"] == source["exponent"], "planted control changed")
        lifts, word, _ = raw_lifts(row["mask"], row["exponent"])
        check(str(encode(word)) == row["word"] == source["orbit_x"],
              "archived quotient word changed")
        point = lifts[0]
        check([encode(point[0]), encode(point[1])] == row["raw_point"],
              "minimum-y raw lift changed")
        selected.append(point)
    raw_sum = sum(selected, curve(0))
    q = 4 * raw_sum
    check(not q.is_zero() and (order * q).is_zero(),
          "planted Q outside nonidentity subgroup")
    check([encode(q[0]), encode(q[1])] == result["public_q"],
          "planted public Q mismatch")
    base = pow(4, -1, order) * q
    torsion = [curve(0), curve([decode(0), decode(1)]),
               curve([decode(1), decode(0)]), curve([decode(1), decode(1)])]
    fibers = [base + point for point in torsion]
    check([([encode(p[0]), encode(p[1])] if not p.is_zero() else None)
           for p in fibers] == result["raw_fibers"], "[4] fibers mismatch")
    check(fibers[result["planted_fiber_index"]] == raw_sum,
          "planted fiber mismatch")

    normal_orbit = [decode(value) for value in normal["normal_to_polynomial_columns"]]
    basis_matrix = matrix(GF(2), [[(encode(value) >> bit) & 1
                                   for value in normal_orbit]
                                  for bit in range(131)])
    check(basis_matrix.rank() == 131, "normal map rank")
    inverse = basis_matrix.inverse()
    expected_columns = []
    for seed_word in basis:
        half = half_trace(seed_word)
        coordinate = inverse * vector(GF(2), [(encode(half) >> bit) & 1
                                               for bit in range(131)])
        expected_columns.append(str(sum(int(v) << bit
                                        for bit, v in enumerate(coordinate))))
    check(expected_columns == result["seed_to_normal_u_columns"],
          "normal-basis half-trace input map mismatch")

    status = "PASS_PLANTED_GEOMETRY_NO_SOLVER_WITNESS"
    model_checks = 0
    if result["status"] == "candidate_group_relation":
        model = result["model"]
        check(len(model["masks"]) == len(model["exponents"]) == 5,
              "SAT model leaf count")
        lifts_and_u = [raw_lifts(mask, exponent)
                       for mask, exponent in zip(model["masks"], model["exponents"])]
        leaf_us = [item[2] for item in lifts_and_u]
        fiber = fibers[model["fiber_index"]]
        check(not fiber.is_zero() and encode(fiber[0]) != 1,
              "SAT-selected fiber exceptional")
        chain = [leaf_us[0]] + [decode(word) for word in model["intermediate_us"]] + [
            1 / (fiber[0] + 1)]
        check(len(chain) == 5, "SAT S3 chain length")
        for slot in range(1, 5):
            w0 = chain[slot - 1]**2 + chain[slot - 1]
            w1 = leaf_us[slot]**2 + leaf_us[slot]
            w2 = chain[slot]**2 + chain[slot]
            check(w0 * w1 * w2 + (chain[slot - 1] + leaf_us[slot] + chain[slot])**2 == 0,
                  f"SAT S3 residual at link {slot}")
        for choice in itertools.product(*(item[0] for item in lifts_and_u)):
            if sum(choice, curve(0)) == fiber:
                check(4 * sum(choice, curve(0)) == q, "SAT sum failed cofactor map")
                model_checks += 1
        check(model_checks > 0, "SAT model has no raw group lift")
        status = "PASS_UNKNOWN_WITNESS_GROUP_REPLAY"
    check(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss <=
          config["peak_rss_limit_bytes"], "Sage verifier exceeded RSS cap")
    report = {
        "schema": "ecc2k130-orbit-w24-m5-sat-sage-replay-v1",
        "status": status,
        "candidate_id": None,
        "strict_result_sha256": digest(result_path),
        "runtime_info_sha256": digest(runtime_path),
        "verifier_source_sha256": digest(Path(__file__)),
        "parent_seed_result_sha256": digest(seed_path),
        "parent_normal_result_sha256": digest(normal_path),
        "planted_raw_points": len(selected),
        "normal_input_columns": len(expected_columns),
        "model_group_lifts": model_checks,
        "wall_ms_exploratory": (time.monotonic() - started) * 1000,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("status", "planted_raw_points", "normal_input_columns",
                       "model_group_lifts")}, sort_keys=True))


if __name__ == "__main__":
    main()
