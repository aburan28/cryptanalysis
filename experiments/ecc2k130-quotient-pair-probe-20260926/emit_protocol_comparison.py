#!/usr/bin/env python3
"""Register stage proposals and emit version-2 matched-run records."""

import hashlib
import json
import math
import random
import statistics
from pathlib import Path

from compare_canonical import PROPOSALS

HERE = Path(__file__).resolve().parent
CATALOG = HERE.parent / "ic-candidate-catalog"
CONTRACT = json.loads((CATALOG / "measurement_contract.json").read_text())
ONLINE_TARGET_PHASES = ("target_query", "target_pdp", "target_relation_check",
                        "target_descent", "target_recovery_check")


def frozen_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bootstrap_geomean_ci95(ratios, seed):
    rng = random.Random(seed)
    logs = [math.log(value) for value in ratios]
    draws = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs))))
                   for _ in range(10000))
    return [draws[249], draws[9749]]


def stage_row(raw, raw_path, reference):
    phases = {key: None for key in CONTRACT["phase_operations"]}
    walls = {key: 0 for key in CONTRACT["phase_operations"]}
    walls["factor_base"] = raw["factor_base"]["base_build_ns"]
    walls["precompute"] = raw["index_build"]["wall_ns"]
    walls["pdp"] = sum(query["wall_ns"] for query in raw["query_runs"])
    counts = {key: 0 for key in CONTRACT["required_counts"]}
    counts["effective_columns"] = raw["factor_base"][
        "effective_columns_after_sign_frobenius_folding"]
    if sum(walls.values()) > raw["run_wall_ns"]:
        raise AssertionError("recorded stage phases exceed measured run wall time")
    workload_fixture_sha256 = hashlib.sha256(
        frozen_bytes(reference["workload"])).hexdigest()
    return {
        "schema_version": 2, "kind": "stage", "status": "budget",
        "termination_reason": "fixed_lookup_prefix; no complete PDP attempt",
        "proposal_id": raw["proposal_id"], "candidate_id": None,
        "run_id": raw["run_id"], "workload_id": "W" + raw["workload_id"],
        "pair_block_id": raw["pair_block_id"],
        "source_curve_ref": raw["curve_id"],
        "profile_id": f"n{raw['field_degree']}_weight2_two_orbit_m4",
        "isogeny_route_ref": "none",
        "subgroup_order": raw["subgroup_order"],
        "target_count": None, "target_point_sha256": raw["target_point_sha256"],
        "precomputation_ready": None,
        "online_phase_wall_ns": {key: None for key in ONLINE_TARGET_PHASES},
        "online_wall_ns": None,
        "phase_operations": phases, "phase_wall_ns": walls,
        "total_operations": None,
        "rho_operations": None, "rho_online_wall_ns": None, "rho_verified": None,
        "verified_scalar": False, "scalar_certificate_ref": None,
        "counts": counts,
        "peak_rss_bytes": raw["peak_process_rss_bytes"],
        "wall_ns": raw["run_wall_ns"],
        "provenance": {
            "workload_fixture_sha256": workload_fixture_sha256,
            "source_sha256": raw["source_sha256"],
            "host_id": f"{raw['machine']}_python{raw['python']}",
            "resource_envelope_id": f"one_process_one_thread_{raw['lookup_budget_per_repetition']}lookups_{raw['query_repetitions']}repeats",
            "calibration_id": "point_and_field_operation_vectors_unpriced",
            "raw_receipt": str(raw_path.relative_to(HERE)),
            "raw_receipt_sha256": digest(raw_path),
            "actual_base_sha256": raw["factor_base"]["base_sha256"],
            "bounded_prefix_repetitions_same_target": raw["query_repetitions"],
        },
    }


def validate_stage_row(row):
    """Fail closed on the version-2 stage fields used by this experiment."""
    assert row["schema_version"] == 2 and row["kind"] == "stage"
    assert row["status"] == "budget" and row["candidate_id"] is None
    assert row["proposal_id"] in PROPOSALS.values()
    assert row["run_id"].startswith(row["proposal_id"] + row["workload_id"])
    assert row["isogeny_route_ref"] == "none"
    assert row["total_operations"] is None and row["online_wall_ns"] is None
    assert row["rho_operations"] is None and row["rho_online_wall_ns"] is None
    assert row["verified_scalar"] is False
    assert set(row["counts"]) == set(CONTRACT["required_counts"])
    assert row["counts"]["effective_columns"] == 2
    assert all(value == 0 for key, value in row["counts"].items()
               if key != "effective_columns")
    assert set(row["phase_operations"]) == set(CONTRACT["phase_operations"])
    assert all(value is None for value in row["phase_operations"].values())
    assert set(row["phase_wall_ns"]) == set(CONTRACT["phase_operations"])
    assert sum(row["phase_wall_ns"].values()) <= row["wall_ns"]
    assert set(row["online_phase_wall_ns"]) == set(ONLINE_TARGET_PHASES)
    assert all(value is None for value in row["online_phase_wall_ns"].values())
    assert all(row["provenance"].get(key) for key in CONTRACT["required_provenance"])


def main():
    existing_ids = {json.loads(line)["proposal_id"] for line in
                    (CATALOG / "candidates.jsonl").read_text().splitlines()}
    if existing_ids.intersection(PROPOSALS.values()):
        raise AssertionError("stage proposal ID collides with generated catalog")
    proposals = []
    rows = []
    comparisons = []
    curve_manifest = {row["curve_id"]: row for row in
                      json.loads((HERE / "curve_manifest.json").read_text())}
    for degree in (53, 83, 131):
        reference_name = ("n131_stage_reference.json" if degree == 131
                          else f"n{degree}_perf_prefix.json")
        reference_path = HERE / "runs" / reference_name
        reference = json.loads(reference_path.read_text())
        identity_sha = hashlib.sha256(frozen_bytes(
            reference["curve_identity_record"])).hexdigest()
        assert reference["curve_id"].endswith("h" + identity_sha[:12])
        assert curve_manifest[reference["curve_id"]]["identity_sha256"] == identity_sha
        assert curve_manifest[reference["curve_id"]]["identity_record"] == reference["curve_identity_record"]
        reference_source = ("freeze_n131_stage_reference.py" if degree == 131
                            else "perf_probe.py")
        assert reference["source_sha256"] == digest(HERE / reference_source)
        for variant in ("scan", "xfirst"):
            proposal_id = PROPOSALS[(degree, variant)]
            proposals.append({
                "proposal_id": proposal_id, "candidate_id": None,
                "status": "stage_only_incomplete_ic_pipeline",
                "measured_cost": None,
                "curve_id": reference["curve_id"],
                "field": reference["curve_identity_record"]["field"],
                "curve": reference["curve_identity_record"]["curve"],
                "isogeny": "none", "isogeny_route_ref": "none",
                "endomorphism_order_conductor": None,
                "factor_base": {
                    "construction": reference["base_policy"],
                    "normal_x_weight": 2,
                    "selected_rational_x_orbits": 2,
                    "geometric_points_before_projection": 4 * degree,
                    "actual_usable_points_B_before_folding": reference["base"]["actual_usable_points_B"],
                    "effective_columns_after_sign_frobenius_folding": 2,
                    "base_sha256": reference["base"]["base_sha256"],
                },
                "point_decomposition": {
                    "summands": 4,
                    "family": "complete_selected_base_signed_frobenius_pair_index",
                    "summation_polynomial_or_chain": "none",
                    "canonicalization": variant,
                    "lookup_prefix_budget": 2048,
                    "query_repetitions": 3,
                },
                "relation_collection": None,
                "relation_linear_algebra": None,
                "target_descent": None,
                "implementation_sha256": {
                    name: digest(HERE / name) for name in (
                        "compare_canonical.py", "fast_canonical.py",
                        "perf_probe.py", "quotient_pair_probe.py",
                        "field.py", "curves.py")},
                "frozen_reference_sha256": digest(reference_path),
            })
        pair_rows = []
        for run_number in range(1, 7):
            pair = {}
            for variant in ("scan", "xfirst"):
                raw_path = HERE / "runs" / f"n{degree}_{variant}_r{run_number}.json"
                raw = json.loads(raw_path.read_text())
                assert raw["field_degree"] == degree and raw["variant"] == variant
                assert raw["proposal_id"] == PROPOSALS[(degree, variant)]
                assert raw["curve_id"] == reference["curve_id"]
                assert raw["workload_id"] == reference["workload_id"]
                assert raw["factor_base"]["base_sha256"] == reference["base"]["base_sha256"]
                assert raw["frozen_reference_sha256"] == digest(reference_path)
                assert raw["source_sha256"] == digest(HERE / "compare_canonical.py")
                assert all(raw["dependency_sha256"][name] == digest(HERE / name)
                           for name in raw["dependency_sha256"])
                assert raw["index_build"]["index_sha256"] == reference["index_prefix"]["index_prefix_sha256"]
                assert raw["lookup_budget_per_repetition"] == 2048
                assert raw["query_repetitions"] == 3
                assert all(query["status"] == "budgeted_prefix" and
                           query["lookups"] == 2048 for query in raw["query_runs"])
                row = stage_row(raw, raw_path, reference)
                validate_stage_row(row)
                rows.append(row)
                pair[variant] = raw
            assert pair["scan"]["pair_block_id"] == pair["xfirst"]["pair_block_id"]
            assert [q["hit_positions"] for q in pair["scan"]["query_runs"]] == [
                q["hit_positions"] for q in pair["xfirst"]["query_runs"]]
            pair_rows.append({
                "pair_block_id": pair["scan"]["pair_block_id"],
                "scan_query_median_ns": pair["scan"]["query_wall_ns_median"],
                "xfirst_query_median_ns": pair["xfirst"]["query_wall_ns_median"],
                "query_ratio_scan_over_xfirst": pair["scan"]["query_wall_ns_median"] /
                    pair["xfirst"]["query_wall_ns_median"],
                "scan_index_build_ns": pair["scan"]["index_build"]["wall_ns"],
                "xfirst_index_build_ns": pair["xfirst"]["index_build"]["wall_ns"],
                "verified_hits_per_repetition": pair["scan"]["query_runs"][0]["verified_hits"],
            })
        ratios = [row["query_ratio_scan_over_xfirst"] for row in pair_rows]
        comparisons.append({
            "field_degree": degree, "curve_id": reference["curve_id"],
            "workload_id": reference["workload_id"],
            "matched_pair_blocks": len(pair_rows),
            "matched_factor_base_B": reference["base"]["actual_usable_points_B"],
            "effective_columns": 2,
            "identical_complete_selected_base_index": True,
            "query_budget_per_repetition": 2048,
            "query_repetitions_per_block": 3,
            "paired_rows": pair_rows,
            "query_ratio_geometric_mean": math.exp(statistics.mean(map(math.log, ratios))),
            "query_ratio_geomean_paired_bootstrap_ci95":
                bootstrap_geomean_ci95(ratios, 260926 + degree),
            "query_ratio_median": statistics.median(ratios),
            "query_ratio_range": [min(ratios), max(ratios)],
            "blocks_with_xfirst_faster": sum(ratio > 1 for ratio in ratios),
            "ordinary_relation_yield_estimate": None,
            "verified_single_target_dlp": False,
        })
    (HERE / "stage_proposals.json").write_text(json.dumps(proposals, indent=2) + "\n")
    (HERE / "stage_runs.jsonl").write_text("".join(
        json.dumps(row, sort_keys=True) + "\n" for row in rows))
    report = {"kind": "matched_quotient_canonicalization_stage_comparison",
              "candidate_id": None,
              "claim_boundary": "matched bounded stage only; no complete ordinary PDP attempt, relation yield, DLP, or rho comparison",
              "proposal_ids": sorted(PROPOSALS.values()),
              "comparisons": comparisons,
              "full_dlp_work_log2": None,
              "rho_speedup": None,
              "source_sha256": digest(Path(__file__)),
              "stage_runs_sha256": digest(HERE / "stage_runs.jsonl"),
              "stage_proposals_sha256": digest(HERE / "stage_proposals.json")}
    (HERE / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps([{"n": row["field_degree"],
                       "paired_blocks": row["matched_pair_blocks"],
                       "geomean_ratio": row["query_ratio_geometric_mean"],
                       "ci95": row["query_ratio_geomean_paired_bootstrap_ci95"],
                       "faster_blocks": row["blocks_with_xfirst_faster"]}
                      for row in comparisons]))


if __name__ == "__main__":
    main()
