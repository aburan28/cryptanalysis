#!/usr/bin/env python3
"""Fail-closed 2x collection-cost gate on matched, subgroup-valid receipts."""

import argparse
import json
import random
import statistics
from pathlib import Path

from verify_relation_gate import verify

TARGET_RANK = 8
BOOTSTRAPS = 10000


def runs(path):
    data = json.loads(path.read_text())
    out = {(r["seed"], r["repeat"]): r for r in data["runs"]}
    assert len(out) == len(data["runs"]), "duplicate seed/repeat key"
    for r in out.values():
        assert r["target_rank"] == TARGET_RANK
        assert r["status"] == "rank_reached"
        assert r["counts"]["rank"] == TARGET_RANK
        assert r["counts"]["novel_rows"] == TARGET_RANK
        assert 0 < r["counts"]["ordinary_attempts"] <= r["counts"]["attempt_budget"]
        assert r["counts"]["ordinary_attempts"] == len(r["attempts"])
        assert all(attempt["target_scalar"] == r["targets"][i]
                   for i, attempt in enumerate(r["attempts"]))
        assert r["driver_wall_ns_including_startup"] >= r["timings_ns"]["charged_total"]
    return out


def median_cost_ms_by_seed(data):
    by_seed = {}
    for (seed, _), r in data.items():
        by_seed.setdefault(seed, []).append(
            r["driver_wall_ns_including_startup"] / 1e6 / TARGET_RANK)
    return {seed: statistics.median(values) for seed, values in sorted(by_seed.items())}


def overall_median_cost_ms(data):
    return statistics.median(
        r["driver_wall_ns_including_startup"] / 1e6 / TARGET_RANK
        for r in data.values())


def evaluate(baseline_path, candidate_path=None, probe_path=None):
    base = runs(baseline_path)
    assert verify(baseline_path)["status"] == "PASS", "independent baseline replay failed"
    base_cost = median_cost_ms_by_seed(base)
    result = {
        "schema": "homogeneous-fraction-collection-goal.v1",
        "goal": "at least 2x lower fully charged time per new independent "
                "verified relation on identical ordinary workloads, base and rank-eight stop",
        "baseline": str(baseline_path), "candidate": str(candidate_path) if candidate_path else None,
        "target_rank": TARGET_RANK,
        "baseline_median_ms_per_row_by_seed": base_cost,
        "baseline_median_ms_per_row": overall_median_cost_ms(base),
        "required_at_most_ms_per_row_for_2x_at_median":
            overall_median_cost_ms(base) / 2,
        "candidate_median_ms_per_row_by_seed": None,
        "candidate_median_ms_per_row": None, "paired_speedup_by_seed": None,
        "paired_bootstrap_95_percent_interval": None, "gate_met": False,
        "independent_c_baseline_replay": "PASS",
        "independent_c_candidate_replay": None,
    }
    if candidate_path is None:
        probe = json.loads(probe_path.read_text()) if probe_path else None
        result["status"] = "censored_no_complete_candidate"
        result["reason"] = ("diagnostic timed out before a verified independent row"
                            if probe and probe["status"] == "timeout" else
                            "no matched candidate receipts provided")
        result["probe_status"] = probe["status"] if probe else None
        return result
    candidate = runs(candidate_path)
    assert verify(candidate_path, oracle_complete=False)["status"] == "PASS", (
        "independent candidate point and rank replay failed")
    assert set(base) == set(candidate), "missing or extra paired seed/repeat"
    for key in base:
        a, b = base[key], candidate[key]
        assert a["base_sha256"] == b["base_sha256"], "changed factor base"
        assert a["workload_sha256"] == b["workload_sha256"], "changed target stream"
        assert a["targets"] == b["targets"], "changed ordered targets"
        assert a["counts"]["effective_columns"] == b["counts"]["effective_columns"]
        assert a["counts"]["attempt_budget"] == b["counts"]["attempt_budget"]
    candidate_cost = median_cost_ms_by_seed(candidate)
    ratios = {seed: base_cost[seed] / candidate_cost[seed] for seed in base_cost}
    rng = random.Random(20260927)
    seeds = list(ratios)
    draws = sorted(statistics.median(ratios[rng.choice(seeds)] for _ in seeds)
                   for _ in range(BOOTSTRAPS))
    interval = [draws[int(.025 * BOOTSTRAPS)], draws[int(.975 * BOOTSTRAPS) - 1]]
    result.update(candidate_median_ms_per_row_by_seed=candidate_cost,
                  candidate_median_ms_per_row=overall_median_cost_ms(candidate),
                  paired_speedup_by_seed=ratios,
                  paired_bootstrap_95_percent_interval=interval,
                  independent_c_candidate_replay="PASS",
                  gate_met=interval[0] >= 2.0,
                  status="met" if interval[0] >= 2.0 else "not_met",
                  reason="paired bootstrap lower limit must reach 2x")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, default=Path("relation_gate_results.json"))
    p.add_argument("--candidate", type=Path)
    p.add_argument("--probe", type=Path, default=Path("relation_probe_results.json"))
    p.add_argument("--out", type=Path, default=Path("goal_status.json"))
    args = p.parse_args()
    result = evaluate(args.baseline, args.candidate, args.probe)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
