#!/usr/bin/env python3
"""Verify the frozen full-registry matched-native screen and holdout."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "receipt-sage-native-full-screen-20261006.json"
RESULTS = ROOT / "results" / "sage-native-full-screen-20261006"


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
    half_width = t95(len(values) - 1) * statistics.stdev(values) / math.sqrt(len(values))
    return mean, mean - half_width, mean + half_width


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-15)


def verify_native_payload(payload: dict, expected_trials: int) -> None:
    rows = payload["results"]
    ids = [row["candidate_id"] for row in rows]
    assert ids[0] == payload["baseline_candidate_id"] == "p256-root"
    design = payload["benchmark_design"]
    assert design["trials_per_candidate"] == expected_trials
    orders = design["execution_order_by_trial"]
    assert len(orders) == expected_trials
    assert all(sorted(order) == sorted(ids) for order in orders)

    baseline_rates = rows[0]["rate_trials"]
    for row in rows:
        rates = row["rate_trials"]
        assert len(rates) == len(row["iterations_by_trial"]) == expected_trials
        assert row["linear_relation_verified_every_trial"]
        mean, low, high = mean_ci(rates)
        assert close(mean, row["iterations_per_second"])
        assert all(
            close(observed, expected)
            for observed, expected in zip(row["rate_95_percent_ci"], [low, high])
        )
        ratios = [
            math.log2(candidate_rate / baseline_rate)
            for candidate_rate, baseline_rate in zip(rates, baseline_rates)
        ]
        bits, low_bits, high_bits = mean_ci(ratios)
        assert close(bits, row["paired_log2_speedup_mean"])
        assert all(
            close(observed, expected)
            for observed, expected in zip(
                row["paired_log2_speedup_95_percent_ci"], [low_bits, high_bits]
            )
        )


def main() -> None:
    receipt = load(RECEIPT)
    manifest = ROOT / receipt["source"]["manifest"]
    assert sha256(manifest) == receipt["source"]["manifest_sha256"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert sha256(ROOT / relative) == expected, relative
    for relative, expected in receipt["artifacts"].items():
        assert sha256(ROOT / relative) == expected, relative

    screening = load(RESULTS / "screening-summary.json")
    design = screening["design"]
    assert design["candidate_universe"] == 70
    assert design["excluded_prior_native_panel"] == 4
    assert design["screened_candidates"] == 65
    assert design["blocks"] == 11
    assert design["complete_position_rotations_per_block"] == 1
    assert len(screening["results"]) == 65
    assert len({row["candidate_id"] for row in screening["results"]}) == 65
    assert all(row["linear_relation_verified_every_trial"] for row in screening["results"])
    for item in screening["inputs"]:
        assert sha256(ROOT / item["path"]) == item["sha256"]

    block_candidate_ids: list[str] = []
    for block in screening["blocks"]:
        artifact = ROOT / block["artifact"]
        assert sha256(artifact) == block["artifact_sha256"]
        payload = load(artifact)
        expected_ids = block["candidate_ids"]
        assert [row["candidate_id"] for row in payload["results"][1:]] == expected_ids
        verify_native_payload(payload, block["trials_per_candidate"])
        count = len(payload["results"])
        orders = payload["benchmark_design"]["execution_order_by_trial"]
        for candidate_id in [row["candidate_id"] for row in payload["results"]]:
            positions = [order.index(candidate_id) for order in orders]
            assert all(positions.count(position) == 1 for position in range(count))
        block_candidate_ids.extend(expected_ids)
    assert block_candidate_ids == [row["candidate_id"] for row in screening["results"]]

    hits = screening["unadjusted_screening_hits"]
    assert len(hits) == 2
    assert {tuple(row["path_degrees"]) for row in hits} == {(17,), (23,)}
    assert all(row["paired_speedup_significant_at_95_percent"] for row in hits)

    holdout = load(RESULTS / "holdout.json")
    assert holdout["benchmark_design"]["seconds_per_trial"] == 2.0
    verify_native_payload(holdout, 30)
    assert len(holdout["results"]) == 3
    for row in holdout["results"][1:]:
        low, high = row["paired_relative_iteration_speed_95_percent_ci"]
        assert low <= 1.0 <= high
        assert not row["paired_speedup_significant_at_95_percent"]

    print(
        json.dumps(
            {
                "status": "verified",
                "native_screened": 65,
                "screening_hits": 2,
                "holdout_speedups": 0,
                "combined_native_neighbors": 69,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
