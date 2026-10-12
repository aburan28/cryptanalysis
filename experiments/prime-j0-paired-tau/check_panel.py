#!/usr/bin/env python3
"""Serial held-out gate for paired tau on empty digit positions."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = (
    "CMakeLists.txt", "src/ec_tau.c", "src/ec_tau_internal.h",
    "tests/test_joint_tau.c", "experiments/prime-j0-joint-tau-stream/bench.c",
    "experiments/prime-j0-paired-tau/make_inputs.py",
    "experiments/prime-j0-paired-tau/check_panel.py",
    "experiments/prime-j0-paired-tau/PROTOCOL.md",
)
BASE = "paired2-free-gauge-scored"
PAIRED = "paired2-free-gauge-taupair"
MODES = (BASE, PAIRED, PAIRED, BASE)
COUNTERS = (
    "precomp_bytes", "prep_tau", "prep_doubles", "prep_mixed_adds",
    "prep_rotations", "prep_inversions", "tau_steps", "doubles",
    "mixed_adds", "full_adds", "rotations", "output_inversions",
    "overlaps", "fused_hits", "recode_attempts", "pair_scores",
    "selected_changed", "lattice_points_checked", "gauge_selected",
    "digit_rotations", "gauge_transitions", "final_rotations",
    "gauge_table_lookups", "gauge_model_rotations", "free_gauge_transitions",
    "tau_pairs", "tau_pair_cheap_z",
)
PRIOR = ("prime-j0-joint-tau-stream", "prime-j0-hot-orbit-table",
         "prime-j0-paired-lattice-stream", "prime-j0-unit-gauge-stream",
         "prime-j0-gauge-trellis", "prime-j0-free-gauge",
         "prime-j0-gauge-aware-five")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(bench, mode, curve, path):
    command = [str(bench), mode, curve, str(path)]
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    record = {"mode": mode, "curve": curve, "command": command,
              "returncode": process.returncode, "stdout": process.stdout,
              "stderr": process.stderr, "fields": None}
    if process.returncode == 0:
        fields = {}
        for item in process.stdout.strip().split():
            if item.count("=") != 1:
                record["parse_error"] = item
                return record
            key, value = item.split("=", 1)
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
    manifest_path = HERE / "inputs.json"
    inputs = json.loads(manifest_path.read_text())
    result = {
        "schema": 1, "kind": "held-out-algorithmic-diagnostic-batch",
        "cpu_speedup_claim": None, "isolation_receipt": None,
        "timing_status": "exploratory_contended_or_unverified_host",
        "benchmark_sha256": sha(bench), "input_manifest_sha256": sha(manifest_path),
        "source_sha256": {name: sha(REPO / name) for name in SOURCE},
        "trials": [], "curves": {}, "pass": False,
    }
    try:
        if (inputs.get("schema") != 1 or inputs.get("count") != 1024 or
                inputs.get("oracle") != "independent_affine_scalar_and_mix64_digest"):
            raise ValueError("unexpected independent fixture")
        prior = [json.loads((HERE.parent / name / "inputs.json").read_text())
                 for name in PRIOR]
        for curve, spec in inputs["curves"].items():
            path = HERE / spec["file"]
            if sha(path) != spec["sha256"] or any(
                    spec["sha256"] == entry["curves"][curve]["sha256"] for entry in prior):
                raise ValueError(f"held-out input SHA mismatch: {curve}")
            trials = []
            for mode in MODES:
                trial = run(bench, mode, curve, path)
                trials.append(trial)
                result["trials"].append(trial)
            for trial in trials:
                fields = trial["fields"]
                if trial["returncode"] or fields is None:
                    raise ValueError(f"failed trial: {curve} {trial['mode']}")
                for key, expected in (
                    ("curve", curve), ("mode", trial["mode"]), ("count", "1024"),
                    ("base_x", str(spec["base_x"])), ("base_y", str(spec["base_y"])),
                    ("partner_x", str(spec["partner_x"])),
                    ("partner_y", str(spec["partner_y"])),
                    ("input_digest", spec["generic_input_digest"]),
                    ("output_digest", spec["generic_output_digest"]),
                    ("verified", "1"),
                ):
                    if fields.get(key) != expected:
                        raise ValueError(f"{curve} {trial['mode']}: {key} mismatch")
            def counts(mode):
                pair = [trial["fields"] for trial in trials if trial["mode"] == mode]
                if any(pair[0][key] != pair[1][key] for key in COUNTERS):
                    raise ValueError(f"nondeterministic counters: {curve} {mode}")
                return {key: int(pair[0][key]) for key in COUNTERS}
            arms = {mode: counts(mode) for mode in (BASE, PAIRED)}
            baseline, paired = arms[BASE], arms[PAIRED]
            for key in COUNTERS:
                if key not in ("tau_pairs", "tau_pair_cheap_z") and baseline[key] != paired[key]:
                    raise ValueError(f"operation changed: {curve} {key}")
            if (baseline["tau_pairs"] != 0 or baseline["tau_pair_cheap_z"] != 0 or
                    paired["tau_pairs"] <= 0 or
                    paired["tau_pair_cheap_z"] > paired["tau_pairs"] or
                    2 * paired["tau_pairs"] > paired["tau_steps"]):
                raise ValueError(f"tau pair accounting: {curve}")
            result["curves"][curve] = {
                "count": 1024, "pair_sha256": spec["sha256"],
                "arms": arms, "verified": True,
                "field_multiplications_saved_by_formula": (
                    paired["tau_pairs"] + paired["tau_pair_cheap_z"]),
            }
        result["pass"] = True
    except (KeyError, ValueError, OSError) as exc:
        result["error"] = str(exc)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"pass": result["pass"], "curves": result["curves"],
                      "error": result.get("error")}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
