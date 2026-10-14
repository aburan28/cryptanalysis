#!/usr/bin/env python3
"""Freeze sixteen full-scan/zero-gap N83 canonicalization pairs on a Tier 1 instance."""

import argparse
import json
import os
import sys
from pathlib import Path

from verify_inputs import ADAPTER, CANONICAL, HERE, INPUTS, verify


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
    if HERE.parents[2] != root:
        raise ValueError("workdir is not the checkout containing this experiment")
    binary = args.binary.resolve(strict=True)
    python = args.python.resolve(strict=True)
    allocation_receipt = args.allocation_receipt.resolve(strict=True)
    receipt = json.loads(allocation_receipt.read_text())
    if (not isinstance(receipt, dict) or receipt.get("provider") != args.provider or
            receipt.get("instance_id") != args.instance_id):
        raise ValueError("allocation receipt does not match provider and instance ID")

    verify()
    tier_path = HERE / "tier1_protocol.json"
    tier = json.loads(tier_path.read_text())
    stage = CANONICAL / "stage_manifest.json"
    protocol = CANONICAL / "protocol.json"
    bridge = INPUTS / "n83_onb_poly_bridge.json"
    reps = INPUTS / "n83_x_representatives.bin"
    wrapper = (HERE / tier["stage_wrapper"]).resolve()
    reference = (HERE / tier["expected_reference_raw"]).resolve()
    candidate = (HERE / tier["expected_candidate_raw"]).resolve()

    def command(mode, expected):
        return [str(python), str(wrapper), "--binary", str(binary),
                "--manifest", str(stage), "--protocol", str(protocol),
                "--bridge", str(bridge), "--reps", str(reps),
                "--expected", str(expected), "--mode", mode]

    artifacts = [binary, allocation_receipt, wrapper, tier_path,
                 HERE / "make_tier1_manifest.py", HERE / "verify_inputs.py",
                 HERE / "verify_tier1_receipt.py", HERE / "restore_crypto_source.py",
                 CANONICAL / "native_packed_index.rs", CANONICAL / "Cargo.toml",
                 CANONICAL / "Cargo.lock", stage, protocol,
                 CANONICAL / "workload.json", CANONICAL / "summary.json",
                 bridge, reps, reference, candidate,
                 ADAPTER / "make_manifest.py"]
    artifacts += sorted(path for path in (CANONICAL / "crypto_source_snapshot").rglob("*")
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
        "measurement_boundary": tier["measurement_boundary"],
        "pair_fields": tier["pair_fields"],
        "result_field": tier["result_field"],
        "cases": [{"id": "n83-e1-canonical-981ac530e67e",
                   "expected_fields": tier["expected_fields"],
                   "expected_result": tier["expected_result"],
                   "reference": command(tier["reference_mode"], reference),
                   "candidate": command(tier["candidate_mode"], candidate)}],
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
