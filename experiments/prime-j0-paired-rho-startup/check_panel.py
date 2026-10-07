#!/usr/bin/env python3
"""One target, serial ABBA reference/candidate solves, raw failures kept."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = (
    "CMakeLists.txt", "src/curve.c", "src/ec_tau.c", "src/ec_tau_internal.h",
    "include/cryptanalysis/ca_curve.h", "tests/test_curve.c",
    "experiments/prime-j0-paired-rho-startup/bench.c",
    "experiments/prime-j0-paired-rho-startup/make_fixture.py",
    "experiments/prime-j0-paired-rho-startup/check_panel.py",
    "experiments/prime-j0-paired-rho-startup/PROTOCOL.md",
)
COUNTERS = ("group_ops", "table_entries", "table_evaluations",
            "restart_evaluations", "startup_budget_ops")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(bench, mode, fixture):
    command = [str(bench), mode, str(fixture["target_x"]),
               str(fixture["target_y"]), str(fixture["rho_seed"])]
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    record = {"mode": mode, "command": command, "returncode": process.returncode,
              "stdout": process.stdout, "stderr": process.stderr, "fields": None}
    if process.returncode == 0:
        fields = {}
        for part in process.stdout.strip().split():
            if part.count("=") != 1:
                record["parse_error"] = part
                return record
            key, value = part.split("=", 1)
            if key in fields:
                record["parse_error"] = f"duplicate {key}"
                return record
            fields[key] = value
        record["fields"] = fields
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bench", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    bench = args.bench.resolve()
    fixture_path = HERE / "fixture.json"
    fixture = json.loads(fixture_path.read_text())
    result = {
        "schema": 1, "kind": "one-target-rho-correctness-and-exploratory-timing",
        "cpu_speedup_claim": None, "isolation_receipt": None,
        "timing_status": "exploratory_contended_or_unverified_host",
        "fixture_sha256": sha(fixture_path), "benchmark_sha256": sha(bench),
        "source_sha256": {name: sha(REPO / name) for name in SOURCE},
        "trials": [], "summary": None, "pass": False,
    }
    try:
        if fixture["schema"] != 1 or fixture["curve"] != "glv-j0-32":
            raise ValueError("fixture schema or curve mismatch")
        modes = ("reference", "paired2", "paired2", "reference")
        trials = [run(bench, mode, fixture) for mode in modes]
        result["trials"] = trials
        for trial in trials:
            fields = trial["fields"]
            if trial["returncode"] or fields is None:
                raise ValueError(f"failed trial: {trial['mode']}")
            for key, expected in (
                ("mode", trial["mode"]), ("curve", fixture["curve"]),
                ("target_x", str(fixture["target_x"])),
                ("target_y", str(fixture["target_y"])),
                ("seed", str(fixture["rho_seed"])),
                ("scalar", str(fixture["expected_scalar"])), ("verified", "1"),
            ):
                if fields.get(key) != expected:
                    raise ValueError(f"{trial['mode']}: {key} mismatch")
            if float(fields["online_ms"]) <= 0 or float(fields["replay_ms"]) < 0:
                raise ValueError(f"invalid timing: {trial['mode']}")
        def pair(mode):
            rows = [t["fields"] for t in trials if t["mode"] == mode]
            if any(rows[0][key] != rows[1][key] for key in COUNTERS):
                raise ValueError(f"nondeterministic trajectory: {mode}")
            return {key: int(rows[0][key]) for key in COUNTERS}
        reference, candidate = pair("reference"), pair("paired2")
        if reference != candidate:
            raise ValueError("rho trajectory counters diverged")
        candidate_fields = next(t["fields"] for t in trials if t["mode"] == "paired2")
        if not (int(candidate_fields["prepare_inversions"]) == 1 and
                int(candidate_fields["eval_tau"]) > 0 and
                int(candidate_fields["eval_mixed_adds"]) > 0 and
                int(candidate_fields["eval_recode_attempts"]) > 0):
            raise ValueError("candidate startup counters incomplete")
        result["summary"] = {
            "curve": fixture["curve"], "target_x": fixture["target_x"],
            "target_y": fixture["target_y"], "scalar": fixture["expected_scalar"],
            "seed": fixture["rho_seed"], "trajectory": reference,
            "candidate_startup": {
                key: candidate_fields[key] for key in (
                    "prepare_tau", "prepare_doubles", "prepare_mixed_adds",
                    "prepare_inversions", "eval_tau", "eval_mixed_adds",
                    "eval_rotations", "eval_inversions", "eval_recode_attempts",
                    "eval_pair_scores", "eval_lattice_points_checked")
            },
            "verified": True,
        }
        result["pass"] = True
    except (KeyError, ValueError, OSError) as exc:
        result["error"] = str(exc)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"pass": result["pass"], "summary": result["summary"],
                      "error": result.get("error")}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
