#!/usr/bin/env python3
"""Verify the frozen resumed depth-twenty-seven search and native follow-up."""

from __future__ import annotations

import gzip
import json
import math
from collections import Counter
from pathlib import Path

from verify_sage_low_degree_depth_eleven import load, sha256, verify_native_payload
from freeze_large_json import verify_archive

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "sage-low-degree-depth-twenty-seven-20261007"
RECEIPT = ROOT / "receipt-sage-low-degree-depth-twenty-seven-20261007.json"
PRIOR_UNION = (
    ROOT
    / "results"
    / "sage-low-degree-depth-twenty-five-20261007"
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
    assert len(prior_ids) == len(set(prior_ids)) == 4850

    archive = RESULTS / "candidates-delta.json.gz"
    freeze_manifest = load(RESULTS / "candidates-delta.freeze.json")
    archive_status = verify_archive(archive, freeze_manifest)
    assert archive_status == receipt["registry_storage"]["verification"]
    with gzip.open(archive, "rt", encoding="utf-8") as handle:
        delta = json.load(handle)
    search = delta["search"]
    assert search["algorithm"] == "resumed breadth-first rational prime-degree isogenies"
    assert search["ells"] == [3, 5, 11, 13]
    assert search["input"]["curves_including_p256"] == 753
    assert search["input"]["maximum_depth"] == 25
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
    assert search["target_depth"] == 27
    assert search["new_nodes_found"] == 816
    assert search["new_depth_counts"] == {"26": 400, "27": 416}
    assert search["combined_unique_j_invariants"] == 1569

    candidates = delta["candidates"]
    assert candidates[0]["candidate_id"] == "p256-root"
    new_candidates = candidates[1:]
    new_ids = [row["candidate_id"] for row in new_candidates]
    assert len(new_ids) == len(set(new_ids)) == 816
    assert not set(new_ids).intersection(prior_ids)
    assert Counter(len(row["path"]) for row in new_candidates) == Counter(
        {26: 400, 27: 416}
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
    assert union["prior_unique_curves_including_p256"] == 4850
    assert union["new_non_root_curves"] == 816
    assert union["new_depth_counts"] == {"26": 400, "27": 416}
    assert union["candidate_ids"] == [*prior_ids, *new_ids]
    assert union["unique_curves_including_p256"] == 5666
    assert union["unique_non_root_curves"] == 5665
    assert union["inputs"][1]["sha256"] == freeze_manifest["uncompressed"]["sha256"]

    attempts = load(RESULTS / "attempts.json")
    assert len(attempts["attempts"]) >= 1
    completed_search = next(
        attempt
        for attempt in attempts["attempts"]
        if attempt["attempt_id"] == "depth-27-prospective-command"
    )
    assert completed_search["exit_code"] == 0
    assert completed_search["generated_candidates"] == 816
    frozen_registry = next(
        attempt
        for attempt in attempts["attempts"]
        if attempt["attempt_id"] == "deterministic-registry-freeze"
    )
    assert frozen_registry["archive_sha256"] == freeze_manifest["archive"]["sha256"]
    assert frozen_registry["uncompressed_sha256"] == freeze_manifest["uncompressed"][
        "sha256"
    ]
    repack = next(
        attempt
        for attempt in attempts["attempts"]
        if attempt["attempt_id"] == "deterministic-registry-repack-verification"
    )
    assert repack["byte_identical_repack"]
    assert receipt["registry_storage"]["deterministic_repack_verified"]
    completed_screen = next(
        attempt
        for attempt in attempts["attempts"]
        if attempt["attempt_id"] == "native-screen-depth-27"
    )
    assert completed_screen["exit_code"] == 0
    assert completed_screen["blocks"] == 136
    assert completed_screen["candidate_trials"] == 5712
    assert completed_screen["screened_candidates"] == 816
    assert completed_screen["linear_relations_verified_every_trial"]
    assert completed_screen["block_artifact_hashes_verified"]
    model_audit = load(RESULTS / "candidate-model-audit.json")
    assert model_audit["curves_including_p256"] == 817
    assert model_audit["target_a_counts"] == {"1": 422, "3": 395}
    assert model_audit["all_fourth_root_certificates_verified"]
    assert model_audit["all_transported_generators_on_target"]

    coefficient_audit = load(RESULTS / "coefficient-audit.json")
    assert coefficient_audit["publication_status"] == (
        "prospective_depth_twenty_seven_deterministic_audit"
    )
    assert coefficient_audit["input"]["sha256"] == freeze_manifest[
        "uncompressed"
    ]["sha256"]
    assert coefficient_audit["coverage"] == {
        "curves_including_p256": 817,
        "new_candidates": 816,
    }
    assert coefficient_audit["results"]["eligible_candidates"] == 0
    assert coefficient_audit["results"]["minimum_bit_length_row"][
        "signed_addition_chain_operation_lower_bound"
    ] == 245
    assert coefficient_audit["results"]["minimum_binary_upper_bound_row"][
        "binary_double_and_add_operation_upper_bound"
    ] == 353

    conductor_audit = load(RESULTS / "conductor-audit.json")
    assert conductor_audit["publication_status"] == (
        "prospective_depth_twenty_seven_exact_audit"
    )
    assert conductor_audit["proof"]["D_pi_fundamental"]
    assert conductor_audit["proof"]["endpoint_identity"] == "Z[pi] = O_K"
    assert conductor_audit["coverage"] == {
        "curves_including_p256": 817,
        "new_candidates": 816,
        "new_candidates_with_conductor_one": 816,
        "new_candidates_with_unknown_conductor": 0,
    }
    assert len(conductor_audit["candidate_rows"]) == 817
    assert all(
        row["endomorphism_ring_conductor_in_maximal_order"] == 1
        and row["all_path_edges_horizontal_at_level_zero"]
        and set(row["path_prime_volcano_levels"].values()).issubset({0})
        for row in conductor_audit["candidate_rows"]
    )

    screening = load(RESULTS / "native-screen" / "screening-summary.json")
    assert screening["binary"]["sha256"] == receipt["runtime"][
        "native_release_binary_sha256"
    ]
    design = screening["design"]
    assert design["candidate_universe"] == 817
    assert design["screened_candidates"] == 816
    assert design["block_size"] == 6
    assert design["blocks"] == 136
    assert design["seconds_per_trial"] == 0.5
    assert design["complete_position_rotations_per_block"] == 1
    assert len(screening["results"]) == 816
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
    assert candidate_trials == receipt["screening"]["candidate_trials"] == 5712
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

    completed_holdout = next(
        attempt
        for attempt in attempts["attempts"]
        if attempt["attempt_id"] == "native-holdout-depth-27"
    )
    assert completed_holdout["exit_code"] == 0
    assert completed_holdout["curve_trials"] == 30 * len(holdout["results"])
    assert completed_holdout["all_linear_relations_verified"]
    assert completed_holdout["reproduced_speedups"] == len(reproduced)

    mapping_path = RESULTS / "mapping-holdout-positive.json"
    mapping_rows = []
    if reproduced:
        mapping = load(mapping_path)
        assert mapping["inputs"] == [
            {
                "path": "results/sage-low-degree-depth-twenty-seven-20261007/candidates-delta.json",
                "sha256": freeze_manifest["uncompressed"]["sha256"],
            }
        ]
        mapping_rows = mapping["results"]
    else:
        assert not mapping_path.exists()
    assert [row["candidate_id"] for row in mapping_rows] == [
        row["candidate_id"] for row in reproduced
    ]
    for row in mapping_rows:
        timing = row["per_key_mapping"]
        verification = row["verification"]
        assert len(row["path_degrees"]) in {26, 27}
        assert timing["source_points_evaluated"] == 2
        assert timing["samples"] == 25
        assert timing["repetitions_per_sample"] == 50
        assert len(timing["raw_sample_seconds_per_key"]) == 25
        assert all(value > 0 for value in timing["raw_sample_seconds_per_key"])
        assert verification["retained_generator_reproduced"]
        assert verification["discrete_log_relation_preserved"]
        assert verification["endpoint_model_and_retained_maps_reproduced"]
        assert receipt["cost_accounting"]["per_instance_mapping"][
            row["candidate_id"]
        ] == timing
    assert set(receipt["cost_accounting"]["per_instance_mapping"]) == {
        row["candidate_id"] for row in reproduced
    }

    prior_followup = receipt["prior_positive_followup"]
    assert prior_followup["candidate_id"] == (
        "p256-j-87c73c5bb6ad5e615b663e67c797ec104211c306604664c723168bd1b5441d6f"
    )
    assert prior_followup["status"] == "open; local isolation probe failed"

    isolation_probe = load(RESULTS / "isolation-probe.json")
    assert isolation_probe["qualification"] == "not_qualified"
    assert isolation_probe["probe"]["cgroup_isolated_cpus"] is None
    assert isolation_probe["probe"]["nohz_full_cpus"] == ""
    assert isolation_probe["probe"]["numactl"] is None
    assert isolation_probe["failed_requirements"]

    print(
        json.dumps(
            {
                "status": "verified",
                "new_neighbors": 816,
                "combined_unique_curves": 5666,
                "combined_native_neighbors": 5665,
                "screening_hits": len(screening_hits),
                "reproduced_speedups": len(reproduced),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
