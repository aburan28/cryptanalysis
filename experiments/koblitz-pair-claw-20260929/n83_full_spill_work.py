#!/usr/bin/env python3
"""Reconcile exact n=83 search coverage and conditional Q1062 first-hit work.

Completed Q1060 shards and Q1062 full ranges form a union of disjoint
M28-by-R30 cells. A Q1062 full range may overlap earlier Q1060 shards:
the overlap costs work twice but contributes success coverage once.
"""

import hashlib
import json
import math
from pathlib import Path

from n83_identity_contract import (sha as identity_sha, validate_receipt,
                                   validate_reference)

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
BASE = HERE / "n83_large_knownlog_base_screen.json"
SCREEN = HERE / "n83_full_spill_screen.json"
FIRST = RUNS / "n83_orbit_k48194_chunk_M31_R30_tstart0_qstart0_b20_h14_rb8.json"
OUTPUT = HERE / "n83_full_spill_work.json"
M28 = 1 << 28
R30 = 1 << 30
SHARDS = 8
QUERY_RANGES = 118
QUANTILES = ("0.5", "0.8", "0.9", "0.95")
SUCCESS_KIND = "n83_public_target_signed_x_query_k48194_exact_replay_chunk"
FAILED_KIND = "n83_public_target_signed_x_query_k48194_chunk_failed"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def intensity(cells, *, cell_fraction, mean):
    coverage = cells * cell_fraction
    assert 0 <= coverage <= 1
    return mean * (1 - (1 - coverage) ** 6)


def load_terminal_rows(pattern, proposal_id, screen):
    completed, failed = [], []
    for path in sorted(RUNS.glob(pattern)):
        row = json.loads(path.read_text())
        if row.get("kind") not in (SUCCESS_KIND, FAILED_KIND):
            continue
        validate_receipt(screen, row)
        assert row["proposal_id"] == proposal_id
        digest = (row["factor_base"]["enumerated_set_sha256"]
                  if "factor_base" in row else
                  row["factor_base_enumerated_set_sha256"])
        assert digest == screen["factor_base"]["enumerated_set_sha256"]
        assert row["native_source_sha256"] == screen["native_source_sha256"]
        if row["kind"] == SUCCESS_KIND:
            completed.append((path, row))
        else:
            assert row["native_phase_counts"] is None
            failed.append((path, row))
    return completed, failed


def main():
    base = json.loads(BASE.read_text())
    screen = json.loads(SCREEN.read_text())
    first = json.loads(FIRST.read_text())
    assert base["proposal_id"] == first["proposal_id"] == "Q1051"
    assert screen["proposal_id"] == "Q1062"
    validate_reference(screen)
    validate_receipt(screen, first)
    assert all(row["candidate_id"] is None and row["isogeny"] == "none"
               for row in (base, screen, first))
    assert base["curve_id"] == screen["curve_id"] == first["curve_id"]
    assert first["factor_base"]["enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert first["public_target"] == screen["public_target"]
    assert first["table_start"] == first["query_start"] == 0
    assert first["table_descriptors"] == SHARDS * M28
    assert first["query_representatives"] == R30
    assert first["native_result"]["exact_hit_queries"] == 0
    assert not first["verified_public_target_quotient_table_dlp"]

    q1060, failed_q1060 = load_terminal_rows(
        "n83_spill_lowmem_k48194_chunk_M28_R30_tstart*_qstart*_b20_h10_rb8*.json",
        "Q1060", screen)
    q1062, failed_q1062 = load_terminal_rows(
        "n83_full_spill_k48194_chunk_M31_R30_tstart0_qstart*_b20_h10_rb8*.json",
        "Q1062", screen)
    covered = {(0, shard) for shard in range(SHARDS)}
    completed_calls = int(first["native_field_add_mul_sqr_call_model"])
    completed_receipts = [{"proposal_id": "Q1051", "path": str(FIRST),
                           "sha256": sha(FIRST),
                           "field_calls": first[
                               "native_field_add_mul_sqr_call_model"]}]
    solved = []
    unverified_exact_hits = []
    full_done = set()
    shard_done = set()
    terminal_rows = sorted(q1060 + q1062,
                           key=lambda item: (item[1]["finished_at_utc"],
                                             str(item[0])))
    for path, row in terminal_rows:
        index = row["query_start"] // R30
        assert 1 <= index < QUERY_RANGES
        assert row["query_start"] == index * R30
        assert row["query_representatives"] == R30
        if row["proposal_id"] == "Q1060":
            shard = row["table_start"] // M28
            assert 0 <= shard < SHARDS
            assert row["table_start"] == shard * M28
            assert row["table_descriptors"] == M28
            assert (index, shard) not in shard_done, (
                "duplicate completed Q1060 shard", path)
            shard_done.add((index, shard))
            cells = {(index, shard)}
        else:
            assert row["table_start"] == 0
            assert row["table_descriptors"] == SHARDS * M28
            assert index not in full_done, "duplicate completed Q1062 range"
            full_done.add(index)
            cells = {(index, shard) for shard in range(SHARDS)}
        if row["verified_public_target_quotient_table_dlp"]:
            assert row["verified_public_target_relations"]
            solved.append(str(path))
        elif row["native_result"]["exact_hit_queries"]:
            unverified_exact_hits.append(str(path))
        novel = len(cells - covered)
        covered.update(cells)
        calls = int(row["native_field_add_mul_sqr_call_model"])
        completed_calls += calls
        completed_receipts.append({
            "proposal_id": row["proposal_id"], "path": str(path),
            "sha256": sha(path), "field_calls": str(calls),
            "new_disjoint_cells": novel,
            "verified_dlp": row["verified_public_target_quotient_table_dlp"],
        })
    per_range = int(screen["modeled_field_calls_per_full_range"])
    cell_fraction = (M28 /
                     base["zero_pair_key_cap_before_accidental_collisions"]
                     * R30 * base["factor_base"]["signed_frobenius_orbit_size"]
                     / base["unordered_query_pair_domain"])
    mean = base["heuristic_mean_four_point_multisets"]
    future = [index for index in range(1, QUERY_RANGES)
              if index not in full_done]
    cdf = [0.0]
    future_cells = set(covered)
    start_intensity = intensity(len(covered), cell_fraction=cell_fraction,
                                mean=mean)
    for index in future:
        future_cells.update((index, shard) for shard in range(SHARDS))
        cdf.append(-math.expm1(-(
            intensity(len(future_cells), cell_fraction=cell_fraction,
                      mean=mean) - start_intensity)))
    assert len(future_cells) == QUERY_RANGES * SHARDS
    assert all(a <= b for a, b in zip(cdf, cdf[1:]))
    model = None
    if not solved and not unverified_exact_hits:
        success = cdf[-1]
        expected_more = (sum(i * (cdf[i] - cdf[i - 1])
                             for i in range(1, len(cdf))) / success
                         if success else None)
        quantiles = {}
        for label in QUANTILES:
            count = next((i for i in range(1, len(cdf))
                          if cdf[i] >= float(label)), None)
            quantiles[label] = {
                "additional_Q1062_full_ranges": count,
                "model_probability": cdf[count] if count else None,
                "selected_route_field_calls_log2":
                    math.log2(completed_calls + count * per_range)
                    if count else None,
            }
        model = {
            "probability_of_hit_by_plan_end_conditional_on_zero_hits_so_far":
                success,
            "probability_of_no_hit_by_plan_end_conditional_on_zero_hits_so_far":
                1 - success,
            "expected_additional_Q1062_ranges_given_hit_by_plan_end":
                expected_more,
            "selected_route_expected_field_calls_given_hit_log2":
                math.log2(completed_calls + expected_more * per_range)
                if expected_more is not None else None,
            "first_hit_quantiles": quantiles,
            "all_remaining_Q1062_ranges_field_calls_log2":
                math.log2(len(future) * per_range) if future else None,
            "selected_route_all_ranges_field_calls_log2":
                math.log2(completed_calls + len(future) * per_range),
        }
    report = {
        "kind": "n83_q1062_coverage_aware_conditional_work",
        "scope": "completed terminal receipts and finite-support first-hit model; active runs have unknown outcome and are excluded from completed coverage",
        "proposal_id": "Q1062", "candidate_id": None,
        "curve_id": screen["curve_id"], "isogeny": "none",
        "public_target": screen["public_target"],
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "completed_receipts": completed_receipts,
        "completed_disjoint_M28_by_R30_cells": len(covered),
        "full_plan_disjoint_cells": QUERY_RANGES * SHARDS,
        "completed_selected_route_field_calls": str(completed_calls),
        "completed_selected_route_field_calls_log2": math.log2(
            completed_calls),
        "failed_receipts_with_unknown_field_calls": [
            {"path": str(path), "sha256": sha(path)}
            for path, _ in failed_q1060 + failed_q1062],
        "active_start_markers_excluded": [str(path) for path in sorted(
            RUNS.glob("n83_*chunk_M*_R30_*.started.json"))],
        "Q1062_future_full_range_starts": [index * R30 for index in future],
        "verified_quotient_table_dlp_receipts": solved,
        "unverified_exact_hit_receipts": unverified_exact_hits,
        "conditional_model_if_no_verified_dlp": model,
        "complete_solve_work_log2": None,
        "limits": [
            "The finite-support probability is the frozen random-base heuristic, not an empirical relation yield rate.",
            "Selected-route field calls include completed Q1051, Q1060, and Q1062 terminal receipts only; failed attempts and other same-target research trials require separate accounting.",
            "A Q1062 full range may overlap completed Q1060 shards. Calls are charged twice; covered cells are counted once.",
            "Field calls omit keying, Bloom operations, memory and SSD traffic, and independent scalar replay; no complete operation-equivalent cost is claimed.",
        ],
        "base_screen_sha256": sha(BASE),
        "Q1062_screen_sha256": sha(SCREEN),
        "identity_contract_source_sha256": identity_sha(
            HERE / "n83_identity_contract.py"),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "completed_disjoint_cells": len(covered),
        "verified_dlp_receipts": solved,
        "modeled_success_probability": model[
            "probability_of_hit_by_plan_end_conditional_on_zero_hits_so_far"]
        if model else None,
        "complete_solve_work_log2": None,
    }))


if __name__ == "__main__":
    main()
