#!/usr/bin/env python3
"""Independently replay Q1401's native hit on the exact Q1325 factor base."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

from run_probe import HERE, field, curves


sys.path.insert(0, str(HERE.parent / "koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402


OUT = HERE / "runs/n83_q1401_pair_planted_independent_replay.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def descriptor(rank: int, length: int) -> tuple[int, int, int]:
    q, relative = divmod(rank, length)
    second = (1 + math.isqrt(1 + 8 * q)) // 2
    while second * (second + 1) // 2 <= q:
        second += 1
    while second * (second - 1) // 2 > q:
        second -= 1
    first = q - second * (second - 1) // 2
    assert 0 <= first < second
    return first, second, relative


def pair_points(curve, orbit, keys: list[int], desc,
                degree: int):
    left = orbit.point_from_key(keys[desc[0]])
    right = orbit.point_from_key(keys[desc[1]])
    right = curve.frob(right, desc[2] % degree)
    if desc[2] >= degree:
        right = curve.neg(right)
    assert left is not None and right is not None
    return left, right


def canonical_x_cycle(orbit, x: int, n: int) -> int:
    cycle = orbit.cycle_bits(x)
    mask = (1 << n) - 1
    best = cycle
    for _ in range(1, n):
        cycle = ((cycle << 1) | (cycle >> (n - 1))) & mask
        best = min(best, cycle)
    return best


def build() -> dict:
    started = time.perf_counter_ns()
    protocol_path = HERE / "q1401_pair_control_protocol.json"
    q1400_path = HERE / "q1400_pair_protocol.json"
    fixture_path = HERE / "runs/n83_q1401_pair_planted_fixture.json"
    native_path = HERE / "runs/n83_q1401_pair_planted_native.json"
    keys_path = HERE / "bases/n83_weight5_full_point_orbits.bin"
    protocol = json.loads(protocol_path.read_text())
    q1400 = json.loads(q1400_path.read_text())
    fixture = json.loads(fixture_path.read_text())
    native = json.loads(native_path.read_text())
    assert protocol["proposal_id"] == fixture["proposal_id"] == native[
        "proposal_id"] == "Q1401"
    assert native["status"] == "native_hit_pending_independent_replay"
    assert native["planted_fixture_sha256"] == sha(fixture_path)
    assert native["stage_protocol_sha256"] == sha(protocol_path)
    assert native["native_output"] is not None
    assert native["native_output"]["exact_hit_keys"] > 0
    assert protocol["factor_base_enumerated_set_sha256"] == sha(keys_path)
    n = protocol["field_degree"]
    k = protocol["factor_base_folded_columns_K"]
    order = int(fixture["canonical_workload_record"]["subgroup_order_r"])
    pdp = q1400["point_decomposition"]
    domain = pdp["cross_orbit_descriptor_domain"]
    assert domain == math.comb(k, 2) * (2 * n)
    raw_keys = keys_path.read_bytes()
    keys = [int.from_bytes(raw_keys[i:i + 21], "little")
            for i in range(0, len(raw_keys), 21)]
    assert len(keys) == k and keys == sorted(set(keys))
    key_set = set(keys)
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    target = tuple(int(v) for v in fixture["target_onb_native_decimal"])
    assert curve.onCurve(target) and curve.mul(target, order) is None
    assert [format(onb.toCoords(v), "x") for v in target] == fixture[
        "target_onb_coordinate_hex"]

    verified = []
    for hit in native["native_output"]["hits"]:
        table_position = hit["table_position"]
        query_position = hit["query_representative_position"]
        assert 0 <= table_position < pdp["table_descriptors"]
        assert 0 <= query_position < pdp["query_representatives"]
        table_rank = (pdp["table_step"] * (pdp["table_start"] + table_position)
                      + pdp["table_offset"]) % domain
        query_rank = (pdp["query_step"] * (pdp["query_start"] + query_position)
                      + pdp["query_offset"]) % domain
        table_desc = descriptor(table_rank, 2 * n)
        query_desc = descriptor(query_rank, 2 * n)
        table_leaves = pair_points(curve, orbit, keys, table_desc, n)
        query_leaves = pair_points(curve, orbit, keys, query_desc, n)
        table_sum = curve.add(*table_leaves)
        query_sum = curve.add(*query_leaves)
        assert table_sum is not None and query_sum is not None
        assert canonical_x_cycle(orbit, table_sum[0], n) == int(
            hit["x_key_hex"], 16)
        shift = hit["frobenius_shift"]
        assert 0 <= shift < n
        center = curve.frob(target, (-shift) % n)
        query_component = (curve.neg(query_sum) if hit["negative_query_pair"]
                           else query_sum)
        complement = curve.add(center, curve.neg(query_component))
        assert complement is not None
        assert canonical_x_cycle(orbit, complement[0], n) == int(
            hit["x_key_hex"], 16)
        aligned = None
        for table_shift in range(n):
            shifted_table = curve.frob(table_sum, table_shift)
            for table_sign in (1, -1):
                value = (shifted_table if table_sign == 1
                         else curve.neg(shifted_table))
                if value == complement:
                    aligned = (table_shift, table_sign)
                    break
            if aligned is not None:
                break
        assert aligned is not None, "x-only key hit did not lift to a group relation"
        table_shift, table_sign = aligned
        leaves = []
        for leaf in table_leaves:
            lifted = curve.frob(leaf, table_shift)
            if table_sign < 0:
                lifted = curve.neg(lifted)
            leaves.append(curve.frob(lifted, shift))
        for leaf in query_leaves:
            lifted = curve.neg(leaf) if hit["negative_query_pair"] else leaf
            leaves.append(curve.frob(lifted, shift))
        total = None
        columns = []
        for leaf in leaves:
            assert leaf is not None and curve.onCurve(leaf)
            assert curve.mul(leaf, order) is None
            column, _, _ = orbit.canonical(leaf)
            assert column in key_set
            columns.append(column)
            total = curve.add(total, leaf)
        assert total == target
        verified.append({
            "table_position": table_position,
            "query_representative_position": query_position,
            "frobenius_shift": shift,
            "table_alignment_shift": table_shift,
            "table_alignment_sign": table_sign,
            "four_distinct_signed_frobenius_columns": len(set(columns)) == 4,
            "four_leaf_points_onb_native_decimal": [
                [str(x), str(y)] for x, y in leaves],
            "target_sum_verified": True,
        })
    assert verified
    return {
        "kind": "q1401_independent_checked_sage_four_point_replay",
        "status": "PASS",
        "proposal_id": "Q1401",
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "workload_id": protocol["workload_id"],
        "isogeny": "none",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": k,
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "verified_hits": verified,
        "verified_relation_count": len(verified),
        "is_natural_relation_yield_measurement": False,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "verification_wall_ns_outside_target_online": time.perf_counter_ns() - started,
        "stage_protocol_sha256": sha(protocol_path),
        "fixture_sha256": sha(fixture_path),
        "native_receipt_sha256": sha(native_path),
        "point_key_file_sha256": sha(keys_path),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "orbit_source_sha256": sha(Path(sys.modules["orbit_key"].__file__)),
        "checked_sage_runtime_info_sha256": sha(
            HERE / "q1400_sage_runtime_info.json"),
        "source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        report = json.loads(OUT.read_text())
        assert report["status"] == "PASS"
        assert report["native_receipt_sha256"] == sha(
            HERE / "runs/n83_q1401_pair_planted_native.json")
        assert report["source_sha256"] == sha(Path(__file__))
        replay = build()
        assert replay["verified_hits"] == report["verified_hits"]
        print(f"PASS {OUT}")
    else:
        assert not OUT.exists(), "refusing to overwrite a frozen replay"
        report = build()
        OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": report["status"],
                          "verified_relation_count": report[
                              "verified_relation_count"]}))


if __name__ == "__main__":
    main()
