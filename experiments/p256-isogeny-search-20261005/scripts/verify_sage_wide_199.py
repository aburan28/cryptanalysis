#!/usr/bin/env python3
"""Verify the frozen attempted one-hop extension through degree 199."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "sage-wide-depth-one-199-20261006"
RECEIPT = ROOT / "receipt-sage-wide-199-20261006.json"

ATTEMPTED = [
    3, 5, 11, 13, 17, 23, 29, 37, 41, 43, 47, 59, 97, 101, 103,
    137, 149, 151, 157, 163, 179, 181, 191, 197, 199,
]
COMPLETED = [3, 5, 11, 13, 17, 23, 29, 37, 41, 43, 47, 59, 97, 101, 103]
NEW_DEGREES = [59, 59, 97, 97, 101, 101, 103, 103]


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

    panel_4g = load(RESULTS / "degrees" / "panel-status.json")
    assert panel_4g["pari_stack_gib"] == 4
    assert panel_4g["requested_ells"] == [59, 97, 101, 103, 137, 149, 151, 157, 163, 179, 181, 191, 197, 199]
    status_4g = {row["ell"]: row["status"] for row in panel_4g["records"]}
    assert [ell for ell, status in status_4g.items() if status == "completed"] == [59, 97, 103]
    assert all(
        "PARI stack overflows" in row["traceback"]
        for row in panel_4g["records"]
        if row["status"] == "failed"
    )

    panel_8g = load(RESULTS / "degrees-8g" / "panel-status.json")
    assert panel_8g["pari_stack_gib"] == 8
    assert [row["ell"] for row in panel_8g["records"]] == [101, 137, 149, 151]
    assert panel_8g["records"][0]["status"] == "completed"
    assert all(
        row["status"] == "failed" and "PARI stack overflows" in row["traceback"]
        for row in panel_8g["records"][1:]
    )

    boundary = load(RESULTS / "resource-boundary.json")
    assert boundary["scope"]["attempted_ells"] == ATTEMPTED
    assert boundary["scope"]["successful_ells"] == COMPLETED
    termination = boundary["independent_panels"][1]["termination"]
    assert termination["failed_at_full_8_gib"] == [137, 149, 151]
    assert termination["operator_interrupted_during"] == 157
    assert termination["not_started_at_8_gib"] == [163, 179, 181, 191, 197, 199]

    extended = load(RESULTS / "extended-candidates.json")
    candidates = extended["candidates"]
    assert extended["search"]["attempted_ells"] == ATTEMPTED
    assert extended["search"]["completed_ells"] == COMPLETED
    assert len(candidates) == 29
    assert len({candidate["candidate_id"] for candidate in candidates}) == 29
    assert all(candidate["properties"]["explicit_path_verified"] for candidate in candidates)
    assert all(candidate["properties"]["automorphism_order_geometric"] == 2 for candidate in candidates)
    degree_by_id = {
        candidate["candidate_id"]: candidate["path"][0]["degree"]
        for candidate in candidates
        if candidate["candidate_id"] != "p256-root"
    }
    assert sorted(degree_by_id.values()) == [3, 5, 11, 11, 13, 13, 17, 17, 23, 23, 29, 29, 37, 37, 41, 41, 43, 43, 47, 47, *NEW_DEGREES]

    union = load(RESULTS / "retained-union.json")
    assert union["unique_curves_including_p256"] == 78
    assert union["unique_non_root_curves"] == 77
    assert union["new_one_hop_non_root_curves"] == 8
    assert len(union["candidate_ids"]) == len(set(union["candidate_ids"])) == 78

    native = load(RESULTS / "native-screen.json")
    rows = native["results"]
    assert native["baseline_candidate_id"] == rows[0]["candidate_id"] == "p256-root"
    assert native["benchmark_design"]["trials_per_candidate"] == 9
    assert native["benchmark_design"]["seconds_per_trial"] == 0.5
    ids = [row["candidate_id"] for row in rows]
    assert len(rows) == 9
    assert sorted(degree_by_id[candidate_id] for candidate_id in ids[1:]) == NEW_DEGREES
    orders = native["benchmark_design"]["execution_order_by_trial"]
    assert len(orders) == 9
    assert all(sorted(order) == sorted(ids) for order in orders)
    for candidate_id in ids:
        assert sorted(order.index(candidate_id) for order in orders) == list(range(9))

    baseline_rates = rows[0]["rate_trials"]
    for row in rows:
        assert row["linear_relation_verified_every_trial"]
        assert len(row["rate_trials"]) == len(row["iterations_by_trial"]) == 9
        mean, low, high = mean_ci(row["rate_trials"])
        assert close(mean, row["iterations_per_second"])
        assert all(close(a, b) for a, b in zip(row["rate_95_percent_ci"], [low, high]))
        ratios = [
            math.log2(candidate_rate / baseline_rate)
            for candidate_rate, baseline_rate in zip(row["rate_trials"], baseline_rates)
        ]
        bits, low_bits, high_bits = mean_ci(ratios)
        assert close(bits, row["paired_log2_speedup_mean"])
        assert all(
            close(a, b)
            for a, b in zip(
                row["paired_log2_speedup_95_percent_ci"], [low_bits, high_bits]
            )
        )
    assert all(not row["paired_speedup_significant_at_95_percent"] for row in rows[1:])
    assert all(
        low <= 1.0 <= high
        for low, high in (
            row["paired_relative_iteration_speed_95_percent_ci"] for row in rows[1:]
        )
    )

    print(
        json.dumps(
            {
                "status": "verified",
                "new_neighbors": 8,
                "combined_unique_curves": 78,
                "combined_native_neighbors": 77,
                "significant_speedups": 0,
                "unresolved_degrees": 10,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
