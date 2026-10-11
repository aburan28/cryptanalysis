#!/usr/bin/env python3
"""Compare disjoint M34 query lengths after Q1086's first full result.

The first R31 job is the frozen Q1086 plan. Longer follow-on jobs are
designs only; their full-size memory and wall time have not been measured.
"""

import hashlib
import json
import math
from pathlib import Path

import n83_full_spill_work as work
from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCREEN = HERE / "n83_full_spill_screen.json"
BASE = HERE / "n83_large_knownlog_base_screen.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
Q1086 = HERE / "n83_q1086_m34_feasibility.json"
Q1087 = HERE / "n83_q1087_m34_wave_projection.json"
PREFLIGHT = HERE / "runs/n83_local_arm_m33_r30_q1074_preflight.json"
CORE = HERE / "native_n83_bloom_core_portable.hpp"
NATIVE = HERE / "native_n83_orbit_query_spill_portable.cpp"
OUTPUT = HERE / "n83_q1088_long_query_screen.json"
M28 = 1 << 28
R27 = 1 << 27
M34 = 1 << 34
R31 = 1 << 31
R30 = 1 << 30
ROUTES = {
    "eight_R31_jobs": [31] * 8,
    "first_R31_then_R33_R32_R31": [31, 33, 32, 31],
    "first_R31_then_two_R33": [31, 33, 33],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    screen = json.loads(SCREEN.read_text())
    base = json.loads(BASE.read_text())
    ledger = json.loads(LEDGER.read_text())
    q1086 = json.loads(Q1086.read_text())
    q1087 = json.loads(Q1087.read_text())
    preflight = json.loads(PREFLIGHT.read_text())
    validate_reference(screen)
    assert all(row["curve_id"] == screen["curve_id"] and
               row["isogeny"] == "none" and
               row["candidate_id"] is None
               for row in (base, ledger, q1086, q1087, preflight))
    assert q1087["status"] == "design_only_no_wave_dispatch"
    assert q1087["coverage_ledger_sha256"] == sha(LEDGER)
    assert q1087["Q1086_feasibility_sha256"] == sha(Q1086)
    assert q1087["factor_base"] == screen["factor_base"]
    assert q1087["public_target"] == screen["public_target"]
    assert q1086["query_start"] == 50 * R30
    assert q1086["table_descriptors"] == M34
    assert q1086["query_representatives"] == R31
    assert q1086["bits_per_key"] == 16
    assert q1086["hashes"] == 10
    assert q1086["native_source_sha256"] == sha(NATIVE)
    assert q1086["bloom_core_source_sha256"] == sha(CORE)
    assert preflight["system_memory_bytes"] == 48 * (1 << 30)
    assert ledger["complete_solve_work_log2"] is None
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]

    first = q1086["query_start"]
    domain = math.comb(screen["factor_base"]["signed_frobenius_columns"], 2)
    domain *= screen["factor_base"]["signed_frobenius_orbit_size"]
    assert first > M34
    for entry in ledger["completed_receipts"]:
        row = json.loads((REPO / entry["path"]).read_text())
        begin, end = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(begin, first) >= min(end, first + 18 * R30)
    for path in (HERE / "runs").rglob("*.started.json"):
        row = json.loads(path.read_text())
        if row.get("curve_id") != screen["curve_id"]:
            continue
        begin, end = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(begin, first) >= min(end, first + 18 * R30), str(path)

    baseline_cells = q1087["completed_credited_cells_at_screen"]
    baseline_calls = int(q1087[
        "completed_credited_modeled_field_calls_at_screen"])
    fraction = (M28 / base["zero_pair_key_cap_before_accidental_collisions"]
                * R27 * base["factor_base"]["signed_frobenius_orbit_size"]
                / base["unordered_query_pair_domain"])
    mean = base["heuristic_mean_four_point_multisets"]
    prior_intensity = work.intensity(
        baseline_cells, cell_fraction=fraction, mean=mean)
    positives_R31 = q1086["projected_M34_R31_b16_positives"]
    bloom_bytes = q1086["exact_b16_bloom_allocation_bytes"]
    assert bloom_bytes == ((M34 * 16 + 511) // 512 + 1024) * 64
    route_rows = []
    for name, lengths in ROUTES.items():
        start, covered, charged = first, 0, baseline_calls
        rows = []
        cdf = [0.0]
        for index, exponent in enumerate(lengths, 1):
            query_reps = 1 << exponent
            end = start + query_reps
            assert end <= domain
            assert query_reps % R27 == 0
            new_cells = (M34 // M28) * (query_reps // R27)
            covered += new_cells
            charged += field_calls(M34, query_reps)
            intensity = work.intensity(
                baseline_cells + covered, cell_fraction=fraction, mean=mean)
            probability = -math.expm1(-(intensity - prior_intensity))
            assert probability > cdf[-1]
            cdf.append(probability)
            positives = positives_R31 * query_reps // R31
            spool = positives * 24
            candidate_slots = (positives * 10 // 7 + 1024) * 28
            assert max(bloom_bytes, candidate_slots) < preflight[
                "system_memory_bytes"]
            rows.append({
                "job_index": index, "query_start": start,
                "query_end_exclusive": end,
                "query_representatives": query_reps,
                "fresh_M28_by_R27_cells": new_cells,
                "modeled_native_field_calls": str(field_calls(M34, query_reps)),
                "projected_b16_bloom_positives": positives,
                "projected_candidate_spool_bytes": spool,
                "projected_candidate_slot_bytes": candidate_slots,
                "exact_b16_bloom_allocation_bytes": bloom_bytes,
                "cumulative_model_hit_probability": probability,
                "cumulative_field_calls_including_credited_history": str(
                    charged),
                "cumulative_field_calls_log2": math.log2(charged),
            })
            start = end
        expected = sum(
            int(rows[index - 1][
                "cumulative_field_calls_including_credited_history"])
            * (cdf[index] - cdf[index - 1])
            for index in range(1, len(cdf))) / cdf[-1]
        route_rows.append({
            "name": name, "job_count": len(rows),
            "query_end_exclusive": start,
            "total_fresh_cells": covered,
            "model_hit_probability": cdf[-1],
            "conditional_expected_first_hit_field_calls_log2": math.log2(
                expected),
            "all_jobs_field_calls_including_credited_history_log2":
                math.log2(charged),
            "jobs": rows,
        })
    reference, same_cells, extra_cells = route_rows
    assert reference["query_end_exclusive"] == same_cells[
        "query_end_exclusive"] == 66 * R30
    assert extra_cells["query_end_exclusive"] == 68 * R30
    assert reference["total_fresh_cells"] == same_cells[
        "total_fresh_cells"] == 8192
    assert extra_cells["total_fresh_cells"] == 9216
    assert math.isclose(reference["model_hit_probability"], q1087[
        "model_probability_of_hit_by_eight"], rel_tol=1e-12)
    assert math.isclose(reference[
        "all_jobs_field_calls_including_credited_history_log2"], q1087[
            "jobs"][-1]["cumulative_modeled_field_calls_log2"],
        rel_tol=1e-12)
    assert same_cells[
        "all_jobs_field_calls_including_credited_history_log2"] < reference[
            "all_jobs_field_calls_including_credited_history_log2"]
    report = {
        "kind": "n83_q1088_long_query_follow_on_design_screen",
        "proposal_id": "Q1088", "candidate_id": None, "run_id": None,
        "status": "design_only_wait_for_Q1086_terminal_result",
        "curve_id": screen["curve_id"],
        "curve_identity_record": screen["curve_identity_record"],
        "isogeny": "none", "factor_base": screen["factor_base"],
        "public_target": screen["public_target"], "target_count": 1,
        "table_start": 0, "table_descriptors_per_job": M34,
        "bits_per_key": 16, "hashes": 10,
        "physical_arm_system_memory_bytes": preflight[
            "system_memory_bytes"],
        "peak_storage_model": "max(Bloom allocation, exact candidate slots); native source releases Bloom before constructing candidate table; excludes other RSS, allocator behavior, and OS pressure",
        "routes": route_rows,
        "measured_natural_relations": 0,
        "measured_complete_solve_work_log2": None,
        "screen_sha256": sha(SCREEN), "base_sha256": sha(BASE),
        "coverage_ledger_sha256": sha(LEDGER),
        "Q1086_feasibility_sha256": sha(Q1086),
        "Q1087_projection_sha256": sha(Q1087),
        "Q1074_preflight_sha256": sha(PREFLIGHT),
        "native_source_sha256": sha(NATIVE),
        "bloom_core_sha256": sha(CORE),
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "This is a design comparison, not a frozen executable plan or a measured relation yield.",
            "No follow-on search can be dispatched before Q1086 has a terminal independent audit; a verified or unresolved hit stops further search.",
            "R32/R33 positive counts and candidate storage scale a bounded x86 16-bit control; full-size ARM RSS and wall time remain unmeasured.",
            "The analytic storage model omits process overhead and allocator effects; the memory and SSD gates must be set from physical controls before launch.",
            "Hit probabilities use the unvalidated finite-support placement model; zero observed hits give no data-only positive lower yield.",
            "Field-call costs omit keying, Bloom, memory, disk, failed attempts, setup, and scalar replay.",
        ],
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "proposal_id": "Q1088", "routes": [{
            "name": route["name"],
            "model_hit_probability": route["model_hit_probability"],
            "all_jobs_field_calls_log2": route[
                "all_jobs_field_calls_including_credited_history_log2"]}
            for route in route_rows],
        "complete_solve_work_log2": None,
    }))


if __name__ == "__main__":
    main()
