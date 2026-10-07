#!/usr/bin/env python3
"""Compare the fused orbit table with the frozen, same-input joint stream."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
INPUTS = REPO / "experiments/prime-j0-joint-tau-stream/inputs.json"
SOURCES = (
    "src/ec_tau.c", "src/ec_tau_internal.h", "tests/test_joint_tau.c",
    "experiments/prime-j0-joint-tau-stream/bench.c",
    "experiments/prime-j0-joint-orbit-pairs/check_panel.py",
    "experiments/prime-j0-joint-orbit-pairs/PROTOCOL.md",
)
FIELDS = (
    "precomp_bytes", "prep_tau", "prep_doubles", "prep_mixed_adds",
    "prep_rotations", "prep_inversions", "tau_steps", "mixed_adds",
    "full_adds", "rotations", "output_inversions", "overlaps", "fused_hits",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trial(bench, mode, curve, path):
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
    inputs = json.loads(INPUTS.read_text())
    result = {
        "schema": 1, "kind": "algorithmic-diagnostic-batch",
        "cpu_speedup_claim": None, "isolation_receipt": None,
        "timing_status": "exploratory_contended_or_unverified_host",
        "benchmark_sha256": sha(bench), "input_manifest_sha256": sha(INPUTS),
        "source_sha256": {name: sha(REPO / name) for name in SOURCES},
        "trials": [], "curves": {}, "pass": False,
    }
    try:
        for curve, spec in inputs["curves"].items():
            path = INPUTS.parent / spec["file"]
            if sha(path) != spec["sha256"]:
                raise ValueError(f"input SHA mismatch: {curve}")
            runs = [trial(bench, mode, curve, path)
                    for mode in ("joint", "orbit", "orbit", "joint")]
            result["trials"].extend(runs)
            for run in runs:
                f = run["fields"]
                if run["returncode"] != 0 or f is None:
                    raise ValueError(f"failed trial: {curve} {run['mode']}")
                for key, expected in (
                    ("mode", run["mode"]), ("curve", curve),
                    ("count", "1024"), ("verified", "1"),
                    ("input_digest", spec["generic_input_digest"]),
                    ("output_digest", spec["generic_output_digest"]),
                ):
                    if f.get(key) != expected:
                        raise ValueError(f"{curve} {run['mode']}: {key} mismatch")
            def counts(mode):
                selected = [r["fields"] for r in runs if r["mode"] == mode]
                if any(selected[0][key] != selected[1][key] for key in FIELDS):
                    raise ValueError(f"nondeterministic counts: {curve} {mode}")
                return {key: int(selected[0][key]) for key in FIELDS}
            joint, orbit = counts("joint"), counts("orbit")
            same = ("prep_tau", "prep_doubles", "tau_steps", "full_adds",
                    "output_inversions", "overlaps")
            if any(joint[key] != orbit[key] for key in same):
                raise ValueError(f"different stream or output work: {curve}")
            if not (orbit["fused_hits"] == joint["overlaps"] > 0 and
                    joint["fused_hits"] == 0 and
                    joint["mixed_adds"] > orbit["mixed_adds"] and
                    orbit["prep_mixed_adds"] - joint["prep_mixed_adds"] == 486 and
                    orbit["prep_inversions"] - joint["prep_inversions"] == 1):
                raise ValueError(f"fusion or preparation gate failed: {curve}")
            saved = joint["mixed_adds"] - orbit["mixed_adds"]
            result["curves"][curve] = {
                "count": 1024, "pair_sha256": spec["sha256"],
                "joint": joint, "orbit": orbit,
                "online_mixed_adds_saved": saved,
                "extra_prep_mixed_adds": 486,
                "mixed_add_only_break_even_evaluations_lower_bound":
                    (486 * 1024 + saved - 1) // saved,
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
