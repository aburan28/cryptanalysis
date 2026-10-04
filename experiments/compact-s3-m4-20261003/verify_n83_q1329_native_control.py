#!/usr/bin/env python3
"""Independently replay Q1329/Q1332 unpinned N83 planted controls."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

from derive_onb_poly_bridge import poly_element, xor_images
from make_n83_native_planted_control import sampled_state
from run_probe import HERE, ROOT, curves, field, sha

PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PAIR))
from orbit_key import OrbitKey  # noqa: E402


def contains_sorted_key(packed, key):
    assert len(packed) % 21 == 0
    low, high = 0, len(packed) // 21
    while low < high:
        middle = (low + high) // 2
        found = int.from_bytes(packed[21 * middle:21 * (middle + 1)],
                               "little")
        if found < key:
            low = middle + 1
        else:
            high = middle
    return low < len(packed) // 21 and int.from_bytes(
        packed[21 * low:21 * (low + 1)], "little") == key


def replay(variant="scalar"):
    assert variant in ("scalar", "batch", "adaptive", "fast")
    started = time.perf_counter_ns()
    fixture_path = HERE / "runs/n83_q1329_planted_fixture.json"
    fixture = json.loads(fixture_path.read_text())
    manifest_name = {
        "scalar": "n83_planted_control_manifest.json",
        "batch": "n83_batch_planted_manifest.json",
        "adaptive": "n83_adaptive_planted_manifest.json",
        "fast": "n83_fast_planted_manifest.json",
    }[variant]
    manifest_path = HERE / "native_inputs" / manifest_name
    manifest = json.loads(manifest_path.read_text())
    native_name = {
        "scalar": "n83_q1329_planted_unpinned.json",
        "batch": "n83_q1332_batch_planted_unpinned.json",
        "adaptive": "n83_q1335_adaptive_planted_unpinned.json",
        "fast": "n83_q1338_fast_planted_unpinned.json",
    }[variant]
    native_path = HERE / "runs" / native_name
    native = json.loads(native_path.read_text())
    build_path = HERE / {
        "scalar": "native_build_receipt.json",
        "batch": "native_build_receipt.json",
        "adaptive": "native_adaptive_build_receipt.json",
        "fast": "native_fast_build_receipt.json",
    }[variant]
    build = json.loads(build_path.read_text())
    bridge_path = HERE / "field_bridges/n83_onb_poly.json"
    bridge = json.loads(bridge_path.read_text())
    ordinary_path = HERE / "native_inputs/n83_manifest.json"
    ordinary = json.loads(ordinary_path.read_text())
    reps_path = HERE / "native_inputs/n83_x_representatives.bin"
    key_path = HERE / "bases/n83_weight5_full_point_orbits.bin"
    archive_path = HERE / "bases/n83_weight5_full_orbits.json"
    archive = json.loads(archive_path.read_text())
    packed = key_path.read_bytes()
    assert hashlib.sha256(packed).hexdigest() == archive[
        "factor_base"]["enumerated_set_sha256"]
    assert fixture["source_sha256"] == sha(
        HERE / "make_n83_native_planted_control.py")
    assert fixture["ordinary_input_manifest_sha256"] == sha(ordinary_path)
    assert fixture["representatives_file_sha256"] == sha(reps_path)
    assert fixture["bridge_sha256"] == sha(bridge_path)
    proposal = {"scalar": "Q1329", "batch": "Q1332",
                "adaptive": "Q1335", "fast": "Q1338"}[variant]
    assert fixture["proposal_id"] == "Q1329"
    assert manifest["proposal_id"] == native["proposal_id"] == proposal
    assert fixture["parent_solver_proposal_id"] == "Q1328"
    assert manifest["parent_solver_proposal_id"] == {
        "scalar": "Q1328", "batch": "Q1331", "adaptive": "Q1334",
        "fast": "Q1337",
    }[variant]
    assert fixture["parent_factor_base_proposal_id"] == manifest[
        "parent_factor_base_proposal_id"] == "Q1325"
    assert fixture["candidate_id"] is manifest["candidate_id"] is None
    assert fixture["run_id"] is manifest["run_id"] is None
    assert fixture["isogeny"] == manifest["isogeny"] == native[
        "isogeny"] == "none"
    assert fixture["curve_id"] == manifest["curve_id"] == native[
        "curve_id"] == archive["curve"]["curve_id"]
    assert fixture["factor_base_actual_B"] == manifest[
        "actual_usable_points_B"] == native["actual_usable_points_B"] == (
            archive["factor_base"]["actual_usable_points_B_before_folding"])
    assert fixture["factor_base_folded_columns_K"] == manifest[
        "representative_count_K"] == native["folded_columns_K"] == (
            archive["factor_base"]["signed_frobenius_columns"])
    assert fixture["factor_base_enumerated_set_sha256"] == manifest[
        "factor_base_enumerated_set_sha256"] == native[
            "factor_base_enumerated_set_sha256"] == archive[
                "factor_base"]["enumerated_set_sha256"]
    assert fixture["pair_state_cap"] == manifest[
        "pair_state_cap"] == native["limits"]["pair_state_cap"] == 2_000_000
    assert fixture["peak_rss_cap_mib"] == manifest[
        "peak_rss_cap_mib"] == 1024
    assert native["limits"]["peak_rss_cap_bytes"] == 1024 ** 3
    assert native["peak_rss_bytes"] <= 1024 ** 3
    assert fixture["solver_receives_witness_or_index_positions"] is False
    assert fixture["is_natural_yield_measurement"] is False
    assert manifest["target_source_receipt_sha256"] == sha(fixture_path)
    protocol_path = (fixture_path if variant == "scalar" else HERE / {
        "batch": "q1332_batch_planted_control_protocol.json",
        "adaptive": "q1333_q1334_adaptive_window_protocol.json",
        "fast": "q1336_q1337_fast_root_protocol.json",
    }[variant])
    assert manifest["stage_protocol_sha256"] == native[
        "stage_protocol_sha256"] == sha(protocol_path)
    if variant == "scalar":
        assert manifest["source_sha256"] == fixture["source_sha256"]
    elif variant == "batch":
        protocol = json.loads(protocol_path.read_text())
        assert protocol["proposal_id"] == proposal
        assert protocol["parent_solver_proposal_id"] == "Q1331"
        assert protocol["planted_fixture_sha256"] == sha(fixture_path)
        assert protocol["native_source_sha256"] == sha(
            HERE / "native_s3_root.rs")
        assert manifest["source_sha256"] == sha(
            HERE / "freeze_batch_planted_control.py")
        assert manifest["planted_fixture_sha256"] == sha(fixture_path)
        assert manifest["parent_manifest_sha256"] == sha(
            HERE / "native_inputs/n83_planted_control_manifest.json")
    elif variant == "adaptive":
        protocol = json.loads(protocol_path.read_text())
        control = protocol["planted_control"]
        assert control["proposal_id"] == proposal
        assert control["parent_solver_proposal_id"] == "Q1334"
        assert control["target_count"] == manifest["target_count"] == 1
        assert control["target_s3_window_schedule"] == manifest[
            "target_s3_window_schedule"] == [1, 16, 64, 256, 1024, 4096]
        assert control["parent_input_manifest_sha256"] == sha(
            HERE / "native_inputs/n83_batch_planted_manifest.json")
        assert protocol["native_source_sha256"] == sha(
            HERE / "native_s3_root_adaptive.rs")
        assert manifest["source_sha256"] == sha(
            HERE / "freeze_adaptive_window_protocol.py")
    elif variant == "fast":
        protocol = json.loads(protocol_path.read_text())
        control = protocol["planted_control"]
        assert control["proposal_id"] == proposal
        assert control["parent_solver_proposal_id"] == "Q1337"
        assert control["target_count"] == manifest["target_count"] == 1
        assert control["target_s3_window_schedule"] == manifest[
            "target_s3_window_schedule"] == [1, 16, 64, 256, 1024, 4096]
        adaptive_manifest_path = HERE / "native_inputs/n83_adaptive_planted_manifest.json"
        assert manifest["parent_adaptive_input_manifest_sha256"] == sha(
            adaptive_manifest_path)
        assert protocol["native_source_sha256"] == sha(
            HERE / "native_s3_root_fast.rs")
        assert manifest["source_sha256"] == sha(
            HERE / "freeze_fast_root_protocol.py")
    assert native["input_representatives_sha256"] == sha(reps_path)
    build_source = HERE / {
        "scalar": "native_s3_root.rs",
        "batch": "native_s3_root.rs",
        "adaptive": "native_s3_root_adaptive.rs",
        "fast": "native_s3_root_fast.rs",
    }[variant]
    assert native["native_source_sha256"] == build[
        "source_sha256"] == sha(build_source)
    assert build["build_script_sha256"] == sha(HERE / (
        "build_native_s3_root.py" if variant in ("scalar", "batch") else
        "build_native_s3_root_adaptive.py" if variant == "adaptive" else
        "build_native_s3_root_fast.py"))
    assert native["cargo_manifest_sha256"] == build[
        "cargo_manifest_sha256"]
    assert native["sampling"]["orientations_per_state"] == manifest[
        "orientations_per_state"] == 83
    if variant in ("adaptive", "fast"):
        assert manifest["index_s3_window_size"] == 4096
        assert native["index_s3_window_size"] == 4096
        assert "s3_batch_size" not in manifest
    else:
        assert native["s3_batch_size"] == (
            1 if variant == "scalar" else 4096)
    assert native["index_pair_states_examined"] == 2_000_000
    assert native["target_states_scanned"] == 1
    assert 1 <= native["target_state_orientations_tested"] <= 83
    assert native["status"] == "native_relation_found"
    assert native["relation"]["native_group_sum_verified"] is True
    assert native["verified_single_target_dlp"] is False
    assert native["complete_work_log2"] is None
    if variant == "batch":
        unbatched_path = HERE / "runs/n83_q1329_planted_unpinned.json"
        unbatched = json.loads(unbatched_path.read_text())
        assert native["relation"] == unbatched["relation"]
        assert native["target_states_scanned"] == unbatched[
            "target_states_scanned"]
        assert native["target_state_orientations_tested"] == unbatched[
            "target_state_orientations_tested"]
    if variant in ("adaptive", "fast"):
        assert native["target_s3_window_schedule"] == manifest[
            "target_s3_window_schedule"]
        assert native["target_states_prepared"] == 1
        assert native["target_state_orientations_prepared"] == 83
        assert native["target_state_orientations_tested"] == 34
        assert native["target_root_windows"] == 1
        scalar_path = HERE / "runs/n83_q1329_planted_unpinned.json"
        scalar = json.loads(scalar_path.read_text())
        assert native["relation"] == scalar["relation"]
        if variant == "fast":
            adaptive_path = HERE / "runs/n83_q1335_adaptive_planted_unpinned.json"
            adaptive = json.loads(adaptive_path.read_text())
            assert native["target_states_scanned"] == adaptive[
                "target_states_scanned"] == 1
            assert native["target_states_prepared"] == adaptive[
                "target_states_prepared"] == 1
            assert native["target_state_orientations_tested"] == adaptive[
                "target_state_orientations_tested"] == 34
            assert native["relation"] == adaptive["relation"]

    canonical = json.dumps(fixture["workload_record"], sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False).encode()
    assert fixture["workload_canonical_sha256"] == hashlib.sha256(
        canonical).hexdigest()
    assert fixture["workload_id"] == manifest["workload_id"] == native[
        "workload_id"] == hashlib.sha256(canonical).hexdigest()[:12]
    assert fixture["workload_record"]["target_count"] == 1
    assert fixture["selected_index_states"] == [
        sampled_state(position, manifest["representative_count_K"])
        for position in (0, 1)]

    onb = field.Onb(83)
    curve = curves.Curve(onb)
    subgroup_order = int(archive["curve"]["subgroup_order"])
    inverse = bridge["poly_to_onb_basis_images"]
    target = tuple(map(int, fixture["planted_target_onb"]))
    assert curve.onCurve(target) and curve.mul(target, subgroup_order) is None
    mapped_target = [xor_images(onb.toCoords(value), bridge[
        "onb_to_poly_basis_images"]) for value in target]
    assert list(map(str, mapped_target)) == manifest[
        "target_poly_xy"] == fixture["planted_target_poly_decimal"]
    assert fixture["workload_record"]["target_points_onb"] == [list(target)]

    witness = [tuple(map(int, pair)) for pair in fixture[
        "oracle_witness_points_onb"]]
    assert len(witness) == 4
    witness_sum = None
    for point in witness:
        assert curve.onCurve(point) and curve.mul(point, subgroup_order) is None
        witness_sum = curve.add(witness_sum, point)
    assert witness_sum == target

    recovered = [tuple(onb.fromCoords(xor_images(int(word), inverse))
                       for word in pair) for pair in native[
                           "relation"]["poly_points_xy_decimal"]]
    assert len(recovered) == 4
    orbit = OrbitKey(onb)
    recovered_sum = None
    keys = []
    for point in recovered:
        assert curve.onCurve(point)
        assert curve.mul(point, subgroup_order) is None
        key, _, _ = orbit.canonical(point)
        assert contains_sorted_key(packed, key)
        keys.append(key)
        recovered_sum = curve.add(recovered_sum, point)
    assert recovered_sum == target

    ring = PolynomialRing(GF(2), "z")
    z = ring.gen()
    modulus = z ** 83 + sum(z ** degree for degree in manifest[
        "polynomial_low_terms"])
    poly_field = GF(2 ** 83, "verify_q1329", modulus=modulus)
    poly_curve = EllipticCurve(poly_field, [1, 0, 0, 0, 1])
    def poly_point(pair):
        return poly_curve(*(poly_element(poly_field, int(value))
                            for value in pair))
    assert sum((poly_point(pair) for pair in native["relation"][
        "poly_points_xy_decimal"]), poly_curve(0)) == poly_point(
            manifest["target_poly_xy"])

    result = {
        "kind": "independent_sage_n83_native_four_leaf_planted_control_replay",
        "status": "PASS",
        "proposal_id": proposal,
        "candidate_id": None,
        "run_id": None,
        "curve_id": fixture["curve_id"],
        "workload_id": fixture["workload_id"],
        "isogeny": "none",
        "native_relation_independently_verified": True,
        "four_recovered_points_in_exact_q1325_factor_base": True,
        "recovered_signed_frobenius_columns": len(set(keys)),
        "subgroup_points_checked": 4,
        "target_states_scanned": native["target_states_scanned"],
        "target_state_orientations_tested": native[
            "target_state_orientations_tested"],
        "is_natural_yield_measurement": False,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "verification_wall_ns": time.perf_counter_ns() - started,
        "fixture_sha256": sha(fixture_path),
        "manifest_sha256": sha(manifest_path),
        "native_receipt_sha256": sha(native_path),
        "native_build_receipt_sha256": sha(build_path),
        "source_sha256": sha(Path(__file__)),
        "orbit_source_sha256": sha(PAIR / "orbit_key.py"),
    }
    if variant == "batch":
        result.update({
            "s3_batch_size": 4096,
            "target_states_prepared": native["target_states_prepared"],
            "target_state_orientations_prepared": native[
                "target_state_orientations_prepared"],
            "batch_protocol_sha256": sha(protocol_path),
            "matched_unbatched_relation_receipt_sha256": sha(unbatched_path),
        })
    if variant == "adaptive":
        result.update({
            "target_count": 1,
            "target_s3_window_schedule": manifest[
                "target_s3_window_schedule"],
            "target_states_prepared": native["target_states_prepared"],
            "target_state_orientations_prepared": native[
                "target_state_orientations_prepared"],
            "target_root_windows": native["target_root_windows"],
            "adaptive_protocol_sha256": sha(protocol_path),
            "matched_window_1_relation_receipt_sha256": sha(scalar_path),
        })
    if variant == "fast":
        adaptive_path = HERE / "runs/n83_q1335_adaptive_planted_unpinned.json"
        result.update({
            "target_count": 1,
            "target_s3_window_schedule": manifest[
                "target_s3_window_schedule"],
            "target_states_prepared": native["target_states_prepared"],
            "target_state_orientations_prepared": native[
                "target_state_orientations_prepared"],
            "target_root_windows": native["target_root_windows"],
            "target_field_multiplications": native["operation_counts"][
                "target_pdp_and_native_check"]["field_mul_calls"],
            "fast_protocol_sha256": sha(protocol_path),
            "matched_adaptive_relation_receipt_sha256": sha(adaptive_path),
        })
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("scalar", "batch", "adaptive",
                                                "fast"),
                        default="scalar")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = HERE / "runs" / {
        "scalar": "n83_q1329_planted_independent_replay.json",
        "batch": "n83_q1332_batch_planted_independent_replay.json",
        "adaptive": "n83_q1335_adaptive_planted_independent_replay.json",
        "fast": "n83_q1338_fast_planted_independent_replay.json",
    }[args.variant]
    report = replay(args.variant)
    if args.check:
        expected = json.loads(path.read_text())
        report.pop("verification_wall_ns")
        expected.pop("verification_wall_ns")
        assert report == expected
    else:
        assert not path.exists()
        path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"proposal_id": report["proposal_id"], "status": "PASS",
                      "verified_relation": report[
                          "native_relation_independently_verified"]}))


if __name__ == "__main__":
    main()
