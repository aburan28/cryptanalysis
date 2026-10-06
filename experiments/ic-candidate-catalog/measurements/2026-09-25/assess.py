#!/usr/bin/env python3
"""Attach measured stage evidence to every proposal without inventing DLP results."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import platform


HERE = Path(__file__).resolve().parent
CATALOG = HERE.parents[1]
CRYPTO = CATALOG.parents[2] / "crypto"


def read(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify existing outputs")
    args = parser.parse_args()
    catalog = [json.loads(line) for line in (CATALOG / "candidates.jsonl").read_text().splitlines()]
    profiles = {item["id"]: item for item in json.loads((CATALOG / "profiles.json").read_text())["profiles"]}
    geometry = read("geometry.json")
    n131_support = read("n131_poly_d7_exact_support.json")
    n131_pair = read("n131_poly_d7_pair_control.json")
    onb2 = read("n131_onb_hw2_base.json")
    onb3 = read("n131_onb_hw3_base.json")
    onb_points = read("n131_onb_hw2_hw3_usable_points.json")
    poly24_sample = read("n131_poly_d24_sample.json")
    poly28_sample = read("n131_poly_d28_sample.json")
    complete_manifest = read("complete_n13_sat_candidate.json")
    complete_receipt = read("complete_n13_sat_receipt.json")
    sat50 = next(row for row in read("n13_sat_50ms.json")["rows"] if not row["shifted"])
    sat1000 = read("n13_sat_1000ms.json")["row"]

    assert len(catalog) == 1000
    assert [row["proposal_id"] for row in catalog] == [f"Q{i}" for i in range(1, 1001)]
    assert all(row["candidate_id"] is None and row["measured_cost"] is None for row in catalog)
    assert n131_support["independent_pair_sum_replay_matches"]
    assert n131_support["factor_base_digest_sha256"] == profiles["n131_poly_d7_m4"]["base_digest"]
    assert n131_pair["factor_base"]["size"] == n131_support["factor_base_points"] == 26
    assert n131_pair["homogeneous_matrix_audit"]["rank_added_beyond_negation_identities"] == 0
    assert onb2["status"] == onb3["status"] == "complete"
    assert onb2["point_set_sha256"] == onb3["point_set_sha256"] == onb_points["point_set_sha256"]
    assert onb2["subgroup_usable_points_before_folding"] == onb3["subgroup_usable_points_before_folding"] == onb_points["point_count"] == 3668
    assert poly24_sample["profile_id"] == "n131_poly_d24_m6"
    assert poly28_sample["profile_id"] == "n131_poly_d28_m5"
    assert poly24_sample["sample_count"] == poly28_sample["sample_count"] == 1024
    assert poly24_sample["exact_actual_base_points"] is poly28_sample["exact_actual_base_points"] is None
    assert complete_receipt["candidate_id"] == complete_manifest["candidate_id"]
    assert complete_receipt["proposal_lineage"] == "Q1"
    assert complete_receipt["method_distinction"].startswith("exact_sumset_selector_cnf")
    assert len(complete_receipt["targets"]) == 20
    assert all(item["ic"]["scalar"] == item["rho"]["scalar"] == item["audit_fixture_scalar"]
               for item in complete_receipt["targets"])
    assert sat50["base_points"] == sat1000["base_points"] == 6
    assert sat50["solver_statuses"] == {"timeout": 32}
    assert sat1000["solver_statuses"] == {"timeout": 31}

    geometry_rows = {(row["degree"], row["arity"], row["seed"]): row for row in geometry["rows"]}
    n13 = geometry_rows[13, 4, 87006]
    n19 = geometry_rows[19, 5, 87008]
    assert n13["base_points"] == 6 and n13["folded_columns"] == 2
    assert n19["base_points"] * 5 == 30 and n19["union_folded_columns"] == 2
    assert n13["independent_replay"] and n19["independent_replay"]
    n53 = profiles["n53_retained_m5"]
    n53_receipt_path = CRYPTO / n53["evidence"][0].removeprefix("crypto:")
    if not n53_receipt_path.is_file():
        n53_receipt_path = HERE / "n53_prior_receipt.json"
    assert n53_receipt_path.is_file() and sha256(n53_receipt_path) == n53["receipt_sha256"]
    n53_receipt = json.loads(n53_receipt_path.read_text())
    assert n53_receipt["factor_base_points"] == 23320
    assert n53_receipt["orbit_columns"] == 220

    shared = {
        "n13_same_d3_m4": {
            "kind": "exact_forward_sumset_geometry",
            "receipt": "geometry.json",
            "ordinary_nonidentity_supported": n13["same_base"]["nonzero_support"],
            "ordinary_nonidentity_total": n13["prime"] - 1,
            "tuple_leaves": n13["same_base"]["tuple_leaves"],
            "construction_wall_seconds_single_run": n13["phases"]["construction"]["seconds"],
            "forward_enumeration_wall_seconds_single_run": n13["phases"]["same_base"]["seconds"],
            "scope": "profile geometry; not a PDP solver measurement",
        },
        "n19_shifted_d3_m5": {
            "kind": "exact_forward_sumset_geometry",
            "receipt": "geometry.json",
            "ordinary_nonidentity_supported": n19["shifted_bases"]["nonzero_support"],
            "ordinary_nonidentity_total": n19["prime"] - 1,
            "tuple_leaves": n19["shifted_bases"]["tuple_leaves"],
            "construction_wall_seconds_single_run": n19["phases"]["construction"]["seconds"],
            "forward_enumeration_wall_seconds_single_run": n19["phases"]["shifted_bases"]["seconds"],
            "scope": "profile geometry; not a PDP solver measurement",
        },
        "n131_poly_d7_m4": {
            "kind": "exact_four_sum_geometry",
            "receipt": "n131_poly_d7_exact_support.json",
            "ordinary_nonidentity_supported": n131_support["support_points_nonidentity"],
            "ordinary_nonidentity_total": int(n131_support["subgroup_order"]) - 1,
            "tuple_leaves": n131_support["tuple_leaves_unordered_with_repetition"],
            "construction_wall_seconds_single_run": n131_support["phase_wall_ns"]["factor_base_build"] / 1e9,
            "forward_enumeration_wall_seconds_single_run": n131_support["phase_wall_ns"]["four_sum_enumeration"] / 1e9,
            "scope": "profile geometry; the pair lookup receipt is planted-only and is not natural yield",
        },
    }
    prior = {
        "n53_retained_m5": {
            "kind": "prior_retained_factor_base_count",
            "receipt": "n53_prior_receipt.json",
            "receipt_sha256": n53["receipt_sha256"],
            "actual_usable_points_reported": 23320,
            "folded_columns_reported": 220,
            "full_point_set_digest_available": False,
            "scope": "existing count receipt, not a new PDP or DLP measurement",
        },
    }
    measured_bases = {
        profile_id: {
            "kind": "exact_subgroup_filtered_factor_base",
            "receipt": f"n131_onb_hw{weight}_base.json",
            "point_set_receipt": "n131_onb_hw2_hw3_usable_points.json",
            "actual_usable_points": receipt["subgroup_usable_points_before_folding"],
            "folded_columns": receipt["subgroup_usable_folded_columns"],
            "point_set_sha256": receipt["point_set_sha256"],
            "geometric_construction_wall_seconds_single_run": receipt["phase_wall_ns"]["geometric_construction"] / 1e9,
            "subgroup_filter_wall_seconds_single_run": receipt["phase_wall_ns"]["orbit_representative_subgroup_filter"] / 1e9,
            "scope": "exact base only; no PDP, factor logs, or complete DLP",
        }
        for profile_id, weight, receipt in (("n131_onb_hw2_m4", 2, onb2),
                                            ("n131_onb_hw3_m5", 3, onb3))
    }
    sampled_bases = {
        item["profile_id"]: {
            "kind": "bounded_uniform_x_subgroup_base_density_sample",
            "receipt": receipt,
            "sample_count": item["sample_count"],
            "usable_x_sample_count": item["usable_x_sample_count"],
            "estimated_actual_base_points": item["estimated_actual_base_points"],
            "estimated_base_points_wilson95": item["estimated_base_points_wilson95"],
            "exact_actual_base_points": None,
            "scope": "sample estimate with interval; not an actual fb count or PDP measurement",
        }
        for item, receipt in ((poly24_sample, "n131_poly_d24_sample.json"),
                              (poly28_sample, "n131_poly_d28_sample.json"))
    }
    stage = {50: sat50, 1000: sat1000}
    assessments = []
    for proposal in catalog:
        profile = profiles[proposal["profile_id"]]
        reasons = list(proposal["activation_blockers"])
        if profile["actual_factor_base_points"] is None:
            reasons.append("exact_usable_factor_base_unmaterialized")
        if proposal["isogeny_route_ref"] != "none":
            reasons.append("isogeny_route_search_only")
        if proposal["collection_policy"] != "first":
            reasons.append("collection_witness_policy_unwired")
        if proposal["relation_la"] == "bw":
            reasons.append("relation_matrix_bw_unwired")
        row = {
            "proposal_id": proposal["proposal_id"],
            "profile_id": proposal["profile_id"],
            "candidate_id": None,
            "actual_factor_base_points": profile["actual_factor_base_points"],
            "effective_columns": profile["effective_columns"],
            "pdp_method": proposal["pdp_method"],
            "pdp_budget_ms": proposal["pdp_budget_ms"],
            "collection_policy": proposal["collection_policy"],
            "relation_la": proposal["relation_la"],
            "isogeny_route_ref": proposal["isogeny_route_ref"],
            "profile_geometry_evidence": shared.get(proposal["profile_id"]),
            "measured_base_evidence": measured_bases.get(proposal["profile_id"]),
            "sampled_base_evidence": sampled_bases.get(proposal["profile_id"]),
            "prior_profile_evidence": prior.get(proposal["profile_id"]),
            "matched_pdp_stage_evidence": None,
            "related_complete_candidate": {
                "candidate_id": complete_receipt["candidate_id"],
                "receipt": "complete_n13_sat_receipt.json",
                "run_rows": "complete_n13_sat_runs.jsonl",
                "complete_one_target_runs": len(complete_receipt["targets"]),
                "relationship": "Q1 axes with a new exact-sumset selector CNF; distinct from the chained-S3 SAT stage",
            } if proposal["proposal_id"] == "Q1" else None,
            "single_target_online_ms": None,
            "paired_rho_online_ms": None,
            "online_speedup": None,
            "complete_dlp_status": "not_run_blocked",
            "activation_blockers": sorted(set(reasons)),
        }
        if (proposal["profile_id"] == "n13_same_d3_m4"
                and proposal["pdp_method"] == "sat"
                and proposal["collection_policy"] == "first"):
            measured = stage[proposal["pdp_budget_ms"]]
            row["matched_pdp_stage_evidence"] = {
                "receipt": "n13_sat_50ms.json" if proposal["pdp_budget_ms"] == 50 else "n13_sat_1000ms.json",
                "contract_stage_runs": "n13_sat_stage_runs.jsonl",
                "ordinary_queries": len(measured["records"]),
                "verified_decompositions": measured["solver_statuses"].get("verified", 0),
                "native_timeouts": measured["solver_statuses"].get("timeout", 0),
                "charged_solver_load_solve_lift_seconds": measured["phases"]["solver_load_solve_lift"],
                "rank_gain": measured["rank_gain"],
                "scope": "same PDP stage for either final LA choice; no complete pipeline",
            }
        assessments.append(row)

    output = HERE / "assessment.jsonl"
    csv_output = HERE / "assessment.csv"
    summary_path = HERE / "summary.json"
    output_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in assessments)
    columns = ("proposal_id", "profile_id", "actual_factor_base_points", "effective_columns",
               "pdp_method", "pdp_budget_ms", "collection_policy", "relation_la",
               "isogeny_route_ref", "base_receipt", "base_sample_receipt", "base_estimate",
               "base_estimate_low95", "base_estimate_high95", "geometry_receipt", "pdp_receipt",
               "geometry_supported", "geometry_total",
               "matched_pdp_attempts", "matched_pdp_verified", "matched_pdp_timeouts",
               "matched_pdp_wall_seconds", "single_target_online_ms",
               "paired_rho_online_ms", "online_speedup", "complete_dlp_status",
               "related_complete_candidate_id",
               "activation_blockers")
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in assessments:
        geometry_cell = row["profile_geometry_evidence"] or {}
        pdp_cell = row["matched_pdp_stage_evidence"] or {}
        base_cell = row["measured_base_evidence"] or row["prior_profile_evidence"] or {}
        sample_cell = row["sampled_base_evidence"] or {}
        writer.writerow((row["proposal_id"], row["profile_id"], row["actual_factor_base_points"],
                         row["effective_columns"], row["pdp_method"], row["pdp_budget_ms"],
                         row["collection_policy"], row["relation_la"], row["isogeny_route_ref"],
                         base_cell.get("receipt"), sample_cell.get("receipt"),
                         sample_cell.get("estimated_actual_base_points"),
                         (sample_cell.get("estimated_base_points_wilson95") or [None, None])[0],
                         (sample_cell.get("estimated_base_points_wilson95") or [None, None])[1],
                         geometry_cell.get("receipt"), pdp_cell.get("receipt"),
                         geometry_cell.get("ordinary_nonidentity_supported"),
                         geometry_cell.get("ordinary_nonidentity_total"),
                         pdp_cell.get("ordinary_queries"), pdp_cell.get("verified_decompositions"),
                         pdp_cell.get("native_timeouts"),
                         pdp_cell.get("charged_solver_load_solve_lift_seconds"),
                         row["single_target_online_ms"], row["paired_rho_online_ms"],
                         row["online_speedup"], row["complete_dlp_status"],
                         (row["related_complete_candidate"] or {}).get("candidate_id"),
                         ";".join(row["activation_blockers"])))
    csv_text = buffer.getvalue()
    counts = Counter(row["profile_id"] for row in assessments)
    summary = {
        "kind": "catalog_measurement_status",
        "status": "proposal_stage_assessment_with_separate_complete_toy_variant",
        "proposal_count": len(assessments),
        "proposal_counts_by_profile": dict(sorted(counts.items())),
        "proposals_with_exact_shared_profile_geometry": sum(row["profile_geometry_evidence"] is not None for row in assessments),
        "proposals_with_new_exact_onb_base": sum(row["measured_base_evidence"] is not None for row in assessments),
        "proposals_with_sampled_polynomial_base_density": sum(row["sampled_base_evidence"] is not None for row in assessments),
        "proposals_with_prior_retained_base_count": sum(row["prior_profile_evidence"] is not None for row in assessments),
        "proposals_with_matched_sat_pdp_stage_receipt": sum(row["matched_pdp_stage_evidence"] is not None for row in assessments),
        "complete_single_target_dlp_runs": 0,
        "measured_online_speedups": 0,
        "related_complete_one_target_dlp_runs": len(complete_receipt["targets"]),
        "related_complete_candidate_id": complete_receipt["candidate_id"],
        "related_complete_candidate_receipt": "complete_n13_sat_receipt.json",
        "isogeny_search_proposals_blocked": sum("isogeny_route_search_only" in row["activation_blockers"] for row in assessments),
        "profile_geometry": shared,
        "measured_bases": measured_bases,
        "sampled_bases": sampled_bases,
        "prior_profile_evidence": prior,
        "n13_sat_first_witness": {
            str(budget): {"ordinary_queries": len(item["records"]),
                          "verified_decompositions": item["solver_statuses"].get("verified", 0),
                          "timeouts": item["solver_statuses"].get("timeout", 0),
                          "charged_solver_load_solve_lift_seconds": item["phases"]["solver_load_solve_lift"],
                          "rank_gain": item["rank_gain"]}
            for budget, item in stage.items()
        },
        "n131_planted_pair_control": {
            "planted_found": n131_pair["planted_summary"].get("found", 0),
            "homogeneous_rank": n131_pair["homogeneous_matrix_audit"]["rank_mod_subgroup_order"],
            "rank_added_beyond_negation_identities": n131_pair["homogeneous_matrix_audit"]["rank_added_beyond_negation_identities"],
            "natural_query_yield_measured_by_pair_control": False,
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "source_receipts_sha256": {name: sha256(HERE / name) for name in
                                   ("geometry.json", "n53_prior_receipt.json",
                                    "n13_sat_50ms.json", "n13_sat_1000ms.json",
                                    "n131_poly_d7_exact_support.json", "n131_poly_d7_pair_control.json",
                                    "n13_sat_stage_runs.jsonl", "n131_onb_hw2_base.json",
                                    "n131_onb_hw3_base.json", "n131_onb_hw2_hw3_usable_points.json",
                                    "n131_poly_d24_sample.json", "n131_poly_d28_sample.json",
                                    "complete_n13_sat_candidate.json", "complete_n13_sat_receipt.json",
                                    "complete_n13_sat_runs.jsonl")},
        "catalog_sha256": sha256(CATALOG / "candidates.jsonl"),
    }
    summary_text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.check:
        assert output.read_text() == output_text, "assessment differs from source receipts"
        assert csv_output.read_text() == csv_text, "CSV differs from source receipts"
        assert summary_path.read_text() == summary_text, "summary differs from source receipts"
        print("validated 1000 proposal assessment rows and source receipts")
    else:
        if output.exists() or csv_output.exists() or summary_path.exists():
            raise SystemExit("refusing to overwrite assessment outputs")
        output.write_text(output_text)
        csv_output.write_text(csv_text)
        summary_path.write_text(summary_text)


if __name__ == "__main__":
    main()
