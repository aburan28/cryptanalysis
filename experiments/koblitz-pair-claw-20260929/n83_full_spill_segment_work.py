#!/usr/bin/env python3
"""Reconcile Q1062 full and segmented receipts on an M28-by-R27 grid."""

import json
import math
from pathlib import Path

import n83_full_spill_work as work
from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_receipt, validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
OUTPUT = HERE / "n83_full_spill_segment_work.json"
M28 = 1 << 28
M31 = 1 << 31
R27 = 1 << 27
R30 = 1 << 30
SEGMENTS_PER_RANGE = R30 // R27
QUANTILES = ("0.5", "0.8", "0.9", "0.95")


def failed_record(path, row):
    guard_path = path.with_suffix(".guard.json")
    guard = json.loads(guard_path.read_text()) if guard_path.exists() else None
    if guard:
        assert guard["terminal_receipt_sha256"] == work.sha(path)
        assert guard["query_start"] == row["query_start"]
        assert guard["curve_id"] == row["curve_id"]
    return {
        "path": str(path), "sha256": work.sha(path),
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
    covered = {(0, segment, shard)
               for segment in range(SEGMENTS_PER_RANGE)
               for shard in range(8)}
    charged = int(first["native_field_add_mul_sqr_call_model"])
    completed = [{"proposal_id": "Q1051", "path": str(work.FIRST),
                  "sha256": work.sha(work.FIRST),
                  "field_calls": str(charged), "new_cells": 64}]
    complete_segments = set()
    verified_dlp = []
    unverified_hits = []
    for path, row in sorted(q1060 + q1062_full + q1062_seg,
                            key=lambda item: (item[1]["finished_at_utc"],
                                              str(item[0]))):
        qstart = row["query_start"]
        range_index, remainder = divmod(qstart, R30)
        assert 1 <= range_index < 118
        if row["proposal_id"] == "Q1060":
            assert remainder == 0 and row["query_representatives"] == R30
            assert row["table_descriptors"] == M28
            shard = row["table_start"] // M28
            assert 0 <= shard < 8 and row["table_start"] == shard * M28
            cells = {(range_index, segment, shard)
                     for segment in range(SEGMENTS_PER_RANGE)}
        else:
            assert row["table_start"] == 0
            assert row["table_descriptors"] == M31
            if row["query_representatives"] == R30:
                assert remainder == 0
                segments = range(SEGMENTS_PER_RANGE)
            else:
                assert row["query_representatives"] == R27
                assert remainder % R27 == 0
                segments = [remainder // R27]
            cells = {(range_index, segment, shard)
                     for segment in segments for shard in range(8)}
            complete_segments.update((range_index, segment)
                                     for segment in segments)
        if row["verified_public_target_quotient_table_dlp"]:
            assert row["verified_public_target_relations"]
            verified_dlp.append(str(path))
        elif row["native_result"]["exact_hit_queries"]:
            unverified_hits.append(str(path))
        novel = len(cells - covered)
        covered.update(cells)
        calls = int(row["native_field_add_mul_sqr_call_model"])
        charged += calls
        completed.append({"proposal_id": row["proposal_id"],
                          "path": str(path), "sha256": work.sha(path),
                          "field_calls": str(calls), "new_cells": novel})
    failures = [failed_record(path, row) for path, row in
                failed_q1060 + failed_full + failed_seg]
    cell_fraction = (M28 /
                     base["zero_pair_key_cap_before_accidental_collisions"]
                     * R27 * base["factor_base"]["signed_frobenius_orbit_size"]
                     / base["unordered_query_pair_domain"])
    mean = base["heuristic_mean_four_point_multisets"]
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
    conditional = None
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
        "full_plan_disjoint_cells": 118 * SEGMENTS_PER_RANGE * 8,
        "failed_receipts_with_unknown_field_calls": failures,
        "active_start_markers_excluded": [str(path) for path in sorted(
            RUNS.glob("n83_*.started.json"))],
        "future_R27_segment_count": len(future),
        "future_R27_segment_spans": compressed_starts(
            [i * R30 + s * R27 for i, s in future]),
        "modeled_field_calls_per_R27_segment": str(per_segment),
        "modeled_eight_R27_segments_vs_one_R30_field_call_ratio":
            8 * per_segment / field_calls(M31, R30),
        "completed_selected_route_field_calls": str(charged),
        "verified_quotient_table_dlp_receipts": verified_dlp,
        "unverified_exact_hit_receipts": unverified_hits,
        "conditional_model_if_no_verified_dlp": conditional,
        "complete_solve_work_log2": None,
        "limits": [
            "The relation-placement probability is a frozen finite-support heuristic, not measured yield.",
            "Failed attempts have measured wall/CPU time where available but unknown field-call work and no completed coverage.",
            "Field calls exclude keying, Bloom work, SSD traffic, base setup, and scalar replay; no complete operation-equivalent solve cost is claimed.",
        ],
        "Q1062_screen_sha256": work.sha(work.SCREEN),
        "base_screen_sha256": work.sha(work.BASE),
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
