#!/usr/bin/env python3
"""Freeze a Q1325-base four-leaf target known to the Q1400 pair schedule."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from run_probe import HERE, field, curves


sys.path.insert(0, str(HERE.parent / "koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402


OUT = HERE / "runs/n83_q1401_pair_planted_fixture.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cross_pair(rank: int, orbit_length: int) -> tuple[int, int, int]:
    pair_rank, relative = divmod(rank, orbit_length)
    second = (1 + math.isqrt(1 + 8 * pair_rank)) // 2
    while (second + 1) * second // 2 <= pair_rank:
        second += 1
    while second * (second - 1) // 2 > pair_rank:
        second -= 1
    first = pair_rank - second * (second - 1) // 2
    assert 0 <= first < second
    return first, second, relative


def point(curve, orbit, keys: list[int], index: int, shift: int,
          n: int):
    base = orbit.point_from_key(keys[index])
    shifted = curve.frob(base, shift % n)
    return curve.neg(shifted) if shift >= n else shifted


def build() -> dict:
    protocol_path = HERE / "q1400_pair_protocol.json"
    base_protocol_path = HERE / "q1325_protocol.json"
    keys_path = HERE / "bases/n83_weight5_full_point_orbits.bin"
    input_path = HERE / "native_inputs/n83_q1400_pair_manifest.json"
    protocol = json.loads(protocol_path.read_text())
    base_protocol = json.loads(base_protocol_path.read_text())
    inputs = json.loads(input_path.read_text())
    assert protocol["proposal_id"] == "Q1400"
    assert protocol["isogeny"] == "none"
    assert inputs["factor_base_enumerated_set_sha256"] == sha(keys_path)
    n = protocol["field_degree"]
    k = protocol["factor_base_folded_columns_K"]
    orbit_length = 2 * n
    assert n == 83 and k == 186_612
    data = keys_path.read_bytes()
    keys = [int.from_bytes(data[i:i + 21], "little")
            for i in range(0, len(data), 21)]
    assert len(keys) == k and keys == sorted(set(keys))
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    pdp = protocol["point_decomposition"]
    domain = pdp["cross_orbit_descriptor_domain"]
    assert domain == math.comb(k, 2) * orbit_length
    table_position = query_representative_position = 0
    table_rank = (pdp["table_step"] * table_position
                  + pdp["table_offset"]) % domain
    query_rank = (pdp["query_step"] * query_representative_position
                  + pdp["query_offset"]) % domain
    table_descriptor = cross_pair(table_rank, orbit_length)
    query_descriptor = cross_pair(query_rank, orbit_length)
    assert all(index < k for index in table_descriptor[:2]
               + query_descriptor[:2])
    table_leaves = [
        point(curve, orbit, keys, table_descriptor[0], 0, n),
        point(curve, orbit, keys, table_descriptor[1],
              table_descriptor[2], n),
    ]
    query_leaves = [
        point(curve, orbit, keys, query_descriptor[0], 0, n),
        point(curve, orbit, keys, query_descriptor[1],
              query_descriptor[2], n),
    ]
    target = None
    for leaf in table_leaves + query_leaves:
        assert leaf is not None and curve.onCurve(leaf)
        target = curve.add(target, leaf)
    assert target is not None and curve.onCurve(target)
    subgroup_order = base_protocol["curve"]["subgroup_order"]
    assert curve.mul(target, subgroup_order) is None
    target_coords = [onb.toCoords(coordinate) for coordinate in target]
    workload = {
        "curve_id": protocol["curve_id"],
        "subgroup_order_r": subgroup_order,
        "target_onb_native_decimal": [str(v) for v in target],
        "input_law": "sum of Q1400 table descriptor zero and query descriptor zero; witness withheld from native input",
        "target_count": 1,
        "cache_policy": "same target-independent Q1400 table parameters",
    }
    workload_bytes = json.dumps(workload, sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False).encode()
    workload_id = hashlib.sha256(workload_bytes).hexdigest()[:12]
    return {
        "kind": "q1401_q1325_pair_planted_control_fixture",
        "proposal_id": "Q1401",
        "parent_solver_proposal_id": "Q1400",
        "candidate_id": None,
        "run_id": None,
        "curve_id": protocol["curve_id"],
        "workload_id": workload_id,
        "canonical_workload_record": workload,
        "isogeny": "none",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": k,
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "target_onb_native_decimal": [str(v) for v in target],
        "target_onb_coordinate_hex": [format(v, "x") for v in target_coords],
        "witness_metadata_not_passed_to_native_solver": {
            "table_position": table_position,
            "table_rank": table_rank,
            "table_pair_descriptor": list(table_descriptor),
            "query_representative_position": query_representative_position,
            "query_rank": query_rank,
            "query_pair_descriptor": list(query_descriptor),
            "four_leaf_points_onb_native_decimal": [
                [str(x), str(y)] for x, y in table_leaves + query_leaves],
        },
        "q1400_stage_protocol_sha256": sha(protocol_path),
        "q1325_protocol_sha256": sha(base_protocol_path),
        "q1400_input_manifest_sha256": sha(input_path),
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
    expected = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert OUT.read_text() == expected
        print(f"PASS {OUT}")
    else:
        OUT.write_text(expected)
        report = json.loads(expected)
        print(json.dumps({"status": "written",
                          "workload_id": report["workload_id"],
                          "target_onb_coordinate_hex": report[
                              "target_onb_coordinate_hex"]}))


if __name__ == "__main__":
    main()
