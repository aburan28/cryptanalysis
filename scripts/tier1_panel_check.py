#!/usr/bin/env python3
"""Check a frozen five-point Tier 1 panel from serial benchmark job folders."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics


def read_json(path):
    return json.loads(path.read_text())


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(paths):
    problems = []
    fingerprints = []
    points = set()
    case_medians = []
    case_rows = []
    for root in paths:
        root = Path(root)
        manifest = read_json(root / "manifest.json")
        summary = read_json(root / "summary.json")
        pairs = read_jsonl(root / "pairs.jsonl")
        runs = read_jsonl(root / "runs.jsonl")
        calibrations = read_jsonl(root / "calibration_pairs.jsonl")
        if summary.get("manifest_sha256") != sha256(root / "manifest.json"):
            problems.append(f"{root}: manifest digest mismatch")
        if summary.get("calibration_receipt_sha256") != sha256(root / "calibrations.jsonl"):
            problems.append(f"{root}: calibration digest mismatch")
        if len(manifest.get("cases", [])) != 1:
            problems.append(f"{root}: expected one frozen case")
            continue
        case = manifest["cases"][0]
        point = case.get("expected_result")
        if not point or point in points:
            problems.append(f"{root}: repeated or absent expected point")
        points.add(point)
        repeats = manifest.get("repetitions")
        if not isinstance(repeats, int) or repeats < 5:
            problems.append(f"{root}: fewer than five repetitions")
            continue
        if (summary.get("status") != "completed" or summary.get("tier") != "tier1"
                or summary.get("valid_pairs") != repeats or len(pairs) != repeats
                or len(calibrations) != repeats or len(runs) != 2 * repeats
                or not summary.get("artifacts_stable") or not summary.get("binaries_stable")
                or not summary.get("runner_stable")):
            problems.append(f"{root}: incomplete or unstable job")
        if any(p.get("status") != "valid" or not isinstance(p.get("speedup"), (float, int))
               or p["speedup"] <= 0 for p in pairs):
            problems.append(f"{root}: invalid solve pair")
        if any(p.get("status") != "valid" for p in calibrations):
            problems.append(f"{root}: invalid A/A calibration")
        if any(r.get("status") != "valid" or not all(
                isinstance(r.get(k), int) for k in (
                    "attempt_start_utc_ns", "attempt_stop_utc_ns",
                    "attempt_start_monotonic_ns", "attempt_stop_monotonic_ns"))
               or r["attempt_stop_monotonic_ns"] <= r["attempt_start_monotonic_ns"]
               for r in runs):
            problems.append(f"{root}: missing valid run or raw timestamps")
        if summary.get("speedup_qualified") is not False or summary.get("paired_speedup") is not None:
            problems.append(f"{root}: one-case job incorrectly promoted")
        fingerprint = (summary.get("allocation_receipt_sha256"),
                       summary.get("runner_sha256"), summary.get("calibrated_runner_sha256"),
                       tuple(sorted(summary.get("binary_sha256", {}).values())),
                       json.dumps(manifest.get("calibration"), sort_keys=True),
                       json.dumps(manifest.get("isolation"), sort_keys=True),
                       tuple(manifest.get("pair_fields", [])), manifest.get("result_field"),
                       manifest.get("measurement_boundary"), manifest.get("timeout_s"))
        fingerprints.append(fingerprint)
        ratios = [p["speedup"] for p in pairs if isinstance(p.get("speedup"), (float, int))]
        if len(ratios) == repeats:
            median = statistics.median(ratios)
            case_medians.append(median)
            case_rows.append({"path": str(root), "point": point, "median_ratio": median})
    if len(paths) < 5 or len(points) < 5:
        problems.append("panel requires at least five distinct points")
    if fingerprints and any(item != fingerprints[0] for item in fingerprints[1:]):
        problems.append("allocation, artifacts, or resource envelope changed across points")
    bootstrap95 = None
    if not problems:
        rng = random.Random(20261014)
        samples = sorted(statistics.median(case_medians[rng.randrange(len(case_medians))]
                                            for _ in case_medians) for _ in range(10000))
        bootstrap95 = [samples[250], samples[9749]]
    qualified = (not problems and all(x > 1 for x in case_medians)
                 and bootstrap95 is not None and bootstrap95[0] > 1)
    return {"status": "valid_panel" if not problems else "invalid_panel",
            "tier": "tier1", "point_count": len(points), "job_count": len(paths),
            "case_rows": case_rows, "bootstrap95_by_point": bootstrap95,
            "all_points_improved": bool(case_medians) and all(x > 1 for x in case_medians),
            "speedup_qualified": qualified,
            "paired_speedup": statistics.median(case_medians) if qualified else None,
            "problems": problems}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_folders", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.job_folders), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
