#!/usr/bin/env python3
"""Reconcile Q1062 full and segmented receipts on an M28-by-R27 grid."""

import json
import math
from pathlib import Path

import n83_full_spill_work as work
import n83_m32_ci_ingest as m32_portable
import n83_m32_group_ci_ingest as m32_group
import n83_m32_wave_ci_ingest as m32_wave
import n83_m32_wave_q1075_ci_ingest as m32_wave_q1075
import n83_portable_ci_ingest as portable
from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_receipt, validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
REPO = HERE.parents[1]
OUTPUT = HERE / "n83_full_spill_segment_work.json"
M28 = 1 << 28
M31 = 1 << 31
M32 = 1 << 32
R27 = 1 << 27
R30 = 1 << 30
SEGMENTS_PER_RANGE = R30 // R27
QUANTILES = ("0.5", "0.8", "0.9", "0.95")


def repo_path(path):
    return str(path.resolve().relative_to(REPO))


def failed_record(path, row):
    guard_path = path.with_suffix(".guard.json")
    guard = json.loads(guard_path.read_text()) if guard_path.exists() else None
    if guard:
        assert guard["terminal_receipt_sha256"] == work.sha(path)
        assert guard["query_start"] == row["query_start"]
        assert guard["curve_id"] == row["curve_id"]
    return {
        "path": repo_path(path), "sha256": work.sha(path),
        "query_start": row["query_start"],
        "query_representatives": row["query_representatives"],
        "native_subprocess_wall_seconds": row.get(
            "native_subprocess_wall_seconds"),
        "native_child_cpu_total_seconds": row.get(
            "native_child_cpu_total_seconds"),
        "native_phase_counts": None,
        "resource_guard_reason": guard["reason"] if guard else None,
        "resource_guard_receipt_sha256": work.sha(guard_path)
        if guard else None,
    }


def compressed_starts(starts):
    spans = []
    for value in starts:
        if spans and value == spans[-1]["last_query_start"] + R27:
            spans[-1]["last_query_start"] = value
            spans[-1]["count"] += 1
        else:
            spans.append({"first_query_start": value,
                          "last_query_start": value,
                          "count": 1, "stride": R27})
    return spans


def query_segments(query_start, query_reps):
    range_index, remainder = divmod(query_start, R30)
    assert 1 <= range_index < 118
    assert query_reps in (R27, 1 << 28, 1 << 29, R30)
    assert remainder % R27 == 0
    first = remainder // R27
    count = query_reps // R27
    assert first + count <= SEGMENTS_PER_RANGE
    return range_index, range(first, first + count)


def grouped_future_plan(future):
    remaining = set(future)
    groups = []
    for range_index, segment in future:
        if (range_index, segment) not in remaining:
            continue
        count = 4 if (segment + 4 <= SEGMENTS_PER_RANGE and all(
            (range_index, segment + offset) in remaining
            for offset in range(4))) else 1
        for offset in range(count):
            remaining.remove((range_index, segment + offset))
        groups.append((range_index, segment, count))
    assert not remaining
    return groups


def portable_ci_rows(screen):
    completed, failed, incomplete = [], [], []
    for bundle_path in sorted(RUNS.glob(
            "n83_portable_q1061_M31_R*_ci_*/bundle.json")):
        bundle = json.loads(bundle_path.read_text())
        assert bundle["kind"] == (
            "n83_portable_q1061_physical_x86_segment_ci_bundle")
        assert bundle["proposal_id"] == "Q1061"
        assert bundle["curve_id"] == screen["curve_id"]
        assert bundle["factor_base_enumerated_set_sha256"] == screen[
            "factor_base"]["enumerated_set_sha256"]
        query_reps = bundle["query_representatives"]
        assert query_reps in (R27, 1 << 29)
        assert f"_R{int(math.log2(query_reps))}_ci_" in str(bundle_path)
        assert bundle["portable_native_source_sha256"] == work.sha(
            portable.SOURCE)
        for name, digest in bundle["artifact_sha256"].items():
            assert work.sha(bundle_path.parent / name) == digest
        full_path = bundle_path.parent / "full.json"
        if not full_path.exists():
            incomplete.append({"bundle": repo_path(bundle_path),
                               "sha256": work.sha(bundle_path),
                               "status": bundle["status"]})
            continue
        row = json.loads(full_path.read_text())
        validate_receipt(screen, row)
        assert row["proposal_id"] == "Q1061"
        assert row["query_start"] == bundle["query_start"]
        assert row["table_start"] == 0
        assert row["table_descriptors"] == M31
        assert row["query_representatives"] == query_reps
        query_segments(row["query_start"], query_reps)
        if row["kind"] == work.FAILED_KIND:
            assert bundle["status"] == "failed_full_segment_unknown_work"
            assert row["native_phase_counts"] is None
            failed.append((full_path, row))
        else:
            assert row["kind"] == work.SUCCESS_KIND
            portable.verified_row(screen, full_path, full=True,
                                  full_query_reps=query_reps)
            completed.append((full_path, row))
    return completed, failed, incomplete


def m32_ci_rows(screen):
    completed, failed, noncompleted = [], [], []
    proposal_by_path = {}
    specs = (
        ("n83_portable_q1065_M32_R28_ci_*/bundle.json",
         "n83_q1065_physical_x86_M32_R28_ci_bundle", "Q1065",
         1 << 28, 6 * R30, m32_portable),
        ("n83_portable_q1068_M32_R29_ci_*/bundle.json",
         "n83_q1068_physical_x86_M32_R29_ci_bundle", "Q1068",
         1 << 29, 6 * R30 + (1 << 28), m32_group),
        ("n83_portable_q1069_M32_R29_ci_*/bundle.json",
         "n83_q1069_physical_x86_M32_R29_ci_bundle", "Q1069",
         1 << 29, None, m32_wave),
        ("n83_portable_q1075_M32_R29_ci_*/bundle.json",
         "n83_q1075_physical_x86_M32_R29_ci_bundle", "Q1075",
         1 << 29, None, m32_wave_q1075),
    )
    for pattern, kind, proposal, query_reps, query_start, ingester in specs:
        for bundle_path in sorted(RUNS.glob(pattern)):
            bundle = json.loads(bundle_path.read_text())
            assert bundle["kind"] == kind
            assert bundle["proposal_id"] == proposal
            assert bundle["executable_proposal_id"] == "Q1061"
            assert bundle["candidate_id"] is None and bundle["run_id"] is None
            assert bundle["curve_id"] == screen["curve_id"]
            assert bundle["isogeny"] == "none"
            assert bundle["factor_base_enumerated_set_sha256"] == screen[
                "factor_base"]["enumerated_set_sha256"]
            assert bundle["actual_usable_points_B_before_folding"] == screen[
                "factor_base"]["actual_usable_points_B_before_folding"]
            assert bundle["signed_frobenius_columns"] == screen[
                "factor_base"]["signed_frobenius_columns"]
            assert bundle["table_descriptors"] == M32
            assert bundle["query_representatives"] == query_reps
            if query_start is None:
                plan = json.loads(ingester.PLAN.read_text())
                assert bundle["query_start"] in plan["query_starts"]
                assert str(bundle["query_start"]) in str(bundle_path)
            else:
                assert bundle["query_start"] == query_start
            assert bundle["portable_native_source_sha256"] == work.sha(
                ingester.SOURCE)
            assert bundle["source_sha256"] == work.sha(
                Path(ingester.__file__))
            assert bundle["plan_sha256"] == work.sha(ingester.PLAN)
            if proposal in ("Q1068", "Q1069", "Q1075"):
                plan = json.loads(ingester.PLAN.read_text())
                assert bundle["frozen_workflow_sha256"] == plan[
                    "workflow_sha256"]
            for name, digest in bundle["artifact_sha256"].items():
                assert work.sha(bundle_path.parent / name) == digest
            full_path = bundle_path.parent / "full.json"
            proposal_by_path[full_path] = proposal
            if not full_path.exists():
                noncompleted.append({"bundle": repo_path(bundle_path),
                                     "sha256": work.sha(bundle_path),
                                     "status": bundle["status"]})
                continue
            row = json.loads(full_path.read_text())
            validate_receipt(screen, row)
            assert row["proposal_id"] == "Q1061"
            assert row["table_start"] == 0
            assert row["table_descriptors"] == M32
            assert row["query_representatives"] == query_reps
            assert row["query_start"] == bundle["query_start"]
            query_segments(row["query_start"], row["query_representatives"])
            if row["kind"] == work.FAILED_KIND:
                assert bundle["status"] == "failed_full_segment_unknown_work"
                assert row["native_phase_counts"] is None
                failed.append((full_path, row))
            else:
                assert row["kind"] == work.SUCCESS_KIND
                if proposal in ("Q1069", "Q1075"):
                    ingester.verify_row(screen, full_path, full=True,
                                        query_start=bundle["query_start"])
                else:
                    ingester.verify_row(screen, full_path, full=True)
                assert bundle["status"] in (
                    "completed_zero_hit",
                    "native_verified_hit_needs_independent_sage",
                    "unverified_exact_hit_requires_review")
                completed.append((full_path, row))
    return completed, failed, noncompleted, proposal_by_path


def local_m32_rows(screen):
    """Credit Q1071 only from its terminal receipt on the frozen ARM range."""
    plan_path = HERE / "n83_local_arm_m32_q1071_plan.json"
    receipt_path = RUNS / "n83_local_arm_m32_q1071.json"
    runtime_path = RUNS / "n83_local_arm_m32_q1071_runtime_info.json"
    sage_path = RUNS / "n83_local_arm_m32_q1071_sage_verify.json"
    plan = json.loads(plan_path.read_text())
    assert plan["proposal_id"] == "Q1071"
    assert plan["curve_id"] == screen["curve_id"]
    assert plan["isogeny"] == "none"
    assert plan["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert plan["actual_usable_points_B_before_folding"] == screen[
        "factor_base"]["actual_usable_points_B_before_folding"]
    assert plan["signed_frobenius_columns"] == screen[
        "factor_base"]["signed_frobenius_columns"]
    assert plan["table_descriptors"] == M32
    assert plan["query_representatives"] == 1 << 29
    assert plan["query_end_exclusive"] == (plan["query_start"] +
                                           plan["query_representatives"])
    assert plan["query_start"] == 11 * R30
    if not receipt_path.exists():
        return [], [], {}, {}
    row = json.loads(receipt_path.read_text())
    validate_receipt(screen, row)
    assert row["proposal_id"] == "Q1061"
    assert row["table_start"] == plan["table_start"] == 0
    assert row["table_descriptors"] == M32
    assert row["query_start"] == plan["query_start"]
    assert row["query_representatives"] == plan["query_representatives"]
    assert row["cpu_backend"] == plan["cpu_backend"] == "arm_pmull"
    assert row["query_workers"] == plan["query_workers"]
    assert row["representative_batch"] == plan["representative_batch"]
    assert row["bits_per_key"] == plan["bits_per_key"]
    assert row["hashes"] == plan["hashes"]
    assert row["sage_runtime_info_sha256"] == work.sha(runtime_path)
    runtime = json.loads(runtime_path.read_text())
    assert runtime["status"] == "verified"
    for row_key, plan_key, path in (
            ("native_source_sha256", "portable_native_source_sha256",
             HERE / "native_n83_orbit_query_spill_portable.cpp"),
            ("bloom_core_sha256", "portable_core_source_sha256",
             HERE / "native_n83_bloom_core_portable.hpp"),
            ("native_pairs_sha256", "portable_pairs_source_sha256",
             HERE / "native_n83_pairs_portable.cpp"),
            ("wrapper_source_sha256", "portable_wrapper_source_sha256",
             HERE / "run_n83_portable_chunk.py"),
            ("generated_field_sha256", "generated_field_header_sha256",
             REPO / "ecc2k130/runner/generated/eccF83.h"),
            ("base_receipt_sha256", "base_receipt_sha256",
             RUNS / "n83_knownlog_orbit_base_k48194.json")):
        if row["kind"] != work.FAILED_KIND:
            assert row[row_key] == plan[plan_key]
        assert plan[plan_key] == work.sha(path)
    if row["kind"] == work.FAILED_KIND:
        assert row["native_phase_counts"] is None
        return [], [(receipt_path, row)], {}, {}
    assert row["kind"] == work.SUCCESS_KIND
    assert row["native_result"]["actual_B"] == plan[
        "actual_usable_points_B_before_folding"]
    assert row["native_result"]["exact_hit_queries"] >= len(
        row["verified_public_target_relations"])
    assert int(row["native_field_add_mul_sqr_call_model"]) == field_calls(
        M32, plan["query_representatives"])
    assert sage_path.exists(), "local M32 receipt needs independent Sage audit"
    sage = json.loads(sage_path.read_text())
    assert sage["receipt_sha256"] == work.sha(receipt_path)
    assert sage["curve_id"] == screen["curve_id"]
    assert sage["sage_runtime_info_sha256"] == work.sha(runtime_path)
    assert sage["verified_relation_count"] == len(
        row["verified_public_target_relations"])
    assert sage["natural_public_target_relation_verified"] == bool(
        row["verified_public_target_relations"])
    return [(receipt_path, row)], [], {receipt_path: "Q1071"}, {
        receipt_path: sage_path}


def main():
    base = json.loads(work.BASE.read_text())
    screen = json.loads(work.SCREEN.read_text())
    first = json.loads(work.FIRST.read_text())
    validate_reference(screen)
    validate_receipt(screen, first)
    assert first["proposal_id"] == "Q1051"
    assert first["native_result"]["exact_hit_queries"] == 0
    assert not first["verified_public_target_quotient_table_dlp"]
    q1060, failed_q1060 = work.load_terminal_rows(
        "n83_spill_lowmem_k48194_chunk_M28_R30_tstart*_qstart*_b20_h10_rb8*.json",
        "Q1060", screen)
    q1062_full, failed_full = work.load_terminal_rows(
        "n83_full_spill_k48194_chunk_M31_R30_tstart0_qstart*_b20_h10_rb8*.json",
        "Q1062", screen)
    q1062_seg, failed_seg = work.load_terminal_rows(
        "n83_full_spill_k48194_chunk_M31_R27_tstart0_qstart*_b20_h10_rb8*.json",
        "Q1062", screen)
    q1061_ci, failed_q1061_ci, incomplete_q1061_ci = portable_ci_rows(screen)
    m32_ci, failed_m32_ci, noncompleted_m32_ci, m32_proposals = m32_ci_rows(
        screen)
    local_m32, failed_local_m32, local_m32_proposals, local_sage_paths = (
        local_m32_rows(screen))
    m32_proposals.update(local_m32_proposals)
    m32_paths = {path for path, _ in m32_ci + local_m32}
    covered = {(0, segment, shard)
               for segment in range(SEGMENTS_PER_RANGE)
               for shard in range(8)}
    charged = int(first["native_field_add_mul_sqr_call_model"])
    measured_search = {
        "table_descriptors_processed": 0,
        "query_representatives_processed": 0,
        "lifted_query_pairs_tested": 0,
        "bloom_positive_queries_for_exact_replay": 0,
        "target_online_seconds_sum_across_hosts": 0.0,
    }

    def charge_measured_search(row):
        native = row["native_result"]
        measured_search["table_descriptors_processed"] += native[
            "table_descriptors"]
        measured_search["query_representatives_processed"] += native[
            "query_representatives"]
        measured_search["lifted_query_pairs_tested"] += native[
            "lifted_query_pairs"]
        measured_search["bloom_positive_queries_for_exact_replay"] += native[
            "bloom_positive_queries"]
        measured_search["target_online_seconds_sum_across_hosts"] += row[
            "target_online_seconds"]

    charge_measured_search(first)
    completed = [{"proposal_id": "Q1051", "path": repo_path(work.FIRST),
                  "sha256": work.sha(work.FIRST),
                  "field_calls": str(charged), "new_cells": 64}]
    complete_segments = set()
    extra_m32_covered = set()
    verified_dlp = []
    unverified_hits = []
    for path, row in sorted(q1060 + q1062_full + q1062_seg + q1061_ci +
                            m32_ci + local_m32,
                            key=lambda item: (item[1]["finished_at_utc"],
                                              str(item[0]))):
        qstart = row["query_start"]
        range_index, remainder = divmod(qstart, R30)
        assert 1 <= range_index < 118
        is_m32 = row["table_descriptors"] == M32
        novel_extra_m32 = 0
        if row["proposal_id"] == "Q1060":
            assert remainder == 0 and row["query_representatives"] == R30
            assert row["table_descriptors"] == M28
            shard = row["table_start"] // M28
            assert 0 <= shard < 8 and row["table_start"] == shard * M28
            cells = {(range_index, segment, shard)
                     for segment in range(SEGMENTS_PER_RANGE)}
        else:
            assert row["table_start"] == 0
            assert row["table_descriptors"] in (M31, M32)
            assert not is_m32 or path in m32_paths
            checked_range_index, segments = query_segments(
                qstart, row["query_representatives"])
            assert checked_range_index == range_index
            cells = {(range_index, segment, shard)
                     for segment in segments for shard in range(8)}
            if is_m32:
                extra_cells = {(range_index, segment, shard)
                               for segment in segments for shard in range(8, 16)}
                novel_extra_m32 = len(extra_cells - extra_m32_covered)
                extra_m32_covered.update(extra_cells)
            complete_segments.update((range_index, segment)
                                     for segment in segments)
        if row["verified_public_target_quotient_table_dlp"]:
            assert row["verified_public_target_relations"]
            if row["proposal_id"] == "Q1061":
                sage_path = local_sage_paths.get(
                    path, path.with_name("sage_verify.json"))
                if sage_path.exists():
                    sage = json.loads(sage_path.read_text())
                    assert sage["receipt_sha256"] == work.sha(path)
                    assert sage["natural_public_target_relation_verified"]
                    verified_dlp.append(repo_path(path))
                else:
                    unverified_hits.append(repo_path(path))
            else:
                verified_dlp.append(repo_path(path))
        elif row["native_result"]["exact_hit_queries"]:
            unverified_hits.append(repo_path(path))
        novel = len(cells - covered)
        covered.update(cells)
        calls = int(row["native_field_add_mul_sqr_call_model"])
        charged += calls
        charge_measured_search(row)
        entry = {"proposal_id": m32_proposals[path] if is_m32 else row["proposal_id"],
                 "path": repo_path(path), "sha256": work.sha(path),
                 "field_calls": str(calls), "new_cells": novel}
        if is_m32:
            entry["executable_proposal_id"] = row["proposal_id"]
            entry["new_M32_extension_cells"] = novel_extra_m32
        completed.append(entry)
    failures = [failed_record(path, row) for path, row in
                failed_q1060 + failed_full + failed_seg + failed_q1061_ci +
                failed_m32_ci + failed_local_m32]
    interrupted_markers = set()
    interrupted_q1073 = RUNS / "n83_local_arm_m33_q1073_interrupted.json"
    if interrupted_q1073.exists():
        interruption = json.loads(interrupted_q1073.read_text())
        marker = RUNS / "n83_local_arm_m33_q1073.started.json"
        assert interruption["kind"] == (
            "n83_q1073_local_arm_M33_R29_interrupted_attempt")
        assert interruption["status"] == (
            "interrupted_no_terminal_search_receipt")
        assert interruption["curve_id"] == screen["curve_id"]
        assert interruption["factor_base_enumerated_set_sha256"] == screen[
            "factor_base"]["enumerated_set_sha256"]
        assert interruption["start_marker_sha256"] == work.sha(marker)
        assert not (RUNS / "n83_local_arm_m33_q1073.json").exists()
        assert not interruption["coverage_credited"]
        failures.append({
            "path": repo_path(interrupted_q1073),
            "sha256": work.sha(interrupted_q1073),
            "query_start": interruption["query_start"],
            "query_representatives": interruption["query_representatives"],
            "native_phase_counts": None,
            "resource_guard_reason": "interrupted_without_terminal_receipt",
            "resource_guard_receipt_sha256": None,
        })
        interrupted_markers.add(marker)
    cell_fraction = (M28 /
                     base["zero_pair_key_cap_before_accidental_collisions"]
                     * R27 * base["factor_base"]["signed_frobenius_orbit_size"]
                     / base["unordered_query_pair_domain"])
    mean = base["heuristic_mean_four_point_multisets"]
    # A full M31-by-R27 rectangle has eight grid cells. Its finite-base
    # multiset intensity should agree with the direct quotient-key estimate:
    # each table and query pair represents a signed-Frobenius orbit of L.
    finite_segment_intensity = work.intensity(
        8, cell_fraction=cell_fraction, mean=mean)
    quotient_segment_intensity = (
        M31 * R27 *
        base["factor_base"]["signed_frobenius_orbit_size"] ** 2 /
        screen["curve_identity_record"]["curve"]["subgroup_order"])
    assert math.isclose(finite_segment_intensity,
                        quotient_segment_intensity, rel_tol=1e-4)
    start_intensity = work.intensity(len(covered),
                                     cell_fraction=cell_fraction, mean=mean)
    future = [(range_index, segment)
              for range_index in range(1, 118)
              for segment in range(SEGMENTS_PER_RANGE)
              if (range_index, segment) not in complete_segments and
              any((range_index, segment, shard) not in covered
                  for shard in range(8))]
    future_covered = set(covered)
    cdf = [0.0]
    for range_index, segment in future:
        future_covered.update((range_index, segment, shard)
                              for shard in range(8))
        cdf.append(-math.expm1(-(
            work.intensity(len(future_covered),
                           cell_fraction=cell_fraction, mean=mean)
            - start_intensity)))
    assert len(future_covered) == 118 * SEGMENTS_PER_RANGE * 8
    assert all(a <= b for a, b in zip(cdf, cdf[1:]))
    per_segment = field_calls(M31, R27)
    groups = grouped_future_plan(future)
    group_covered = set(covered)
    group_cdf = [0.0]
    group_costs = [0]
    group_segments = [0]
    for range_index, first_segment, count in groups:
        group_covered.update((range_index, segment, shard)
                             for segment in range(first_segment,
                                                  first_segment + count)
                             for shard in range(8))
        group_cdf.append(-math.expm1(-(
            work.intensity(len(group_covered),
                           cell_fraction=cell_fraction, mean=mean)
            - start_intensity)))
        group_costs.append(group_costs[-1] + field_calls(M31, count * R27))
        group_segments.append(group_segments[-1] + count)
    assert group_covered == future_covered
    assert math.isclose(group_cdf[-1], cdf[-1], rel_tol=1e-12)
    assert group_segments[-1] == len(future)
    # The M32 table covers a second set of eight M28 shards. Keep this
    # projection separate from the established M31 grid and schedule the
    # most novel full R29 rectangles first. An already completed M32 cell
    # is never credited twice, even when a new rectangle overlaps it.
    all_covered = covered | extra_m32_covered
    m32_start_intensity = work.intensity(
        len(all_covered), cell_fraction=cell_fraction, mean=mean)
    m32_groups = []
    for range_index in range(118):
        for first_segment in (0, 4):
            cells = {(range_index, segment, shard)
                     for segment in range(first_segment, first_segment + 4)
                     for shard in range(16)}
            novel = len(cells - all_covered)
            if novel:
                m32_groups.append((range_index, first_segment, cells, novel))
    m32_groups.sort(key=lambda group: (-group[3], group[0], group[1]))
    m32_future_covered = set(all_covered)
    m32_cdf = [0.0]
    for _, _, cells, _ in m32_groups:
        m32_future_covered.update(cells)
        m32_cdf.append(-math.expm1(-(
            work.intensity(len(m32_future_covered),
                           cell_fraction=cell_fraction, mean=mean)
            - m32_start_intensity)))
    assert len(m32_future_covered) == 118 * SEGMENTS_PER_RANGE * 16
    assert all(a <= b for a, b in zip(m32_cdf, m32_cdf[1:]))
    conditional = None
    grouped_conditional = None
    m32_conditional = None
    if not verified_dlp and not unverified_hits:
        probability = cdf[-1]
        expected = (sum(i * (cdf[i] - cdf[i - 1])
                        for i in range(1, len(cdf))) / probability
                    if probability else None)
        quantiles = {}
        for label in QUANTILES:
            count = next((i for i in range(1, len(cdf))
                          if cdf[i] >= float(label)), None)
            quantiles[label] = {
                "additional_R27_segments": count,
                "model_probability": cdf[count] if count else None,
                "selected_route_field_calls_log2":
                    math.log2(charged + count * per_segment)
                    if count else None,
            }
        conditional = {
            "probability_of_hit_by_plan_end_conditional_on_zero_hits_so_far":
                probability,
            "expected_additional_R27_segments_given_hit_by_plan_end":
                expected,
            "selected_route_expected_field_calls_given_hit_log2":
                math.log2(charged + expected * per_segment)
                if expected is not None else None,
            "first_hit_quantiles": quantiles,
            "all_remaining_segments_field_calls_log2": math.log2(
                len(future) * per_segment) if future else None,
        }
        grouped_quantiles = {}
        for label in QUANTILES:
            count = next((i for i in range(1, len(group_cdf))
                          if group_cdf[i] >= float(label)), None)
            grouped_quantiles[label] = {
                "additional_grouped_calls": count,
                "additional_R27_segments_covered":
                    group_segments[count] if count else None,
                "model_probability": group_cdf[count] if count else None,
                "selected_route_field_calls_log2":
                    math.log2(charged + group_costs[count])
                    if count else None,
            }
        expected_group_cost = (
            sum((charged + group_costs[i]) *
                (group_cdf[i] - group_cdf[i - 1])
                for i in range(1, len(group_cdf))) / probability
            if probability else None)
        grouped_conditional = {
            "shape": "greedy_earliest_four_contiguous_R27_segments_as_R29_else_R27",
            "future_R29_group_count": sum(count == 4 for _, _, count in groups),
            "future_R27_single_count": sum(count == 1 for _, _, count in groups),
            "first_group_query_start": (
                groups[0][0] * R30 + groups[0][1] * R27)
            if groups else None,
            "probability_of_hit_by_plan_end_conditional_on_zero_hits_so_far":
                probability,
            "expected_additional_grouped_calls_given_hit_by_plan_end":
                sum(i * (group_cdf[i] - group_cdf[i - 1])
                    for i in range(1, len(group_cdf))) / probability
                if probability else None,
            "expected_additional_R27_segments_covered_given_hit_by_plan_end":
                sum(group_segments[i] *
                    (group_cdf[i] - group_cdf[i - 1])
                    for i in range(1, len(group_cdf))) / probability
                if probability else None,
            "selected_route_expected_field_calls_given_hit_log2":
                math.log2(expected_group_cost)
                if expected_group_cost is not None else None,
            "first_hit_quantiles": grouped_quantiles,
            "all_remaining_grouped_calls_field_calls_log2":
                math.log2(group_costs[-1]) if groups else None,
        }
        m32_cost = field_calls(M32, 1 << 29)
        m32_probability = m32_cdf[-1]
        m32_expected_calls = (
            sum(i * (m32_cdf[i] - m32_cdf[i - 1])
                for i in range(1, len(m32_cdf))) / m32_probability
            if m32_probability else None)
        m32_quantiles = {}
        for label in QUANTILES:
            count = next((i for i in range(1, len(m32_cdf))
                          if m32_cdf[i] >= float(label)), None)
            m32_quantiles[label] = {
                "additional_M32_R29_calls": count,
                "model_probability": m32_cdf[count] if count else None,
                "selected_route_field_calls_log2":
                    math.log2(charged + count * m32_cost)
                    if count else None,
            }
        m32_conditional = {
            "shape": "M32_R29_aligned_groups_most_novel_cells_first",
            "initial_completed_primary_cells": len(covered),
            "initial_completed_M32_extension_cells":
                len(extra_m32_covered),
            "future_group_count": len(m32_groups),
            "modeled_field_calls_per_group": str(m32_cost),
            "probability_of_hit_by_plan_end_conditional_on_zero_hits_so_far":
                m32_probability,
            "expected_additional_calls_given_hit_by_plan_end":
                m32_expected_calls,
            "selected_route_expected_field_calls_given_hit_log2":
                math.log2(charged + m32_expected_calls * m32_cost)
                if m32_expected_calls is not None else None,
            "first_hit_quantiles": m32_quantiles,
            "all_remaining_grouped_calls_field_calls_log2":
                math.log2(len(m32_groups) * m32_cost)
                if m32_groups else None,
            "limits": [
                "This is a finite-support placement model, not measured relation yield or a completed DLP.",
                "Active wave and Q1068 jobs are excluded until terminal receipts are ingested.",
                "Every projected group rebuilds its M32 table; failed attempts and non-field work are omitted from the field-call model.",
            ],
        }
    report = {
        "kind": "n83_q1062_segmented_coverage_aware_conditional_work",
        "proposal_id": "Q1062", "candidate_id": None, "run_id": None,
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "query_shape": "eight_R27_segments_per_R30_range",
        "completed_receipts": completed,
        "completed_disjoint_M28_by_R27_cells": len(covered),
        "completed_M32_extension_M28_by_R27_cells": len(extra_m32_covered),
        "full_plan_disjoint_cells": 118 * SEGMENTS_PER_RANGE * 8,
        "failed_receipts_with_unknown_field_calls": failures,
        "incomplete_portable_ci_bundles_with_unknown_work":
            incomplete_q1061_ci,
        "noncompleted_M32_ci_bundles": noncompleted_m32_ci,
        "active_start_markers_excluded": [repo_path(path) for path in sorted(
            RUNS.glob("n83_*.started.json")) if path not in
            interrupted_markers],
        "future_R27_segment_count": len(future),
        "future_R27_segment_spans": compressed_starts(
            [i * R30 + s * R27 for i, s in future]),
        "modeled_field_calls_per_R27_segment": str(per_segment),
        "modeled_eight_R27_segments_vs_one_R30_field_call_ratio":
            8 * per_segment / field_calls(M31, R30),
        "R27_hit_intensity_cross_check": {
            "finite_base_four_point_multiset_model":
                finite_segment_intensity,
            "quotient_pair_collision_model": quotient_segment_intensity,
            "relative_difference": abs(
                finite_segment_intensity - quotient_segment_intensity) /
                quotient_segment_intensity,
        },
        "completed_selected_route_field_calls": str(charged),
        "completed_selected_route_field_calls_log2": math.log2(charged),
        "completed_measured_search_work": {
            **{key: str(value) for key, value in measured_search.items()
               if key != "target_online_seconds_sum_across_hosts"},
            "lifted_query_pairs_tested_log2": math.log2(
                measured_search["lifted_query_pairs_tested"]),
            "target_online_seconds_sum_across_hosts": measured_search[
                "target_online_seconds_sum_across_hosts"],
            "scope": "successful terminal receipts only; repeated work is charged, including overlapping coverage; excluded failed attempt has unknown operation counts; online seconds sum separate hosts and are not one continuous wall-clock solve",
        },
        "verified_quotient_table_dlp_receipts": verified_dlp,
        "unverified_exact_hit_receipts": unverified_hits,
        "conditional_model_if_no_verified_dlp": conditional,
        "conditional_grouped_R29_route_if_no_verified_dlp":
            grouped_conditional,
        "conditional_M32_grouped_R29_route_if_no_verified_dlp":
            m32_conditional,
        "complete_solve_work_log2": None,
        "limits": [
            "The relation-placement probability is a frozen finite-support heuristic, not measured yield.",
            "Failed attempts have measured wall/CPU time where available but unknown field-call work and no completed coverage.",
            "Field calls exclude keying, Bloom work, SSD traffic, base setup, and scalar replay; no complete operation-equivalent solve cost is claimed.",
            "M32 completed receipts credit their M31-overlapping first eight table shards to the primary grid; the extra eight table shards are counted separately and are omitted from its conservative future-hit projection.",
        ],
        "Q1062_screen_sha256": work.sha(work.SCREEN),
        "base_screen_sha256": work.sha(work.BASE),
        "portable_ci_ingest_source_sha256": work.sha(
            HERE / "n83_portable_ci_ingest.py"),
        "m32_ci_ingest_source_sha256": work.sha(
            HERE / "n83_m32_ci_ingest.py"),
        "m32_group_ci_ingest_source_sha256": work.sha(
            HERE / "n83_m32_group_ci_ingest.py"),
        "m32_wave_ci_ingest_source_sha256": work.sha(
            HERE / "n83_m32_wave_ci_ingest.py"),
        "m32_wave_q1075_ci_ingest_source_sha256": work.sha(
            HERE / "n83_m32_wave_q1075_ci_ingest.py"),
        "local_M32_Q1071_plan_sha256": work.sha(
            HERE / "n83_local_arm_m32_q1071_plan.json"),
        "portable_native_source_sha256": work.sha(portable.SOURCE),
        "segment_campaign_source_sha256": work.sha(
            HERE / "n83_full_spill_segment_campaign.py"),
        "source_sha256": work.sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "completed_cells": len(covered),
        "failed_attempts": len(failures),
        "future_segments": len(future),
        "conditional_hit_probability": conditional[
            "probability_of_hit_by_plan_end_conditional_on_zero_hits_so_far"]
        if conditional else None,
        "complete_solve_work_log2": None,
    }), flush=True)


if __name__ == "__main__":
    main()
