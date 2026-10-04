#!/usr/bin/env python3
"""Losslessly adapt exact Q1325 point keys to the native pair comparator."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_probe import field, curves


HERE = Path(__file__).resolve().parent
KEY_BYTES = 21
NATIVE_RECORD_BYTES = 32
DEFAULT_BASE = Path("/private/tmp/q1400_n83_q1325_pair_base.bin")
MANIFEST = HERE / "native_inputs/n83_q1400_pair_manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(base_output: Path) -> dict:
    protocol_path = HERE / "q1325_protocol.json"
    archive_path = HERE / "bases/n83_weight5_full_orbits.json"
    keys_path = HERE / "bases/n83_weight5_full_point_orbits.bin"
    runtime_path = HERE / "q1400_sage_runtime_info.json"
    protocol = json.loads(protocol_path.read_text())
    archive = json.loads(archive_path.read_text())
    factor_base = protocol["factor_base"]
    assert protocol["proposal_id"] == "Q1325"
    assert protocol["isogeny"] == "none"
    assert archive["curve"]["curve_id"] == protocol["curve"]["curve_id"]
    assert archive["factor_base"]["enumerated_set_sha256"] == factor_base[
        "enumerated_set_sha256"] == sha(keys_path)
    n = protocol["field"]["n"]
    k = factor_base["signed_frobenius_columns"]
    b = factor_base["actual_usable_points_B_before_folding"]
    assert n == 83 and k == 186_612 and b == 166 * k
    packed = keys_path.read_bytes()
    assert len(packed) == k * KEY_BYTES
    max_key = 1 << (2 * n)
    previous = -1
    with base_output.open("wb") as stream:
        for position in range(k):
            key = int.from_bytes(packed[
                position * KEY_BYTES:(position + 1) * KEY_BYTES], "little")
            assert previous < key < max_key
            previous = key
            stream.write(key.to_bytes(NATIVE_RECORD_BYTES, "little"))
    assert base_output.stat().st_size == k * NATIVE_RECORD_BYTES

    onb = field.Onb(n)
    curve = curves.Curve(onb)
    target = tuple(int(value) for value in protocol["ordinary_public_target"])
    subgroup_order = protocol["curve"]["subgroup_order"]
    assert curve.onCurve(target) and curve.mul(target, subgroup_order) is None
    target_coords = [onb.toCoords(coordinate) for coordinate in target]
    assert tuple(onb.fromCoords(value) for value in target_coords) == target
    runtime_hash = sha(runtime_path)
    return {
        "kind": "q1400_exact_q1325_native_pair_input",
        "proposal_id": "Q1400",
        "parent_factor_base_proposal_id": "Q1325",
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "curve_id": protocol["curve"]["curve_id"],
        "workload_id": protocol["ordinary_workload_id"],
        "field_degree": n,
        "subgroup_order_r": subgroup_order,
        "actual_usable_points_B": b,
        "folded_columns_K": k,
        "factor_base_enumerated_set_sha256": factor_base[
            "enumerated_set_sha256"],
        "base_input_encoding": "sorted canonical packed signed-Frobenius full-point keys; 21-byte little-endian source records padded with eleven zero bytes to 32-byte native records; low n bits y_cycle, next n bits x_cycle",
        "base_binary_sha256": sha(base_output),
        "base_binary_bytes": base_output.stat().st_size,
        "ordinary_public_target_onb_hex": [format(value, "x")
                                           for value in target_coords],
        "ordinary_public_target_onb_native_decimal": [str(value)
                                                      for value in target],
        "q1325_protocol_sha256": sha(protocol_path),
        "q1325_base_archive_sha256": sha(archive_path),
        "q1325_point_key_file_sha256": sha(keys_path),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "checked_sage_runtime_info_sha256": runtime_hash,
        "source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-output", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    args.base_output.parent.mkdir(parents=True, exist_ok=True)
    expected = json.dumps(build(args.base_output), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert MANIFEST.read_text() == expected
        print(f"PASS {MANIFEST}")
    else:
        MANIFEST.write_text(expected)
        print(json.dumps({"status": "written", "base_bytes": args.base_output.stat().st_size,
                          "base_sha256": sha(args.base_output)}))


if __name__ == "__main__":
    main()
