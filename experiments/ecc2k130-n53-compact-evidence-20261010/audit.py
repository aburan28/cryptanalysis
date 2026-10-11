#!/usr/bin/env python3
"""Audit the archived compact-orbit rank traces at a pinned crypto commit."""

import argparse
import hashlib
import json
import math
import statistics
import subprocess
from pathlib import Path


COMMIT = "de11f98ee53e63750596561f2b97fe84e41e50da"
ROOT = "experiments/koblitz-base-size-cold-panel-20261004"
ANALYSIS = f"{ROOT}/HOLDOUT_ANALYSIS.json"
ANALYSIS_SHA256 = "b54be182170a0986be1773e8e7a788cd380cc27c7dc8a3c4ea8ec4869acd8218"
TRACE_SHA256 = {
    (41, 85): "32089caba5f591a1d63dd40ccca1973fe1a4470b0f47e10a6d62883f1e56a3aa",
    (41, 64): "7dffcf6b8558475a3f716fb7f9221e536795b597ee652f9e0dfad214986b3c2e",
    (53, 220): "876ba0f23824e8ad0fcbe01bfe55c3018531f847f383e2825bd624b7c3fe9011",
    (53, 160): "48c00a5fdc64fa5848843f838353fe3ae1e2bc95e433f1f5da18e1e9230066a0",
}
CURVES = {
    41: {"curve_id": "EC1N41Ce0he09550ab560a", "subgroup_order": 549756390943,
         "generator": [2056947637384, 1635505394702]},
    53: {"curve_id": "EC1N53Ce0hb097de99be9a", "subgroup_order": 21044858204113,
         "generator": [198217578752339, 7929897206038174]},
}


def blob(crypto_root: Path, path: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(crypto_root), "show", f"{COMMIT}:{path}"],
        stderr=subprocess.PIPE,
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def as_decimal(value: float) -> str:
    return f"{value:.6f}"


def audit_arm(crypto_root: Path, n: int, arm: dict) -> dict:
    k = arm["K"]
    require((n, k) in TRACE_SHA256, f"unexpected n/K: {n}/{k}")
    require(len(arm["rows"]) == 6, f"expected six paired repeats: {n}/{k}")
    require({row["repeat"] for row in arm["rows"]} == set(range(1, 7)), "repeat IDs")
    require(all(row["verified"] and row["ic_status"] == 0 and row["rho_status"] == 0
                and row["replay_status"] == 0 for row in arm["rows"]), "unverified pair")
    require(all(row["ic_cold_ms"] > 0 and row["rho_cold_ms"] > 0
                and row["ic_online_ms"] > 0 and row["rho_online_ms"] > 0
                and abs(row["ic_cold_ms"] / row["rho_cold_ms"] -
                        row["ic_over_rho_cold"]) < 1e-10
                and abs(row["rho_online_ms"] / row["ic_online_ms"] -
                        row["rho_over_ic_online"]) < 1e-10
                for row in arm["rows"]), "paired IC/rho arithmetic")

    hashes = []
    first = None
    for repeat in range(1, 7):
        path = f"{ROOT}/runs/holdout/n{n}/k{k}/r{repeat}/rank.jsonl"
        raw = blob(crypto_root, path)
        hashes.append(sha256(raw))
        if first is None:
            first = [json.loads(line) for line in raw.splitlines()]
    require(len(set(hashes)) == 1, f"rank trace changed across repeats: {n}/{k}")
    require(hashes[0] == TRACE_SHA256[(n, k)], f"rank trace hash mismatch: {n}/{k}")

    header, *body = first
    solution = body.pop()
    require(header["kind"] == "compact_orbit_rank_header", "rank header kind")
    require(solution["kind"] == "compact_orbit_rank_solution", "rank solution kind")
    require(header["n"] == n and header["orbit_columns"] == k, "field/columns")
    require(header["a"] == 0 and header["subgroup_order"] == CURVES[n]["subgroup_order"]
            and header["generator"] == CURVES[n]["generator"], "curve/subgroup")
    require(header["factor_base_points"] == arm["actual_base_points"], "actual base size")
    require(header["base_hash"] == arm["base_hash"], "base point digest")
    require(solution["rank"] == k and solution["attempts"] == k, "full rank/attempts")
    require(solution["failures"] == 0 and len(body) == k, "failed/missing rank row")
    require(all(row["kind"] == "compact_orbit_rank_attempt" and row["found"]
                and row["gained"] and row["attempt_index"] == i
                and row["rank_before"] == i and row["rank_after"] == i + 1
                for i, row in enumerate(body)), "rank transition")

    probes = [row["probes"] for row in body]
    require(all(isinstance(count, int) and count > 0 for count in probes), "probe count")
    total = sum(probes)
    expected_mean = arm["rows"][0]["rank_probes_mean"]
    require(abs(total / k - expected_mean) < 1e-8, "rank-probe summary mismatch")
    upper = math.ceil(k / 10)
    quartiles = [probes[i * k // 4:(i + 1) * k // 4] for i in range(4)]
    return {
        "n": n,
        "curve_id": CURVES[n]["curve_id"],
        "K": k,
        "actual_base_points": arm["actual_base_points"],
        "base_hash": arm["base_hash"],
        "rank_trace_sha256": hashes[0],
        "timing_repeats": 6,
        "distinct_rank_probe_streams": 1,
        "rank_attempts": k,
        "rank_novel_rows": k,
        "rank_failed_attempts": 0,
        "total_rank_probes": total,
        "median_probes_per_row": as_decimal(statistics.median(probes)),
        "p90_probes_per_row_nearest_rank": sorted(probes)[math.ceil(0.9 * k) - 1],
        "max_probes_per_row": max(probes),
        "top_decile_count": upper,
        "top_decile_probe_share": as_decimal(sum(sorted(probes, reverse=True)[:upper]) / total),
        "rank_order_quartile_probe_shares": [as_decimal(sum(part) / total) for part in quartiles],
        "median_ic_online_ms": as_decimal(arm["spread"]["ic_online_ms"]["median"]),
        "median_rho_online_ms": as_decimal(arm["spread"]["rho_online_ms"]["median"]),
        "median_paired_rho_over_ic_online": as_decimal(
            statistics.median(row["rho_over_ic_online"] for row in arm["rows"])),
        "median_ic_cold_ms": as_decimal(arm["spread"]["ic_cold_ms"]["median"]),
        "median_rho_cold_ms": as_decimal(arm["spread"]["rho_cold_ms"]["median"]),
        "median_paired_ic_over_rho_cold": as_decimal(
            statistics.median(row["ic_over_rho_cold"] for row in arm["rows"])),
        "median_rank_pdp_ms": as_decimal(arm["spread"]["rank_pdp_ms"]["median"]),
        "median_index_build_ms": as_decimal(arm["spread"]["precompute_index_ms"]["median"]),
    }


def audit(crypto_root: Path) -> dict:
    raw = blob(crypto_root, ANALYSIS)
    require(sha256(raw) == ANALYSIS_SHA256, "holdout analysis hash mismatch")
    analysis = json.loads(raw)
    require(len(analysis["cells"]) == 2, "expected n41 and n53")
    result = []
    for cell in sorted(analysis["cells"], key=lambda item: item["n"]):
        n = cell["n"]
        require(n in (41, 53), "unexpected curve")
        baseline = audit_arm(crypto_root, n, cell["baseline"])
        selected = audit_arm(crypto_root, n, cell["selected"])
        require(baseline["K"] == cell["baseline_K"], "baseline K")
        require(selected["K"] == cell["selected_smaller_K"], "selected K")
        paired = cell["paired_rows"]
        require(len(paired) == 6 and {row["repeat"] for row in paired} == set(range(1, 7)),
                "paired cold repeats")
        cold_by_repeat = {row["repeat"]: row["ic_cold_ms"] for row in cell["baseline"]["rows"]}
        selected_by_repeat = {row["repeat"]: row["ic_cold_ms"] for row in cell["selected"]["rows"]}
        ratios = [selected_by_repeat[row["repeat"]] / cold_by_repeat[row["repeat"]]
                  for row in paired]
        require(all(abs(ratio - row["selected_over_baseline_ic_cold"]) < 1e-10
                    for ratio, row in zip(ratios, paired)), "paired cold ratio")
        require(abs(statistics.median(ratios) -
                    cell["paired_selected_over_baseline_ic_cold"]["median"]) < 1e-10,
                "median paired cold ratio")
        result.append({
            "n": n,
            "heldout_target": cell["heldout_target"],
            "baseline": baseline,
            "smaller": selected,
            "paired_smaller_over_baseline_cold_median": as_decimal(statistics.median(ratios)),
            "paired_smaller_over_baseline_cold_min": as_decimal(min(ratios)),
            "paired_smaller_over_baseline_cold_max": as_decimal(max(ratios)),
            "rank_probe_total_smaller_over_baseline": as_decimal(
                selected["total_rank_probes"] / baseline["total_rank_probes"]),
        })
    return {
        "schema": "compact_orbit_rank_trace_audit_v1",
        "evidence_type": "retrospective_cross_repository_audit",
        "crypto_commit": COMMIT,
        "producer_commit": analysis["source_commit"],
        "analysis_path": ANALYSIS,
        "analysis_sha256": ANALYSIS_SHA256,
        "cells": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crypto-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = (json.dumps(audit(args.crypto_root), indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        require(args.out.read_bytes() == encoded, "checked-in audit result differs")
        print("compact-orbit rank audit: PASS")
    else:
        args.out.write_bytes(encoded)
        print(args.out)


if __name__ == "__main__":
    main()
