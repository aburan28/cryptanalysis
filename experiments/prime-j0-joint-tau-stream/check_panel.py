#!/usr/bin/env python3
"""Replay the frozen panel; preserve raw trials and decline CPU speed claims."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_FILES = (
    "CMakeLists.txt", "src/ec_tau.c", "src/ec_tau_internal.h",
    "experiments/prime-j0-joint-tau-stream/bench.c",
    "experiments/prime-j0-joint-tau-stream/make_inputs.py",
    "experiments/prime-j0-joint-tau-stream/check_panel.py",
    "experiments/prime-j0-joint-tau-stream/PROTOCOL.md",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_line(line):
    result = {}
    for field in line.strip().split():
        if field.count("=") != 1:
            raise ValueError(f"bad output field: {field}")
        key, value = field.split("=", 1)
        if key in result:
            raise ValueError(f"duplicate output field: {key}")
        result[key] = value
    return result


def run(bench, mode, curve, pair_path):
    completed = subprocess.run([str(bench), mode, curve, str(pair_path)],
                               capture_output=True, text=True, check=False)
    trial = {
        "mode": mode, "curve": curve, "returncode": completed.returncode,
        "stdout": completed.stdout, "stderr": completed.stderr,
        "fields": None,
    }
    if completed.returncode == 0:
        try:
            trial["fields"] = parse_line(completed.stdout)
        except ValueError as exc:
            trial["parse_error"] = str(exc)
    return trial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bench", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    repo = HERE.parents[1]
    bench = args.bench.resolve()
    manifest_path = HERE / "inputs.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["count"] != 1024 or manifest["schema"] != 1:
        raise SystemExit("unsupported frozen input manifest")
    result = {
        "schema": 1, "kind": "algorithmic-diagnostic-batch",
        "cpu_speedup_claim": None, "isolation_receipt": None,
        "timing_status": "exploratory_contended_or_unverified_host",
        "benchmark_sha256": sha(bench), "manifest_sha256": sha(manifest_path),
        "source_sha256": {name: sha(repo / name) for name in SOURCE_FILES},
        "trials": [], "curves": {}, "pass": False,
    }
    try:
        for curve, spec in manifest["curves"].items():
            pair_path = HERE / spec["file"]
            if sha(pair_path) != spec["sha256"]:
                raise ValueError(f"input SHA mismatch for {curve}")
            if not spec["generic_input_digest"] or not spec["generic_output_digest"]:
                raise ValueError(f"generic digest not frozen for {curve}")
            # ABBA order makes drift visible; no local wall-time claim follows.
            trials = [run(bench, mode, curve, pair_path)
                      for mode in ("split", "joint", "joint", "split")]
            result["trials"].extend(trials)
            for trial in trials:
                fields = trial["fields"]
                if trial["returncode"] or fields is None:
                    raise ValueError(f"failed trial: {curve} {trial['mode']}")
                if fields.get("verified") != "1" or fields.get("count") != "1024":
                    raise ValueError(f"unverified or incomplete trial: {curve}")
                if fields.get("input_digest") != spec["generic_input_digest"]:
                    raise ValueError(f"input digest mismatch: {curve}")
                if fields.get("output_digest") != spec["generic_output_digest"]:
                    raise ValueError(f"generic output mismatch: {curve} {trial['mode']}")
                if fields.get("curve") != curve or fields.get("mode") != trial["mode"]:
                    raise ValueError(f"identity mismatch: {curve}")
            def one(mode, key):
                values = [int(t["fields"][key]) for t in trials if t["mode"] == mode]
                if values[0] != values[1]:
                    raise ValueError(f"nondeterministic {key}: {curve} {mode}")
                return values[0]
            prep_keys = ("prep_tau", "prep_doubles", "prep_mixed_adds", "prep_inversions")
            online_keys = ("tau_steps", "doubles", "mixed_adds", "full_adds",
                           "rotations", "output_inversions")
            for key in prep_keys + ("mixed_adds", "rotations", "output_inversions"):
                if one("split", key) != one("joint", key):
                    raise ValueError(f"unpaired {key}: {curve}")
            split = {key: one("split", key) for key in online_keys}
            joint = {key: one("joint", key) for key in online_keys}
            if not (split["tau_steps"] > joint["tau_steps"] and
                    split["full_adds"] > joint["full_adds"] and
                    joint["full_adds"] == 0):
                raise ValueError(f"expected operation saving absent: {curve}")
            result["curves"][curve] = {
                "count": manifest["count"], "pair_sha256": spec["sha256"],
                "prep": {key: one("joint", key) for key in prep_keys},
                "split": split, "joint": joint,
                "tau_steps_saved": split["tau_steps"] - joint["tau_steps"],
                "full_adds_saved": split["full_adds"] - joint["full_adds"],
                "verified": True,
            }
        result["pass"] = True
    except (ValueError, KeyError, OSError) as exc:
        result["error"] = str(exc)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"pass": result["pass"], "curves": result["curves"],
                      "error": result.get("error")}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
