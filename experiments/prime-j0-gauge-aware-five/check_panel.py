#!/usr/bin/env python3
"""Serial held-out gate for gauge-aware two- and five-neighbor recoding."""

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
    "experiments/prime-j0-gauge-aware-five/make_inputs.py",
    "experiments/prime-j0-gauge-aware-five/check_panel.py",
    "experiments/prime-j0-gauge-aware-five/PROTOCOL.md",
)
BASE = "paired2-free-gauge"
TWO = "paired2-free-gauge-scored"
FIVE = "paired5-free-gauge-scored"
MODES = (BASE, TWO, FIVE, FIVE, TWO, BASE)
COUNTERS = (
    "precomp_bytes", "prep_tau", "prep_doubles", "prep_mixed_adds",
    "prep_rotations", "prep_inversions", "tau_steps", "doubles",
    "mixed_adds", "full_adds", "rotations", "output_inversions",
    "overlaps", "fused_hits", "recode_attempts", "pair_scores",
    "selected_changed", "lattice_points_checked", "gauge_selected",
    "digit_rotations", "gauge_transitions", "final_rotations",
    "gauge_table_lookups", "gauge_model_rotations", "free_gauge_transitions",
)
PRIOR = ("prime-j0-joint-tau-stream", "prime-j0-hot-orbit-table",
         "prime-j0-paired-lattice-stream", "prime-j0-unit-gauge-stream",
         "prime-j0-gauge-trellis", "prime-j0-free-gauge")


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
            arms = {mode: counts(mode) for mode in (BASE, TWO, FIVE)}
            baseline, scored_two, scored_five = (arms[mode] for mode in
                                                  (BASE, TWO, FIVE))
            for key in ("precomp_bytes", "prep_tau", "prep_doubles",
                        "prep_mixed_adds", "prep_rotations", "prep_inversions",
                        "output_inversions", "full_adds"):
                if len({arm[key] for arm in arms.values()}) != 1:
                    raise ValueError(f"unpaired {key}: {curve}")
            if (baseline["recode_attempts"] != scored_two["recode_attempts"] or
                    baseline["pair_scores"] != scored_two["pair_scores"] or
                    scored_five["recode_attempts"] <= scored_two["recode_attempts"] or
                    scored_five["pair_scores"] <= scored_two["pair_scores"]):
                raise ValueError(f"neighbor search accounting: {curve}")
            for arm in arms.values():
                if (arm["rotations"] != arm["digit_rotations"] +
                        arm["final_rotations"] or arm["gauge_transitions"] != 0 or
                        arm["gauge_model_rotations"] < arm["rotations"]):
                    raise ValueError(f"free-gauge rotation accounting: {curve}")
                arm["weighted_cost_model"] = (6 * arm["tau_steps"] +
                                              11 * arm["mixed_adds"] +
                                              arm["rotations"])
            if not (scored_five["weighted_cost_model"] <=
                    scored_two["weighted_cost_model"] <=
                    baseline["weighted_cost_model"]):
                raise ValueError(f"search lost frozen weighted objective: {curve}")
            result["curves"][curve] = {
                "count": 1024, "pair_sha256": spec["sha256"],
                "arms": arms, "verified": True,
                "two_model_saving": (baseline["weighted_cost_model"] -
                                     scored_two["weighted_cost_model"]),
                "five_model_saving": (baseline["weighted_cost_model"] -
                                      scored_five["weighted_cost_model"]),
                "five_extra_recode_attempts": (scored_five["recode_attempts"] -
                                               baseline["recode_attempts"]),
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
