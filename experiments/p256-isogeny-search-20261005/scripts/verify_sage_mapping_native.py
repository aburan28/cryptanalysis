#!/usr/bin/env python3
"""Verify the frozen explicit-mapping and matched-native benchmark run."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "receipt-sage-mapping-native-20261006.json"
RESULTS = ROOT / "results" / "sage-mapping-20261006"


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


def main() -> None:
    receipt = load(RECEIPT)
    manifest = ROOT / receipt["source"]["manifest"]
    assert sha256(manifest) == receipt["source"]["manifest_sha256"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert sha256(ROOT / relative) == expected, relative
    for relative, expected in receipt["artifacts"].items():
        assert sha256(ROOT / relative) == expected, relative

    mapping = load(RESULTS / "mapping-benchmark.json")
    native = load(RESULTS / "native-benchmark.json")
    mapping_rows = mapping["results"]
    native_rows = native["results"]
    assert mapping["sage_version"] == "10.6"
    assert len(mapping_rows) == 4
    assert len(native_rows) == 5
    assert {tuple(row["path_degrees"]) for row in mapping_rows} == {
        (3, 11),
        (3, 13),
        (5, 13),
        (47,),
    }
    assert {row["candidate_id"] for row in mapping_rows} == {
        row["candidate_id"] for row in native_rows if row["candidate_id"] != "p256-root"
    }
    for item in mapping["inputs"]:
        assert sha256(ROOT / item["path"]) == item["sha256"]

    for row in mapping_rows:
        verification = row["verification"]
        assert verification["retained_generator_reproduced"]
        assert verification["discrete_log_relation_preserved"]
        assert verification["endpoint_model_and_retained_maps_reproduced"]
        timing = row["per_key_mapping"]
        assert timing["source_points_evaluated"] == 2
        assert timing["samples"] == 25
        assert timing["repetitions_per_sample"] == 50
        raw = timing["raw_sample_seconds_per_key"]
        assert len(raw) == 25
        mean, low, high = mean_ci(raw)
        assert close(mean, timing["mean_seconds"])
        assert all(
            close(observed, expected)
            for observed, expected in zip(
                timing["mean_95_percent_ci_seconds"], [low, high]
            )
        )

    ids = [row["candidate_id"] for row in native_rows]
    assert ids[0] == native["baseline_candidate_id"] == "p256-root"
    design = native["benchmark_design"]
    assert design["seconds_per_trial"] == 1.0
    assert design["trials_per_candidate"] == 15
    orders = design["execution_order_by_trial"]
    assert len(orders) == 15
    assert all(sorted(order) == sorted(ids) for order in orders)
    for candidate_id in ids:
        positions = [order.index(candidate_id) for order in orders]
        assert all(positions.count(position) == 3 for position in range(5))

    baseline_rates = native_rows[0]["rate_trials"]
    for row in native_rows:
        rates = row["rate_trials"]
        assert len(rates) == len(row["iterations_by_trial"]) == 15
        assert row["linear_relation_verified_every_trial"]
        rate_mean, rate_low, rate_high = mean_ci(rates)
        assert close(rate_mean, row["iterations_per_second"])
        assert all(
            close(observed, expected)
            for observed, expected in zip(
                row["rate_95_percent_ci"], [rate_low, rate_high]
            )
        )
        log2_ratios = [
            math.log2(candidate_rate / baseline_rate)
            for candidate_rate, baseline_rate in zip(rates, baseline_rates)
        ]
        bits, low_bits, high_bits = mean_ci(log2_ratios)
        assert close(bits, row["paired_log2_speedup_mean"])
        assert all(
            close(observed, expected)
            for observed, expected in zip(
                row["paired_log2_speedup_95_percent_ci"], [low_bits, high_bits]
            )
        )
        relative_low, relative_high = row[
            "paired_relative_iteration_speed_95_percent_ci"
        ]
        assert relative_low <= 1.0 <= relative_high
        assert not row["paired_speedup_significant_at_95_percent"]

    print(
        json.dumps(
            {
                "status": "verified",
                "mapped_candidates": len(mapping_rows),
                "native_trials": sum(len(row["rate_trials"]) for row in native_rows),
                "significant_speedups": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
