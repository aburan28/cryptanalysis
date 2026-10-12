#!/usr/bin/env python3
"""Optimistic quotient pair-index screen on Q1303's W<=6 base estimate.

This applies the pure pair-index family's random-support law to the proposed
base geometry. It is a model in logical pair states and probes, not a measured
PDP cost, field-operation conversion, or complete ECDLP projection.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def costs(n, r, b):
    k = b / (2 * n)
    index_states = n * k * k
    probes_per_row = 2 * r / (b * b)
    probes_for_k_rows = k * probes_per_row
    return {
        "conditional_B": b,
        "conditional_folded_columns_K": k,
        "index_states": index_states,
        "index_states_log2": math.log2(index_states),
        "one_rank_row_pair_probes": probes_per_row,
        "one_rank_row_pair_probes_log2": math.log2(probes_per_row),
        "K_rank_rows_pair_probes": probes_for_k_rows,
        "K_rank_rows_pair_probes_log2": math.log2(probes_for_k_rows),
        "minimum_17_byte_key_storage_bytes": 17 * index_states,
        "minimum_17_byte_key_storage_log2_bytes": math.log2(17 * index_states),
    }


def main():
    output = HERE / "runs/n131_weight6_pure_pair_index_screen.json"
    assert not output.exists()
    protocol_path = HERE / "protocol.json"
    sample_path = HERE / "runs/n131_weight6_stratified_sample.json"
    replay_path = HERE / "runs/n131_weight6_sage_independent_replay.json"
    protocol = json.loads(protocol_path.read_text())
    sample = json.loads(sample_path.read_text())
    replay = json.loads(replay_path.read_text())
    design = protocol["degree_131_design"]
    assert design["proposal_id"] == sample["proposal_id"] == "Q1303"
    assert design["candidate_id"] is sample["candidate_id"] is None
    assert design["isogeny"] == sample["isogeny"] == "none"
    assert replay["status"] == "PASS"
    assert replay["sample_receipt_sha256"] == sha(sample_path)
    n = design["field"]["n"]
    r = design["curve"]["subgroup_order"]
    assert n == sample["n"] == 131
    assert design["curve"]["curve_id"] == sample["curve_id"]
    assert sample["weight_bound"] == 6
    assert design["factor_base"]["actual_usable_points_B_before_folding"] is None
    assert sample["conditional_B_estimate"] == 2 * n * sample[
        "conditional_folded_columns_estimate"]
    low, high = sample["conditional_B_normal_95_percent_interval"]
    assert 0 < low < sample["conditional_B_estimate"] < high
    estimate = costs(n, r, sample["conditional_B_estimate"])
    lower_b_case = costs(n, r, low)
    upper_b_case = costs(n, r, high)
    # A larger base increases the index but decreases the number of probes.
    assert lower_b_case["index_states"] < upper_b_case["index_states"]
    assert lower_b_case["K_rank_rows_pair_probes"] > upper_b_case[
        "K_rank_rows_pair_probes"]
    receipt = {
        "kind": "conditional_n131_weight6_pure_quotient_pair_index_screen",
        "proposal_id": "Q1303", "candidate_id": None,
        "workload_id": None, "run_id": None,
        "curve_id": sample["curve_id"], "isogeny": "none",
        "n": n,
        "subgroup_order_r": r,
        "factor_base_exact_B": None,
        "factor_base_exact_digest": None,
        "method_family": "pure signed-Frobenius quotient pair index with one stored table of all n*K^2 pair states",
        "law": "B=2*n*K; index=n*K^2; pair probes per rank row=2*r/B^2; optimistic total for K independent rows=index+K*2*r/B^2",
        "estimate": estimate,
        "sampling_95_percent_B_interval_cases": {
            "lower_B": lower_b_case,
            "upper_B": upper_b_case,
        },
        "optimistic_total_pair_actions": (estimate["index_states"]
                                          + estimate["K_rank_rows_pair_probes"]),
        "optimistic_total_pair_actions_log2": math.log2(
            estimate["index_states"]
            + estimate["K_rank_rows_pair_probes"]),
        "gap_above_2pow61_pair_actions_log2": math.log2(
            estimate["index_states"]
            + estimate["K_rank_rows_pair_probes"]) - 61,
        "model_assumptions": [
            "Q1303's sampled B estimate and 95% normal interval are conditional on its listed geometric assumptions",
            "pair keys distribute uniformly over signed-Frobenius quotient classes",
            "each matching pair probe supplies one novel rank row",
            "all index states are built exactly once and reused",
            "key storage uses only 17 bytes per 131-bit key, without values or table overhead",
            "final relation-matrix LA, target descent, replay, base construction, and conversion cost zero in this screen",
        ],
        "is_empirical_relation_yield": False,
        "is_lower_bound_on_other_pdp_algorithms": False,
        "is_complete_solve_projection": False,
        "challenge_dispatch_allowed": False,
        "protocol_sha256": sha(protocol_path),
        "base_sample_receipt_sha256": sha(sample_path),
        "independent_replay_receipt_sha256": sha(replay_path),
        "source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({
        "estimate_log2_pair_actions": receipt[
            "optimistic_total_pair_actions_log2"],
        "gap_above_2pow61_log2": receipt[
            "gap_above_2pow61_pair_actions_log2"],
        "minimum_key_bytes_log2": estimate[
            "minimum_17_byte_key_storage_log2_bytes"],
    }))


if __name__ == "__main__":
    main()
