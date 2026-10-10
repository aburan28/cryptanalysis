#!/usr/bin/env python3
"""Verify the frozen low-degree depth-five search and native follow-up."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "sage-low-degree-depth-five-20261006"
RECEIPT = ROOT / "receipt-sage-low-degree-depth-five-20261006.json"
PRIOR_UNION = (
    ROOT
    / "results"
    / "sage-wide-depth-one-199-20261006"
    / "retained-union.json"
)

ALLOWED_DEGREES = {3, 5, 11, 13}
EXPECTED_DEPTH_COUNTS = {0: 1, 1: 6, 2: 17, 3: 32, 4: 48, 5: 64}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def t95(degrees_of_freedom: int) -> float:
    z = 1.959963984540054
    v = float(degrees_of_freedom)
    return (
        z
        + (z**3 + z) / (4 * v)
        + (5 * z**5 + 16 * z**3 + 3 * z) / (96 * v**2)
        + (3 * z**7 + 19 * z**5 + 17 * z**3 - 15 * z) / (384 * v**3)
    )


def mean_ci(values: list[float]) -> tuple[float, float, float]:
    mean = statistics.fmean(values)
    half_width = t95(len(values) - 1) * statistics.stdev(values) / math.sqrt(
        len(values)
    )
    return mean, mean - half_width, mean + half_width


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-15)


def verify_native_payload(payload: dict, expected_trials: int) -> None:
    rows = payload["results"]
    ids = [row["candidate_id"] for row in rows]
    assert payload["baseline_candidate_id"] == ids[0] == "p256-root"
    design = payload["benchmark_design"]
    assert design["trials_per_candidate"] == expected_trials
    orders = design["execution_order_by_trial"]
    assert len(orders) == expected_trials
    assert all(sorted(order) == sorted(ids) for order in orders)
    if expected_trials == len(ids):
        for candidate_id in ids:
            assert sorted(order.index(candidate_id) for order in orders) == list(
                range(len(ids))
            )

    baseline_rates = rows[0]["rate_trials"]
    for row in rows:
        assert row["linear_relation_verified_every_trial"]
        assert len(row["rate_trials"]) == expected_trials
        assert len(row["iterations_by_trial"]) == expected_trials
        mean, low, high = mean_ci(row["rate_trials"])
        assert close(mean, row["iterations_per_second"])
        assert all(
            close(left, right)
            for left, right in zip(row["rate_95_percent_ci"], [low, high])
        )
        ratios = [
            math.log2(candidate_rate / baseline_rate)
            for candidate_rate, baseline_rate in zip(
                row["rate_trials"], baseline_rates
            )
        ]
        bits, low_bits, high_bits = mean_ci(ratios)
        assert close(bits, row["paired_log2_speedup_mean"])
        assert all(
            close(left, right)
            for left, right in zip(
                row["paired_log2_speedup_95_percent_ci"],
                [low_bits, high_bits],
            )
        )
        expected_significant = low_bits > 0.0
        assert row["paired_speedup_significant_at_95_percent"] == expected_significant


def main() -> None:
    receipt = load(RECEIPT)
    manifest = ROOT / receipt["source"]["manifest"]
    assert sha256(manifest) == receipt["source"]["manifest_sha256"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert sha256(ROOT / relative) == expected, relative
    for relative, expected in receipt["artifacts"].items():
        assert sha256(ROOT / relative) == expected, relative

    depth_five = load(RESULTS / "candidates.json")
    assert depth_five["search"]["ells"] == [3, 5, 11, 13]
    assert depth_five["search"]["depth"] == 5
    assert depth_five["search"]["nodes_found"] == 168
    assert depth_five["search"]["max_nodes"] == 1000
    candidates = depth_five["candidates"]
    ids = [row["candidate_id"] for row in candidates]
    assert ids[0] == "p256-root"
    assert len(ids) == len(set(ids)) == 168
    assert Counter(len(row["path"]) for row in candidates) == Counter(
        EXPECTED_DEPTH_COUNTS
    )

    root_j = candidates[0]["curve"]["j_invariant"]
    root_p = candidates[0]["curve"]["p"]
    root_n = candidates[0]["curve"]["n"]
    for candidate in candidates:
        assert candidate["properties"]["explicit_path_verified"]
        assert candidate["properties"]["automorphism_order_geometric"] == 2
        assert candidate["curve"]["p"] == root_p
        assert candidate["curve"]["n"] == root_n
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

    prior_ids = load(PRIOR_UNION)["candidate_ids"]
    prior_set = set(prior_ids)
    expected_new = [row for row in candidates if row["candidate_id"] not in prior_set]
    expected_new_ids = [row["candidate_id"] for row in expected_new]
    assert len(expected_new_ids) == 112
    assert Counter(len(row["path"]) for row in expected_new) == Counter({4: 48, 5: 64})

    native_panel = load(RESULTS / "new-candidates.json")
    native_candidates = native_panel["candidates"]
    assert native_candidates[0] == candidates[0]
    assert native_candidates[1:] == expected_new
    assert native_panel["search"]["new_non_root_curves"] == 112

    union = load(RESULTS / "retained-union.json")
    assert union["prior_unique_curves_including_p256"] == 98
    assert union["low_degree_depth_five_curves_including_p256"] == 168
    assert union["overlap_curves_including_p256"] == 56
    assert union["new_non_root_curves"] == 112
    assert union["new_depth_counts"] == {"4": 48, "5": 64}
    assert union["candidate_ids"] == [*prior_ids, *expected_new_ids]
    assert len(set(union["candidate_ids"])) == 210
    assert union["unique_curves_including_p256"] == 210
    assert union["unique_non_root_curves"] == 209

    screening = load(RESULTS / "native-screen" / "screening-summary.json")
    design = screening["design"]
    assert design["candidate_universe"] == 113
    assert design["screened_candidates"] == 112
    assert design["block_size"] == 6
    assert design["blocks"] == 19
    assert design["seconds_per_trial"] == 0.5
    assert design["complete_position_rotations_per_block"] == 1
    assert len(screening["results"]) == 112
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
    assert screened_ids == expected_new_ids
    assert screened_ids == [row["candidate_id"] for row in screening["results"]]
    assert all(row["linear_relation_verified_every_trial"] for row in screening["results"])
    screening_hits = [
        row
        for row in screening["results"]
        if row["paired_speedup_significant_at_95_percent"]
    ]
    assert screening["unadjusted_screening_hits"] == screening_hits
    assert len(screening_hits) == 6

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
                "depth_five_curves": 168,
                "new_neighbors": 112,
                "combined_unique_curves": 210,
                "combined_native_neighbors": 209,
                "screening_hits": 6,
                "reproduced_speedups": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
