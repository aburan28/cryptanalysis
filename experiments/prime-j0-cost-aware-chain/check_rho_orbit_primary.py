#!/usr/bin/env python3
"""Capture serial legacy/factored full solves of the frozen large target."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from make_rho_orbit_manifest import checked_fixture

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fields(stdout):
    return dict(word.split("=", 1) for word in stdout.strip().split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "rho-orbit-primary-smoke.json")
    args = parser.parse_args()
    fixture = checked_fixture("j0-56")
    paths = {"hash": args.reference.resolve(), "factored": args.candidate.resolve()}
    rows = []
    for arm in ("hash", "factored"):
        command = [str(paths[arm]), "j0-56"]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=600)
        row = {"arm": arm, "command": command, "exit_code": proc.returncode,
               "stdout": proc.stdout, "stderr": proc.stderr, "verified": False}
        if proc.returncode == 0:
            got = fields(proc.stdout)
            expected = {key: fixture[key] for key in
                        ("curve", "base_x", "base_y", "target_x", "target_y", "scalar")}
            expected["seed"] = str(fixture["walk_seed"])
            row["verified"] = (got.get("arm") == arm and got.get("verified") == "1"
                               and all(got.get(key) == value for key, value in expected.items()))
            if row["verified"]:
                row["group_ops"] = int(got["group_ops"])
                row["replay_ops"] = int(got["replay_ops"])
                row["online_ms_exploratory"] = float(got["online_ms"])
        rows.append(row)
    passed = all(row["verified"] for row in rows)
    equal_ops = passed and rows[0]["group_ops"] == rows[1]["group_ops"]
    report = {
        "schema": 1,
        "status": "one_target_correctness_only" if passed and equal_ops else "smoke_failed",
        "cpu_speedup_claim": None,
        "isolation_receipt": None,
        "fixture_sha256": digest(HERE / "rho-orbit-primary-target.json"),
        "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in
                          (ROOT / "src" / "curve.c", ROOT / "src" / "curve_internal.h",
                           HERE / "rho_orbit_one_target.c", Path(__file__).resolve())},
        "binary_sha256": {arm: digest(path) for arm, path in paths.items()},
        "build_cache_sha256": {arm: digest(path.parent / "CMakeCache.txt")
                               for arm, path in paths.items()},
        "platform": platform.platform(),
        "identical_group_ops": equal_ops,
        "runs": rows,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"],
                      "group_ops": rows[0].get("group_ops"),
                      "identical_group_ops": equal_ops}, sort_keys=True))
    if report["status"] != "one_target_correctness_only":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
