#!/usr/bin/env python3
"""Replay each reported N83 packed-root collision in an independent Sage field."""

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUTS = ROOT / "experiments/koblitz-n83-index-design-20260929/adaptive_all_orientations_20261004/inputs"
BRIDGE = INPUTS / "n83_onb_poly_bridge.json"
REPS = INPUTS / "n83_x_representatives.bin"
RAW = HERE / "collision_audit_29900000.json"
OUTPUT = HERE / "independent_sage_replay.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    assert not args.output.exists(), "refusing to overwrite the replay receipt"
    started = time.perf_counter_ns()
    stage = json.loads((HERE / "stage_manifest.json").read_text())
    raw = json.loads(args.raw.read_text())
    bridge = json.loads(BRIDGE.read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    assert raw["status"] == "collision_audit_complete"
    assert raw["curve_id"] == stage["curve_id"] == bridge["curve_id"]
    assert raw["workload_id"] == stage["workload_id"]
    assert raw["factor_base_enumerated_set_sha256"] == stage["factor_base_enumerated_set_sha256"]
    assert raw["native_source_sha256"] == sha(HERE / "native_packed_index.rs")
    assert raw["cargo_manifest_sha256"] == sha(HERE / "Cargo.toml")
    assert sha(REPS) == stage["representatives_file_sha256"]
    assert raw["index_pair_states_examined"] == stage["pair_state_cap"] == 29_900_000
    assert raw["index_satisfiable_s3_states"] == 29_900_000
    assert raw["root_table_records"] == 59_800_000
    assert raw["root_table_records"] - raw["index_distinct_root_keys"] == raw["duplicate_records"]
    assert raw["duplicate_records"] == raw["collision_groups"] == len(raw["collision_witnesses"])
    assert raw["representative_count_K"] == stage["representative_count_K"] == 186_612
    assert raw["actual_usable_points_B"] == stage["actual_usable_points_B"] == 30_977_592

    binary = GF(2)
    ring = PolynomialRing(binary, "t")
    t = ring.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**83, name="z", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def from_bits(bits):
        return field(ring([(int(bits) >> j) & 1 for j in range(83)]))

    def to_bits(value):
        return sum(int(coefficient) << j for j, coefficient in
                   enumerate(value.polynomial().list()))

    positions = bridge["onb_gamma_frobenius_coordinate_cycle"]
    basis = bridge["onb_to_poly_basis_images"]
    assert len(positions) == len(basis) == 83
    assert sorted(positions) == list(range(83))
    with REPS.open("rb") as source:
        data = source.read()
    assert len(data) == 16 * stage["representative_count_K"]

    def representative(index):
        return from_bits(int.from_bytes(data[16 * index:16 * index + 16], "little"))

    def from_cycle(bits):
        value = 0
        for j, position in enumerate(positions):
            if (bits >> j) & 1:
                value ^= basis[position]
        return from_bits(value)

    total = 83 * stage["representative_count_K"] ** 2
    origin = 0x7e52_18ac_2026_1003 % total
    step = 0x9e37_79b9_7f4a_7c15 % total
    while math.gcd(step, total) != 1:
        step += 1
    assert stage["pair_state_cap"] < total
    seen_roots = set()
    categories = {"swapped_pair": 0, "same_state_two_selectors": 0,
                  "distinct_pair": 0}
    checked_witnesses = 0
    lifted_x = {}

    def lift(x):
        key = to_bits(x)
        if key not in lifted_x:
            lifted_x[key] = curve.lift_x(x)
        return lifted_x[key]

    for group in raw["collision_witnesses"]:
        key = int(group["canonical_root_cycle"])
        assert key not in seen_roots
        seen_roots.add(key)
        z = from_bits(group["root_x_poly"])
        assert z == from_cycle(key)
        lift(z)
        witnesses = group["witnesses"]
        assert len(witnesses) == 2
        pair_x = []
        for witness in witnesses:
            offset = witness["state_offset"]
            state_id = (origin + offset * step) % total
            relative = state_id % 83
            pair_id = state_id // 83
            left = pair_id // stage["representative_count_K"]
            right = pair_id % stage["representative_count_K"]
            assert (left, right, relative) == (
                witness["left_representative"], witness["right_representative"],
                witness["relative"])
            shift = witness["shift"]
            assert 0 <= shift < 83
            x = representative(left) ** (2 ** shift)
            y = representative(right) ** (2 ** ((shift + relative) % 83))
            assert to_bits(x) == int(witness["left_x_poly"])
            assert to_bits(y) == int(witness["right_x_poly"])
            assert (x*y + x*z + y*z)**2 + x*y*z + 1 == 0
            lift(x)
            lift(y)
            pair_x.append((x, y))
            checked_witnesses += 1
        a, b = pair_x
        if a == b and witnesses[0]["state_offset"] == witnesses[1]["state_offset"]:
            categories["same_state_two_selectors"] += 1
        elif a == b[::-1]:
            categories["swapped_pair"] += 1
        else:
            categories["distinct_pair"] += 1

    assert categories == {"swapped_pair": 292,
                          "same_state_two_selectors": 2,
                          "distinct_pair": 0}
    assert checked_witnesses == 588
    report = {
        "status": "PASS", "curve_id": raw["curve_id"],
        "workload_id": raw["workload_id"],
        "indexed_states": raw["index_pair_states_examined"],
        "collision_groups": len(seen_roots),
        "checked_witnesses": checked_witnesses,
        "categories": categories,
        "nontrivial_relation_rows": 0,
        "nontrivial_rank_increment": 0,
        "reason": "Every reported root collision reuses the same unordered pair of x coordinates.",
        "raw_sha256": sha(args.raw), "stage_manifest_sha256": sha(HERE / "stage_manifest.json"),
        "bridge_sha256": sha(BRIDGE), "representatives_sha256": sha(REPS),
        "native_source_sha256": sha(HERE / "native_packed_index.rs"),
        "verifier_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "replay_wall_ns": time.perf_counter_ns() - started,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in (
        "status", "collision_groups", "checked_witnesses", "categories",
        "nontrivial_rank_increment")}, sort_keys=True))


if __name__ == "__main__":
    main()
