#!/usr/bin/env python3
"""Verify the frozen resumed depth-twenty-three search and native follow-up."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from verify_sage_low_degree_depth_eleven import load, sha256, verify_native_payload

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "sage-low-degree-depth-twenty-three-20261007"
RECEIPT = ROOT / "receipt-sage-low-degree-depth-twenty-three-20261007.json"
PRIOR_UNION = (
    ROOT
    / "results"
    / "sage-low-degree-depth-twenty-one-20261007"
    / "retained-union.json"
)

ALLOWED_DEGREES = {3, 5, 11, 13}


def main() -> None:
    receipt = load(RECEIPT)
    manifest = ROOT / receipt["source"]["manifest"]
    assert sha256(manifest) == receipt["source"]["manifest_sha256"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert sha256(ROOT / relative) == expected, relative
    for relative, expected in receipt["artifacts"].items():
        assert sha256(ROOT / relative) == expected, relative

    prior = load(PRIOR_UNION)
    prior_ids = prior["candidate_ids"]
    assert len(prior_ids) == len(set(prior_ids)) == 3410

    delta = load(RESULTS / "candidates-delta.json")
    search = delta["search"]
    assert search["algorithm"] == "resumed breadth-first rational prime-degree isogenies"
    assert search["ells"] == [3, 5, 11, 13]
    assert search["input"]["curves_including_p256"] == 625
    assert search["input"]["maximum_depth"] == 21
    input_path = Path(search["input"]["path"])
    if input_path.is_absolute() and not input_path.exists() and input_path.parts[:2] == (
        "/",
        "repo",
    ):
        input_path = ROOT.parents[1] / Path(*input_path.parts[2:])
    elif not input_path.is_absolute():
        experiment_relative = ROOT / input_path
        input_path = (
            experiment_relative
            if experiment_relative.exists()
            else ROOT.parents[1] / input_path
        )
    assert search["input"]["sha256"] == sha256(input_path)
    assert search["target_depth"] == 23
    assert search["new_nodes_found"] == 688
    assert search["new_depth_counts"] == {"22": 336, "23": 352}
    assert search["combined_unique_j_invariants"] == 1313

    candidates = delta["candidates"]
    assert candidates[0]["candidate_id"] == "p256-root"
    new_candidates = candidates[1:]
    new_ids = [row["candidate_id"] for row in new_candidates]
    assert len(new_ids) == len(set(new_ids)) == 688
    assert not set(new_ids).intersection(prior_ids)
    assert Counter(len(row["path"]) for row in new_candidates) == Counter(
        {22: 336, 23: 352}
    )

    root = candidates[0]
    root_j = root["curve"]["j_invariant"]
    for candidate in candidates:
        assert candidate["properties"]["explicit_path_verified"]
        assert candidate["properties"]["automorphism_order_geometric"] == 2
        assert candidate["curve"]["p"] == root["curve"]["p"]
        assert candidate["curve"]["n"] == root["curve"]["n"]
        path = candidate["path"]
        if not path:
            assert candidate["curve"]["j_invariant"] == root_j
            continue
        assert path[0]["domain_j"] == root_j
        assert path[-1]["codomain_j"] == candidate["curve"]["j_invariant"]
        assert all(step["degree"] in ALLOWED_DEGREES for step in path)
        assert all(
            left["codomain_j"] == right["domain_j"]
            for left, right in zip(path, path[1:])
        )
        assert int(
            candidate["cost_accounting"]["discovery_and_reusable_precomputation"][
                "path_degree_product"
            ]
        ) == math.prod(step["degree"] for step in path)

    union = load(RESULTS / "retained-union.json")
    assert union["prior_unique_curves_including_p256"] == 3410
    assert union["new_non_root_curves"] == 688
    assert union["new_depth_counts"] == {"22": 336, "23": 352}
    assert union["candidate_ids"] == [*prior_ids, *new_ids]
    assert union["unique_curves_including_p256"] == 4098
    assert union["unique_non_root_curves"] == 4097

    attempts = load(RESULTS / "attempts.json")
    assert len(attempts["attempts"]) >= 1
    completed_search = next(
        attempt
        for attempt in attempts["attempts"]
        if attempt["attempt_id"] == "depth-23-prospective-command"
    )
    assert completed_search["exit_code"] == 0
    assert completed_search["generated_candidates"] == 688

    model_audit = load(RESULTS / "candidate-model-audit.json")
    assert model_audit["curves_including_p256"] == 689
    assert model_audit["target_a_counts"] == {"1": 338, "3": 351}
    assert model_audit["all_fourth_root_certificates_verified"]
    assert model_audit["all_transported_generators_on_target"]

    coefficient_audit = load(RESULTS / "coefficient-audit.json")
    assert coefficient_audit["publication_status"] == (
        "prospective_depth_twenty_three_deterministic_audit"
    )
    assert coefficient_audit["input"]["sha256"] == sha256(
        RESULTS / "candidates-delta.json"
    )
    assert coefficient_audit["coverage"] == {
        "curves_including_p256": 689,
        "new_candidates": 688,
    }
    assert coefficient_audit["results"]["eligible_candidates"] == 0
    assert coefficient_audit["results"]["minimum_bit_length_row"][
        "signed_addition_chain_operation_lower_bound"
    ] == 244
    assert coefficient_audit["results"]["minimum_binary_upper_bound_row"][
        "binary_double_and_add_operation_upper_bound"
    ] == 357

    conductor_audit = load(RESULTS / "conductor-audit.json")
    assert conductor_audit["publication_status"] == (
        "prospective_depth_twenty_three_exact_audit"
    )
    assert conductor_audit["proof"]["D_pi_fundamental"]
    assert conductor_audit["proof"]["endpoint_identity"] == "Z[pi] = O_K"
    assert conductor_audit["coverage"] == {
        "curves_including_p256": 689,
        "new_candidates": 688,
        "new_candidates_with_conductor_one": 688,
        "new_candidates_with_unknown_conductor": 0,
    }
    assert len(conductor_audit["candidate_rows"]) == 689
    assert all(
        row["endomorphism_ring_conductor_in_maximal_order"] == 1
        and row["all_path_edges_horizontal_at_level_zero"]
        and set(row["path_prime_volcano_levels"].values()).issubset({0})
        for row in conductor_audit["candidate_rows"]
    )

    screening = load(RESULTS / "native-screen" / "screening-summary.json")
    design = screening["design"]
    assert design["candidate_universe"] == 689
    assert design["screened_candidates"] == 688
    assert design["block_size"] == 6
    assert design["blocks"] == 115
    assert design["seconds_per_trial"] == 0.5
    assert design["complete_position_rotations_per_block"] == 1
    assert len(screening["results"]) == 688
    screened_ids = []
    candidate_trials = 0
    for block in screening["blocks"]:
        artifact = ROOT / block["artifact"]
        assert sha256(artifact) == block["artifact_sha256"]
        payload = load(artifact)
        expected_ids = block["candidate_ids"]
        expected_trials = len(expected_ids) + 1
        assert block["trials_per_candidate"] == expected_trials
        assert [row["candidate_id"] for row in payload["results"][1:]] == expected_ids
        verify_native_payload(payload, expected_trials)
        screened_ids.extend(expected_ids)
        candidate_trials += block["trials_per_candidate"] * len(expected_ids)
    assert candidate_trials == receipt["screening"]["candidate_trials"] == 4808
    assert screened_ids == new_ids
    assert screened_ids == [row["candidate_id"] for row in screening["results"]]
    screening_hits = [
        row
        for row in screening["results"]
        if row["paired_speedup_significant_at_95_percent"]
    ]
    assert screening["unadjusted_screening_hits"] == screening_hits
    assert len(screening_hits) == receipt["screening"]["unadjusted_screening_hits"]

    holdout = load(RESULTS / "holdout.json")
    holdout_ids = [row["candidate_id"] for row in holdout["results"]]
    assert holdout_ids == [
        "p256-root",
        *[row["candidate_id"] for row in screening_hits],
    ]
    verify_native_payload(holdout, 30)
    assert holdout["benchmark_design"]["seconds_per_trial"] == 2.0
    reproduced = [
        row
        for row in holdout["results"][1:]
        if row["paired_speedup_significant_at_95_percent"]
    ]
    assert len(reproduced) == receipt["holdout"]["reproduced_speedups"]

    print(
        json.dumps(
            {
                "status": "verified",
                "new_neighbors": 688,
                "combined_unique_curves": 4098,
                "combined_native_neighbors": 4097,
                "screening_hits": len(screening_hits),
                "reproduced_speedups": len(reproduced),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
