#!/usr/bin/env python3
"""Freeze a Q1074-audited, pre-Q1086 first-hit search estimate.

Q1086 is active and therefore projected, not credited. This estimates
search-stage field API calls only; it cannot estimate complete DLP work.
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
PLAN = HERE / "n83_q1086_local_m34_plan.json"
STARTED = HERE / "runs/n83_local_arm_m34_r31_q1086.started.json"
Q1074 = HERE / "runs/n83_local_arm_m33_r30_q1074.json"
Q1074_AUDIT = HERE / "runs/n83_local_arm_m33_r30_q1074_sage_verify.json"
OUTPUT = HERE / "n83_q1089_post_q1074_projection.json"
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
    plan = json.loads(PLAN.read_text())
    started = json.loads(STARTED.read_text())
    q1074 = json.loads(Q1074.read_text())
    audit = json.loads(Q1074_AUDIT.read_text())
    validate_reference(screen)
    assert all(row["curve_id"] == screen["curve_id"] and
               row["isogeny"] == "none" and
               row["candidate_id"] is None for row in
               (base, ledger, plan, started, q1074))
    assert all(row["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"] for row in
        (ledger, plan, started))
    assert q1074["factor_base"]["enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert plan["coverage_ledger_sha256"] != sha(LEDGER), (
        "the ledger must include the Q1086 start marker")
    assert len(ledger["pending_Q1086_terminal_receipts"]) == 1
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    assert ledger["complete_solve_work_log2"] is None
    assert q1074["native_result"]["exact_hit_queries"] == 0
    assert audit["receipt_sha256"] == sha(Q1074)
    assert audit["verified_relation_count"] == 0
    assert any(entry["path"] == str(Q1074.relative_to(REPO)) and
               entry["sha256"] == sha(Q1074)
               for entry in ledger["completed_receipts"])
    assert started["query_start"] == plan["query_start"] == 50 * (1 << 30)
    assert started["query_representatives"] == plan[
        "query_representatives"] == R31
    assert started["table_descriptors"] == plan["table_descriptors"] == M34
    assert started["sage_runtime_info_sha256"]
    assert started["native_source_sha256"] == plan[
        "portable_native_source_sha256"]
    assert plan["finite_support_placement_model_hit_probability"] > 0
    first = plan["query_start"]
    last = first + JOBS * R31
    domain = math.comb(screen["factor_base"][
        "signed_frobenius_columns"], 2) * screen["factor_base"][
            "signed_frobenius_orbit_size"]
    assert last <= domain
    for entry in ledger["completed_receipts"]:
        row = json.loads((REPO / entry["path"]).read_text())
        begin, end = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(begin, first) >= min(end, last), entry["path"]
    for path in (HERE / "runs").rglob("*.started.json"):
        row = json.loads(path.read_text())
        if row.get("curve_id") != screen["curve_id"]:
            continue
        begin, end = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        if max(begin, first) < min(end, last):
            assert path == STARTED

    cells = sum(ledger[key] for key in (
        "completed_disjoint_M28_by_R27_cells",
        "completed_M32_extension_M28_by_R27_cells",
        "completed_M33_extension_M28_by_R27_cells",
        "completed_M34_extension_M28_by_R27_cells"))
    charged = int(ledger["completed_selected_route_field_calls"])
    added = (M34 // M28) * (R31 // R27)
    assert added == 1024
    per_job = field_calls(M34, R31)
    assert str(per_job) == plan["modeled_native_field_calls"]
    fraction = (M28 / base["zero_pair_key_cap_before_accidental_collisions"]
                * R27 * base["factor_base"]["signed_frobenius_orbit_size"]
                / base["unordered_query_pair_domain"])
    mean = base["heuristic_mean_four_point_multisets"]
    before = work.intensity(cells, cell_fraction=fraction, mean=mean)
    cdf = [0.0]
    rows = []
    for index in range(1, JOBS + 1):
        delta = work.intensity(cells + index * added,
                               cell_fraction=fraction, mean=mean) - before
        probability = -math.expm1(-delta)
        assert probability > cdf[-1]
        cdf.append(probability)
        calls = charged + index * per_job
        rows.append({
            "job_index": index,
            "query_start": first + (index - 1) * R31,
            "query_end_exclusive": first + index * R31,
            "cumulative_model_hit_probability": probability,
            "cumulative_search_field_calls_log2": math.log2(calls),
        })
    assert math.isclose(cdf[1], plan[
        "finite_support_placement_model_hit_probability"], rel_tol=1e-12)
    expected_index = sum(index * (cdf[index] - cdf[index - 1])
                         for index in range(1, JOBS + 1)) / cdf[-1]
    result = {
        "kind": "n83_q1089_post_q1074_conditional_first_hit_search_projection",
        "proposal_id": "Q1089", "candidate_id": None, "run_id": None,
        "status": "design_only_q1086_active_uncredited",
        "curve_id": screen["curve_id"],
        "curve_identity_record": screen["curve_identity_record"],
        "factor_base": screen["factor_base"],
        "isogeny": "none", "public_target": screen["public_target"],
        "target_count": 1, "table_descriptors_per_job": M34,
        "query_representatives_per_job": R31,
        "completed_credited_cells": cells,
        "completed_credited_field_calls": str(charged),
        "per_job_modeled_field_calls": str(per_job),
        "projected_jobs": rows,
        "model_hit_probability_by_eight": cdf[-1],
        "model_no_hit_probability_by_eight": 1 - cdf[-1],
        "conditional_expected_first_hit_job_given_hit_by_eight": expected_index,
        "conditional_expected_search_field_calls_log2": math.log2(
            charged + expected_index * per_job),
        "all_eight_search_field_calls_log2": math.log2(
            charged + JOBS * per_job),
        "rate_sensitivity": [{
            "intensity_multiplier": factor,
            "model_hit_probability_by_eight": -math.expm1(
                factor * math.log1p(-cdf[-1])),
        } for factor in (0.25, 0.5, 1.0)],
        "measured_natural_relations": 0,
        "measured_complete_solve_work_log2": None,
        "data_only_positive_yield_lower_bound": 0,
        "data_only_finite_first_hit_work_upper_bound": None,
        "screen_sha256": sha(SCREEN), "base_sha256": sha(BASE),
        "coverage_ledger_sha256": sha(LEDGER),
        "Q1086_plan_sha256": sha(PLAN),
        "Q1086_start_sha256": sha(STARTED),
        "Q1074_receipt_sha256": sha(Q1074),
        "Q1074_sage_audit_sha256": sha(Q1074_AUDIT),
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "A first-hit search model is not an estimate or bound for complete DLP work.",
            "The finite-support placement rate has not been validated by a natural n83 relation.",
            "Q1086 and Q1083 are pending and excluded from credited historical work.",
            "A hit requires a terminal receipt and independent checked-Sage scalar replay.",
            "Field API calls omit Bloom, memory, SSD, setup, failed work with unknown counts, and replay; no operation-equivalent total is available.",
            "These projected jobs do not authorize a follow-on launch.",
        ],
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "completed_credited_cells", "model_hit_probability_by_eight",
        "conditional_expected_search_field_calls_log2",
        "all_eight_search_field_calls_log2",
        "measured_complete_solve_work_log2")}))


if __name__ == "__main__":
    main()
