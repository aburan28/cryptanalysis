#!/usr/bin/env python3
"""Held-out paired-lattice panel; retain all trials without CPU claims."""
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
    "experiments/prime-j0-paired-lattice-stream/make_inputs.py",
    "experiments/prime-j0-paired-lattice-stream/check_panel.py",
    "experiments/prime-j0-paired-lattice-stream/PROTOCOL.md",
)
COUNTERS = (
    "precomp_bytes", "prep_tau", "prep_doubles", "prep_mixed_adds",
    "prep_rotations", "prep_inversions", "tau_steps", "doubles",
    "mixed_adds", "full_adds", "rotations", "output_inversions",
    "overlaps", "fused_hits", "recode_attempts", "pair_scores",
    "selected_changed", "lattice_points_checked",
)
MODES = ("joint", "paired2", "paired5", "paired", "paired", "paired5", "paired2", "joint")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(bench, mode, curve, path):
    process = subprocess.run([str(bench), mode, curve, str(path)],
                             capture_output=True, text=True, check=False)
    record = {"mode": mode, "curve": curve, "returncode": process.returncode,
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
    input_path = HERE / "inputs.json"
    inputs = json.loads(input_path.read_text())
    result = {
        "schema": 1, "kind": "held-out-algorithmic-diagnostic-batch",
        "cpu_speedup_claim": None, "isolation_receipt": None,
        "timing_status": "exploratory_contended_or_unverified_host",
        "benchmark_sha256": sha(bench), "input_manifest_sha256": sha(input_path),
        "source_sha256": {name: sha(REPO / name) for name in SOURCE},
        "trials": [], "curves": {}, "pass": False,
    }
    try:
        if inputs["count"] != 1024 or inputs["schema"] != 1:
            raise ValueError("manifest schema or count mismatch")
        old = json.loads((HERE.parent / "prime-j0-joint-tau-stream/inputs.json").read_text())
        hot = json.loads((HERE.parent / "prime-j0-hot-orbit-table/inputs.json").read_text())
        for curve, spec in inputs["curves"].items():
            path = HERE / spec["file"]
            if sha(path) != spec["sha256"] or spec["sha256"] in (
                old["curves"][curve]["sha256"], hot["curves"][curve]["sha256"]
            ):
                raise ValueError(f"held-out input SHA mismatch: {curve}")
            if not spec["generic_input_digest"] or not spec["generic_output_digest"]:
                raise ValueError(f"generic digests not frozen: {curve}")
            runs = [run(bench, mode, curve, path) for mode in MODES]
            result["trials"].extend(runs)
            for record in runs:
                f = record["fields"]
                if record["returncode"] or f is None:
                    raise ValueError(f"failed trial: {curve} {record['mode']}")
                for key, expected in (("curve", curve), ("mode", record["mode"]),
                                      ("count", "1024"), ("verified", "1"),
                                      ("input_digest", spec["generic_input_digest"]),
                                      ("output_digest", spec["generic_output_digest"])):
                    if f.get(key) != expected:
                        raise ValueError(f"{curve} {record['mode']}: {key} mismatch")
            def counts(mode):
                pair = [r["fields"] for r in runs if r["mode"] == mode]
                if any(pair[0][key] != pair[1][key] for key in COUNTERS):
                    raise ValueError(f"nondeterministic counters: {curve} {mode}")
                return {key: int(pair[0][key]) for key in COUNTERS}
            arms = {mode: counts(mode) for mode in ("joint", "paired2", "paired5", "paired")}
            common = ("precomp_bytes", "prep_tau", "prep_doubles", "prep_mixed_adds",
                      "prep_rotations", "prep_inversions", "full_adds", "output_inversions")
            for key in common:
                if len({arm[key] for arm in arms.values()}) != 1:
                    raise ValueError(f"unpaired {key}: {curve}")
            joint, two, five, full = (arms[mode] for mode in ("joint", "paired2", "paired5", "paired"))
            if not (joint["recode_attempts"] <= two["recode_attempts"] <= five["recode_attempts"] <= full["recode_attempts"]
                    and two["pair_scores"] <= five["pair_scores"] <= full["pair_scores"]
                    and all(arm["fused_hits"] == 0 for arm in arms.values())):
                raise ValueError(f"recoding structure mismatch: {curve}")
            for arm in arms.values():
                arm["field_operation_model"] = 6 * arm["tau_steps"] + 11 * arm["mixed_adds"] + arm["rotations"]
            result["curves"][curve] = {
                "count": 1024, "pair_sha256": spec["sha256"],
                "arms": arms,
                "paired2_tau_steps_saved": joint["tau_steps"] - two["tau_steps"],
                "paired2_mixed_adds_saved": joint["mixed_adds"] - two["mixed_adds"],
                "paired2_rotations_saved": joint["rotations"] - two["rotations"],
                "verified": True,
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
