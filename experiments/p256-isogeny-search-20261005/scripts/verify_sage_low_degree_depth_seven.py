#!/usr/bin/env python3
"""Verify the frozen resumed depth-seven search and native follow-up."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "sage-low-degree-depth-seven-20261006"
RECEIPT = ROOT / "receipt-sage-low-degree-depth-seven-20261006.json"
PRIOR_UNION = (
    ROOT
    / "results"
    / "sage-low-degree-depth-five-20261006"
    / "retained-union.json"
)

ALLOWED_DEGREES = {3, 5, 11, 13}


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
        assert row["paired_speedup_significant_at_95_percent"] == (low_bits > 0.0)


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
    assert len(prior_ids) == len(set(prior_ids)) == 210

    delta = load(RESULTS / "candidates-delta.json")
    search = delta["search"]
    assert search["algorithm"] == "resumed breadth-first rational prime-degree isogenies"
    assert search["ells"] == [3, 5, 11, 13]
    assert search["input"]["curves_including_p256"] == 168
    assert search["input"]["maximum_depth"] == 5
    input_path = Path(search["input"]["path"])
    if not input_path.is_absolute():
        input_path = ROOT.parents[1] / input_path
    assert search["input"]["sha256"] == sha256(input_path)
    assert search["target_depth"] == 7
    assert search["new_nodes_found"] == 176
    assert search["new_depth_counts"] == {"6": 80, "7": 96}
    assert search["combined_unique_j_invariants"] == 344

    candidates = delta["candidates"]
    assert candidates[0]["candidate_id"] == "p256-root"
    new_candidates = candidates[1:]
    new_ids = [row["candidate_id"] for row in new_candidates]
    assert len(new_ids) == len(set(new_ids)) == 176
    assert not set(new_ids).intersection(prior_ids)
    assert Counter(len(row["path"]) for row in new_candidates) == Counter(
        {6: 80, 7: 96}
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
    assert union["prior_unique_curves_including_p256"] == 210
    assert union["new_non_root_curves"] == 176
    assert union["new_depth_counts"] == {"6": 80, "7": 96}
    assert union["candidate_ids"] == [*prior_ids, *new_ids]
    assert union["unique_curves_including_p256"] == 386
    assert union["unique_non_root_curves"] == 385

    screening = load(RESULTS / "native-screen" / "screening-summary.json")
    design = screening["design"]
    assert design["candidate_universe"] == 177
    assert design["screened_candidates"] == 176
    assert design["block_size"] == 6
    assert design["blocks"] == 30
    assert design["seconds_per_trial"] == 0.5
    assert design["complete_position_rotations_per_block"] == 1
    assert len(screening["results"]) == 176
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
    assert len(screening_hits) == 1

    holdout = load(RESULTS / "holdout.json")
    holdout_ids = [row["candidate_id"] for row in holdout["results"]]
    assert holdout_ids == ["p256-root", screening_hits[0]["candidate_id"]]
    verify_native_payload(holdout, 30)
    assert holdout["benchmark_design"]["seconds_per_trial"] == 2.0
    result = holdout["results"][1]
    assert not result["paired_speedup_significant_at_95_percent"]
    low, high = result["paired_relative_iteration_speed_95_percent_ci"]
    assert low <= 1.0 <= high

    print(
        json.dumps(
            {
                "status": "verified",
                "new_neighbors": 176,
                "combined_unique_curves": 386,
                "combined_native_neighbors": 385,
                "screening_hits": 1,
                "reproduced_speedups": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
