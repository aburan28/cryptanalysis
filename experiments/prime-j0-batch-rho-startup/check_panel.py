#!/usr/bin/env python3
"""One-target serial panel for batch-normalized paired2 rho startup."""

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
    "tests/test_joint_tau.c", "experiments/prime-j0-paired-rho-startup/bench.c",
    "experiments/prime-j0-batch-rho-startup/make_fixture.py",
    "experiments/prime-j0-batch-rho-startup/check_panel.py",
    "experiments/prime-j0-batch-rho-startup/PROTOCOL.md",
)
MODES = ("reference", "paired2", "paired2-batch", "paired2-batch",
         "paired2", "reference")
TRAJECTORY = ("group_ops", "table_entries", "table_evaluations",
              "restart_evaluations", "startup_budget_ops")
POINT_WORK = ("prepare_tau", "prepare_doubles", "prepare_mixed_adds",
              "prepare_inversions", "eval_tau", "eval_mixed_adds",
              "eval_rotations", "eval_recode_attempts", "eval_pair_scores",
              "eval_lattice_points_checked")


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
    parser = argparse.ArgumentParser(description=__doc__)
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
        previous = json.loads((HERE.parent / "prime-j0-paired-rho-startup/fixture.json").read_text())
        if (fixture.get("schema") != 1 or fixture.get("curve") != "glv-j0-32" or
                fixture.get("target_input_law") != "one_previously_unseen_public_point" or
                (fixture["target_x"], fixture["target_y"]) ==
                (previous["target_x"], previous["target_y"])):
            raise ValueError("fixture is invalid or reuses prior target")
        trials = [run(bench, mode, fixture) for mode in MODES]
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
            rows = [trial["fields"] for trial in trials if trial["mode"] == mode]
            if any(rows[0][key] != rows[1][key] for key in
                   TRAJECTORY + POINT_WORK + ("eval_inversions",
                                              "table_output_inversions",
                                              "restart_output_inversions",
                                              "table_batch_size")):
                raise ValueError(f"nondeterministic counters: {mode}")
            return rows[0]
        reference, paired, batch = (pair(mode) for mode in
                                    ("reference", "paired2", "paired2-batch"))
        for key in TRAJECTORY:
            if len({reference[key], paired[key], batch[key]}) != 1:
                raise ValueError(f"rho trajectory differs: {key}")
        for key in POINT_WORK:
            if paired[key] != batch[key]:
                raise ValueError(f"batch changed point work: {key}")
        table_count = int(batch["table_evaluations"])
        if (int(paired["table_output_inversions"]) != table_count or
                int(batch["table_output_inversions"]) != 1 or
                int(batch["table_batch_size"]) != table_count or
                paired["restart_output_inversions"] != batch["restart_output_inversions"] or
                int(batch["eval_inversions"]) !=
                int(batch["table_output_inversions"]) +
                int(batch["restart_output_inversions"])):
            raise ValueError("batch inversion accounting differs from frozen expectation")
        result["summary"] = {
            "curve": fixture["curve"], "target_x": fixture["target_x"],
            "target_y": fixture["target_y"], "scalar": fixture["expected_scalar"],
            "seed": fixture["rho_seed"],
            "trajectory": {key: int(reference[key]) for key in TRAJECTORY},
            "paired2_output_inversions": int(paired["eval_inversions"]),
            "batch_output_inversions": int(batch["eval_inversions"]),
            "table_inversions_saved": (int(paired["table_output_inversions"]) -
                                       int(batch["table_output_inversions"])),
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
