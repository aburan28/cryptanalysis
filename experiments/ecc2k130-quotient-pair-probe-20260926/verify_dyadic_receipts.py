#!/usr/bin/env python3
"""Verify curve IDs, dyadic labels, counts, and any ordinary relation receipt."""

import hashlib
import json
import math
import random
from pathlib import Path

import curves
import field
from dyadic_base_geometry import CONFIG, enumerate_points
from dyadic_two_seed_geometry import CONFIG as TWO_SEED_CONFIG
from dyadic_n53_five_sum_dlp import build_g_pair_index
from dyadic_n83_compact_index import build_packed
from dyadic_n83_five_sum_symmetric_stage import build_symmetric
from dyadic_n83_g_pair_scalar_support import coefficients_by_window, quotient_keys
from perf_probe import sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def verify_geometry(n):
    path = HERE / "runs" / f"n{n}_dyadic_base_geometry.json"
    report = json.loads(path.read_text())
    reference_path = HERE / "runs" / f"n{n}_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    cfg = CONFIG[n]
    assert report["candidate_id"] is None and report["isogeny"] == "none"
    assert report["source_sha256"] == sha(HERE / "dyadic_base_geometry.py")
    assert report["reference_sha256"] == sha(reference_path)
    assert report["curve_identity_record"] == reference["curve_identity_record"]
    identity_hash = hashlib.sha256(frozen(report["curve_identity_record"])).hexdigest()
    assert report["curve_id"] == reference["curve_id"]
    assert report["curve_id"].endswith("h" + identity_hash[:12])
    workload_id = hashlib.sha256(frozen(report["workload"])).hexdigest()[:12]
    assert report["workload_id"] == workload_id
    assert report["run_id"] == f"{report['proposal_id']}W{workload_id}R1"
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    order = int(report["subgroup_order"])
    seeds = [tuple(seed) for seed in report["seed_points"]]
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    assert seeds[0] == generator
    lam = int(report["frobenius_eigenvalue_mod_r"])
    assert (lam * lam + lam + 2) % order == 0
    assert curve.mul(generator, lam) == curve.frob(generator)
    for seed_index, power, shift, coefficient, x, y in report[
            "sample_scalar_label_replays"]:
        assert coefficient == pow(2, power, order) * pow(lam, shift, order) % order
        assert curve.mul(seeds[seed_index], coefficient) == (x, y)
    base = report["factor_base"]
    k, length = cfg["seed_columns"], cfg["doubling_window"]
    b = 2 * n * k * length
    assert base["actual_usable_points_B_before_folding"] == b
    assert base["signed_frobenius_columns"] == k * length
    assert base["effective_unknown_log_columns_after_dyadic_labels"] == k - 1
    pair_count = math.comb(k, 2) * (2 * n * length)**2
    screen = report["conditional_direct_pair_screen"]
    assert int(screen["exact_cross_seed_unordered_pair_count"]) == pair_count
    assert math.isclose(screen["rank_plus_target_pair_probes_model_log2"],
                        math.log2(k * order / pair_count), abs_tol=1e-12)
    return report, seeds, curve


def verify_n53_relation(report, seeds, curve):
    reference = json.loads((HERE / "runs" / "n53_perf_prefix.json").read_text())
    order = int(reference["subgroup_order"])
    assert report["curve_id"] == reference["curve_id"]
    relation = report.get("relation")
    if relation is None:
        assert report["ordinary_query"]["status"] == "complete_index_miss"
        assert report["ordinary_query"]["lookups_including_failed"] == report[
            "index_build"]["quotient_keys"] * 2 * 53
        return "complete_miss"
    points = [tuple(point) for point in relation["point_witness"]]
    total = None
    for point in points:
        total = curve.add(total, point)
    assert total == tuple(report["target"])
    vector = relation["seed_coefficient_vector_mod_r"]
    scalar_total = None
    for seed, coefficient in zip(seeds, vector):
        if coefficient:
            scalar_total = curve.add(scalar_total, curve.mul(seed, coefficient))
    assert scalar_total == total
    assert curve.mul(seeds[0], relation["fixture_scalar_validation_only"]) == total
    assert relation["known_scalar_rhs_after_generator_seed"] == (
        relation["fixture_scalar_validation_only"] - vector[0]) % order
    return "verified_relation"


def verify_two_seed_geometry(n):
    path = HERE / "runs" / f"n{n}_dyadic_two_seed_geometry.json"
    report = json.loads(path.read_text())
    reference = json.loads((HERE / "runs" / f"n{n}_perf_prefix.json").read_text())
    cfg = TWO_SEED_CONFIG[n]
    assert report["source_sha256"] == sha(HERE / "dyadic_two_seed_geometry.py")
    assert report["curve_id"] == reference["curve_id"]
    assert report["curve_identity_record"] == reference["curve_identity_record"]
    assert report["candidate_id"] is None and report["isogeny"] == "none"
    assert report["workload_id"] == hashlib.sha256(frozen(report["workload"])).hexdigest()[:12]
    assert report["run_id"] == f"{report['proposal_id']}W{report['workload_id']}R1"
    curve = curves.Curve(field.Onb(n))
    order = int(report["subgroup_order"])
    seeds = [tuple(seed) for seed in report["seed_points"]]
    assert seeds[0] == tuple(reference["curve_identity_record"]["curve"]["generator"])
    lam = int(report["frobenius_eigenvalue_mod_r"])
    assert (lam * lam + lam + 2) % order == 0
    assert curve.mul(seeds[0], lam) == curve.frob(seeds[0])
    for seed_index, power, shift, coefficient, x, y in report[
            "sample_scalar_label_replays"]:
        assert coefficient == pow(2, power, order) * pow(lam, shift, order) % order
        assert curve.mul(seeds[seed_index], coefficient) == (x, y)
    base = report["factor_base"]
    assert base["actual_usable_points_B_before_folding"] == 4 * n * cfg["window"]
    assert base["signed_frobenius_columns"] == 2 * cfg["window"]
    assert base["effective_unknown_log_columns_after_dyadic_labels"] == 1
    pair_count = (2 * n * cfg["window"])**2
    screen = report["conditional_direct_pair_screen"]
    assert int(screen["exact_cross_seed_unordered_pair_count"]) == pair_count
    assert math.isclose(screen["one_seed_log_relation_plus_one_target_pair_probes_model_log2"],
                        math.log2(2 * order / pair_count), abs_tol=1e-12)
    return report


def verify_n83_target_geometry():
    path = HERE / "runs" / "n83_dyadic_target_seed_geometry.json"
    report = json.loads(path.read_text())
    reference = json.loads((HERE / "runs" / "n83_perf_prefix.json").read_text())
    assert report["source_sha256"] == sha(HERE / "dyadic_n83_target_base.py")
    assert report["curve_id"] == reference["curve_id"]
    assert report["curve_identity_record"] == reference["curve_identity_record"]
    assert report["candidate_id"] is None and report["isogeny"] == "none"
    assert report["workload_id"] == hashlib.sha256(frozen(report["workload"])).hexdigest()[:12]
    assert report["run_id"] == f"Q1020W{report['workload_id']}R1"
    curve = curves.Curve(field.Onb(83))
    order = int(report["subgroup_order"])
    seeds = [tuple(report["generator"]), tuple(report["target"])]
    assert seeds[1] == tuple(reference["workload"]["target"])
    lam = int(report["frobenius_eigenvalue_mod_r"])
    assert (lam * lam + lam + 2) % order == 0
    labels, representatives, digests = enumerate_points(
        curve, curve.f, seeds, 1000, lam, order)
    base = report["factor_base"]
    assert len(labels) == base["actual_usable_points_B_before_folding"] == 332000
    assert len(representatives) == base["signed_frobenius_columns"] == 2000
    assert base["effective_unknown_log_columns_after_dyadic_labels"] == 1
    for name, value in digests.items():
        assert base[name] == value
    for seed_index, power, shift, coefficient, x, y in report[
            "sample_scalar_label_replays"]:
        assert coefficient == pow(2, power, order) * pow(lam, shift, order) % order
        assert curve.mul(seeds[seed_index], coefficient) == (x, y)
    return report


def verify_panel(seeds, curve):
    path = HERE / "runs" / "n53_dyadic_relation_panel.json"
    if not path.exists():
        return "not_run"
    report = json.loads(path.read_text())
    fixture_path = HERE / "runs" / "n53_dyadic_panel_fixtures.json"
    fixture = json.loads(fixture_path.read_text())
    assert report["fixture_sha256"] == sha(fixture_path)
    assert report["source_sha256"] == sha(HERE / "dyadic_n53_relation_panel.py")
    assert report["workload_id"] == hashlib.sha256(frozen(report["workload"])).hexdigest()[:12]
    assert report["run_id"] == f"Q1016W{report['workload_id']}R1"
    assert fixture["workload"] == report["workload"]
    order = int(json.loads((HERE / "runs" / "n53_perf_prefix.json").read_text())[
        "subgroup_order"])
    for row in report["target_rows"]:
        target = tuple(row["target"])
        assert curve.mul(seeds[0], row["fixture_scalar_validation_only"]) == target
        assert target == tuple(report["workload"]["target_points"][row["target_index"]])
        relation = row["relation"]
        if relation is None:
            assert row["ordinary_query"]["status"] == "complete_index_miss"
            assert row["ordinary_query"]["lookups_including_failed"] == (
                report["index_build"]["quotient_keys"] * 106)
            continue
        points = [tuple(point) for point in relation["point_witness"]]
        total = None
        for point in points:
            total = curve.add(total, point)
        assert total == target
        vector = relation["seed_coefficient_vector_mod_r"]
        replay = None
        for seed, coefficient in zip(seeds, vector):
            replay = curve.add(replay, curve.mul(seed, coefficient))
        assert replay == target
        assert relation["known_scalar_rhs_after_generator_seed"] == (
            row["fixture_scalar_validation_only"] - vector[0]) % order
    return report["status"]


def verify_n53_target_seed_dlp(filename, source_name, window, proposal_id):
    path = HERE / "runs" / filename
    if not path.exists():
        return "not_run"
    report = json.loads(path.read_text())
    reference = json.loads((HERE / "runs" / "n53_perf_prefix.json").read_text())
    assert report["source_sha256"] == sha(HERE / source_name)
    assert report["curve_id"] == reference["curve_id"]
    assert report["candidate_id"] is None and report["isogeny"] == "none"
    assert report["workload_id"] == hashlib.sha256(frozen(report["workload"])).hexdigest()[:12]
    assert report["run_id"] == f"{proposal_id}W{report['workload_id']}R1"
    curve = curves.Curve(field.Onb(53))
    order = int(report["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(report["target"])
    lam = int(report["frobenius_eigenvalue_mod_r"])
    labels, representatives, digests = enumerate_points(
        curve, curve.f, [generator, target], window, lam, order)
    assert len(labels) == 4 * 53 * window and len(representatives) == 2 * window
    for name, value in digests.items():
        assert report["factor_base"][name] == value
    assert report["total_pair_complement_probes"] == sum(row["ordinary_query"][
        "lookups_including_failed"] for row in report["query_rows"])
    for row in report["query_rows"]:
        alpha = row["known_scalar_alpha"]
        query_target = tuple(row["query_target"])
        assert curve.mul(generator, alpha) == query_target
        relation = row["relation"]
        if relation is None:
            assert row["ordinary_query"]["status"] == "complete_index_miss"
            assert row["ordinary_query"]["lookups_including_failed"] == (
                report["index_build"]["quotient_keys"] * 106)
            continue
        vector = [0, 0]
        total = None
        for point_json in relation["point_witness"]:
            point = tuple(point_json)
            total = curve.add(total, point)
            seed, coefficient = labels[point]
            vector[seed] = (vector[seed] + coefficient) % order
        assert total == query_target
        assert vector == relation["coefficient_vector_mod_r"]
        if vector[1]:
            scalar = (alpha - vector[0]) * pow(vector[1], -1, order) % order
            assert scalar == relation["recovered_scalar"]
            assert curve.mul(generator, scalar) == target
            assert scalar == reference["target_fixture_scalar"]
    if report["verified_single_target_dlp"]:
        assert report["status"] == "verified_dlp"
        assert curve.mul(generator, report["recovered_scalar"]) == target
        assert report["online_wall_seconds"] is not None
    return report["status"]


def verify_promoted_candidate(window):
    source_name = ("n53_dyadic_target_seed_dlp.json" if window == 16 else
                   "n53_dyadic_target_seed_dlp_w64.json")
    raw_path = HERE / "runs" / source_name
    raw = json.loads(raw_path.read_text())
    run_path = HERE / "runs" / f"n53_dyadic_candidate_w{window}.json"
    run = json.loads(run_path.read_text())
    candidate_id = run["candidate_id"]
    manifest_path = HERE / "candidates" / f"{candidate_id}.json"
    manifest = json.loads(manifest_path.read_text())
    record = manifest["identity_record"]
    assert candidate_id == manifest["candidate_id"]
    digest = hashlib.sha256(frozen(record)).hexdigest()[:12]
    assert candidate_id.endswith("h" + digest)
    assert candidate_id.startswith(f"IC1N53Ckb1fb{4*53*window}PDP4qpairRCsampleLAgaussTDdirectISO0h")
    curve = dict(record["curve"])
    curve_id = curve.pop("curve_id")
    assert hashlib.sha256(frozen({"field": record["field"],
                                  "curve": curve})).hexdigest()[:12] == curve_id.rsplit("h", 1)[1]
    assert curve_id == raw["curve_id"] == run["curve_id"]
    assert record["isogeny"] == "none"
    assert record["endomorphism"]["order_conductor"] is None
    base = record["factor_base"]
    assert base["actual_usable_point_count_B"] == raw["factor_base"][
        "actual_usable_points_B_before_folding"]
    assert base["signed_frobenius_columns"] == raw["factor_base"][
        "signed_frobenius_columns"]
    assert base["enumerated_set_sha256"] == raw["factor_base"][
        "enumerated_set_sha256"]
    assert manifest["source_receipt_sha256"] == run["source_receipt_sha256"] == sha(raw_path)
    assert run["manifest_sha256"] == sha(manifest_path)
    assert run["workload_id"] == raw["workload_id"]
    assert run["run_id"] == f"{candidate_id}W{raw['workload_id']}R1"
    assert run["verified_scalar"] == raw["recovered_scalar"]
    assert run["formal_online_wall_seconds"] is None
    assert run["total_calibrated_field_operations"] is None
    return candidate_id


def verify_n83_perf():
    path = HERE / "runs" / "n83_dyadic_target_perf_L32.json"
    report = json.loads(path.read_text())
    reference = json.loads((HERE / "runs" / "n83_perf_prefix.json").read_text())
    assert report["source_sha256"] == sha(HERE / "dyadic_n83_target_perf.py")
    assert report["curve_id"] == reference["curve_id"]
    assert report["curve_identity_record"] == reference["curve_identity_record"]
    assert report["candidate_id"] is None and report["isogeny"] == "none"
    assert report["workload_id"] == hashlib.sha256(frozen(report["workload"])).hexdigest()[:12]
    assert report["run_id"] == f"Q1022W{report['workload_id']}R1"
    curve = curves.Curve(field.Onb(83))
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(report["target_seed"])
    assert target == tuple(reference["workload"]["target"])
    assert curve.mul(target, order) is None
    assert curve.mul(generator, report["workload"]["known_log_query_scalar"]) is not None
    lam = int(report["frobenius_eigenvalue_mod_r"])
    labels, representatives, digests = enumerate_points(
        curve, curve.f, [generator, target], 32, lam, order)
    base = report["factor_base"]
    assert len(labels) == base["actual_usable_points_B_before_folding"] == 10624
    assert len(representatives) == base["signed_frobenius_columns"] == 64
    assert base["effective_unknown_log_columns_after_dyadic_labels"] == 1
    for name, value in digests.items():
        assert base[name] == value
    index = report["index_build"]
    assert index["pair_generators"] == 2 * 169984
    assert index["quotient_keys"] == 169984
    assert len(report["ordinary_query_prefixes"]) == 3
    for row in report["ordinary_query_prefixes"]:
        assert row["lookups"] == 166 * 64
        assert row["verified_hit_positions"] == []
        assert row["batches"] == 64
    assert report["planted_positive_control"]["verified_hit_positions"] == [1]
    assert report["verified_single_target_dlp"] is False
    return {"B": len(labels), "keys": index["quotient_keys"],
            "median_prefix_ms": report["ordinary_query_prefix_median_wall_ns"] / 1e6}


def verify_n83_compact():
    baseline_path = HERE / "runs" / "n83_dyadic_target_perf_L32.json"
    baseline = json.loads(baseline_path.read_text())
    reports = {}
    for mode, run_number in (("packed", 1), ("compare", 2)):
        path = HERE / "runs" / f"n83_dyadic_compact_{mode}.json"
        report = json.loads(path.read_text())
        assert report["source_sha256"] == sha(HERE / "dyadic_n83_compact_index.py")
        assert report["baseline_receipt_sha256"] == sha(baseline_path)
        assert report["curve_id"] == baseline["curve_id"]
        assert report["candidate_id"] is None and report["isogeny"] == "none"
        assert report["workload_id"] == hashlib.sha256(frozen(report["workload"])).hexdigest()[:12]
        assert report["run_id"] == f"Q1023W{report['workload_id']}R{run_number}"
        assert report["factor_base"]["enumerated_set_sha256"] == baseline[
            "factor_base"]["enumerated_set_sha256"]
        build = report["packed_build"]
        assert build["pair_generators"] == 169984
        assert build["quotient_keys"] == baseline["index_build"]["quotient_keys"]
        assert build["row_bytes"] == 24
        assert build["retained_array_bytes"] == 24 * build["quotient_keys"]
        assert len(report["ordinary_query_prefixes"]) == 3
        assert all(row["lookups"] == 166 * 64 and
                   row["verified_hit_positions"] == [] for row in report[
                       "ordinary_query_prefixes"])
        assert report["planted_positive_control"]["verified_hit_positions"] == [1]
        assert report["verified_single_target_dlp"] is False
        reports[mode] = report
    assert reports["packed"]["packed_build"]["retained_array_sha256"] == reports[
        "compare"]["packed_build"]["retained_array_sha256"]
    control = reports["compare"]["dictionary_comparison"]
    assert control["full_dict_key_sha256"] == reports["packed"]["packed_build"][
        "key_sha256"]
    assert control["full_dict_index_sha256"] == control[
        "baseline_dict_index_sha256"] == baseline["index_build"]["index_sha256"]
    assert control["sampled_witness_replays"] == 1001
    return {"retained_bytes": reports["packed"]["packed_build"][
        "retained_array_bytes"],
            "packed_peak_rss_bytes": reports["packed"]["peak_process_rss_bytes"]}


def verify_five_sum_witness(witness, labels, curve, generator, target, order,
                            alpha_g, relation, scalar_expected=None):
    points = [tuple(point) for point in witness]
    assert len(points) == 5 and all(point in labels for point in points)
    assert [labels[point][0] for point in points] == [0, 0, 1, 1, 1]
    total = None
    for point in points:
        total = curve.add(total, point)
    assert total == alpha_g
    a = sum(labels[point][1] for point in points[:2]) % order
    b = sum(labels[point][1] for point in points[2:]) % order
    assert a == relation["known_G_coefficient_mod_r"]
    assert b == relation["target_Q_coefficient_mod_r"]
    assert curve.add(curve.mul(generator, a), curve.mul(target, b)) == alpha_g
    if scalar_expected is not None:
        assert b != 0
        assert (relation["known_query_scalar_alpha"] - a) * pow(
            b, -1, order) % order == scalar_expected
        assert curve.mul(generator, scalar_expected) == target


def verify_five_sum_n53():
    path = HERE / "runs" / "n53_dyadic_five_sum_dlp.json"
    report = json.loads(path.read_text())
    reference = json.loads((HERE / "runs" / "n53_perf_prefix.json").read_text())
    assert report["source_sha256"] == sha(HERE / "dyadic_n53_five_sum_dlp.py")
    assert report["reference_sha256"] == sha(HERE / "runs" / "n53_perf_prefix.json")
    for name, digest in report["dependency_sha256"].items():
        assert digest == sha(HERE / name)
    assert report["curve_id"] == reference["curve_id"]
    assert report["curve_identity_record"] == reference["curve_identity_record"]
    assert report["candidate_id"] is None and report["isogeny"] == "none"
    assert report["workload_id"] == hashlib.sha256(frozen(report["workload"])).hexdigest()[:12]
    assert report["run_id"] == f"Q1024W{report['workload_id']}R1"
    curve = curves.Curve(field.Onb(53))
    order = int(report["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(report["target"])
    lam = int(report["frobenius_eigenvalue_mod_r"])
    assert pow(lam, 53, order) == 1
    assert all(pow(lam, j, order) not in (1, order - 1) for j in range(1, 53))
    labels, representatives, digests = enumerate_points(
        curve, curve.f, [generator, target], 64, lam, order)
    base = report["factor_base"]
    assert len(labels) == base["actual_usable_points_B_before_folding"] == 13568
    assert len(representatives) == base["signed_frobenius_columns"] == 128
    assert base["effective_unknown_log_columns_after_dyadic_labels"] == 1
    for name, value in digests.items():
        assert base[name] == value
    g_base = [point for point in sorted(labels) if labels[point][0] == 0]
    g_reps = [point for point in sorted(representatives) if labels[point][0] == 0]
    index, build = build_g_pair_index(curve, g_base, g_reps, XOnlyCycle(curve.f))
    assert build["index_sha256"] == report["index_build"]["index_sha256"]
    assert len(index) == report["index_build"]["quotient_keys"]
    assert report["query"]["triple_attempts_including_failed"] == 121430
    assert report["query"]["quotient_hits"] == 1
    assert report["query"]["verified_group_relations"] == 1
    assert report["verified_single_target_dlp"]
    assert report["recovered_scalar"] == reference["target_fixture_scalar"]
    relation = report["relation"]
    alpha_g = curve.mul(generator, relation["known_query_scalar_alpha"])
    verify_five_sum_witness(relation["point_witness"], labels, curve,
                            generator, target, order, alpha_g, relation,
                            report["recovered_scalar"])
    return {"B": len(labels), "index_keys": len(index),
            "triple_attempts": report["query"]["triple_attempts_including_failed"],
            "verified_scalar": report["recovered_scalar"]}


def verify_five_sum_n83():
    path = HERE / "runs" / "n83_dyadic_five_sum_stage.json"
    report = json.loads(path.read_text())
    reference = json.loads((HERE / "runs" / "n83_perf_prefix.json").read_text())
    assert report["source_sha256"] == sha(HERE / "dyadic_n83_five_sum_stage.py")
    for name, digest in report["dependency_sha256"].items():
        assert digest == sha(HERE / name)
    assert report["reference_sha256"] == sha(HERE / "runs" / "n83_perf_prefix.json")
    assert report["curve_id"] == reference["curve_id"]
    assert report["curve_identity_record"] == reference["curve_identity_record"]
    assert report["candidate_id"] is None and report["isogeny"] == "none"
    assert report["workload_id"] == hashlib.sha256(frozen(report["workload"])).hexdigest()[:12]
    assert report["run_id"] == f"Q1025W{report['workload_id']}R1"
    curve = curves.Curve(field.Onb(83))
    order = int(report["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(report["target_seed"])
    lam = int(report["frobenius_eigenvalue_mod_r"])
    assert pow(lam, 83, order) == 1
    assert all(pow(lam, j, order) not in (1, order - 1) for j in range(1, 83))
    labels, representatives, digests = enumerate_points(
        curve, curve.f, [generator, target], 32, lam, order)
    base = report["factor_base"]
    assert len(labels) == base["actual_usable_points_B_before_folding"] == 10624
    assert len(representatives) == base["signed_frobenius_columns"] == 64
    assert base["effective_unknown_log_columns_after_dyadic_labels"] == 1
    for name, value in digests.items():
        assert base[name] == value
    g_base = [point for point in sorted(labels) if labels[point][0] == 0]
    g_reps = [point for point in sorted(representatives) if labels[point][0] == 0]
    index, build = build_g_pair_index(curve, g_base, g_reps, XOnlyCycle(curve.f))
    assert build["index_sha256"] == report["index_build"]["index_sha256"]
    assert len(index) == report["index_build"]["quotient_keys"] == 80868
    scalar_twos, scalar_buckets = coefficients_by_window(order, lam, 32)
    scalar_keys, _, _, _ = quotient_keys(order, scalar_twos, scalar_buckets)
    point_index_scalar_keys = {
        pow((labels[pair[0]][1] + labels[pair[1]][1]) % order, 166, order)
        for _, pair in index.values()}
    assert scalar_keys == point_index_scalar_keys
    assert -1 in index
    assert report["exact_two_G_pair_sum_support"] == 1 + (len(index) - 1) * 166
    assert sum(block["attempts_including_failed"] for block in report[
        "ordinary_blocks"]) == 12288
    assert all(block["quotient_hits"] == 0 and not block[
        "verified_relations"] for block in report["ordinary_blocks"])
    assert report["verified_single_target_dlp"] is False
    planted = report["planted_positive_control"]
    total = None
    for point in planted["point_witness"]:
        total = curve.add(total, tuple(point))
    verify_five_sum_witness(planted["point_witness"], labels, curve,
                            generator, target, order, total, planted)
    projection_path = HERE / "dyadic_five_sum_n83_projection.json"
    projection = json.loads(projection_path.read_text())
    assert projection["source_sha256"] == sha(HERE / "dyadic_five_sum_n83_projection.py")
    assert projection["stage_receipt_sha256"] == sha(path)
    support_path = HERE / "runs" / "n83_dyadic_G_pair_scalar_support_L1000.json"
    support = json.loads(support_path.read_text())
    assert support["source_sha256"] == sha(HERE / "dyadic_n83_g_pair_scalar_support.py")
    assert support["geometry_receipt_sha256"] == sha(
        HERE / "runs" / "n83_dyadic_target_seed_geometry.json")
    assert support["stage_control_receipt_sha256"] == sha(path)
    assert support["curve_id"] == report["curve_id"]
    assert support["curve_identity_record"] == report["curve_identity_record"]
    assert support["candidate_id"] is None and support["isogeny"] == "none"
    assert support["factor_base"]["actual_usable_points_B_before_folding"] == 332000
    assert support["factor_base"]["signed_frobenius_columns"] == 2000
    assert support["workload_id"] == hashlib.sha256(frozen(support["workload"])).hexdigest()[:12]
    assert support["run_id"] == f"Q1026W{support['workload_id']}R1"
    assert support["L32_independent_curve_point_key_control"]["quotient_keys"] == len(scalar_keys)
    assert support["L1000_unordered_pair_orbit_generators"] == 83 * 1000 * 1001
    assert support["L1000_exact_quotient_keys"] == 82843900
    assert support["L1000_exact_distinct_G_pair_sums"] == (
        1 + (support["L1000_exact_quotient_keys"] - 1) * 166)
    assert len(support["L1000_prefix_checkpoints"]) == 10
    assert support["L1000_prefix_checkpoints"][-1]["quotient_keys"] == 82843900
    assert projection["exact_support_receipt_sha256"] == sha(support_path)
    assert projection["L1000_exact_G_pair_sum_support"] == support[
        "L1000_exact_distinct_G_pair_sums"]
    assert projection["L32_exact_two_G_pair_sum_support"] == report[
        "exact_two_G_pair_sum_support"]
    assert projection["L1000_unordered_pair_sum_support_cap"] == 166000 * 166001 // 2
    return {"B": len(labels), "index_keys": len(index),
            "ordinary_triple_attempts": 12288, "ordinary_hits": 0}


def verify_five_sum_candidate():
    receipt_path = HERE / "runs" / "n53_dyadic_five_sum_dlp.json"
    receipt = json.loads(receipt_path.read_text())
    run_path = HERE / "runs" / "n53_dyadic_five_sum_candidate.json"
    run = json.loads(run_path.read_text())
    candidate_id = run["candidate_id"]
    manifest_path = HERE / "candidates" / f"{candidate_id}.json"
    manifest = json.loads(manifest_path.read_text())
    record = manifest["identity_record"]
    assert manifest["candidate_id"] == candidate_id
    assert candidate_id.startswith(
        "IC1N53Ckb1fb13568PDP5q23RCsampleLAgaussTDdirectISO0h")
    assert candidate_id.endswith("h" + hashlib.sha256(frozen(record)).hexdigest()[:12])
    curve = dict(record["curve"])
    curve_id = curve.pop("curve_id")
    assert curve_id == receipt["curve_id"]
    assert hashlib.sha256(frozen({"field": record["field"],
                                  "curve": curve})).hexdigest()[:12] == curve_id.rsplit("h", 1)[1]
    assert record["isogeny"] == "none"
    assert record["endomorphism"]["order_conductor"] is None
    assert record["factor_base"]["actual_usable_point_count_B"] == 13568
    assert record["factor_base"]["enumerated_set_sha256"] == receipt[
        "factor_base"]["enumerated_set_sha256"]
    assert record["point_decomposition"]["m"] == 5
    assert record["point_decomposition"]["solver_family"] == (
        "two_plus_three_quotient_pair_index")
    for name, digest in record["implementation"][
            "source_sha256_by_component"].items():
        assert sha(HERE / name) == digest
    assert manifest["source_receipt_sha256"] == run[
        "source_receipt_sha256"] == sha(receipt_path)
    assert run["manifest_sha256"] == sha(manifest_path)
    assert run["run_id"] == f"{candidate_id}W{receipt['workload_id']}R1"
    assert run["verified_scalar"] == receipt["recovered_scalar"]
    assert run["total_calibrated_field_operations"] is None
    assert run["complete_work_log2"] is None
    return candidate_id


def verify_n83_five_sum_packed():
    path = HERE / "runs" / "n83_dyadic_five_sum_packed_stage.json"
    report = json.loads(path.read_text())
    baseline_path = HERE / "runs" / "n83_dyadic_five_sum_stage.json"
    baseline = json.loads(baseline_path.read_text())
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    assert report["source_sha256"] == sha(HERE / "dyadic_n83_five_sum_packed_stage.py")
    assert report["baseline_sha256"] == sha(baseline_path)
    assert report["reference_sha256"] == sha(reference_path)
    for name, digest in report["dependency_sha256"].items():
        assert digest == sha(HERE / name)
    assert report["candidate_id"] is None and report["isogeny"] == "none"
    assert report["curve_id"] == baseline["curve_id"] == reference["curve_id"]
    assert report["curve_identity_record"] == reference["curve_identity_record"]
    assert report["factor_base"] == baseline["factor_base"]
    assert report["workload_id"] == hashlib.sha256(frozen(report["workload"])).hexdigest()[:12]
    assert report["run_id"] == f"Q1027W{report['workload_id']}R1"
    curve = curves.Curve(field.Onb(83))
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    lam = int(baseline["frobenius_eigenvalue_mod_r"])
    labels, representatives, digests = enumerate_points(
        curve, curve.f, [generator, target], 32, lam, order)
    assert report["factor_base"]["enumerated_set_sha256"] == digests[
        "enumerated_set_sha256"]
    g_base = [point for point in sorted(labels) if labels[point][0] == 0]
    g_reps = [point for point in sorted(representatives) if labels[point][0] == 0]
    packed, build = build_packed(curve, g_reps, g_base, XOnlyCycle(curve.f))
    receipt_build = report["packed_build"]
    assert len(packed) == receipt_build["quotient_keys"] == 80868
    assert build["retained_array_sha256"] == receipt_build[
        "retained_array_sha256"]
    assert build["key_sha256"] == receipt_build["key_sha256"] == report[
        "full_key_set_sha256"]
    assert receipt_build["row_bytes"] == 24
    assert receipt_build["retained_array_bytes"] == 24 * 80868
    assert report["dictionary_build"]["index_sha256"] == baseline[
        "index_build"]["index_sha256"]
    assert report["sampled_witness_replays"] == 1001
    assert len(report["paired_blocks"]) == 3
    for row in report["paired_blocks"]:
        assert set(row["execution_order"]) == {
            "dictionary", "packed_binary", "packed_vectorized"}
        for variant in ("dictionary", "packed_binary", "packed_vectorized"):
            assert row[variant]["attempts_including_failed"] == 4096
            assert row[variant]["quotient_hits"] == 0
            assert row[variant]["verified_relations"] == []
        assert row["dictionary_wall_over_packed_binary_wall"] > 0
        assert row["dictionary_wall_over_packed_vectorized_wall"] > 0
    witness = report["planted_positive_control"]
    assert len({point[0] for point in witness["point_witness"][2:]}) == 3
    total = None
    for raw in witness["point_witness"]:
        total = curve.add(total, tuple(raw))
    verify_five_sum_witness(witness["point_witness"], labels, curve,
                            generator, target, order, total, witness)
    planted_query = report["planted_vectorized_query_control"]
    assert planted_query["verified_relations"][0] == {
        "attempt": 1, "relation": witness}
    assert report["ordinary_quotient_hits"] == 0
    assert report["verified_single_target_dlp"] is False
    return {"keys": len(packed),
            "retained_bytes": receipt_build["retained_array_bytes"],
            "packed_only_peak_rss_bytes": report[
                "packed_only_peak_rss_bytes_before_dictionary_build"],
            "median_dictionary_wall_over_packed_binary_wall": report[
                "median_dictionary_wall_over_packed_binary_wall"],
            "median_dictionary_wall_over_packed_vectorized_wall": report[
                "median_dictionary_wall_over_packed_vectorized_wall"]}


def verify_n83_five_sum_symmetric():
    path = HERE / "runs" / "n83_dyadic_five_sum_symmetric_stage.json"
    report = json.loads(path.read_text())
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    baseline_path = HERE / "runs" / "n83_dyadic_five_sum_stage.json"
    packed_path = HERE / "runs" / "n83_dyadic_five_sum_packed_stage.json"
    reference = json.loads(reference_path.read_text())
    baseline = json.loads(baseline_path.read_text())
    packed = json.loads(packed_path.read_text())
    assert report["source_sha256"] == sha(HERE / "dyadic_n83_five_sum_symmetric_stage.py")
    assert report["reference_sha256"] == sha(reference_path)
    assert report["baseline_sha256"] == sha(baseline_path)
    assert report["packed_receipt_sha256"] == sha(packed_path)
    for name, digest in report["dependency_sha256"].items():
        assert digest == sha(HERE / name)
    assert report["candidate_id"] is None and report["isogeny"] == "none"
    assert report["curve_id"] == packed["curve_id"] == baseline["curve_id"]
    assert report["factor_base"] == packed["factor_base"]
    assert report["workload_id"] == hashlib.sha256(frozen(report["workload"])).hexdigest()[:12]
    assert report["run_id"] == f"Q1028W{report['workload_id']}R1"
    curve = curves.Curve(field.Onb(83))
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    labels, representatives, digests = enumerate_points(
        curve, curve.f, [generator, target], 32,
        int(baseline["frobenius_eigenvalue_mod_r"]),
        int(reference["subgroup_order"]))
    assert digests["enumerated_set_sha256"] == report["factor_base"][
        "enumerated_set_sha256"]
    g_base = [point for point in sorted(labels) if labels[point][0] == 0]
    g_reps = [point for point in sorted(representatives) if labels[point][0] == 0]
    canonicalize = XOnlyCycle(curve.f)
    index, build = build_symmetric(curve, g_reps, g_base, canonicalize)
    receipt_build = report["build"]
    assert receipt_build["pair_generators"] == build["pair_generators"] == 87648
    assert receipt_build["pair_generators"] < report[
        "reference_full_pair_generators"] == 169984
    assert len(index) == receipt_build["quotient_keys"] == 80868
    assert build["retained_array_sha256"] == receipt_build[
        "retained_array_sha256"]
    assert build["key_sha256"] == receipt_build["key_sha256"] == report[
        "reference_full_key_sha256"] == packed["full_key_set_sha256"]
    assert receipt_build["row_bytes"] == 24
    assert receipt_build["retained_array_bytes"] == 24 * len(index)
    assert report["sampled_witness_replays"] == 1001
    witness_keys = [next(index.keys()), *random.Random(202609300836).sample(
        list(index.keys()), 1000)]
    for key in witness_keys:
        representative, pair = index.get(key)
        assert curve.add(*pair) == representative
        assert canonicalize.key_and_shift(curve, representative) == (key, 0)
    assert index.get(report["planted_G_pair_key"]) is not None
    assert report["verified_single_target_dlp"] is False
    assert report["complete_work_log2"] is None
    return {"pair_generators": receipt_build["pair_generators"],
            "keys": len(index),
            "build_seconds": receipt_build[
                "build_seconds_including_orbit_partition"]}


def main():
    geometry = {}
    for n in (53, 83):
        report, seeds, curve = verify_geometry(n)
        geometry[n] = {"report": report, "seeds": seeds, "curve": curve}
        verify_two_seed_geometry(n)
    target_geometry = verify_n83_target_geometry()
    projection_path = HERE / "dyadic_n83_work_projection.json"
    projection = json.loads(projection_path.read_text())
    assert projection["source_sha256"] == sha(HERE / "dyadic_n83_work_projection.py")
    assert projection["geometry_receipt_sha256"] == sha(HERE / "runs" /
                                                        "n83_dyadic_base_geometry.json")
    assert projection["curve_id"] == geometry[83]["report"]["curve_id"]
    two_seed_projection = json.loads((HERE / "dyadic_two_seed_n83_projection.json").read_text())
    assert two_seed_projection["source_sha256"] == sha(HERE / "dyadic_two_seed_n83_projection.py")
    assert two_seed_projection["geometry_receipt_sha256"] == sha(
        HERE / "runs" / "n83_dyadic_target_seed_geometry.json")
    assert two_seed_projection["curve_id"] == target_geometry["curve_id"]
    assert two_seed_projection["L32_packed_receipt_sha256"] == sha(
        HERE / "runs" / "n83_dyadic_compact_packed.json")
    support_path = HERE / "dyadic_coefficient_support.json"
    support = json.loads(support_path.read_text())
    assert support["source_sha256"] == sha(HERE / "dyadic_coefficient_support.py")
    assert two_seed_projection["coefficient_support_receipt_sha256"] == sha(support_path)
    for row in support["rows"]:
        n, length = row["degree"], row["doubling_window"]
        assert row["coefficient_set_cardinality"] == 2 * n * length
        assert row["cross_seed_pair_count"] == (2 * n * length)**2
        if row["two_coefficient_sum_count_exact"] is not None:
            assert row["two_coefficient_sum_count_exact"] <= row[
                "two_coefficient_sum_count_upper"]
        if n == 83 and length == 1000:
            support_path = HERE / "runs" / "n83_dyadic_G_pair_scalar_support_L1000.json"
            exact_support = json.loads(support_path.read_text())
            assert row["external_exact_support_receipt_sha256"] == sha(support_path)
            assert row["two_coefficient_sum_count_exact"] == exact_support[
                "L1000_exact_distinct_G_pair_sums"]
        assert math.isclose(row["uniform_known_log_query_hit_probability_upper"],
                            min(1, int(row["query_scalar_support_count_upper"]) /
                                (int(geometry[n]["report"]["subgroup_order"]) - 1)),
                            abs_tol=1e-12)
    single_path = HERE / "runs" / "n53_dyadic_ordinary_relation.json"
    if single_path.exists():
        single = json.loads(single_path.read_text())
        assert single["source_sha256"] == sha(HERE / "dyadic_n53_relation_probe.py")
        single_status = verify_n53_relation(
            single, geometry[53]["seeds"], geometry[53]["curve"])
    else:
        single_status = "not_run"
    panel_status = verify_panel(geometry[53]["seeds"], geometry[53]["curve"])
    target_dlp_status = verify_n53_target_seed_dlp(
        "n53_dyadic_target_seed_dlp.json", "dyadic_n53_target_seed_dlp.py",
        16, "Q1019")
    wide_dlp_status = verify_n53_target_seed_dlp(
        "n53_dyadic_target_seed_dlp_w64.json", "dyadic_n53_target_seed_dlp_w64.py",
        64, "Q1021")
    candidate_ids = [verify_promoted_candidate(window) for window in (16, 64)]
    n83_perf = verify_n83_perf()
    compact = verify_n83_compact()
    five_sum_n53 = verify_five_sum_n53()
    five_sum_n83 = verify_five_sum_n83()
    five_sum_candidate = verify_five_sum_candidate()
    five_sum_packed = verify_n83_five_sum_packed()
    five_sum_symmetric = verify_n83_five_sum_symmetric()
    print(json.dumps({"n53_curve_id": geometry[53]["report"]["curve_id"],
                      "n83_curve_id": geometry[83]["report"]["curve_id"],
                      "n83_actual_B": geometry[83]["report"]["factor_base"][
                          "actual_usable_points_B_before_folding"],
                      "n83_target_seed_B": target_geometry["factor_base"][
                          "actual_usable_points_B_before_folding"],
                      "n53_single_target_status": single_status,
                      "n53_panel_status": panel_status,
                      "n53_target_seed_dlp_status": target_dlp_status,
                      "n53_wide_target_seed_dlp_status": wide_dlp_status,
                      "n53_candidate_ids": candidate_ids,
                      "n83_L32_perf": n83_perf,
                      "n83_L32_compact": compact,
                      "n53_five_sum": five_sum_n53,
                      "n83_five_sum": five_sum_n83,
                      "n53_five_sum_candidate_id": five_sum_candidate,
                      "n83_five_sum_packed": five_sum_packed,
                      "n83_five_sum_symmetric": five_sum_symmetric}))


if __name__ == "__main__":
    main()
