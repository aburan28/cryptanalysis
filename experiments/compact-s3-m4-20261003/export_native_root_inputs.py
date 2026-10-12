#!/usr/bin/env python3
"""Export exact frozen ONB factor-base representatives for native S3 search.

The public curve/field identity stays normal-basis. The polynomial words are
only an internal encoding under the independently replayed field bridge.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path

from derive_onb_poly_bridge import xor_images
from run_probe import HERE, ROOT, curves, field, sha

PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PAIR))
from orbit_key import OrbitKey  # noqa: E402


def export(n):
    protocol_path = HERE / "q1327_q1328_native_root_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    stage = next(row for row in protocol["profiles"]
                 if row["field_degree"] == n)
    assert stage["proposal_id"] == {53: "Q1327", 83: "Q1328"}[n]
    assert stage["parent_factor_base_proposal_id"] == {
        53: "Q1301", 83: "Q1325"}[n]
    bridge_path = HERE / "field_bridges" / f"n{n}_onb_poly.json"
    bridge = json.loads(bridge_path.read_text())
    replay_path = HERE / "runs" / f"n{n}_onb_poly_bridge_replay.json"
    replay = json.loads(replay_path.read_text())
    assert bridge["status"] == replay["status"] == "PASS"
    assert replay["bridge_sha256"] == sha(bridge_path)
    runtime_path = HERE / "native_root_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    source_path = HERE / "runs" / f"n{n}_ordinary_frozen.json"
    source = json.loads(source_path.read_text())
    assert source["curve_id"] == bridge["curve_id"]
    assert source["workload_kind"] == "ordinary"
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    target = tuple(map(int, source["public_subgroup_target"]))
    assert curve.onCurve(target)
    forward = bridge["onb_to_poly_basis_images"]
    target_poly = [xor_images(onb.toCoords(value), forward)
                   for value in target]
    assert target_poly == bridge["mapped_public_target_poly"]

    if n == 53:
        archive_path = HERE / "bases/n53_weight3_orbits.json.gz"
        with gzip.open(archive_path, "rt") as stream:
            archive = json.load(stream)
        packed = base64.b64decode(archive["factor_base"][
            "packed_canonical_x_keys_base64"], validate=True)
        assert hashlib.sha256(packed).hexdigest() == archive[
            "factor_base"]["enumerated_set_sha256"]
        assert len(packed) % 7 == 0
        reps_onb = [int.from_bytes(packed[i:i + 7], "little")
                    for i in range(0, len(packed), 7)]
    else:
        archive_path = HERE / "bases/n83_weight5_full_orbits.json"
        archive = json.loads(archive_path.read_text())
        point_key_path = HERE / "bases/n83_weight5_full_point_orbits.bin"
        packed = point_key_path.read_bytes()
        assert hashlib.sha256(packed).hexdigest() == archive[
            "factor_base"]["enumerated_set_sha256"]
        assert len(packed) % 21 == 0
        orbit = OrbitKey(onb)
        reps_onb = []
        for offset in range(0, len(packed), 21):
            key = int.from_bytes(packed[offset:offset + 21], "little")
            point = orbit.point_from_key(key)
            assert point is not None
            reps_onb.append(onb.toCoords(point[0]))
    assert len(reps_onb) == archive["factor_base"][
        "signed_frobenius_columns"]
    assert archive["proposal_id"] == stage[
        "parent_factor_base_proposal_id"]
    assert archive["curve"]["curve_id"] == bridge["curve_id"]
    assert stage["curve_id"] == bridge["curve_id"]
    assert stage["workload_id"] == source["workload_id"]
    assert stage["factor_base_actual_B"] == archive["factor_base"][
        "actual_usable_points_B_before_folding"]
    assert stage["factor_base_folded_columns_K"] == len(reps_onb)
    assert stage["factor_base_enumerated_set_sha256"] == archive[
        "factor_base"]["enumerated_set_sha256"]
    assert len(set(reps_onb)) == len(reps_onb)
    assert all(0 < value < 1 << n for value in reps_onb)
    reps_poly = [xor_images(value, forward) for value in reps_onb]
    assert len(set(reps_poly)) == len(reps_poly)
    content = b"".join(value.to_bytes(16, "little") for value in reps_poly)
    result_path = HERE / "native_inputs" / f"n{n}_x_representatives.bin"
    manifest_path = HERE / "native_inputs" / f"n{n}_manifest.json"
    record = {
        "kind": "exact_native_s3_root_input",
        "proposal_id": stage["proposal_id"],
        "parent_factor_base_proposal_id": stage[
            "parent_factor_base_proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "field_degree": n,
        "curve_id": bridge["curve_id"],
        "isogeny": "none",
        "workload_id": source["workload_id"],
        "target_poly_xy": [str(value) for value in target_poly],
        "target_encoding": "two exact decimal strings of unsigned polynomial-basis words",
        "polynomial_low_terms": bridge["target_implementation_basis"][
            "low_terms"],
        "representative_encoding": "16-byte little-endian polynomial x per signed-Frobenius orbit",
        "representative_count_K": len(reps_poly),
        "actual_usable_points_B": archive["factor_base"][
            "actual_usable_points_B_before_folding"],
        "factor_base_enumerated_set_sha256": archive["factor_base"][
            "enumerated_set_sha256"],
        "pair_state_cap": stage["pair_state_cap"],
        "peak_rss_cap_mib": stage["peak_rss_cap_mib"],
        "stage_protocol_sha256": sha(protocol_path),
        "representatives_file_sha256": hashlib.sha256(content).hexdigest(),
        "source_base_archive_sha256": sha(archive_path),
        "bridge_sha256": sha(bridge_path),
        "bridge_replay_sha256": sha(replay_path),
        "target_source_receipt_sha256": sha(source_path),
        "runtime_info_sha256": sha(runtime_path),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "orbit_source_sha256": sha(PAIR / "orbit_key.py"),
        "source_sha256": sha(Path(__file__)),
    }
    return result_path, manifest_path, content, json.dumps(record, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result_path, manifest_path, content, manifest = export(args.n)
    if args.check:
        assert result_path.read_bytes() == content
        assert manifest_path.read_text() == manifest
    else:
        assert not result_path.exists() and not manifest_path.exists()
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_bytes(content)
        manifest_path.write_text(manifest)
    print(json.dumps({"n": args.n, "representatives": len(content) // 16,
                      "status": "PASS"}))


if __name__ == "__main__":
    main()
