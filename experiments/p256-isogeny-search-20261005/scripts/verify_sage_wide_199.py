#!/usr/bin/env python3
"""Verify the frozen complete one-hop enumeration through degree 199."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "sage-wide-depth-one-199-20261006"
RECEIPT = ROOT / "receipt-sage-wide-199-20261006.json"

ATTEMPTED = [
    3, 5, 11, 13, 17, 23, 29, 37, 41, 43, 47, 59, 97, 101, 103,
    137, 149, 151, 157, 163, 179, 181, 191, 197, 199,
]
MODULAR_DEGREES = [137, 149, 151, 157, 163, 179, 181, 191, 197, 199]
EXPECTED_DEGREE_COUNTS = {3: 1, 5: 1, **{ell: 2 for ell in ATTEMPTED if ell not in (3, 5)}}


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
        assert len(row["rate_trials"]) == len(row["iterations_by_trial"]) == expected_trials
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


def main() -> None:
    receipt = load(RECEIPT)
    manifest = ROOT / receipt["source"]["manifest"]
    assert sha256(manifest) == receipt["source"]["manifest_sha256"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        assert sha256(ROOT / relative) == expected, relative
    for relative, expected in receipt["artifacts"].items():
        assert sha256(ROOT / relative) == expected, relative

    # Preserve and verify the failed division-polynomial boundary.
    panel_4g = load(RESULTS / "degrees" / "panel-status.json")
    assert panel_4g["pari_stack_gib"] == 4
    assert panel_4g["requested_ells"] == [59, 97, 101, 103, *MODULAR_DEGREES]
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

    # The lower-memory method completed every prior failure and exactly
    # reproduced the legacy degree-103 curves and maps.
    modular_panel = load(RESULTS / "modular-degrees" / "panel-status.json")
    assert modular_panel["requested_ells"] == [103, *MODULAR_DEGREES]
    assert modular_panel["pari_stack_gib"] == 4
    assert len(modular_panel["records"]) == 11
    assert all(
        row["status"] == "completed" and row["nodes_found"] == 3
        for row in modular_panel["records"]
    )
    assert max(row["max_rss_kib"] for row in modular_panel["records"]) == 299908
    legacy_103 = {
        row["candidate_id"]: row
        for row in load(RESULTS / "degrees" / "degree-103.json")["candidates"]
    }
    modular_103 = {
        row["candidate_id"]: row
        for row in load(RESULTS / "modular-degrees" / "degree-103.json")["candidates"]
    }
    assert legacy_103.keys() == modular_103.keys()
    assert all(
        legacy_103[candidate_id]["curve"] == modular_103[candidate_id]["curve"]
        and legacy_103[candidate_id]["path"] == modular_103[candidate_id]["path"]
        for candidate_id in legacy_103
    )
    for ell in MODULAR_DEGREES:
        degree_candidates = load(
            RESULTS / "modular-degrees" / f"degree-{ell}.json"
        )["candidates"]
        assert len(degree_candidates) == 3
        assert all(
            candidate["properties"]["explicit_path_verified"]
            and candidate["properties"]["automorphism_order_geometric"] == 2
            for candidate in degree_candidates
        )
        assert [candidate["path"][0]["degree"] for candidate in degree_candidates[1:]] == [ell, ell]

    boundary = load(RESULTS / "resource-boundary.json")
    assert boundary["scope"]["attempted_ells"] == ATTEMPTED
    assert boundary["scope"]["successful_ells"] == ATTEMPTED
    assert boundary["scope"]["unresolved_ells"] == []
    assert boundary["successful_modular_recovery"]["degree_103_validation"][
        "candidate_ids_curves_and_paths_match_exactly"
    ]

    extended = load(RESULTS / "extended-candidates.json")
    candidates = extended["candidates"]
    assert extended["search"]["attempted_ells"] == ATTEMPTED
    assert extended["search"]["completed_ells"] == ATTEMPTED
    assert len(candidates) == 49
    assert len({candidate["candidate_id"] for candidate in candidates}) == 49
    assert all(candidate["properties"]["explicit_path_verified"] for candidate in candidates)
    assert all(candidate["properties"]["automorphism_order_geometric"] == 2 for candidate in candidates)
    degree_by_id = {
        candidate["candidate_id"]: candidate["path"][0]["degree"]
        for candidate in candidates
        if candidate["candidate_id"] != "p256-root"
    }
    assert Counter(degree_by_id.values()) == Counter(EXPECTED_DEGREE_COUNTS)

    union = load(RESULTS / "retained-union.json")
    assert union["unique_curves_including_p256"] == 98
    assert union["unique_non_root_curves"] == 97
    assert union["new_since_degree_47_non_root_curves"] == 28
    assert union["new_modular_recovery_non_root_curves"] == 20
    assert len(union["candidate_ids"]) == len(set(union["candidate_ids"])) == 98

    high = load(RESULTS / "new-high-candidates.json")["candidates"]
    high_ids = [candidate["candidate_id"] for candidate in high]
    assert high_ids[0] == "p256-root"
    assert len(high_ids) == len(set(high_ids)) == 21
    assert sorted(degree_by_id[candidate_id] for candidate_id in high_ids[1:]) == sorted(
        [ell for ell in MODULAR_DEGREES for _ in range(2)]
    )

    initial_native = load(RESULTS / "native-screen.json")
    verify_native_payload(initial_native, 9)
    assert len(initial_native["results"]) == 9
    assert all(
        not row["paired_speedup_significant_at_95_percent"]
        for row in initial_native["results"][1:]
    )

    screening = load(RESULTS / "native-high-screen" / "screening-summary.json")
    design = screening["design"]
    assert design["candidate_universe"] == 21
    assert design["screened_candidates"] == 20
    assert design["blocks"] == 4
    assert design["complete_position_rotations_per_block"] == 1
    assert len(screening["results"]) == 20
    assert screening["unadjusted_screening_hits"] == []
    screened_ids = []
    for block in screening["blocks"]:
        artifact = ROOT / block["artifact"]
        assert sha256(artifact) == block["artifact_sha256"]
        payload = load(artifact)
        expected_ids = block["candidate_ids"]
        assert [row["candidate_id"] for row in payload["results"][1:]] == expected_ids
        verify_native_payload(payload, block["trials_per_candidate"])
        screened_ids.extend(expected_ids)
    assert screened_ids == high_ids[1:]
    assert screened_ids == [row["candidate_id"] for row in screening["results"]]
    assert all(row["linear_relation_verified_every_trial"] for row in screening["results"])
    assert all(
        not row["paired_speedup_significant_at_95_percent"]
        for row in screening["results"]
    )
    assert all(
        low <= 1.0 <= high_bound
        for low, high_bound in (
            row["paired_relative_iteration_speed_95_percent_ci"]
            for row in screening["results"]
        )
    )

    print(
        json.dumps(
            {
                "status": "verified",
                "one_hop_curves": 49,
                "combined_unique_curves": 98,
                "combined_native_neighbors": 97,
                "new_high_neighbors": 20,
                "significant_speedups": 0,
                "unresolved_degrees": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
