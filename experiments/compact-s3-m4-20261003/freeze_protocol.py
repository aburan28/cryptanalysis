#!/usr/bin/env python3
"""Freeze the exact stage inputs and the still-provisional degree-131 design."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_probe import HERE, ROOT, base_record, curve_record, sha


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def workload_id(record):
    return hashlib.sha256(canonical(record)).hexdigest()[:12]


def protocol():
    profiles = []
    for n, weight, planted_seed, ordinary_seed in (
            (53, 3, 530301, 530302), (83, 4, 830401, 830402)):
        curve_path, candidate = curve_record(n)
        base_path, base = base_record(n, weight, candidate)
        workload = {
            "curve_id": candidate["curve"]["curve_id"],
            "target_group": candidate["curve"]["target_group"],
            "target_count": 1,
            "input_law": "uniform scalar in [1,r), seed via random.Random; public target Q=[k]G; solve raw preimage [h^-1 mod r]Q",
            "seed": ordinary_seed,
            "cold_or_warm": "stage-only, fresh one-target query",
        }
        profiles.append({
            "proposal_id": {53: "Q1301", 83: "Q1302"}[n],
            "candidate_id": None,
            "field": candidate["field"],
            "curve": candidate["curve"],
            "curve_manifest_sha256": sha(curve_path),
            "isogeny": "none",
            "factor_base": {key: base[key] for key in (
                "construction", "normal_basis_weight_bound",
                "cofactor_projection", "nominal_x_mask_count",
                "geometric_point_count_before_projection",
                "actual_usable_points_B_before_folding",
                "sign_frobenius_quotient", "signed_frobenius_columns",
                "enumerated_set_encoding", "enumerated_set_sha256")},
            "factor_base_archive_sha256": sha(base_path),
            "point_decomposition": {
                "m": 4,
                "summation_chain": "three S3 links with two free intermediate x coordinates",
                "formula": "(uv+uw+vw)^2+uvw+1=0 on each link",
                "encoding": "type-II normal-basis bilinear multiplication; shared AND gates and native XOR rows; Sinz weight counters",
                "solver": "cryptominisat5, one thread",
                "max_conflicts_per_attempt": 100000,
                "target_pdp_wall_limit_seconds": 20,
                "max_invalid_models": 3,
            },
            "planted_control_seed": planted_seed,
            "ordinary_workload": workload,
            "ordinary_workload_id": workload_id(workload),
            "pair_table_comparison": "pending same-base bounded implementation",
            "relation_collection": None,
            "relation_linear_algebra": None,
            "target_descent": None,
            "complete_cost": None,
        })
    reference_path = ROOT / ("experiments/ecc2k130-quotient-pair-probe-"
                             "20260926/runs/n131_stage_reference.json")
    reference = json.loads(reference_path.read_text())
    identity = reference["curve_identity_record"]
    assert reference["curve_id"] == "EC1N131Ckb1h6816f880945e"
    assert identity["field"]["n"] == 131
    return {
        "kind": "compact_four_summand_s3_chain_comparison_protocol",
        "schema_version": 1,
        "status": "exact_n53_n83_bases_frozen_degree131_proposal_only",
        "profiles": profiles,
        "degree_131_design": {
            "proposal_id": "Q1303", "candidate_id": None,
            "field": identity["field"],
            "curve": dict(identity["curve"], curve_id=reference["curve_id"]),
            "curve_reference_sha256": sha(reference_path),
            "isogeny": "none",
            "factor_base": {
                "construction": "proposed cofactor-projected normal-basis x weight at most 6",
                "normal_basis_weight_bound": 6,
                "cofactor_projection": 4,
                "actual_usable_points_B_before_folding": None,
                "signed_frobenius_columns": None,
                "enumerated_set_sha256": None,
            },
            "point_decomposition": "proposed compact three-link S3 chain",
            "relation_collection": None,
            "relation_linear_algebra": None,
            "target_descent": None,
            "complete_cost_log2": None,
            "challenge_dispatch_allowed": False,
        },
        "claim_gate": "no degree-131 challenge dispatch until a source-bound, fully charged complete-solve upper projection is credibly below 2^61 in a named unit",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = HERE / "protocol.json"
    content = json.dumps(protocol(), sort_keys=True, indent=2,
                         ensure_ascii=False) + "\n"
    if args.check:
        assert path.read_text() == content
    else:
        assert not path.exists()
        path.write_text(content)
    print(json.dumps({"protocol_sha256": sha(path),
                      "profiles": len(protocol()["profiles"])}))


if __name__ == "__main__":
    main()
