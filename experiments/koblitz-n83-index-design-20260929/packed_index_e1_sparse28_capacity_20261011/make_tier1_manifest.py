#!/usr/bin/env python3
"""Freeze eight same-target sparse26/sparse28 pairs for a Tier 1 instance."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from benchmark_stage import MODES, PAIR_FIELDS, canonical, digest
from make_manifest import EXPERIMENT, INPUTS
from restore_crypto_source import ensure_snapshot
from verify import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", required=True, type=int)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--allocation-receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    root = args.workdir.resolve(strict=True)
    experiment = root / EXPERIMENT
    inputs = root / INPUTS
    binary = args.binary.resolve(strict=True)
    python = args.python.resolve(strict=True)
    allocation_receipt = args.allocation_receipt.resolve(strict=True)
    allocation = json.loads(allocation_receipt.read_text())
    if (not isinstance(allocation, dict) or allocation.get("provider") != args.provider or
            allocation.get("instance_id") != args.instance_id):
        raise ValueError("allocation receipt does not match provider and instance ID")

    parent_path = experiment / "protocol.json"
    tier_path = experiment / "tier1_protocol.json"
    parent = json.loads(parent_path.read_text())
    tier = json.loads(tier_path.read_text())
    if digest(parent_path) != tier["parent_protocol_sha256"]:
        raise ValueError("Tier 1 protocol does not bind the frozen capacity protocol")
    if (tier["measurement_tier"] != "tier1_instance" or
            tier["proposal_id"] != parent["proposal_id"] or
            tier["curve_id"] != parent["curve_id"] or
            tier["workload_id"] != parent["workload_id"] or
            (tier["reference_mode"], tier["candidate_mode"]) != MODES or
            tier["repetitions"] != 8 or tier["timeout_s_per_arm"] != 300 or
            tier["pair_order"] != [["reference", "candidate"],
                                    ["candidate", "reference"]] * 4 or
            not tier["same_binary_required"]):
        raise ValueError("Tier 1 comparison differs from the frozen capacity inputs")

    ensure_snapshot()
    verify(inputs)
    stage = experiment / "stage_manifest.json"
    bridge = inputs / "n83_onb_poly_bridge.json"
    reps = inputs / "n83_x_representatives.bin"
    reference = experiment / "run_1_sparse26.json"
    candidate = experiment / "run_2_sparse28.json"
    frozen = json.loads(stage.read_text())
    expected_reference = json.loads(reference.read_text())
    expected_candidate = json.loads(candidate.read_text())
    if (frozen["target_count"] != 1 or frozen["pair_state_cap"] != 29_900_000 or
            frozen["peak_rss_cap_mib"] != 5500 or
            any(expected_reference[name] != expected_candidate[name]
                for name in PAIR_FIELDS)):
        raise ValueError("frozen arm fields or workload differ")

    certificate = hashlib.sha256(canonical(
        {name: expected_reference[name] for name in PAIR_FIELDS})).hexdigest()
    expected = tier["expected_fields"]
    raw_mapping = {"curve_id": "curve_id", "workload_id": "workload_id",
                   "input_sha256": "input_representatives_sha256", "status": "status",
                   "indexed_states": "index_pair_states_examined",
                   "target_states": "target_states_scanned",
                   "native_source_sha256": "native_source_sha256"}
    if (any(str(expected_reference[key]) != expected[field] or
            str(expected_candidate[key]) != expected[field]
            for field, key in raw_mapping.items()) or
            expected["pair_certificate"] != certificate or
            tier["expected_result"] != certificate or
            tier["pair_fields"] != list(expected) or
            tier["result_field"] != "pair_certificate"):
        raise ValueError("Tier 1 expected answer or source differs from frozen arms")

    wrapper = experiment / "benchmark_stage.py"
    def command(mode, frozen_result):
        return [str(python), str(wrapper), "--binary", str(binary),
                "--manifest", str(stage), "--protocol", str(parent_path),
                "--bridge", str(bridge), "--reps", str(reps),
                "--expected", str(frozen_result), "--mode", mode]

    artifacts = [binary, allocation_receipt, wrapper,
                 experiment / "make_tier1_manifest.py", tier_path, parent_path,
                 experiment / "restore_crypto_source.py", experiment / "verify.py",
                 experiment / "native_packed_index.rs", experiment / "Cargo.toml",
                 experiment / "Cargo.lock", stage, bridge, reps, reference, candidate,
                 experiment / "summary.json", experiment / "audit_sparse28.json",
                 experiment / "audit_protocol.json", experiment / "audit.record.json",
                 experiment / "test_record.json"]
    artifacts += sorted(path for path in (experiment / "crypto_source_snapshot").rglob("*")
                        if path.is_file())
    if any(not path.is_file() for path in artifacts):
        raise FileNotFoundError("missing frozen artifact")
    manifest = {
        "schema": 1,
        "measurement_tier": "tier1_instance",
        "allocation": {"provider": args.provider, "instance_id": args.instance_id,
                       "receipt": str(allocation_receipt)},
        "workdir": str(root),
        "isolation": {"cpus": args.cpus, "execution_cpu": args.execution_cpu},
        "measurement_boundary": (
            "Native N83 one-target PDP interval after reusable index construction and "
            "lookup sample, through target query preparation, batched point partners, "
            "canonicalization, exact lookup, and native relation checks; wrapper "
            "verification and process launch are outside the native timer."
        ),
        "pair_fields": tier["pair_fields"],
        "result_field": tier["result_field"],
        "cases": [{"id": "n83-e1-sparse28-capacity-63dd0929cf33",
                   "expected_fields": expected,
                   "expected_result": certificate,
                   "reference": command(MODES[0], reference),
                   "candidate": command(MODES[1], candidate)}],
        "repetitions": tier["repetitions"],
        "timeout_s": tier["timeout_s_per_arm"],
        "artifacts": [str(path) for path in artifacts],
    }
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(manifest, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(str(args.output))


if __name__ == "__main__":
    main()
