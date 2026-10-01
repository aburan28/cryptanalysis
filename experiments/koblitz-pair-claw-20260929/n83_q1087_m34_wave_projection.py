#!/usr/bin/env python3
"""Freeze a conditional eight-job M34/R31 first-hit search projection.

This is a design screen, not permission to dispatch or a measured DLP.
Each job rebuilds the same table and searches a disjoint query interval.
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
OUTPUT = HERE / "n83_q1087_m34_wave_projection.json"
M28 = 1 << 28
R27 = 1 << 27
M34 = 1 << 34
R31 = 1 << 31
JOBS = 8


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    screen = json.loads(SCREEN.read_text())
    base = json.loads(BASE.read_text())
    ledger = json.loads(LEDGER.read_text())
    q1086 = json.loads(Q1086.read_text())
    validate_reference(screen)
    assert q1086["proposal_id"] == "Q1086"
    assert q1086["status"].startswith("design_only_")
    assert q1086["candidate_id"] is None and q1086["run_id"] is None
    assert ledger["M34_two_range_accounting_enabled"]
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    assert ledger["complete_solve_work_log2"] is None
    for row in (base, ledger, q1086):
        assert row["curve_id"] == screen["curve_id"]
        assert row["isogeny"] == "none"
        assert row["candidate_id"] is None
    assert base["factor_base"]["enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert q1086["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert ledger["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert q1086["public_target"] == screen["public_target"]
    assert q1086["table_start"] == 0
    assert q1086["table_descriptors"] == M34
    assert q1086["query_representatives"] == R31
    assert q1086["query_start"] == 50 * (1 << 30)
    assert q1086["query_end_exclusive"] == q1086["query_start"] + R31
    assert q1086["bits_per_key"] == 16
    assert q1086["modeled_native_field_calls"] == str(field_calls(M34, R31))

    first = q1086["query_start"]
    last = first + JOBS * R31
    domain = math.comb(screen["factor_base"]["signed_frobenius_columns"], 2)
    domain *= screen["factor_base"]["signed_frobenius_orbit_size"]
    assert M34 < first and last <= domain
    for entry in ledger["completed_receipts"]:
        row = json.loads((REPO / entry["path"]).read_text())
        begin = row["query_start"]
        end = begin + row["query_representatives"]
        assert max(begin, first) >= min(end, last), entry["path"]
    for path in (HERE / "runs").rglob("*.started.json"):
        row = json.loads(path.read_text())
        if row.get("curve_id") != screen["curve_id"]:
            continue
        begin = row["query_start"]
        end = begin + row["query_representatives"]
        assert max(begin, first) >= min(end, last), str(path)

    cells = sum(ledger[key] for key in (
        "completed_disjoint_M28_by_R27_cells",
        "completed_M32_extension_M28_by_R27_cells",
        "completed_M33_extension_M28_by_R27_cells",
        "completed_M34_extension_M28_by_R27_cells"))
    added = (M34 // M28) * (R31 // R27)
    assert added == 1024
    fraction = (
        M28 / base["zero_pair_key_cap_before_accidental_collisions"]
        * R27 * base["factor_base"]["signed_frobenius_orbit_size"]
        / base["unordered_query_pair_domain"])
    mean = base["heuristic_mean_four_point_multisets"]
    before = work.intensity(cells, cell_fraction=fraction, mean=mean)
    charged = int(ledger["completed_selected_route_field_calls"])
    per_job = field_calls(M34, R31)
    cdf = [0.0]
    jobs = []
    for index in range(1, JOBS + 1):
        intensity = work.intensity(cells + index * added,
                                   cell_fraction=fraction, mean=mean)
        probability = -math.expm1(-(intensity - before))
        assert probability > cdf[-1]
        cdf.append(probability)
        calls = charged + index * per_job
        jobs.append({
            "job_index": index,
            "query_start": first + (index - 1) * R31,
            "query_end_exclusive": first + index * R31,
            "fresh_M28_by_R27_cells": added,
            "cumulative_model_hit_probability": probability,
            "cumulative_modeled_field_calls_including_credited_history": str(calls),
            "cumulative_modeled_field_calls_log2": math.log2(calls),
        })
    if sha(LEDGER) == q1086["coverage_ledger_sha256"]:
        assert math.isclose(
            jobs[0]["cumulative_model_hit_probability"],
            q1086["finite_support_placement_model_hit_probability_at_screen"],
            rel_tol=1e-12)
    expected_index = sum(index * (cdf[index] - cdf[index - 1])
                         for index in range(1, JOBS + 1)) / cdf[-1]
    expected_calls = charged + expected_index * per_job
    quantiles = {}
    for label in ("0.5", "0.8", "0.9", "0.95"):
        index = next((i for i in range(1, JOBS + 1)
                      if cdf[i] >= float(label)), None)
        quantiles[label] = (None if index is None else {
            "job_index": index,
            "modeled_field_calls_log2": jobs[index - 1][
                "cumulative_modeled_field_calls_log2"],
        })
    result = {
        "kind": "n83_q1087_eight_disjoint_M34_R31_conditional_search_projection",
        "proposal_id": "Q1087", "candidate_id": None, "run_id": None,
        "status": "design_only_no_wave_dispatch",
        "curve_id": screen["curve_id"], "curve_identity_record": screen[
            "curve_identity_record"], "isogeny": "none",
        "factor_base": screen["factor_base"],
        "public_target": screen["public_target"], "target_count": 1,
        "table_start": 0, "table_descriptors_per_job": M34,
        "query_representatives_per_job": R31,
        "bits_per_key": 16, "hashes": 10,
        "completed_credited_cells_at_screen": cells,
        "completed_credited_modeled_field_calls_at_screen": str(charged),
        "modeled_field_calls_per_job": str(per_job),
        "modeled_field_calls_per_job_log2": math.log2(per_job),
        "jobs": jobs,
        "conditional_expected_first_hit_job_given_hit_by_eight": expected_index,
        "conditional_expected_search_field_calls_given_hit_by_eight_log2":
            math.log2(expected_calls),
        "first_hit_quantiles": quantiles,
        "model_probability_of_hit_by_eight": cdf[-1],
        "model_probability_of_no_hit_by_eight": 1 - cdf[-1],
        "measured_natural_relation_count": 0,
        "measured_complete_solve_work_log2": None,
        "screen_sha256": sha(SCREEN), "base_sha256": sha(BASE),
        "coverage_ledger_sha256": sha(LEDGER),
        "Q1086_feasibility_sha256": sha(Q1086),
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "The eight jobs are a projection only; dispatch requires a separate audited plan after Q1086's first terminal result.",
            "Q1074 and Q1083 are active at this frozen screen; their work and coverage are excluded until terminal audits.",
            "Probabilities use the frozen finite-support placement heuristic, not a measured n=83 natural-relation rate.",
            "A no-hit outcome is possible; the eight-job route is not a complete-solve guarantee.",
            "Every job rebuilds its M34 table, and the work model includes credited historical attempts but excludes failed or active work of unknown cost.",
            "Field calls omit Bloom and keying, memory and disk, setup, and independent scalar replay; wall time and full-size ARM RSS are unmeasured.",
            "The known-log base could yield a direct scalar from a verified exact hit, but no such n=83 hit or scalar has been observed.",
        ],
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "proposal_id": "Q1087", "jobs": JOBS,
        "model_hit_probability": cdf[-1],
        "conditional_expected_search_field_calls_log2": math.log2(expected_calls),
        "all_eight_search_field_calls_log2": jobs[-1][
            "cumulative_modeled_field_calls_log2"],
        "complete_solve_work_log2": None,
    }))


if __name__ == "__main__":
    main()
