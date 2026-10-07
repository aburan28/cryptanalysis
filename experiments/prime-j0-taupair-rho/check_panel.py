#!/usr/bin/env python3
"""One-target serial panel for the gauge-carrying paired-tau rho startup."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = (
    "CMakeLists.txt", "src/curve.c", "src/ec_tau.c", "src/ec_tau_internal.h",
    "src/generated/tau_gauge_trellis.h",
    "include/cryptanalysis/ca_curve.h", "tests/test_curve.c",
    "tests/test_joint_tau.c", "experiments/prime-j0-paired-rho-startup/bench.c",
    "experiments/prime-j0-taupair-rho/make_fixture.py",
    "experiments/prime-j0-taupair-rho/check_panel.py",
    "experiments/prime-j0-taupair-rho/make_isolated_manifest.py",
    "experiments/prime-j0-taupair-rho/PROTOCOL.md",
)
BASE = "paired2-free-gauge-batch"
CANDIDATE = "taupair-steered-batch"
MODES = ("reference", BASE, CANDIDATE, CANDIDATE, BASE, "reference")
TRAJECTORY = ("group_ops", "table_entries", "table_evaluations",
              "restart_evaluations", "startup_budget_ops",
              "startup_point_count", "startup_point_digest_lo",
              "startup_point_digest_hi")
PREPARATION = ("prepare_tau", "prepare_doubles", "prepare_mixed_adds",
               "prepare_inversions", "prepare_rotations", "precomp_bytes",
               "table_output_inversions", "restart_output_inversions",
               "table_batch_size", "eval_inversions", "eval_recode_attempts",
               "eval_pair_scores", "eval_lattice_points_checked")
EVALUATION = ("eval_tau", "eval_mixed_adds", "eval_rotations",
              "eval_free_gauge_transitions", "eval_tau_pairs",
              "eval_tau_pair_cheap_z", "eval_gauge_table_lookups")
OTHER_TARGETS = {(1214753992, 1398575280), (2247774444, 1906310386)}


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
        previous = [json.loads((HERE.parent / name / "fixture.json").read_text())
                    for name in ("prime-j0-paired-rho-startup",
                                 "prime-j0-batch-rho-startup",
                                 "prime-j0-unit-plane-rho",
                                 "prime-j0-free-gauge-rho")]
        if (fixture.get("schema") != 1 or fixture.get("curve") != "glv-j0-32" or
                fixture.get("target_input_law") != "one_previously_unseen_public_point" or
                any((fixture["target_x"], fixture["target_y"]) ==
                    (item["target_x"], item["target_y"]) for item in previous) or
                (fixture["target_x"], fixture["target_y"]) in OTHER_TARGETS):
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
                   TRAJECTORY + PREPARATION + EVALUATION):
                raise ValueError(f"nondeterministic counters: {mode}")
            return rows[0]
        reference, baseline, candidate = (pair(mode) for mode in
                                          ("reference", BASE, CANDIDATE))
        for key in TRAJECTORY:
            if len({reference[key], baseline[key], candidate[key]}) != 1:
                raise ValueError(f"rho trajectory differs: {key}")
        for key in ("startup_point_digest_lo", "startup_point_digest_hi"):
            if not re.fullmatch(r"[0-9a-f]{16}", reference[key]):
                raise ValueError(f"malformed startup point fingerprint: {key}")
        if (int(reference["startup_point_count"]) !=
                int(reference["table_evaluations"]) +
                int(reference["restart_evaluations"])):
            raise ValueError("startup point count misses an evaluation")
        for key in PREPARATION:
            if baseline[key] != candidate[key]:
                raise ValueError(f"preparation or invariant changed: {key}")
        if (int(baseline["precomp_bytes"]) != 1104 or
                int(baseline["table_output_inversions"]) != 1 or
                int(baseline["eval_tau_pairs"]) != 0 or
                int(baseline["eval_tau_pair_cheap_z"]) != 0 or
                int(baseline["eval_gauge_table_lookups"]) != 0 or
                int(candidate["eval_tau_pairs"]) <= 0 or
                int(candidate["eval_tau_pair_cheap_z"]) >
                int(candidate["eval_tau_pairs"]) or
                int(candidate["eval_gauge_table_lookups"]) !=
                int(candidate["eval_tau_pairs"])):
            raise ValueError("paired-tau accounting differs from frozen expectation")
        def formula_m(row):
            return (4 * int(row["eval_tau"]) +
                    8 * int(row["eval_mixed_adds"]) +
                    int(row["eval_rotations"]) -
                    int(row["eval_tau_pairs"]) -
                    int(row["eval_tau_pair_cheap_z"]))
        m_saved = formula_m(baseline) - formula_m(candidate)
        if m_saved <= 0:
            raise ValueError("candidate did not lower frozen formula M count")
        result["summary"] = {
            "curve": fixture["curve"], "target_x": fixture["target_x"],
            "target_y": fixture["target_y"], "scalar": fixture["expected_scalar"],
            "seed": fixture["rho_seed"],
            "trajectory": {key: (reference[key] if key.startswith("startup_point_digest")
                                else int(reference[key])) for key in TRAJECTORY},
            "baseline_formula_m": formula_m(baseline),
            "candidate_formula_m": formula_m(candidate),
            "formula_m_saved": m_saved,
            "candidate_tau_pairs": int(candidate["eval_tau_pairs"]),
            "candidate_cheap_z": int(candidate["eval_tau_pair_cheap_z"]),
            "candidate_gauge_lookups": int(candidate["eval_gauge_table_lookups"]),
            "precomp_bytes": int(candidate["precomp_bytes"]),
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
