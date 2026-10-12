#!/usr/bin/env python3
"""Validate bounded n53/n83 receipts and register stage proposal identities."""

import hashlib
import json
import math
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = HERE.parent / "ic-candidate-catalog" / "candidates.jsonl"
CONTRACT = json.loads((HERE.parent / "ic-candidate-catalog" /
                       "measurement_contract.json").read_text())
ONLINE_PHASES = ("target_query", "target_pdp", "target_relation_check",
                 "target_descent", "target_recovery_check")


def validate_stage_row(row):
    assert row["schema_version"] == 2 and row["kind"] == "stage"
    assert row["status"] == "budget" and row["candidate_id"] is None
    assert row["proposal_id"] in {"Q1007", "Q1008", "Q1009", "Q1010"}
    assert row["run_id"].startswith(row["proposal_id"] + row["workload_id"])
    assert row["isogeny_route_ref"] == "none"
    assert row["online_wall_ns"] is None and row["total_operations"] is None
    assert row["rho_online_wall_ns"] is None and row["verified_scalar"] is False
    assert set(row["counts"]) == set(CONTRACT["required_counts"])
    assert row["counts"]["effective_columns"] == 2
    assert set(row["phase_operations"]) == set(CONTRACT["phase_operations"])
    assert all(value is None for value in row["phase_operations"].values())
    assert set(row["phase_wall_ns"]) == set(CONTRACT["phase_operations"])
    assert sum(row["phase_wall_ns"].values()) == row["wall_ns"]
    assert all(value is None for value in row["online_phase_wall_ns"].values())
    assert all(row["provenance"].get(key) for key in CONTRACT["required_provenance"])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def bootstrap_ci(ratios, seed):
    rng = random.Random(seed)
    logs = [math.log(value) for value in ratios]
    draws = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs))))
                   for _ in range(10000))
    return [draws[249], draws[9749]]


def read_receipt(degree, variant):
    family = "cycle" if variant == "cycle" else "x_only"
    path = HERE / "runs" / f"n{degree}_{family}_comparison.json"
    report = json.loads(path.read_text())
    reference_path = HERE / "runs" / f"n{degree}_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    assert report["frozen_reference_sha256"] == sha(reference_path)
    assert report["curve_id"] == reference["curve_id"]
    assert report["curve_identity_record"] == reference["curve_identity_record"]
    assert report["curve_id"].endswith("h" + hashlib.sha256(
        frozen(report["curve_identity_record"])).hexdigest()[:12])
    assert report["workload_id"] == "W" + reference["workload_id"]
    assert report["factor_base"]["base_sha256"] == reference["base"]["base_sha256"]
    assert report["factor_base"]["actual_usable_points_B_before_folding"] == reference[
        "base"]["actual_usable_points_B"]
    assert report["factor_base"]["effective_columns_after_sign_frobenius_folding"] == 2
    assert report["index_builds"]["xfirst"]["index_sha256"] == reference[
        "index_prefix"]["index_prefix_sha256"]
    assert report["index_builds"][variant]["keys"] == report["index_builds"]["xfirst"]["keys"]
    assert report["isogeny"] == "none" and report["candidate_id"] is None
    assert report["verified_full_dlp_work_log2"] is None
    assert report["verified_single_target_online_work_log2"] is None
    assert report["source_sha256"] == sha(HERE / ("compare_cycle.py" if variant == "cycle"
                                           else "compare_x_only.py"))
    assert all(value == sha(HERE / name)
               for name, value in report["dependency_sha256"].items())
    assert report["paired_blocks"] == 6 and report["repetitions_per_block"] == 3
    assert report["lookup_budget_per_repetition"] == 2048
    pairs = []
    for block in range(1, 7):
        rows = {row["variant"]: row for row in report["samples"] if row["block"] == block}
        assert set(rows) == {"xfirst", variant}
        for name, row in rows.items():
            assert row["run_id"].startswith(row["proposal_id"] + report["workload_id"])
            assert len(row["repetitions"]) == 3
            assert all(r["status"] == "bounded_prefix" and r["lookups"] == 2048
                       for r in row["repetitions"])
            assert all(r["verified_hit_positions"] == [] for r in row["repetitions"])
        pairs.append(rows["xfirst"]["median_wall_ns"] / rows[variant]["median_wall_ns"])
    return path, report, pairs


def main():
    existing = {json.loads(line)["proposal_id"] for line in CATALOG.read_text().splitlines()}
    assert not existing.intersection({"Q1007", "Q1008", "Q1009", "Q1010"})
    proposals = []
    rows = []
    stage_rows = []
    for degree in (53, 83):
        for variant in ("cycle", "xonly"):
            path, report, ratios = read_receipt(degree, variant)
            proposal_id = {("cycle", 53): "Q1007", ("cycle", 83): "Q1008",
                           ("xonly", 53): "Q1009", ("xonly", 83): "Q1010"}[(variant, degree)]
            assert {r["proposal_id"] for r in report["samples"] if r["variant"] == (
                "cycle" if variant == "cycle" else "xonly")} == {proposal_id}
            identity = report["curve_identity_record"]
            proposals.append({
                "proposal_id": proposal_id, "candidate_id": None,
                "status": "stage_only_incomplete_ic_pipeline", "measured_cost": None,
                "curve_id": report["curve_id"], "field": identity["field"],
                "curve": identity["curve"], "isogeny": "none",
                "endomorphism_order_conductor": None,
                "factor_base": {"construction": "first two rational normal-x weight-two orbits after subgroup projection",
                                **report["factor_base"]},
                "point_decomposition": {"summands": 4,
                                        "family": "complete_selected_base_signed_frobenius_pair_index",
                                        "summation_polynomial_or_chain": "none",
                                        "canonicalization": variant,
                                        "lookup_prefix_budget": 2048,
                                        "query_repetitions": 3},
                "relation_collection": None, "relation_linear_algebra": None,
                "target_descent": None,
                "implementation_sha256": {"source": report["source_sha256"],
                                          **report["dependency_sha256"]},
                "frozen_reference_sha256": report["frozen_reference_sha256"]})
            reference = json.loads((HERE / "runs" / f"n{degree}_perf_prefix.json").read_text())
            for sample in report["samples"]:
                if sample["variant"] != variant:
                    continue
                phase_walls = {key: 0 for key in CONTRACT["phase_operations"]}
                phase_walls["pdp"] = sum(r["wall_ns"] for r in sample["repetitions"])
                counts = {key: 0 for key in CONTRACT["required_counts"]}
                counts["effective_columns"] = 2
                stage = {
                    "schema_version": 2, "kind": "stage", "status": "budget",
                    "termination_reason": "three fixed lookup prefixes on one ordinary target",
                    "proposal_id": proposal_id, "candidate_id": None,
                    "run_id": sample["run_id"], "workload_id": report["workload_id"],
                    "pair_block_id": f"n{degree}_{variant}_r{sample['block']}",
                    "source_curve_ref": report["curve_id"],
                    "profile_id": f"n{degree}_weight2_two_orbit_m4",
                    "isogeny_route_ref": "none",
                    "subgroup_order": reference["subgroup_order"],
                    "target_count": None,
                    "target_point_sha256": hashlib.sha256(frozen(report["target"])).hexdigest(),
                    "precomputation_ready": None,
                    "online_phase_wall_ns": {key: None for key in ONLINE_PHASES},
                    "online_wall_ns": None,
                    "phase_operations": {key: None for key in CONTRACT["phase_operations"]},
                    "phase_wall_ns": phase_walls,
                    "total_operations": None, "rho_operations": None,
                    "rho_online_wall_ns": None, "rho_verified": None,
                    "verified_scalar": False, "scalar_certificate_ref": None,
                    "counts": counts,
                    "peak_rss_bytes": report["peak_process_rss_bytes"],
                    "wall_ns": phase_walls["pdp"],
                    "provenance": {
                        "workload_fixture_sha256": hashlib.sha256(frozen(
                            reference["workload"])).hexdigest(),
                        "source_sha256": report["source_sha256"],
                        "host_id": f"{report['machine']}_python{report['python']}",
                        "resource_envelope_id": "one_process_one_thread_2048lookups_3repeats",
                        "calibration_id": "point_and_word_operation_vectors_unpriced",
                        "raw_receipt": str(path.relative_to(HERE)),
                        "raw_receipt_sha256": sha(path),
                        "actual_base_sha256": report["factor_base"]["base_sha256"],
                        "bounded_prefix_repetitions_same_target": 3,
                    },
                }
                validate_stage_row(stage)
                stage_rows.append(stage)
            rows.append({
                "proposal_id": proposal_id, "candidate_id": None,
                "curve_id": report["curve_id"], "workload_id": report["workload_id"],
                "actual_base_B": report["factor_base"]["actual_usable_points_B_before_folding"],
                "effective_columns": 2,
                "index_keys": report["index_builds"][variant]["keys"],
                "lookup_budget_per_repetition": 2048,
                "paired_blocks": 6, "repetitions_per_block": 3,
                "xfirst_over_variant_query_geomean": math.exp(statistics.mean(
                    math.log(ratio) for ratio in ratios)),
                "paired_block_bootstrap_ci95": bootstrap_ci(ratios, 270926 + degree),
                "ratio_range": [min(ratios), max(ratios)],
                "blocks_variant_faster": sum(ratio > 1 for ratio in ratios),
                "index_build_xfirst_ns": report["index_builds"]["xfirst"]["wall_ns"],
                "index_build_variant_ns": report["index_builds"][variant]["wall_ns"],
                "canonical_operations_per_miss": report["samples"][1]["repetitions"][0][
                    "canonical_operations"],
                "verified_hits_in_prefix": 0,
                "ordinary_relation_yield_estimate": None,
                "verified_single_target_dlp": False,
                "receipt_path": str(path.relative_to(HERE)),
                "receipt_sha256": sha(path)})
    (HERE / "cycle_stage_proposals.json").write_text(json.dumps(proposals, indent=2) + "\n")
    (HERE / "cycle_stage_runs.jsonl").write_text("".join(
        json.dumps(row, sort_keys=True) + "\n" for row in stage_rows))
    (HERE / "cycle_stage_comparison.json").write_text(json.dumps({
        "kind": "matched_onb_cycle_quotient_stage_comparison",
        "candidate_id": None,
        "claim_boundary": "bounded stage only; no measured relation yield, complete DLP, or sub-2^61 work",
        "rows": rows,
        "source_sha256": sha(Path(__file__)),
    }, indent=2) + "\n")
    for row in rows:
        print(row["proposal_id"], row["curve_id"],
              "speedup=%.2f" % row["xfirst_over_variant_query_geomean"])


if __name__ == "__main__":
    main()
