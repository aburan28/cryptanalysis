#!/usr/bin/env python3
"""Freeze the matched sparse24/sparse26 N83 isolated-stage comparison."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from benchmark_stage import ARM_FIELDS, PAIR_FIELDS, canonical, digest
import run as stage_run


RELATIVE = Path("experiments/koblitz-n83-index-design-20260929")
EXPERIMENT = RELATIVE / "packed_index_e1_sparse26_cachedxy_cpu_20261011"
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
    parser.add_argument("--repetitions", type=int, default=6)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    root = args.workdir.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    python = args.python.resolve(strict=True)
    experiment = root / EXPERIMENT
    stage = experiment / "stage_manifest.json"
    protocol = experiment / "protocol.json"
    source = experiment / "native_packed_index.rs"
    bridge = root / INPUTS / "n83_onb_poly_bridge.json"
    reps = root / INPUTS / "n83_x_representatives.bin"
    reference = experiment / "run_1_packed_sparse24_compact16_cachedxy.json"
    candidate = experiment / "run_2_packed_sparse26_compact16_cachedxy.json"
    wrapper = experiment / "benchmark_stage.py"
    summary_path = experiment / "summary.json"
    audit_path = experiment / "audit_sparse26_cachedxy.json"
    frozen = json.loads(stage.read_text())
    receipt = json.loads(protocol.read_text())
    summary = json.loads(summary_path.read_text())
    audit = json.loads(audit_path.read_text())
    expected_reference = json.loads(reference.read_text())
    expected_candidate = json.loads(candidate.read_text())

    if summary["status"] != "validated_stage_comparison" or summary["invariant_mismatches"]:
        raise ValueError("frozen stage comparison failed")
    if (audit["index_mode"] != stage_run.CANDIDATE + "_audit" or
            audit["partner_audit_pairs"] != 4_000_000 or
            audit["target_partner_roots"] != 8_000_000 or
            audit["index_root_x_precomputed"] != 4_000_000 or
            audit["index_root_y_precomputed"] != 4_000_000 or
            audit["status"] != "state_cap_no_relation" or
            audit["native_source_sha256"] != receipt["inputs_sha256"]["native_source"]):
        raise ValueError("full partner audit failed")
    if digest(protocol) != frozen["stage_protocol_sha256"]:
        raise ValueError("stage/protocol digest mismatch")
    for path, key in ((source, "native_source"), (bridge, "bridge"),
                      (reps, "representatives"),
                      (experiment / "run.py", "runner"),
                      (experiment / "Cargo.toml", "cargo_manifest"),
                      (experiment / "Cargo.lock", "cargo_lock"),
                      (experiment / "crypto_source_snapshot" / "Cargo.toml",
                       "crypto_manifest")):
        if digest(path) != receipt["inputs_sha256"][key]:
            raise ValueError("frozen input digest mismatch: " + str(path))
    if stage_run.source_tree_digest() != receipt["inputs_sha256"]["crypto_source_tree"]:
        raise ValueError("crypto source-tree digest mismatch")
    if stage_run.rust_source_tree_digest() != receipt["inputs_sha256"]["crypto_rust_source_tree"]:
        raise ValueError("crypto Rust source-tree digest mismatch")
    if (expected_reference["index_mode"] != stage_run.REFERENCE or
            expected_candidate["index_mode"] != stage_run.CANDIDATE):
        raise ValueError("frozen mode mismatch")
    for expected in (expected_reference, expected_candidate):
        if (expected["stage_protocol_sha256"] != digest(protocol) or
                expected["native_source_sha256"] != receipt["inputs_sha256"]["native_source"] or
                expected["cargo_manifest_sha256"] != receipt["inputs_sha256"]["cargo_manifest"] or
                expected["input_representatives_sha256"] != receipt["inputs_sha256"]["representatives"]):
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

    artifacts = [binary, wrapper, experiment / "make_manifest.py", source,
                 experiment / "run.py", experiment / "Cargo.toml",
                 experiment / "Cargo.lock", stage, protocol, bridge, reps,
                 reference, candidate, summary_path, audit_path,
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
        "cases": [{"id": "n83-e1-sparse26-cpu-981ac530e67e",
                   "reference": command(stage_run.REFERENCE, reference),
                   "candidate": command(stage_run.CANDIDATE, candidate)}],
        "repetitions": args.repetitions,
        "timeout_s": args.timeout_s,
        "artifacts": [str(path) for path in artifacts],
    }
    if not certificate:
        raise AssertionError("missing pair certificate")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(str(args.output))


if __name__ == "__main__":
    main()
