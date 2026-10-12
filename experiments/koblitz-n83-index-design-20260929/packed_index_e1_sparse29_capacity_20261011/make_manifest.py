#!/usr/bin/env python3
"""Freeze the matched N83 sparse28/sparse29 physical-host capacity replay."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from benchmark_stage import ARM_FIELDS, MODES, PAIR_FIELDS, canonical, digest
from restore_crypto_source import ensure_snapshot
from verify_partial import main as verify_partial


RELATIVE = Path("experiments/koblitz-n83-index-design-20260929")
EXPERIMENT = RELATIVE / "packed_index_e1_sparse29_capacity_20261011"
INPUTS = RELATIVE / "adaptive_all_orientations_20261004" / "inputs"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--cgroup", required=True, type=Path)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", required=True, type=int)
    parser.add_argument("--mem-nodes", required=True)
    parser.add_argument("--repetitions", type=int, default=4)
    parser.add_argument("--timeout-s", type=int, default=900)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    root = args.workdir.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    python = args.python.resolve(strict=True)
    experiment = root / EXPERIMENT
    inputs = root / INPUTS
    stage = experiment / "stage_manifest.json"
    protocol = experiment / "protocol.json"
    source = experiment / "native_packed_index.rs"
    bridge = inputs / "n83_onb_poly_bridge.json"
    reps = inputs / "n83_x_representatives.bin"
    reference = experiment / "run_1_sparse28.json"
    candidate = experiment / "run_2_sparse29.json"
    wrapper = experiment / "benchmark_stage.py"
    interruption_path = experiment / "interruption.json"
    tests_path = experiment / "test_record.json"
    frozen = json.loads(stage.read_text())
    receipt = json.loads(protocol.read_text())
    interruption = json.loads(interruption_path.read_text())
    tests = json.loads(tests_path.read_text())
    expected_reference = json.loads(reference.read_text())
    expected_candidate = json.loads(candidate.read_text())
    ensure_snapshot()
    verify_partial()

    if (receipt["workload_id"] != "63dd0929cf33" or
            receipt["run_order"][:2] != list(MODES) or
            frozen["target_count"] != 1 or frozen["pair_state_cap"] != 29_900_000 or
            frozen["peak_rss_cap_mib"] != 5500 or
            interruption["panel_complete"] is not False or
            interruption["interrupted_run"] != "run_4_sparse28" or
            tests["status"] != "PASS"):
        raise ValueError("frozen capacity protocol differs")
    for path, key in ((source, "source"), (bridge, "bridge"),
                      (reps, "representatives"), (stage, "stage_manifest"),
                      (experiment / "run.py", "runner"),
                      (experiment / "Cargo.toml", "cargo_manifest"),
                      (experiment / "Cargo.lock", "cargo_lock")):
        if digest(path) != receipt["input_sha256"][key]:
            raise ValueError("frozen input digest mismatch: " + str(path))
    if (expected_reference["index_mode"] != MODES[0] or
            expected_candidate["index_mode"] != MODES[1]):
        raise ValueError("frozen mode mismatch")
    for expected in (expected_reference, expected_candidate):
        if (expected["stage_protocol_sha256"] != frozen["stage_protocol_sha256"] or
                expected["native_source_sha256"] != receipt["input_sha256"]["source"] or
                expected["cargo_manifest_sha256"] != receipt["input_sha256"]["cargo_manifest"] or
                expected["input_representatives_sha256"] != receipt["input_sha256"]["representatives"]):
            raise ValueError("frozen result digest mismatch")
    if any(expected_reference[name] != expected_candidate[name] for name in PAIR_FIELDS):
        raise ValueError("paired correctness fields differ")
    for field in ARM_FIELDS:
        if field not in expected_reference or field not in expected_candidate:
            raise ValueError("missing frozen arm field: " + field)
    certificate = hashlib.sha256(canonical(
        {name: expected_reference[name] for name in PAIR_FIELDS})).hexdigest()

    def command(mode, expected):
        return [str(python), str(wrapper), "--binary", str(binary),
                "--manifest", str(stage), "--protocol", str(protocol),
                "--bridge", str(bridge), "--reps", str(reps),
                "--expected", str(expected), "--mode", mode]

    artifacts = [binary, wrapper, experiment / "make_manifest.py",
                 experiment / "restore_crypto_source.py", source,
                 experiment / "run.py", experiment / "Cargo.toml",
                 experiment / "Cargo.lock", stage, protocol, bridge, reps,
                 reference, candidate, experiment / "run_3_sparse29.json",
                 interruption_path, tests_path, experiment / "test.stdout.txt",
                 experiment / "test.stderr.txt", experiment / "verify_partial.py",
                 experiment / "workload.json", experiment / "README.md",
                 experiment / "crypto_source_snapshot" / "Cargo.toml"]
    if any(not path.is_file() for path in artifacts):
        raise FileNotFoundError("missing frozen artifact")
    manifest = {
        "schema": 1,
        "workdir": str(root),
        "isolation": {"cgroup": str(args.cgroup), "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_nodes},
        "measurement_boundary": (
            "N83 bounded one-target point-decomposition stage: native target clock "
            "after reusable factor-base/index construction and lookup sample, through "
            "target-dependent query preparation, batched point addition, partner "
            "canonicalization, exact root lookup, and native relation checks; "
            "wrapper verification is outside the native interval."
        ),
        "pair_fields": ["curve_id", "workload_id", "input_sha256", "status",
                        "indexed_states", "target_states", "pair_certificate",
                        "native_source_sha256"],
        "frozen_pair_certificate": certificate,
        "cases": [{"id": "n83-e1-sparse29-capacity-63dd0929cf33",
                   "reference": command(MODES[0], reference),
                   "candidate": command(MODES[1], candidate)}],
        "repetitions": args.repetitions,
        "timeout_s": args.timeout_s,
        "artifacts": [str(path) for path in artifacts],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(str(args.output))


if __name__ == "__main__":
    main()
