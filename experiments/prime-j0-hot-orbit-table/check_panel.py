#!/usr/bin/env python3
"""Held-out three-arm panel with raw trials and no CPU speedup promotion."""
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
    "CMakeLists.txt", "src/ec_tau.c", "src/ec_tau_internal.h",
    "tests/test_joint_tau.c", "experiments/prime-j0-joint-tau-stream/bench.c",
    "experiments/prime-j0-hot-orbit-table/hist.c",
    "experiments/prime-j0-hot-orbit-table/choose_hot.py",
    "experiments/prime-j0-hot-orbit-table/make_inputs.py",
    "experiments/prime-j0-hot-orbit-table/check_panel.py",
    "experiments/prime-j0-hot-orbit-table/hot64_selected.h",
    "experiments/prime-j0-hot-orbit-table/PROTOCOL.md",
)
COUNT_FIELDS = (
    "precomp_bytes", "prep_tau", "prep_doubles", "prep_mixed_adds",
    "prep_rotations", "prep_inversions", "tau_steps", "doubles",
    "mixed_adds", "full_adds", "rotations", "output_inversions",
    "overlaps", "fused_hits",
)


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
    selection_path = HERE / "selection.json"
    inputs = json.loads(input_path.read_text())
    selection = json.loads(selection_path.read_text())
    result = {
        "schema": 1, "kind": "held-out-algorithmic-diagnostic-batch",
        "cpu_speedup_claim": None, "isolation_receipt": None,
        "timing_status": "exploratory_contended_or_unverified_host",
        "benchmark_sha256": sha(bench), "input_manifest_sha256": sha(input_path),
        "selection_sha256": sha(selection_path),
        "source_sha256": {name: sha(REPO / name) for name in SOURCE},
        "trials": [], "curves": {}, "pass": False,
    }
    try:
        if inputs["count"] != 1024 or inputs["schema"] != 1 or selection["schema"] != 1:
            raise ValueError("manifest schema or count mismatch")
        old_manifest = REPO / "experiments/prime-j0-joint-tau-stream/inputs.json"
        if sha(old_manifest) != selection["training_manifest_sha256"]:
            raise ValueError("training manifest SHA mismatch")
        header = (HERE / "hot64_selected.h").read_text()
        for curve, symbol in (("glv-j0-32", "ca_hot64_j0_32"),
                              ("j0-56", "ca_hot64_j0_56")):
            match = re.search(rf"static const uint16_t {symbol}\[64\] = \{{([^}}]*)\}};", header)
            if match is None or [int(x) for x in re.findall(r"\d+", match.group(1))] != selection["curves"][curve]["selected"]:
                raise ValueError(f"selected header mismatch: {curve}")
        if inputs["label"] == "joint-prime-j0-tau-stream-prospective-20261007-v1":
            raise ValueError("training input reused for held-out evaluation")
        for curve, spec in inputs["curves"].items():
            path = HERE / spec["file"]
            if sha(path) != spec["sha256"] or spec["sha256"] == selection["curves"][curve]["input_sha256"]:
                raise ValueError(f"held-out input SHA mismatch: {curve}")
            if not spec["generic_input_digest"] or not spec["generic_output_digest"]:
                raise ValueError(f"generic digests not frozen: {curve}")
            runs = [run(bench, mode, curve, path)
                    for mode in ("joint", "hot64", "orbit", "orbit", "hot64", "joint")]
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
                if any(pair[0][key] != pair[1][key] for key in COUNT_FIELDS):
                    raise ValueError(f"nondeterministic counts: {curve} {mode}")
                return {key: int(pair[0][key]) for key in COUNT_FIELDS}
            joint, hot, dense = (counts(mode) for mode in ("joint", "hot64", "orbit"))
            for key in ("tau_steps", "doubles", "full_adds", "output_inversions", "overlaps"):
                if len({joint[key], hot[key], dense[key]}) != 1:
                    raise ValueError(f"unpaired {key}: {curve}")
            if not (joint["fused_hits"] == 0 and dense["fused_hits"] == joint["overlaps"]
                    and 0 < hot["fused_hits"] < dense["fused_hits"]
                    and joint["mixed_adds"] > hot["mixed_adds"] >= dense["mixed_adds"]
                    and hot["prep_mixed_adds"] - joint["prep_mixed_adds"] == 64
                    and dense["prep_mixed_adds"] - joint["prep_mixed_adds"] == 486
                    and hot["prep_inversions"] == dense["prep_inversions"] == joint["prep_inversions"] + 1):
                raise ValueError(f"hot/dense operation gate failed: {curve}")
            saved = joint["mixed_adds"] - hot["mixed_adds"]
            result["curves"][curve] = {
                "count": 1024, "pair_sha256": spec["sha256"],
                "joint": joint, "hot64": hot, "dense": dense,
                "hot_hit_fraction": f"{hot['fused_hits']}/{joint['overlaps']}",
                "hot_mixed_adds_saved": saved,
                "hot_mixed_add_only_break_even_evaluations_lower_bound":
                    (64 * 1024 + saved - 1) // saved,
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
