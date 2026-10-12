#!/usr/bin/env python3
"""Freeze eight sparse28/sparse30 pairs on a Tier 1 instance."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from restore_crypto_source import ensure_snapshot
from verify_screen import main as verify_screen

RELATIVE = Path("experiments/koblitz-n83-index-design-20260929")
EXPERIMENT = RELATIVE / "packed_index_e1_sparse30_vs28_20261011"
INPUTS = RELATIVE / "adaptive_all_orientations_20261004" / "inputs"


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


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
    receipt = json.loads(allocation_receipt.read_text())
    if (not isinstance(receipt, dict) or receipt.get("provider") != args.provider or
            receipt.get("instance_id") != args.instance_id):
        raise ValueError("allocation receipt does not match provider and instance ID")

    parent_path = experiment / "comparison_protocol.json"
    tier_path = experiment / "tier1_protocol.json"
    parent = json.loads(parent_path.read_text())
    tier = json.loads(tier_path.read_text())
    if digest(parent_path) != tier["parent_protocol_sha256"]:
        raise ValueError("Tier 1 protocol does not bind the frozen stage protocol")
    if (tier["measurement_tier"] != "tier1_instance" or
            tier["proposal_id"] != parent["proposal_id"] or
            tier["curve_id"] != parent["curve_id"] or
            tier["workload_id"] != parent["workload_id"] or
            tier["reference_mode"] != parent["reference_mode"] or
            tier["candidate_mode"] != parent["candidate_mode"] or
            tier["expected_result"] != parent["frozen_pair_certificate"] or
            tier["repetitions"] != 8 or tier["timeout_s_per_arm"] != 300 or
            tier["pair_order"] != [["reference", "candidate"],
                                    ["candidate", "reference"]] * 4 or
            not tier["same_binary_required"]):
        raise ValueError("Tier 1 comparison differs from the frozen protocol")

    ensure_snapshot()
    verify_screen()
    prior = json.loads((experiment / "prior_source_sparse28_reference.json").read_text())
    candidate = json.loads((experiment / "screen_sparse30_rank16.json").read_text())
    if digest(experiment / "prior_source_sparse28_reference.json") != parent["input_sha256"]["prior_source_reference_raw"]:
        raise ValueError("sparse28 raw reference differs from the frozen protocol")
    if any(prior.get(field) != candidate.get(field)
           for field in parent["exact_pair_fields"]):
        raise ValueError("sparse28 and sparse30 exact fields differ")
    expected = tier["expected_fields"]
    raw_mapping = {"curve_id": "curve_id", "workload_id": "workload_id",
                   "input_sha256": "input_representatives_sha256", "status": "status",
                   "indexed_states": "index_pair_states_examined",
                   "target_states": "target_states_scanned"}
    if any(str(prior[key]) != expected[field] or str(candidate[key]) != expected[field]
           for field, key in raw_mapping.items()):
        raise ValueError("Tier 1 expected fields differ from frozen arm receipts")
    if (expected["pair_certificate"] != parent["frozen_pair_certificate"] or
            expected["native_source_sha256"] != parent["input_sha256"]["source"] or
            tier["pair_fields"] != list(expected) or
            tier["result_field"] != "pair_certificate"):
        raise ValueError("Tier 1 pair certificate or source binding differs")

    wrapper = experiment / "benchmark_stage.py"
    stage = experiment / "stage_manifest.json"
    bridge = inputs / "n83_onb_poly_bridge.json"
    reps = inputs / "n83_x_representatives.bin"
    reference = experiment / "prior_source_sparse28_reference.json"
    candidate_path = experiment / "screen_sparse30_rank16.json"

    def command(mode, frozen_result):
        return [str(python), str(wrapper), "--binary", str(binary),
                "--manifest", str(stage), "--protocol", str(parent_path),
                "--bridge", str(bridge), "--reps", str(reps),
                "--expected", str(frozen_result), "--mode", mode]

    artifacts = [binary, allocation_receipt, wrapper,
                 experiment / "make_tier1_manifest.py", tier_path, parent_path,
                 experiment / "protocol.json",
                 experiment / "verify_screen.py", experiment / "restore_crypto_source.py",
                 experiment / "native_packed_index.rs", experiment / "Cargo.toml",
                 experiment / "Cargo.lock", stage, experiment / "workload.json",
                 bridge, reps, reference, candidate_path,
                 experiment / "screen_sparse30_rank16.guard.json",
                 experiment / "screen_sparse29_interruption.json",
                 experiment / "prior_source_sparse29_reference.json",
                 experiment / "screen_report.json", experiment / "test_record.json",
                 experiment / "test.stdout.txt", experiment / "test.stderr.txt"]
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
        "measurement_boundary": parent["measurement_boundary"],
        "pair_fields": tier["pair_fields"],
        "result_field": tier["result_field"],
        "cases": [{"id": "n83-e1-sparse30-vs28-63dd0929cf33",
                   "expected_fields": expected,
                   "expected_result": tier["expected_result"],
                   "reference": command(tier["reference_mode"], reference),
                   "candidate": command(tier["candidate_mode"], candidate_path)}],
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
