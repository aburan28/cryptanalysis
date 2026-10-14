#!/usr/bin/env python3
"""Replay a serial panel from raw isolated-benchmark job directories."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
from statistics import median


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], probability: float) -> float:
    position = (len(values) - 1) * probability
    low = int(position)
    fraction = position - low
    return values[low] * (1 - fraction) + values[low + 1] * fraction


def summarize(root: Path, cases: list[tuple[int, str]], comparison: str,
              archive_sha: str, seed: int, replicates: int) -> dict:
    if not cases or len({index for index, _ in cases}) != len(cases):
        raise ValueError("case indices must be nonempty and unique")
    rows = []
    binaries = []
    runners = []
    for index, job_id in sorted(cases):
        job = root / job_id
        summary = json.loads((job / "summary.json").read_text())
        pairs = [json.loads(line) for line in (job / "pairs.jsonl").read_text().splitlines()]
        runs = [json.loads(line) for line in (job / "runs.jsonl").read_text().splitlines()]
        if (summary["status"] != "completed" or
                summary["valid_pairs"] != summary["expected_pairs"] or
                len(pairs) != summary["valid_pairs"] or
                len(runs) != 2 * len(pairs) or
                not all(row["status"] == "valid" for row in pairs + runs) or
                not all(summary[key] for key in (
                    "artifacts_stable", "binaries_stable", "runner_stable")) or
                summary["host_exclusivity_proved"]):
            raise ValueError(f"invalid or incomparable job: {job_id}")
        ratios = [pair["speedup"] for pair in pairs]
        if median(ratios) != summary["observed_ratio_median"]:
            raise ValueError(f"ratio mismatch: {job_id}")
        binaries.append(summary["binary_sha256"])
        runners.append(summary["runner_sha256"])
        rows.append({
            "case_index": index,
            "job_id": job_id,
            "manifest_sha256": digest(job / "manifest.json"),
            "summary_sha256": digest(job / "summary.json"),
            "valid_pairs": len(pairs),
            "median_ratio": median(ratios),
            "ratios": ratios,
            "bootstrap95_by_pair": summary["bootstrap95_by_pair"],
        })
    if any(item != binaries[0] for item in binaries) or len(set(runners)) != 1:
        raise ValueError("binary or runner changed across cases")
    rng = random.Random(seed)
    boot = []
    for _ in range(replicates):
        selected = [rng.choice(rows) for _ in rows]
        case_medians = [median(rng.choices(row["ratios"], k=len(row["ratios"])))
                        for row in selected]
        boot.append(median(case_medians))
    boot.sort()
    case_medians = [row["median_ratio"] for row in rows]
    return {
        "schema": 1,
        "comparison": comparison,
        "tier": "instance_scoped_tier1",
        "aggregation": "median of case medians; hierarchical bootstrap resamples cases then ratios within each case with replacement, then takes median",
        "bootstrap_seed": seed,
        "bootstrap_replicates": replicates,
        "case_medians": rows,
        "median_of_case_medians": median(case_medians),
        "range_of_case_medians": [min(case_medians), max(case_medians)],
        "hierarchical_bootstrap95": [percentile(boot, .025), percentile(boot, .975)],
        "valid_pair_count": sum(row["valid_pairs"] for row in rows),
        "valid_run_count": 2 * sum(row["valid_pairs"] for row in rows),
        "job_count": len(rows),
        "binary_sha256": binaries[0],
        "runner_sha256": runners[0],
        "transferred_archive_sha256": archive_sha,
        "host_exclusivity_proved": False,
        "qualified_host_isolated_speedup": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--case", action="append", required=True,
                        help="frozen case index followed by job ID, e.g. 1:abc123")
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--archive-sha", required=True)
    parser.add_argument("--seed", type=int, default=20261014)
    parser.add_argument("--replicates", type=int, default=20000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = []
    for item in args.case:
        index, job_id = item.split(":", 1)
        cases.append((int(index), job_id))
    result = summarize(args.root, cases, args.comparison, args.archive_sha,
                       args.seed, args.replicates)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "median_of_case_medians", "hierarchical_bootstrap95",
        "valid_pair_count", "valid_run_count")}, sort_keys=True))


if __name__ == "__main__":
    main()
