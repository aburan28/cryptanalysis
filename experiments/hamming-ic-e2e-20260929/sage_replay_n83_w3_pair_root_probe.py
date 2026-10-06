#!/usr/bin/env python3
"""Independently replay sampled wide S3 roots as exact N83 group sums."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


N = 83
R = 2417851639230796216685689
H = 4
CURVE_ID = "EC1N83Ckb1h2bcb59d56ad6"
ROOT = Path(__file__).resolve().parent
PROTOCOL = ROOT / "n83_w3_pair_root_probe_protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(run, left_limit):
    run = run.resolve()
    started = time.perf_counter_ns()
    protocol = json.loads(PROTOCOL.read_text())
    input_path = run / "input.json"
    result_path = run / f"left{left_limit}.json"
    input_data = json.loads(input_path.read_text())
    result = json.loads(result_path.read_text())
    assert sha(input_path) == protocol["input_sha256"]
    assert input_data["curve_id"] == result["curve_id"] == CURVE_ID
    assert input_data["field_polynomial_low_terms"] == result["field_polynomial_low_terms"] == [0, 2, 4, 7]
    assert result["status"] == "PRODUCER_PASS_PENDING_INDEPENDENT_REPLAY"
    assert result["left_limit"] == left_limit
    assert result["representative_count"] == input_data["representative_count"] == 539
    assert result["s3_calls"] == left_limit * 539 * N
    assert 0 <= result["s3_roots_found"] <= result["s3_calls"]
    assert (run / "sage_runtime_info_replay.json").is_file()

    binary = GF(2)
    ring = PolynomialRing(binary, "v")
    v = ring.gen()
    field = GF(2**N, "w", modulus=v**N + v**7 + v**4 + v**2 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert ZZ(R).is_prime(proof=True) and curve.cardinality() == R * H

    def element(code):
        return field(ring([(code >> bit) & 1 for bit in range(N)]))

    def code(value):
        return sum(int(coefficient) << bit
                   for bit, coefficient in enumerate(value.polynomial().list()))

    reps = [curve(element(int(x)), element(int(y)))
            for x, y in input_data["representatives_xy_decimal"]]
    assert len(reps) == 539
    for point in reps:
        assert point != curve(0) and R * point == curve(0)
    samples = result["sampled_roots"]
    assert len(samples) == 64
    for sample in samples:
        left = sample["left"]
        right = sample["right"]
        relative = sample["relative"]
        assert 0 <= left < left_limit and 0 <= right < 539 and 0 <= relative < N
        p = reps[left]
        q = reps[right]
        for _ in range(relative):
            q = curve(q[0]**2, q[1]**2)
        assert int(sample["left_x"]) == code(p[0])
        assert int(sample["right_x"]) == code(q[0])
        plus, minus = p + q, p - q
        assert plus != curve(0) and minus != curve(0)
        expected = sorted((code(plus[0]), code(minus[0])))
        observed = sorted(int(root) for root in sample["roots"])
        assert observed == expected

    report = {
        "schema_version": 1,
        "kind": "n83_w3_pair_root_kernel_independent_replay",
        "status": "PASS",
        "curve_id": CURVE_ID,
        "left_limit": left_limit,
        "s3_calls": result["s3_calls"],
        "s3_roots_found": result["s3_roots_found"],
        "sampled_group_sum_roots_checked": len(samples),
        "input_sha256": sha(input_path),
        "result_sha256": sha(result_path),
        "protocol_sha256": sha(PROTOCOL),
        "replay_source_sha256": sha(Path(__file__)),
        "sage_runtime_info_replay_sha256": sha(run / "sage_runtime_info_replay.json"),
        "replay_wall_ms": (time.perf_counter_ns() - started) / 1e6,
        "claim_boundary": "64 sampled S3 roots replayed as N83 group sums; no full index, six-summand PDP, ordinary yield, DLP, or speedup",
    }
    (run / f"left{left_limit}_sage_replay.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({key: report[key] for key in (
        "status", "left_limit", "sampled_group_sum_roots_checked")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("left_limit", type=int)
    args = parser.parse_args()
    main(args.run, args.left_limit)
