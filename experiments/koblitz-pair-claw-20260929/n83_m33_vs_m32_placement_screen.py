#!/usr/bin/env python3
"""Compare frozen finite-support yield per field call on fresh N83 ranges."""

import hashlib
import json
import math
from pathlib import Path

import n83_full_spill_work as work
from n83_full_spill_screen import field_calls

HERE = Path(__file__).resolve().parent
BASE = HERE / "n83_large_knownlog_base_screen.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
Q1074 = HERE / "n83_local_arm_m33_r30_q1074_plan.json"
OUTPUT = HERE / "n83_m33_vs_m32_placement_screen.json"
M28 = 1 << 28
R27 = 1 << 27


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base = json.loads(BASE.read_text())
    ledger = json.loads(LEDGER.read_text())
    q1074 = json.loads(Q1074.read_text())
    assert ledger["curve_id"] == q1074["curve_id"] == (
        "EC1N83Ckb1h876c2921cb64")
    assert ledger["isogeny"] == q1074["isogeny"] == "none"
    assert ledger["factor_base_enumerated_set_sha256"] == q1074[
        "factor_base_enumerated_set_sha256"] == base["factor_base"][
            "enumerated_set_sha256"]
    assert ledger["actual_usable_points_B_before_folding"] == 8000204
    assert ledger["signed_frobenius_columns"] == 48194
    assert ledger["complete_solve_work_log2"] is None
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    assert q1074["table_descriptors"] == 1 << 33
    assert q1074["query_representatives"] == 1 << 30
    assert int(q1074["modeled_native_field_calls"]) == field_calls(
        1 << 33, 1 << 30)

    primary = ledger["completed_disjoint_M28_by_R27_cells"]
    m32_extension = ledger["completed_M32_extension_M28_by_R27_cells"]
    m33_extension = ledger["completed_M33_extension_M28_by_R27_cells"]
    completed_cells = primary + m32_extension + m33_extension
    cell_fraction = (
        M28 / base["zero_pair_key_cap_before_accidental_collisions"]
        * R27 * base["factor_base"]["signed_frobenius_orbit_size"]
        / base["unordered_query_pair_domain"])
    mean = base["heuristic_mean_four_point_multisets"]
    baseline = work.intensity(
        completed_cells, cell_fraction=cell_fraction, mean=mean)

    def route(name, table_descriptors, query_representatives, jobs):
        added_cells = jobs * (table_descriptors // M28) * (
            query_representatives // R27)
        delta = work.intensity(
            completed_cells + added_cells,
            cell_fraction=cell_fraction, mean=mean) - baseline
        calls = jobs * field_calls(table_descriptors,
                                  query_representatives)
        return {
            "shape": name,
            "jobs": jobs,
            "table_descriptors_per_job": table_descriptors,
            "query_representatives_per_job": query_representatives,
            "additional_unique_M28_R27_cells_if_disjoint": added_cells,
            "modeled_additional_hit_intensity": delta,
            "modeled_hit_probability": -math.expm1(-delta),
            "modeled_native_field_calls": str(calls),
            "modeled_native_field_calls_log2": math.log2(calls),
            "modeled_field_calls_per_unit_hit_intensity": calls / delta,
        }

    m32 = route("M32_R29_one_fresh_group", 1 << 32, 1 << 29, 1)
    four_m32 = route("M32_R29_four_fresh_groups", 1 << 32, 1 << 29, 4)
    m33 = route("M33_R30_one_fresh_group", 1 << 33, 1 << 30, 1)
    assert m33["additional_unique_M28_R27_cells_if_disjoint"] == (
        four_m32["additional_unique_M28_R27_cells_if_disjoint"])
    assert math.isclose(m33["modeled_additional_hit_intensity"],
                        four_m32["modeled_additional_hit_intensity"])
    assert int(m33["modeled_native_field_calls"]) * 2 == int(
        four_m32["modeled_native_field_calls"])
    report = {
        "kind": "n83_fresh_disjoint_M33_R30_vs_M32_R29_placement_screen",
        "compared_proposal_ids": ["Q1074", "Q1079"],
        "candidate_id": None, "run_id": None,
        "curve_id": ledger["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": ledger[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "completed_unique_cells_at_screen": completed_cells,
        "active_Q1074_and_Q1081_excluded": True,
        "routes": [m32, four_m32, m33],
        "M33_R30_vs_four_M32_R29_modeled_field_call_saving_fraction":
            1 - int(m33["modeled_native_field_calls"]) / int(
                four_m32["modeled_native_field_calls"]),
        "limits": [
            "Hit probabilities are from the frozen finite-support placement heuristic, not measured natural yield.",
            "Each route is projected onto fresh disjoint query ranges; active Q1074 and Q1081 work is excluded.",
            "M33 needs more memory and its R30 target-online time has no terminal measurement yet.",
            "Field calls exclude keying, Bloom, memory, disk, setup, failed work, and scalar replay.",
            "This screen is not a complete DLP work estimate."
        ],
        "base_screen_sha256": sha(BASE),
        "coverage_ledger_sha256": sha(LEDGER),
        "Q1074_plan_sha256": sha(Q1074),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "M32_R29_one_hit_probability": m32["modeled_hit_probability"],
        "M33_R30_one_hit_probability": m33["modeled_hit_probability"],
        "M33_vs_four_M32_call_saving_fraction": report[
            "M33_R30_vs_four_M32_R29_modeled_field_call_saving_fraction"],
        "complete_solve_work_log2": None,
    }))


if __name__ == "__main__":
    main()
