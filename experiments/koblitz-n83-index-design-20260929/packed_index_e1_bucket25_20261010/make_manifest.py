#!/usr/bin/env python3
"""Freeze an isolated-service panel for the exact N83 bucket-width pair."""

import argparse
import json
import sys
from pathlib import Path

from benchmark_stage import PAIR_FIELDS, digest
import run as stage_run


RELATIVE = Path("experiments/koblitz-n83-index-design-20260929")
EXPERIMENT = RELATIVE / "packed_index_e1_bucket25_20261010"
PARENT = RELATIVE / "adaptive_all_orientations_20261004" / "inputs"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--cgroup", required=True, type=Path)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", required=True, type=int)
    parser.add_argument("--mem-nodes", required=True)
    parser.add_argument("--repetitions", type=int, default=6)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    root = args.workdir.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    python = args.python.resolve(strict=True)
    stage = root / EXPERIMENT / "stage_manifest.json"
    protocol = root / EXPERIMENT / "protocol.json"
    source = root / EXPERIMENT / "native_packed_index.rs"
    bridge = root / PARENT / "n83_onb_poly_bridge.json"
    reps = root / PARENT / "n83_x_representatives.bin"
    reference = root / EXPERIMENT / "run_1_packed_bucket24_fastcanon_tag.json"
    candidate = root / EXPERIMENT / "run_2_packed_bucket25_fastcanon_tag.json"
    wrapper = root / EXPERIMENT / "benchmark_stage.py"
    frozen = json.loads(stage.read_text())
    receipt = json.loads(protocol.read_text())
    expected_reference = json.loads(reference.read_text())
    expected_candidate = json.loads(candidate.read_text())
    if digest(protocol) != frozen["stage_protocol_sha256"]:
        raise ValueError("stage-manifest protocol digest mismatch")
    for path, key in ((source, "native_source"), (bridge, "bridge"),
                      (reps, "representatives"),
                      (root / RELATIVE / "packed_index_e1_bucket24_20261010" /
                       "summary.json", "e1_bucket24_summary"),
                      (root / EXPERIMENT / "run.py", "runner"),
                      (root / EXPERIMENT / "Cargo.toml", "cargo_manifest"),
                      (root / EXPERIMENT / "Cargo.lock", "cargo_lock"),
                      (root / EXPERIMENT / "crypto_source_snapshot" / "Cargo.toml",
                       "crypto_manifest")):
        if digest(path) != receipt["inputs_sha256"][key]:
            raise ValueError("frozen input digest mismatch: " + str(path))
    if stage_run.source_tree_digest() != receipt["inputs_sha256"]["crypto_source_tree"]:
        raise ValueError("frozen crypto source-tree digest mismatch")
    if stage_run.rust_source_tree_digest() != receipt["inputs_sha256"]["crypto_rust_source_tree"]:
        raise ValueError("frozen crypto Rust source-tree digest mismatch")
    if expected_reference["index_mode"] != "packed_bucket24_fastcanon_tag":
        raise ValueError("reference fixture mode mismatch")
    if expected_candidate["index_mode"] != "packed_bucket25_fastcanon_tag":
        raise ValueError("candidate fixture mode mismatch")
    for expected in (expected_reference, expected_candidate):
        if expected["stage_protocol_sha256"] != digest(protocol):
            raise ValueError("fixture protocol digest mismatch")
        if expected["native_source_sha256"] != receipt["inputs_sha256"]["native_source"]:
            raise ValueError("fixture native-source digest mismatch")
        if expected["cargo_manifest_sha256"] != receipt["inputs_sha256"]["cargo_manifest"]:
            raise ValueError("fixture cargo-manifest digest mismatch")
        if expected["input_representatives_sha256"] != receipt["inputs_sha256"]["representatives"]:
            raise ValueError("fixture representative digest mismatch")
    if any(expected_reference[name] != expected_candidate[name] for name in PAIR_FIELDS):
        raise ValueError("frozen arms differ in paired correctness fields")

    def command(mode, expected):
        return [str(python), str(wrapper), "--binary", str(binary),
                "--manifest", str(stage), "--protocol", str(protocol),
                "--bridge", str(bridge), "--reps", str(reps),
                "--expected", str(expected), "--mode", mode]

    artifacts = [binary, wrapper, root / EXPERIMENT / "make_manifest.py",
                 source, root / EXPERIMENT / "run.py",
                 root / EXPERIMENT / "Cargo.toml",
                 root / EXPERIMENT / "Cargo.lock", stage, protocol,
                 bridge, reps, reference, candidate,
                 root / EXPERIMENT / "summary.json",
                 root / EXPERIMENT / "crypto_source_snapshot" / "Cargo.toml"]
    for path in artifacts:
        if not path.is_file():
            raise FileNotFoundError(path)
    manifest = {
        "schema": 1,
        "workdir": str(root),
        "isolation": {
            "cgroup": str(args.cgroup), "cpus": args.cpus,
            "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_nodes,
        },
        "measurement_boundary": (
            "N83 bounded one-target point-decomposition stage: native target clock "
            "after reusable factor-base/index construction and lookup sample, through "
            "target-dependent query preparation, batched S3, exact root lookup, and "
            "native relation checks; stage verification by the wrapper is outside "
            "the native interval."
        ),
        "pair_fields": ["curve_id", "workload_id", "input_sha256", "status",
                        "indexed_states", "target_states", "pair_certificate",
                        "native_source_sha256"],
        "cases": [{
            "id": "n83-e1-bucket25-981ac530e67e",
            "reference": command("packed_bucket24_fastcanon_tag", reference),
            "candidate": command("packed_bucket25_fastcanon_tag", candidate),
        }],
        "repetitions": args.repetitions,
        "timeout_s": args.timeout_s,
        "artifacts": [str(path) for path in artifacts],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(str(args.output))


if __name__ == "__main__":
    main()
