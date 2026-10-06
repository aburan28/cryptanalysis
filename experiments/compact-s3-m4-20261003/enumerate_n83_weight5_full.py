#!/usr/bin/env python3
"""Enumerate every weight-at-most-five normal-x orbit at n=83.

The Fredricksen-Kessler-Maiorana recursion emits one binary necklace per
cyclic orbit. Frobenius is exactly cyclic rotation in OrbitKey's cycle-bit
order, so this avoids retaining 31 million visited x masks.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import resource
import sys
import time
from pathlib import Path

from run_probe import HERE, ROOT, curves, field, sha

PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PAIR))
from orbit_key import OrbitKey  # noqa: E402

N = 83
WEIGHT = 5
PROPOSAL = "Q1325"
KEY_BYTES = 21


def necklaces(n: int, max_weight: int):
    """Yield one binary word per cyclic orbit, omitting zero."""
    bits = [0] * (n + 1)

    def visit(t: int, period: int, ones: int):
        if ones > max_weight:
            return
        if t > n:
            if n % period == 0 and ones:
                yield sum(bits[i] << (i - 1) for i in range(1, n + 1))
            return
        inherited = bits[t - period]
        bits[t] = inherited
        yield from visit(t + 1, period, ones + inherited)
        if inherited == 0:
            bits[t] = 1
            yield from visit(t + 1, t, ones + 1)

    yield from visit(1, 1, 0)


def rotate(value: int, n: int):
    mask = (1 << n) - 1
    return ((value << 1) | (value >> (n - 1))) & mask


def self_test():
    for n, weight in ((5, 2), (7, 3), (11, 3)):
        generated = list(necklaces(n, weight))
        assert len(generated) == len(set(generated))
        expected = set()
        for size in range(1, weight + 1):
            for subset in itertools.combinations(range(n), size):
                value = sum(1 << bit for bit in subset)
                turns = []
                current = value
                for _ in range(n):
                    turns.append(current)
                    current = rotate(current, n)
                expected.add(min(turns))
        observed = set()
        for value in generated:
            turns = []
            current = value
            for _ in range(n):
                turns.append(current)
                current = rotate(current, n)
            observed.add(min(turns))
        assert observed == expected
    assert sum(1 for _ in necklaces(N, WEIGHT)) == sum(
        math.comb(N, weight) // N for weight in range(1, WEIGHT + 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.self_test:
        print(json.dumps({"status": "PASS", "n83_orbits": 373101}))
        return

    out_bin = HERE / "bases/n83_weight5_full_point_orbits.bin"
    out_json = HERE / "bases/n83_weight5_full_orbits.json"
    assert not out_bin.exists() and not out_json.exists()
    runtime_path = HERE / "q1325_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    q1041_path = PAIR / "runs/n83_weight5_orbit_base.json"
    q1041 = json.loads(q1041_path.read_text())
    q1041_key_path = PAIR / q1041["factor_base"]["orbit_key_file"]
    q1041_data = q1041_key_path.read_bytes()
    assert hashlib.sha256(q1041_data).hexdigest() == q1041[
        "factor_base"]["enumerated_set_sha256"]
    assert q1041["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert q1041["isogeny"] == "none"
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    r = q1041["curve_identity_record"]["curve"]["subgroup_order"]
    assert q1041["curve_identity_record"]["curve"]["order"] == 4 * r
    keys = set()
    weight_stats = {weight: {"weight": weight, "x_orbits": 0,
                             "rational_x_orbits": 0,
                             "identity_projection_orbits": 0,
                             "duplicate_projection_orbits": 0}
                    for weight in range(1, WEIGHT + 1)}
    began = time.perf_counter()
    subgroup_checks = 0
    for cycle_mask in necklaces(N, WEIGHT):
        weight = cycle_mask.bit_count()
        stratum = weight_stats[weight]
        stratum["x_orbits"] += 1
        coords = sum(1 << orbit.coordinate_cycle[i]
                     for i in range(N) if cycle_mask >> i & 1)
        raw = curve.pointFromX(onb.fromCoords(coords))
        if raw is None:
            continue
        stratum["rational_x_orbits"] += 1
        projected = curve.mul(raw, 4)
        if projected is None:
            stratum["identity_projection_orbits"] += 1
            continue
        if subgroup_checks < 32:
            assert curve.onCurve(projected)
            assert curve.mul(projected, r) is None
            subgroup_checks += 1
        key = orbit.canonical(projected)[0]
        if key in keys:
            stratum["duplicate_projection_orbits"] += 1
        else:
            keys.add(key)
    weight_stats = list(weight_stats.values())
    assert [row["weight"] for row in weight_stats] == list(range(1, 6))
    assert [row["x_orbits"] for row in weight_stats] == [
        math.comb(N, weight) // N for weight in range(1, WEIGHT + 1)]
    q1041_keys = set(int.from_bytes(q1041_data[i:i + KEY_BYTES], "little")
                     for i in range(0, len(q1041_data), KEY_BYTES))
    assert len(q1041_keys) == 24097 and q1041_keys <= keys
    data = b"".join(key.to_bytes(KEY_BYTES, "little")
                    for key in sorted(keys))
    out_bin.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    actual_b = 2 * N * len(keys)
    report = {
        "kind": "exact_full_n83_normal_x_weight5_projected_orbit_base",
        "proposal_id": PROPOSAL,
        "candidate_id": None, "workload_id": None, "run_id": None,
        "field": q1041["curve_identity_record"]["field"],
        "curve": dict(q1041["curve_identity_record"]["curve"],
                      curve_id=q1041["curve_id"]),
        "isogeny": "none",
        "factor_base": {
            "construction": "all nonzero normal-basis x masks of Hamming weight at most five; rational lift; cofactor-four projection; discard identity and deduplicate; both signs and every Frobenius power",
            "normal_basis_weight_bound": WEIGHT,
            "nominal_x_mask_count": sum(math.comb(N, weight)
                                        for weight in range(1, WEIGHT + 1)),
            "raw_x_frobenius_orbits": sum(row["x_orbits"] for row in weight_stats),
            "rational_raw_x_orbits": sum(row["rational_x_orbits"]
                                         for row in weight_stats),
            "identity_projection_orbits": sum(row[
                "identity_projection_orbits"] for row in weight_stats),
            "duplicate_projection_orbits": sum(row[
                "duplicate_projection_orbits"] for row in weight_stats),
            "geometric_point_count_before_projection": 2 * N * sum(
                row["rational_x_orbits"] for row in weight_stats),
            "actual_usable_points_B_before_folding": actual_b,
            "signed_frobenius_columns": len(keys),
            "signed_frobenius_orbit_size": 2 * N,
            "quotient_rule": "both signs and all 83 Frobenius powers; canonical packed full-point key",
            "enumerated_set_encoding": "sorted 21-byte little-endian packed signed-Frobenius point keys",
            "enumerated_set_sha256": digest,
            "point_key_file": out_bin.name,
            "point_key_file_bytes": len(data),
        },
        "weight_strata": weight_stats,
        "q1041_subset": {"source_base_receipt_sha256": sha(q1041_path),
                         "source_key_file_sha256": sha(q1041_key_path),
                         "subset_columns_verified": len(q1041_keys)},
        "sampled_subgroup_checks": subgroup_checks,
        "enumeration_wall_seconds": time.perf_counter() - began,
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "runtime_info_sha256": sha(runtime_path),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "orbit_source_sha256": sha(PAIR / "orbit_key.py"),
        "source_sha256": sha(Path(__file__)),
    }
    out_json.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"B": actual_b, "K": len(keys),
                      "q1041_subset": len(q1041_keys),
                      "seconds": report["enumeration_wall_seconds"]}))


if __name__ == "__main__":
    main()
