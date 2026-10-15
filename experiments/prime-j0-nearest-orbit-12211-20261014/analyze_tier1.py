#!/usr/bin/env python3
"""Audit the frozen RunPod direct-versus-rolling panel and A/A controls."""

from hashlib import sha256
import json
from pathlib import Path
import re
import statistics


ROOT = Path(__file__).resolve().parent / "tier1-runpod-20261014"
REJECTED = "6420977ea4ee4ce6ab78c5eb1a4cdd89"
COMPLETED = "9cf2881670f8411a8850c19ab6aa0525"


def load(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    rules = load(ROOT / "panels/panel-rules.json")
    planned = load(ROOT / "panels/direct-vs-rolling.json")
    rejected = load(ROOT / REJECTED / "summary.json")
    folder = ROOT / COMPLETED
    manifest = load(folder / "manifest.json")
    summary = load(folder / "summary.json")
    runs = rows(folder / "runs.jsonl")
    pairs = rows(folder / "pairs.jsonl")
    assert manifest == planned, "executed manifest differs from frozen panel"
    assert rejected["status"] == "rejected"
    assert "execution CPU is outside container affinity" in rejected["problems"]
    assert summary["status"] == "completed" and summary["artifacts_stable"]
    assert len(runs) == 2 * len(manifest["cases"]) * rules["repetitions"]
    assert len(pairs) == len(manifest["cases"]) * rules["repetitions"]
    assert summary["valid_pairs"] == len(pairs) == summary["expected_pairs"]

    expected = {case["id"]: case for case in manifest["cases"]}
    for serial, run in enumerate(runs, 1):
        assert run["serial"] == serial and run["status"] == "valid"
        case = expected[run["case"]]
        assert all(run["fields"].get(k) == v
                   for k, v in case["expected_fields"].items())
        assert run["fields"].get("point") == case["expected_result"]
        assert run["fields"].get("verified") == "1"
        assert run["binary_sha256"] == summary["artifact_sha256"][run["command"][0]]

    bound = re.search(r"\[([0-9.]+),([0-9.]+)\]", rules["calibration_acceptance"])
    assert bound, "A/A bound absent from the preregistered rules"
    low, high = map(float, bound.groups())
    lookup = {(pair["repeat"], pair["case"]): pair for pair in pairs}
    failures = []
    per_case = []
    comparison = []
    for index in rules["case_indices"]:
        ratios = []
        calibrated = 0
        for repeat in range(rules["repetitions"]):
            before = lookup[(repeat, f"cal_before_{index}")]
            measured = lookup[(repeat, f"compare_{index}")]
            after = lookup[(repeat, f"cal_after_{index}")]
            assert all(item["status"] == "valid" for item in (before, measured, after))
            ratios.append(measured["speedup"])
            comparison.append(measured["speedup"])
            if low <= before["speedup"] <= high and low <= after["speedup"] <= high:
                calibrated += 1
            else:
                failures.append({"case_index": index, "repeat": repeat,
                                 "before_ratio": before["speedup"],
                                 "after_ratio": after["speedup"],
                                 "comparison_ratio": measured["speedup"]})
        per_case.append({"case_index": index, "calibrated_repeats": calibrated,
                         "median_direct_over_rolling": statistics.median(ratios),
                         "min_direct_over_rolling": min(ratios),
                         "max_direct_over_rolling": max(ratios)})

    return {
        "measurement_tier": "tier1_instance",
        "runpod_instance_id": manifest["allocation"]["instance_id"],
        "rejected_job": REJECTED,
        "completed_job": COMPLETED,
        "completed_runs": len(runs),
        "valid_runs": sum(run["status"] == "valid" for run in runs),
        "completed_pairs": len(pairs),
        "point_and_scalar_mismatches": 0,
        "artifact_stable": summary["artifacts_stable"],
        "aa_acceptance_range": [low, high],
        "aa_failed_comparisons": failures,
        "qualified_latency_ratio": None if failures else statistics.median(comparison),
        "descriptive_direct_over_rolling_median": statistics.median(comparison),
        "descriptive_direct_over_rolling_mean": statistics.mean(comparison),
        "per_case": per_case,
        "runs_sha256": sha256((folder / "runs.jsonl").read_bytes()).hexdigest(),
        "pairs_sha256": sha256((folder / "pairs.jsonl").read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
