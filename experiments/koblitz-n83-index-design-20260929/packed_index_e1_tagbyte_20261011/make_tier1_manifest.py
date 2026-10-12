#!/usr/bin/env python3
"""Freeze eight same-target sparse28/tagbyte pairs for a Tier 1 instance."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from benchmark_stage import MODES, PAIR_FIELDS, canonical, digest
from verify_screen import verify as verify_screen


RELATIVE = Path("experiments/koblitz-n83-index-design-20260929")
EXPERIMENT = RELATIVE / "packed_index_e1_tagbyte_20261011"
BASE = RELATIVE / "packed_index_e1_sparse28_capacity_20261011"
INPUTS = RELATIVE / "adaptive_all_orientations_20261004" / "inputs"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent /
                       "packed_index_e1_sparse28_capacity_20261011"))
from restore_crypto_source import ensure_snapshot  # noqa: E402
from verify import verify  # noqa: E402


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
    base = root / BASE
    inputs = root / INPUTS
    binary = args.binary.resolve(strict=True)
    python = args.python.resolve(strict=True)
    allocation_receipt = args.allocation_receipt.resolve(strict=True)
    allocation = json.loads(allocation_receipt.read_text())
    if (not isinstance(allocation, dict) or
            allocation.get("provider") != args.provider or
            allocation.get("instance_id") != args.instance_id):
        raise ValueError("allocation receipt differs from provider or instance ID")

    parent_path = base / "protocol.json"
    tier_path = experiment / "tier1_protocol.json"
    parent = json.loads(parent_path.read_text())
    tier = json.loads(tier_path.read_text())
    if (digest(parent_path) != tier["parent_protocol_sha256"] or
            digest(experiment / "native_packed_index.rs") != tier["source_sha256"] or
            digest(experiment / "Cargo.toml") != tier["cargo_manifest_sha256"] or
            tier["measurement_tier"] != "tier1_instance" or
            tier["curve_id"] != parent["curve_id"] or
            tier["workload_id"] != parent["workload_id"] or
            (tier["reference_mode"], tier["candidate_mode"]) != MODES or
            tier["repetitions"] != 8 or tier["timeout_s_per_arm"] != 300 or
            tier["maximum_panel_wall_s"] != 6600 or
            tier["pair_order"] != [["reference", "candidate"],
                                    ["candidate", "reference"]] * 4 or
            not tier["same_binary_required"]):
        raise ValueError("Tier 1 protocol differs from frozen sources")

    ensure_snapshot()
    verify(inputs)
    verify_screen()
    stage = base / "stage_manifest.json"
    bridge = inputs / "n83_onb_poly_bridge.json"
    reps = inputs / "n83_x_representatives.bin"
    reference = base / "run_2_sparse28.json"
    frozen = json.loads(stage.read_text())
    expected_reference = json.loads(reference.read_text())
    if (frozen["target_count"] != 1 or
            frozen["pair_state_cap"] != 29_900_000 or
            frozen["peak_rss_cap_mib"] != 5500 or
            expected_reference["index_mode"] != MODES[0]):
        raise ValueError("full-capacity workload or reference differs")
    certificate = hashlib.sha256(canonical(
        {name: expected_reference[name] for name in PAIR_FIELDS})).hexdigest()
    expected = tier["expected_fields"]
    mapping = {"curve_id": "curve_id", "workload_id": "workload_id",
               "input_sha256": "input_representatives_sha256",
               "status": "status", "indexed_states": "index_pair_states_examined",
               "target_states": "target_states_scanned"}
    if (any(str(expected_reference[key]) != expected[field]
            for field, key in mapping.items()) or
            expected["native_source_sha256"] != tier["source_sha256"] or
            expected["pair_certificate"] != certificate or
            tier["expected_result"] != certificate or
            tier["pair_fields"] != list(expected) or
            tier["result_field"] != "pair_certificate"):
        raise ValueError("expected target certificate differs")

    screen = experiment / "screen_2m"
    screen_protocol = json.loads((screen / "protocol.json").read_text())
    screen_summary = json.loads((screen / "summary.json").read_text())
    if (screen_summary["protocol_sha256"] != digest(screen / "protocol.json") or
            screen_protocol["source_sha256"] != tier["source_sha256"] or
            screen_protocol["runner_sha256"] != digest(experiment / "screen.py") or
            len(screen_summary["runs"]) != 4):
        raise ValueError("short-screen receipts differ")

    wrapper = experiment / "benchmark_stage.py"
    def command(mode):
        return [str(python), str(wrapper), "--binary", str(binary),
                "--manifest", str(stage), "--bridge", str(bridge),
                "--reps", str(reps), "--mode", mode]

    artifacts = [binary, allocation_receipt, wrapper,
                 experiment / "make_tier1_manifest.py", tier_path,
                 experiment / "native_packed_index.rs", experiment / "Cargo.toml",
                 experiment / "Cargo.lock", experiment / "screen.py",
                 experiment / "verify_screen.py", experiment / "full_audit.py",
                 screen / "protocol.json", screen / "summary.json", parent_path,
                 experiment / "full_reference_audit.py",
                 experiment / "test_record.json", experiment / "test.stdout.txt",
                 experiment / "test.stderr.txt",
                 base / "restore_crypto_source.py", base / "verify.py",
                 stage, bridge, reps, reference]
    artifacts += sorted(screen.glob("run_*"))
    artifacts += sorted((experiment / "full_audit_local").glob("*"))
    artifacts += sorted((experiment / "full_reference_local").glob("*"))
    artifacts += sorted(path for path in (base / "crypto_source_snapshot").rglob("*")
                        if path.is_file())
    if any(not path.is_file() for path in artifacts):
        raise FileNotFoundError("missing frozen source or input")
    manifest = {
        "schema": 1,
        "measurement_tier": "tier1_instance",
        "allocation": {"provider": args.provider,
                       "instance_id": args.instance_id,
                       "receipt": str(allocation_receipt)},
        "workdir": str(root),
        "isolation": {"cpus": args.cpus,
                      "execution_cpu": args.execution_cpu},
        "measurement_boundary": (
            "Native N83 one-target PDP interval after reusable index construction "
            "and lookup sample, through query preparation, batched point partners, "
            "canonicalization, exact lookup, and native relation checks; wrapper "
            "verification and process launch are outside the native timer."
        ),
        "pair_fields": tier["pair_fields"],
        "result_field": tier["result_field"],
        "cases": [{"id": "n83-e1-tagbyte-full-63dd0929cf33",
                   "expected_fields": expected,
                   "expected_result": certificate,
                   "reference": command(MODES[0]),
                   "candidate": command(MODES[1])}],
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
