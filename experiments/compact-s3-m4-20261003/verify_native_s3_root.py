#!/usr/bin/env python3
"""Independently replay native S3 stage receipts on the frozen Sage curves."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

from derive_onb_poly_bridge import poly_element, xor_images
from run_probe import HERE, curves, field, sha


def canonical_x(onb, value):
    current = value
    masks = []
    for _ in range(onb.m):
        masks.append(onb.toCoords(current))
        current = onb.sqr(current)
    assert current == value
    return min(masks)


def frobenius_eigenvalue(curve, archive):
    r = int(archive["curve"]["subgroup_order"])
    assert GF(r).characteristic() == r
    # The one-step Frobenius is the degree-2 endomorphism over F2.
    # This exact Koblitz model has four F2 points including infinity.
    tiny = EllipticCurve(GF(2), [1, 0, 0, 0, 1])
    assert tiny.cardinality() == 4
    trace = 2 + 1 - tiny.cardinality()
    ring = PolynomialRing(GF(r), "v")
    v = ring.gen()
    roots = (v * v - trace * v + 2).roots()
    generator = tuple(map(int, archive["curve"]["generator"]))
    assert curve.onCurve(generator) and curve.mul(generator, r) is None
    matches = [int(root) for root, _ in roots
               if curve.mul(generator, int(root)) == curve.frob(generator)]
    assert len(matches) == 1
    return matches[0]


def row_for_points(points, keys, curve, onb, eigenvalue, r):
    index = {key: col for col, key in enumerate(keys)}
    row = {}
    leaves = []
    for point in points:
        key = canonical_x(onb, point[0])
        assert key in index
        representative = curve.pointFromX(onb.fromCoords(key))
        assert representative is not None
        shifted = representative
        coefficient = 1
        found = None
        for shift in range(onb.m):
            if point == shifted:
                found = (shift, 1, coefficient)
                break
            if point == curve.neg(shifted):
                found = (shift, -1, (-coefficient) % r)
                break
            shifted = curve.frob(shifted)
            coefficient = coefficient * eigenvalue % r
        assert found is not None
        col = index[key]
        row[col] = (row.get(col, 0) + found[2]) % r
        leaves.append({"column": col, "frobenius_shift": found[0],
                       "sign": found[1], "coefficient_mod_r": found[2]})
    row = {col: value for col, value in row.items() if value}
    assert row
    reconstructed = None
    for col, coefficient in row.items():
        rep = curve.pointFromX(onb.fromCoords(keys[col]))
        reconstructed = curve.add(reconstructed,
                                  curve.mul(rep, coefficient))
    return row, leaves, reconstructed


def independent_rank_two(left, right, r):
    assert left and right
    pivot = next(iter(left))
    ratio = right.get(pivot, 0) * pow(left[pivot], -1, r) % r
    return 1 if all(right.get(col, 0) == ratio * left.get(col, 0) % r
                    for col in left.keys() | right.keys()) else 2


def replay(n, variant="scalar"):
    assert variant in ("scalar", "batch", "adaptive", "fast")
    started = time.perf_counter_ns()
    if variant == "scalar":
        source_name = ("n53_native_root_full.json" if n == 53 else
                       "n83_native_root_capped_2m.json")
        manifest_name = f"n{n}_manifest.json"
        protocol_name = "q1327_q1328_native_root_protocol.json"
        build_name = "native_build_receipt.json"
    elif variant == "batch":
        source_name = ("n53_batch_root_full.json" if n == 53 else
                       "n83_batch_root_capped_2m.json")
        manifest_name = f"n{n}_batch_manifest.json"
        protocol_name = "q1330_q1331_batch_root_protocol.json"
        build_name = "native_build_receipt.json"
    elif variant == "adaptive":
        source_name = ("n53_adaptive_root_full.json" if n == 53 else
                       "n83_adaptive_root_capped_2m.json")
        manifest_name = f"n{n}_adaptive_manifest.json"
        protocol_name = "q1333_q1334_adaptive_window_protocol.json"
        build_name = "native_adaptive_build_receipt.json"
    else:
        source_name = ("n53_fast_root_full.json" if n == 53 else
                       "n83_fast_root_capped_2m.json")
        manifest_name = f"n{n}_fast_manifest.json"
        protocol_name = "q1336_q1337_fast_root_protocol.json"
        build_name = "native_fast_build_receipt.json"
    source_path = HERE / "runs" / source_name
    source = json.loads(source_path.read_text())
    manifest_path = HERE / "native_inputs" / manifest_name
    manifest = json.loads(manifest_path.read_text())
    protocol_path = HERE / protocol_name
    protocol = json.loads(protocol_path.read_text())
    stage = next(row for row in protocol["profiles"]
                 if row["field_degree"] == n)
    reps_path = HERE / "native_inputs" / f"n{n}_x_representatives.bin"
    bridge_path = HERE / "field_bridges" / f"n{n}_onb_poly.json"
    bridge = json.loads(bridge_path.read_text())
    build_path = HERE / build_name
    build = json.loads(build_path.read_text())
    runtime_path = HERE / "native_root_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    assert manifest["runtime_info_sha256"] == sha(runtime_path)
    assert manifest["stage_protocol_sha256"] == sha(protocol_path)
    if variant == "batch":
        assert protocol["native_source_sha256"] == sha(
            HERE / "native_s3_root.rs")
        assert manifest["ordinary_input_manifest_sha256"] == sha(
            HERE / "native_inputs" / f"n{n}_manifest.json")
        assert manifest["parent_solver_proposal_id"] == (
            "Q1327" if n == 53 else "Q1328")
    if variant == "adaptive":
        assert protocol["native_source_sha256"] == sha(
            HERE / "native_s3_root_adaptive.rs")
        assert manifest["target_count"] == stage["target_count"] == 1
        assert manifest["target_s3_window_schedule"] == [
            1, 16, 64, 256, 1024, 4096]
        assert source["target_s3_window_schedule"] == manifest[
            "target_s3_window_schedule"]
        assert manifest["parent_solver_proposal_id"] == (
            "Q1330" if n == 53 else "Q1331")
    if variant == "fast":
        assert protocol["native_source_sha256"] == sha(
            HERE / "native_s3_root_fast.rs")
        assert manifest["target_count"] == stage["target_count"] == 1
        assert manifest["target_s3_window_schedule"] == [
            1, 16, 64, 256, 1024, 4096]
        assert source["target_s3_window_schedule"] == manifest[
            "target_s3_window_schedule"]
        assert manifest["parent_solver_proposal_id"] == (
            "Q1333" if n == 53 else "Q1334")
    assert manifest["proposal_id"] == stage["proposal_id"]
    assert manifest["parent_factor_base_proposal_id"] == stage[
        "parent_factor_base_proposal_id"]
    assert manifest["pair_state_cap"] == stage["pair_state_cap"]
    assert manifest["peak_rss_cap_mib"] == stage[
        "peak_rss_cap_mib"]
    assert build["status"] == "PASS"
    source_file = {
        "scalar": "native_s3_root.rs",
        "batch": "native_s3_root.rs",
        "adaptive": "native_s3_root_adaptive.rs",
        "fast": "native_s3_root_fast.rs",
    }[variant]
    build_script = {
        "scalar": "build_native_s3_root.py",
        "batch": "build_native_s3_root.py",
        "adaptive": "build_native_s3_root_adaptive.py",
        "fast": "build_native_s3_root_fast.py",
    }[variant]
    assert build["source_sha256"] == sha(HERE / source_file)
    assert build["build_script_sha256"] == sha(HERE / build_script)
    assert source["native_source_sha256"] == build["source_sha256"]
    assert source["cargo_manifest_sha256"] == build[
        "cargo_manifest_sha256"]
    binary_path = Path(build["binary_path"])
    if binary_path.exists():
        assert sha(binary_path) == build["binary_sha256"]
    expected_manifest_source = {
        "scalar": "export_native_root_inputs.py",
        "batch": "freeze_batch_root_protocol.py",
        "adaptive": "freeze_adaptive_window_protocol.py",
        "fast": "freeze_fast_root_protocol.py",
    }[variant]
    assert manifest["source_sha256"] == sha(HERE / expected_manifest_source)
    assert manifest["representatives_file_sha256"] == sha(reps_path)
    assert manifest["bridge_sha256"] == sha(bridge_path)
    assert source["input_representatives_sha256"] == sha(reps_path)
    assert source["curve_id"] == manifest["curve_id"] == bridge["curve_id"]
    assert source["workload_id"] == manifest["workload_id"]
    assert source["proposal_id"] == manifest["proposal_id"]
    assert source["parent_factor_base_proposal_id"] == manifest[
        "parent_factor_base_proposal_id"]
    assert source["stage_protocol_sha256"] == sha(protocol_path)
    assert source["isogeny"] == manifest["isogeny"] == "none"
    assert source["candidate_id"] is None and source["run_id"] is None
    assert source["actual_usable_points_B"] == manifest["actual_usable_points_B"]
    assert source["folded_columns_K"] == manifest["representative_count_K"]
    assert source["factor_base_enumerated_set_sha256"] == manifest[
        "factor_base_enumerated_set_sha256"]
    assert source["peak_rss_bytes"] <= source["limits"]["peak_rss_cap_bytes"]
    assert source["limits"]["pair_state_cap"] == stage["pair_state_cap"]
    assert source["limits"]["peak_rss_cap_bytes"] == (
        stage["peak_rss_cap_mib"] * 1024 * 1024)
    assert source["sampling"]["orientations_per_state"] == 1
    if variant in ("adaptive", "fast"):
        assert manifest["index_s3_window_size"] == 4096
        assert source["index_s3_window_size"] == 4096
        assert "s3_batch_size" not in manifest
    else:
        assert source["s3_batch_size"] == (1 if variant == "scalar" else 4096)
    assert source["target_states_prepared"] >= source[
        "target_states_scanned"]
    assert source["target_state_orientations_prepared"] >= source[
        "target_state_orientations_tested"]
    if variant in ("batch", "adaptive", "fast"):
        if variant == "batch":
            assert source["index_root_batches"] == (
                source["index_pair_states_examined"] + 4095) // 4096
            assert source["target_root_batches"] == (
                source["target_states_prepared"] + 4095) // 4096
        else:
            assert source["index_root_windows"] == (
                source["index_pair_states_examined"] + 4095) // 4096
            prepared = 0
            windows = 0
            schedule = manifest["target_s3_window_schedule"]
            while prepared < source["target_states_prepared"]:
                size = (schedule[windows] if windows < len(schedule) else
                        source["index_s3_window_size"])
                prepared += min(size,
                                source["target_states_prepared"] - prepared)
                windows += 1
            assert windows == source["target_root_windows"]
        scalar_path = HERE / "runs" / (
            "n53_native_root_full.json" if n == 53
            else "n83_native_root_capped_2m.json")
        scalar = json.loads(scalar_path.read_text())
        for key in ("curve_id", "workload_id", "actual_usable_points_B",
                    "folded_columns_K", "index_pair_states_examined",
                    "index_distinct_root_keys", "target_states_scanned",
                    "status", "relation", "target_table_hits"):
            assert source[key] == scalar[key]
        if variant == "adaptive":
            fixed_path = HERE / "runs" / (
                "n53_batch_root_full.json" if n == 53 else
                "n83_batch_root_capped_2m.json")
            fixed = json.loads(fixed_path.read_text())
            for key in ("curve_id", "workload_id", "actual_usable_points_B",
                        "folded_columns_K", "index_pair_states_examined",
                        "index_distinct_root_keys", "target_states_scanned",
                        "status", "relation", "target_table_hits"):
                assert source[key] == fixed[key]
        if variant == "fast":
            adaptive_path = HERE / "runs" / (
                "n53_adaptive_root_full.json" if n == 53 else
                "n83_adaptive_root_capped_2m.json")
            adaptive = json.loads(adaptive_path.read_text())
            for key in ("curve_id", "workload_id", "actual_usable_points_B",
                        "folded_columns_K", "index_pair_states_examined",
                        "index_distinct_root_keys", "target_states_scanned",
                        "target_states_prepared", "target_root_windows",
                        "status", "relation", "target_table_hits"):
                assert source[key] == adaptive[key]
    assert source["index_pair_states_examined"] <= source["limits"][
        "pair_state_cap"]
    assert source["target_states_scanned"] <= source[
        "index_satisfiable_s3_states"]
    assert source["operation_counts"]["index_build"]["s3_root_calls"] == source[
        "index_pair_states_examined"]
    assert source["verified_single_target_dlp"] is False
    assert source["complete_work_log2"] is None

    onb = field.Onb(n)
    curve = curves.Curve(onb)
    ring = PolynomialRing(GF(2), "z")
    z = ring.gen()
    modulus = z ** n + sum(z ** degree for degree in manifest[
        "polynomial_low_terms"])
    poly_field = GF(2 ** n, f"verify_u{n}", modulus=modulus)
    poly_curve = EllipticCurve(poly_field, [1, 0, 0, 0, 1])
    to_poly_point = lambda values: poly_curve(*(
        poly_element(poly_field, int(value)) for value in values))
    generator_poly = to_poly_point(bridge["mapped_generator_poly"])
    target_poly = to_poly_point(manifest["target_poly_xy"])
    control = source["native_s3_generator_target_control"]
    assert control["status"] == "PASS"
    assert generator_poly + target_poly == to_poly_point(
        control["sum_poly_xy_decimal"])
    assert control["sum_x_is_s3_root"] is True
    u, v, w = generator_poly[0], target_poly[0], (
        generator_poly + target_poly)[0]
    assert (u * v + u * w + v * w) ** 2 + u * v * w + 1 == 0

    result = {
        "kind": "independent_sage_native_s3_root_replay",
        "status": "PASS",
        "field_degree": n,
        "curve_id": source["curve_id"],
        "workload_id": source["workload_id"],
        "proposal_id": source["proposal_id"],
        "candidate_id": None,
        "isogeny": "none",
        "native_stage_status": source["status"],
        "parent_factor_base_proposal_id": source[
            "parent_factor_base_proposal_id"],
        "native_s3_generator_target_control_replayed": True,
        "ordinary_relation_independently_verified": False,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
    }
    if variant == "batch":
        result.update({
            "s3_batch_size": 4096,
            "parent_solver_proposal_id": manifest["parent_solver_proposal_id"],
            "matched_scalar_stage_sha256": sha(scalar_path),
        })
    if variant == "adaptive":
        fixed_path = HERE / "runs" / (
            "n53_batch_root_full.json" if n == 53 else
            "n83_batch_root_capped_2m.json")
        result.update({
            "target_count": 1,
            "target_s3_window_schedule": manifest[
                "target_s3_window_schedule"],
            "target_states_scanned": source["target_states_scanned"],
            "target_states_prepared": source["target_states_prepared"],
            "target_root_windows": source["target_root_windows"],
            "matched_fixed_window_stage_sha256": sha(fixed_path),
            "parent_solver_proposal_id": manifest[
                "parent_solver_proposal_id"],
        })
    if variant == "fast":
        adaptive_path = HERE / "runs" / (
            "n53_adaptive_root_full.json" if n == 53 else
            "n83_adaptive_root_capped_2m.json")
        result.update({
            "target_count": 1,
            "target_s3_window_schedule": manifest[
                "target_s3_window_schedule"],
            "target_states_scanned": source["target_states_scanned"],
            "target_states_prepared": source["target_states_prepared"],
            "target_root_windows": source["target_root_windows"],
            "parent_solver_proposal_id": manifest[
                "parent_solver_proposal_id"],
            "matched_adaptive_stage_sha256": sha(adaptive_path),
            "target_field_multiplications": source[
                "operation_counts"]["target_pdp_and_native_check"][
                    "field_mul_calls"],
        })
    if n == 53:
        assert source["status"] == "native_relation_found"
        assert source["relation"]["native_group_sum_verified"] is True
        archive_path = HERE / "bases/n53_weight3_orbits.json.gz"
        with gzip.open(archive_path, "rt") as stream:
            archive = json.load(stream)
        packed = base64.b64decode(archive["factor_base"][
            "packed_canonical_x_keys_base64"], validate=True)
        assert hashlib.sha256(packed).hexdigest() == manifest[
            "factor_base_enumerated_set_sha256"]
        keys = [int.from_bytes(packed[i:i + 7], "little")
                for i in range(0, len(packed), 7)]
        assert len(keys) == source["folded_columns_K"] == 227
        inverse = bridge["poly_to_onb_basis_images"]
        poly_values = source["relation"]["poly_points_xy_decimal"]
        poly_points = [to_poly_point(pair) for pair in poly_values]
        assert sum(poly_points, poly_curve(0)) == target_poly
        points = [tuple(onb.fromCoords(xor_images(int(word), inverse))
                        for word in pair) for pair in poly_values]
        r = int(archive["curve"]["subgroup_order"])
        for point in points:
            assert curve.onCurve(point)
            assert curve.mul(point, r) is None
            assert canonical_x(onb, point[0]) in keys
        total = None
        for point in points:
            total = curve.add(total, point)
        ordinary = json.loads((HERE / "runs/n53_ordinary_frozen.json").read_text())
        target = tuple(map(int, ordinary["public_subgroup_target"]))
        assert total == target
        eigenvalue = frobenius_eigenvalue(curve, archive)
        row, leaves, row_total = row_for_points(
            points, keys, curve, onb, eigenvalue, r)
        assert row_total == target
        matched = json.loads((HERE /
            "runs/n53_ordinary_matched_pair_table.json").read_text())
        matched_points = [tuple(map(int, pair)) for pair in matched[
            "ordinary_query"]["relation"]["points"]]
        matched_row, _, matched_total = row_for_points(
            matched_points, keys, curve, onb, eigenvalue, r)
        assert matched_total == target
        result.update({
            "ordinary_relation_independently_verified": True,
            "four_points_in_exact_factor_base": True,
            "subgroup_points_checked": 4,
            "frobenius_eigenvalue_mod_r": eigenvalue,
            "relation_row_nonzero_columns": len(row),
            "relation_row": {str(col): value for col, value in sorted(row.items())},
            "relation_leaf_labels": leaves,
            "rank_of_native_and_matched_pair_rows": independent_rank_two(
                row, matched_row, r),
            "matched_pair_receipt_sha256": sha(HERE /
                "runs/n53_ordinary_matched_pair_table.json"),
        })
    else:
        assert source["status"] == "state_cap_no_relation"
        assert source["relation"] is None
        assert source["index_pair_states_examined"] == 2_000_000
        assert source["target_states_scanned"] == 2_000_000
        result["censored_ordinary_query"] = True
        result["proves_target_unsupported"] = False
    result.update({
        "verification_wall_ns": time.perf_counter_ns() - started,
        "native_receipt_sha256": sha(source_path),
        "native_build_receipt_sha256": sha(build_path),
        "native_input_manifest_sha256": sha(manifest_path),
        "stage_protocol_sha256": sha(protocol_path),
        "native_input_representatives_sha256": sha(reps_path),
        "bridge_sha256": sha(bridge_path),
        "runtime_info_sha256": sha(runtime_path),
        "source_sha256": sha(Path(__file__)),
    })
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--variant", choices=("scalar", "batch", "adaptive",
                                                "fast"),
                        default="scalar")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    replay_name = {
        "scalar": f"n{args.n}_native_root_independent_replay.json",
        "batch": f"n{args.n}_batch_root_independent_replay.json",
        "adaptive": f"n{args.n}_adaptive_root_independent_replay.json",
        "fast": f"n{args.n}_fast_root_independent_replay.json",
    }[args.variant]
    path = HERE / "runs" / replay_name
    report = replay(args.n, args.variant)
    content = json.dumps(report, indent=2) + "\n"
    if args.check:
        stable = json.loads(path.read_text())
        report.pop("verification_wall_ns")
        stable.pop("verification_wall_ns")
        assert stable == report
    else:
        assert not path.exists()
        path.write_text(content)
    print(json.dumps({"n": args.n, "variant": args.variant, "status": "PASS",
                      "native_stage_status": report["native_stage_status"],
                      "verified_relation": report[
                          "ordinary_relation_independently_verified"]}))


if __name__ == "__main__":
    main()
