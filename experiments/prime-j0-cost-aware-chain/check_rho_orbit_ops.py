#!/usr/bin/env python3
"""Replay one frozen rho target across walk seeds; retain operation evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIRST_SEED = 20261007
SEEDS = tuple(range(FIRST_SEED, FIRST_SEED + 32))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fields(stdout):
    return dict(word.split("=", 1) for word in stdout.strip().split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--candidate-kind", choices=("coordinate", "factored"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    fixture = json.loads((HERE / "rho-orbit-one-target.json").read_text())
    paths = {"hash": args.reference.resolve(),
             args.candidate_kind: args.candidate.resolve()}
    rows = []
    for seed in SEEDS:
        pair = {"walk_seed": seed, "runs": {}}
        for arm in paths:
            proc = subprocess.run([str(paths[arm]), str(seed)], capture_output=True,
                                  text=True, timeout=120)
            row = {"exit_code": proc.returncode, "stdout": proc.stdout,
                   "stderr": proc.stderr, "verified": False}
            if proc.returncode == 0:
                got = fields(proc.stdout)
                row["verified"] = all((got.get("arm") == arm,
                                       got.get("curve") == fixture["curve"],
                                       got.get("base_x") == fixture["base_x"],
                                       got.get("base_y") == fixture["base_y"],
                                       got.get("target_x") == fixture["target_x"],
                                       got.get("target_y") == fixture["target_y"],
                                       got.get("scalar") == fixture["scalar"],
                                       got.get("seed") == str(seed),
                                       got.get("verified") == "1"))
                if row["verified"]:
                    row["group_ops"] = int(got["group_ops"])
                    row["replay_ops"] = int(got["replay_ops"])
            pair["runs"][arm] = row
        rows.append(pair)
    complete = all(row["verified"] for pair in rows for row in pair["runs"].values())
    equal_ops = complete and all(
        pair["runs"][args.candidate_kind]["group_ops"] == pair["runs"]["hash"]["group_ops"]
        for pair in rows)
    if args.candidate_kind == "factored" and not equal_ops:
        complete = False
    report = {
        "schema": 1,
        "status": "operation_diagnostic_only" if complete else "diagnostic_failed",
        "cpu_speedup_claim": None,
        "identical_group_ops_all": equal_ops,
        "workload": "one frozen known target replayed independently under 32 walk seeds; secondary operation diagnostic",
        "fixture_sha256": digest(HERE / "rho-orbit-one-target.json"),
        "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in
                          (ROOT / "src" / "curve.c", ROOT / "src" / "curve_internal.h",
                           HERE / "rho_orbit_one_target.c", Path(__file__).resolve())},
        "builds": {arm: {"binary_sha256": digest(path),
                         "cmake_cache_sha256": digest(path.parent / "CMakeCache.txt")}
                   for arm, path in paths.items()},
        "platform": platform.platform(),
        "rows": rows,
    }
    if complete:
        report["median_group_ops"] = {arm: statistics.median(
            pair["runs"][arm]["group_ops"] for pair in rows) for arm in paths}
        report["candidate_fewer_ops_count"] = sum(
            pair["runs"][args.candidate_kind]["group_ops"] < pair["runs"]["hash"]["group_ops"]
            for pair in rows)
    output = args.output or HERE / f"rho-orbit-ops-{args.candidate_kind}.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report.get(key) for key in
                      ("status", "median_group_ops", "candidate_fewer_ops_count")},
                     sort_keys=True))
    if not complete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
