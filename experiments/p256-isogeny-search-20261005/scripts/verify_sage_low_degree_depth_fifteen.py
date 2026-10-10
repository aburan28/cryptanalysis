#!/usr/bin/env python3
"""Verify the frozen resumed depth-fifteen search and native follow-up."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from verify_sage_low_degree_depth_eleven import load, sha256, verify_native_payload

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "sage-low-degree-depth-fifteen-20261006"
RECEIPT = ROOT / "receipt-sage-low-degree-depth-fifteen-20261006.json"
PRIOR_UNION = (
    ROOT
    / "results"
    / "sage-low-degree-depth-thirteen-20261006"
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
    assert len(prior_ids) == len(set(prior_ids)) == 1298

    delta = load(RESULTS / "candidates-delta.json")
    search = delta["search"]
    assert search["algorithm"] == "resumed breadth-first rational prime-degree isogenies"
    assert search["ells"] == [3, 5, 11, 13]
    assert search["input"]["curves_including_p256"] == 369
    assert search["input"]["maximum_depth"] == 13
    input_path = Path(search["input"]["path"])
    if not input_path.is_absolute():
        input_path = ROOT.parents[1] / input_path
    assert search["input"]["sha256"] == sha256(input_path)
    assert search["target_depth"] == 15
    assert search["new_nodes_found"] == 432
    assert search["new_depth_counts"] == {"14": 208, "15": 224}
    assert search["combined_unique_j_invariants"] == 801

    candidates = delta["candidates"]
    assert candidates[0]["candidate_id"] == "p256-root"
    new_candidates = candidates[1:]
    new_ids = [row["candidate_id"] for row in new_candidates]
    assert len(new_ids) == len(set(new_ids)) == 432
    assert not set(new_ids).intersection(prior_ids)
    assert Counter(len(row["path"]) for row in new_candidates) == Counter(
        {14: 208, 15: 224}
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
    assert union["prior_unique_curves_including_p256"] == 1298
    assert union["new_non_root_curves"] == 432
    assert union["new_depth_counts"] == {"14": 208, "15": 224}
    assert union["candidate_ids"] == [*prior_ids, *new_ids]
    assert union["unique_curves_including_p256"] == 1730
    assert union["unique_non_root_curves"] == 1729

    screening = load(RESULTS / "native-screen" / "screening-summary.json")
    design = screening["design"]
    assert design["candidate_universe"] == 433
    assert design["screened_candidates"] == 432
    assert design["block_size"] == 6
    assert design["blocks"] == 72
    assert design["seconds_per_trial"] == 0.5
    assert design["complete_position_rotations_per_block"] == 1
    assert len(screening["results"]) == 432
    screened_ids = []
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
    assert holdout_ids == ["p256-root", *[row["candidate_id"] for row in screening_hits]]
    verify_native_payload(holdout, 30)
    assert holdout["benchmark_design"]["seconds_per_trial"] == 2.0
    assert all(
        not row["paired_speedup_significant_at_95_percent"]
        for row in holdout["results"][1:]
    )
    assert all(
        low <= 1.0 <= high
        for low, high in (
            row["paired_relative_iteration_speed_95_percent_ci"]
            for row in holdout["results"][1:]
        )
    )

    print(
        json.dumps(
            {
                "status": "verified",
                "new_neighbors": 432,
                "combined_unique_curves": 1730,
                "combined_native_neighbors": 1729,
                "screening_hits": len(screening_hits),
                "reproduced_speedups": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
