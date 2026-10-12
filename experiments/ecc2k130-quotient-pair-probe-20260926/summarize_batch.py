#!/usr/bin/env python3
"""Validate matched batch-inversion receipts and emit stage-only records."""

import hashlib
import json
import math
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE.parent / "ic-candidate-catalog" /
                       "measurement_contract.json").read_text())
ONLINE_PHASES = ("target_query", "target_pdp", "target_relation_check",
                 "target_descent", "target_recovery_check")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def ci95(ratios, seed):
    rng = random.Random(seed)
    logs = [math.log(ratio) for ratio in ratios]
    values = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs))))
                    for _ in range(10000))
    return [values[249], values[9749]]


def stage_row(sample, receipt, path, reference):
    walls = {phase: 0 for phase in CONTRACT["phase_operations"]}
    walls["pdp"] = sum(row["wall_ns"] for row in sample["repetitions"])
    counts = {key: 0 for key in CONTRACT["required_counts"]}
    counts["effective_columns"] = 2
    result = {
        "schema_version": 2, "kind": "stage", "status": "budget",
        "termination_reason": "three fixed lookup prefixes on one ordinary target",
        "proposal_id": sample["proposal_id"], "candidate_id": None,
        "run_id": sample["run_id"], "workload_id": receipt["workload_id"],
        "pair_block_id": f"n{reference['field_degree']}_batch_r{sample['block']}",
        "source_curve_ref": receipt["curve_id"],
        "profile_id": f"n{reference['field_degree']}_weight2_two_orbit_m4",
        "isogeny_route_ref": "none", "subgroup_order": reference["subgroup_order"],
        "target_count": None,
        "target_point_sha256": hashlib.sha256(frozen(receipt["target"])).hexdigest(),
        "precomputation_ready": None,
        "online_phase_wall_ns": {phase: None for phase in ONLINE_PHASES},
        "online_wall_ns": None,
        "phase_operations": {phase: None for phase in CONTRACT["phase_operations"]},
        "phase_wall_ns": walls, "total_operations": None,
        "rho_operations": None, "rho_online_wall_ns": None,
        "rho_verified": None, "verified_scalar": False,
        "scalar_certificate_ref": None, "counts": counts,
        "peak_rss_bytes": receipt["peak_process_rss_bytes"],
        "wall_ns": walls["pdp"],
        "provenance": {
            "workload_fixture_sha256": hashlib.sha256(frozen(
                reference["workload"])).hexdigest(),
            "source_sha256": receipt["source_sha256"],
            "host_id": f"{receipt['machine']}_python{receipt['python']}",
            "resource_envelope_id": "one_process_one_thread_2048lookups_3repeats",
            "calibration_id": "field_api_vector_with_batch_xors_unpriced",
            "raw_receipt": str(path.relative_to(HERE)),
            "raw_receipt_sha256": sha(path),
            "actual_base_sha256": receipt["factor_base"]["base_sha256"],
            "bounded_prefix_repetitions_same_target": 3,
        },
    }
    assert result["run_id"].startswith(result["proposal_id"] + result["workload_id"])
    assert set(counts) == set(CONTRACT["required_counts"])
    assert set(walls) == set(CONTRACT["phase_operations"])
    assert all(result["provenance"].get(key) for key in CONTRACT["required_provenance"])
    return result


def main():
    existing = {json.loads(line)["proposal_id"] for line in
                (HERE.parent / "ic-candidate-catalog" / "candidates.jsonl").read_text().splitlines()}
    assert not existing.intersection({"Q1011", "Q1012"})
    proposals, rows, stage_rows = [], [], []
    for n, proposal_id in ((53, "Q1011"), (83, "Q1012")):
        path = HERE / "runs" / f"n{n}_batch_x_only_comparison.json"
        receipt = json.loads(path.read_text())
        reference_path = HERE / "runs" / f"n{n}_perf_prefix.json"
        reference = json.loads(reference_path.read_text())
        prior_path = HERE / "runs" / f"n{n}_x_only_comparison.json"
        assert receipt["source_sha256"] == sha(HERE / "compare_batch_x_only.py")
        assert all(value == sha(HERE / name) for name, value in receipt[
            "dependency_sha256"].items())
        assert receipt["frozen_reference_sha256"] == sha(reference_path)
        assert receipt["prior_x_only_receipt_sha256"] == sha(prior_path)
        assert receipt["curve_id"] == reference["curve_id"]
        assert receipt["curve_id"].endswith("h" + hashlib.sha256(frozen(
            receipt["curve_identity_record"])).hexdigest()[:12])
        assert receipt["workload_id"] == "W" + reference["workload_id"]
        assert receipt["factor_base"]["base_sha256"] == reference[
            "base"]["base_sha256"]
        assert receipt["index_build"]["index_sha256"] == json.loads(
            prior_path.read_text())["index_builds"]["xonly"]["index_sha256"]
        assert receipt["isogeny"] == "none" and receipt["candidate_id"] is None
        assert receipt["paired_blocks"] == 6 and receipt["repetitions_per_block"] == 3
        assert receipt["lookup_budget_per_repetition"] == 2048
        identity = receipt["curve_identity_record"]
        proposals.append({
            "proposal_id": proposal_id, "candidate_id": None,
            "status": "stage_only_incomplete_ic_pipeline", "measured_cost": None,
            "curve_id": receipt["curve_id"], "field": identity["field"],
            "curve": identity["curve"], "isogeny": "none",
            "endomorphism_order_conductor": None,
            "factor_base": {"construction": "first two rational normal-x weight-two orbits after subgroup projection",
                            **receipt["factor_base"]},
            "point_decomposition": {"summands": 4,
                                    "family": "complete_selected_base_signed_frobenius_pair_index",
                                    "canonicalization": "cyclic_x_only",
                                    "complement_addition": "one batch inversion per signed-Frobenius orbit",
                                    "lookup_prefix_budget": 2048,
                                    "query_repetitions": 3},
            "relation_collection": None, "relation_linear_algebra": None,
            "target_descent": None,
            "implementation_sha256": {"source": receipt["source_sha256"],
                                      **receipt["dependency_sha256"]},
            "frozen_reference_sha256": receipt["frozen_reference_sha256"],
        })
        ratios = []
        for block in range(1, 7):
            pair = {row["variant"]: row for row in receipt["samples"]
                    if row["block"] == block}
            assert set(pair) == {"affine", "batch"}
            for row in pair.values():
                assert len(row["repetitions"]) == 3
                assert all(item["status"] == "bounded_prefix" and
                           item["lookups"] == 2048 and
                           item["verified_hit_positions"] == []
                           for item in row["repetitions"])
                stage_rows.append(stage_row(row, receipt, path, reference))
            ratios.append(pair["affine"]["median_wall_ns"] /
                          pair["batch"]["median_wall_ns"])
        affine = next(row for row in receipt["samples"] if row["variant"] == "affine")
        batch = next(row for row in receipt["samples"] if row["variant"] == "batch")
        rows.append({
            "proposal_id": proposal_id, "candidate_id": None,
            "curve_id": receipt["curve_id"], "workload_id": receipt["workload_id"],
            "actual_base_B": receipt["factor_base"]["actual_usable_points_B_before_folding"],
            "effective_columns": 2, "index_keys": receipt["index_build"]["keys"],
            "lookups_per_repetition": 2048,
            "affine_field_api_operations_per_prefix": affine["repetitions"][0][
                "field_api_operations"],
            "batch_field_api_operations_per_prefix": batch["repetitions"][0][
                "field_api_operations"],
            "batch_count_per_prefix": batch["repetitions"][0]["batches"],
            "affine_over_batch_wall_ratio_geomean": math.exp(statistics.mean(
                map(math.log, ratios))),
            "paired_bootstrap_ci95": ci95(ratios, 280926 + n),
            "ratio_range": [min(ratios), max(ratios)],
            "blocks_batch_faster": sum(ratio > 1 for ratio in ratios),
            "ordinary_relation_yield_estimate": None,
            "verified_single_target_dlp": False,
            "receipt_path": str(path.relative_to(HERE)),
            "receipt_sha256": sha(path),
        })
    (HERE / "batch_stage_proposals.json").write_text(json.dumps(proposals, indent=2) + "\n")
    (HERE / "batch_stage_runs.jsonl").write_text("".join(
        json.dumps(row, sort_keys=True) + "\n" for row in stage_rows))
    (HERE / "batch_stage_comparison.json").write_text(json.dumps({
        "kind": "paired_x_only_batch_inversion_stage_comparison",
        "candidate_id": None,
        "claim_boundary": "bounded stage and field API vector only; no ordinary relation yield or verified DLP",
        "rows": rows,
        "source_sha256": sha(Path(__file__)),
    }, indent=2) + "\n")
    for row in rows:
        print(row["proposal_id"], row["curve_id"],
              "affine_over_batch=%.3f" % row["affine_over_batch_wall_ratio_geomean"])


if __name__ == "__main__":
    main()
