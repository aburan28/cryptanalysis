#!/usr/bin/env python3
"""Freeze four sparse29/sparse30-rank16 pairs for the isolated CPU service."""

import argparse
import json
import sys
from pathlib import Path

from restore_crypto_source import ensure_snapshot
from verify_screen import main as verify_screen

RELATIVE = Path("experiments/koblitz-n83-index-design-20260929")
EXPERIMENT = RELATIVE / "packed_index_e1_sparse30_rank_20261011"
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
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    root = args.workdir.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    python = args.python.resolve(strict=True)
    experiment = root / EXPERIMENT
    inputs = root / INPUTS
    protocol = json.loads((experiment / "protocol.json").read_text())
    ensure_snapshot()
    verify_screen()
    if (protocol["proposal_id"] != "Q2026101134" or
            protocol["pair_order"] != [["reference", "candidate"],
                                       ["candidate", "reference"],
                                       ["reference", "candidate"],
                                       ["candidate", "reference"]] or
            protocol["repetitions"] != 4 or protocol["timeout_s_per_arm"] != 900 or
            not protocol["same_binary_required"] or
            not protocol["physical_host_isolation_required"]):
        raise ValueError("frozen host comparison differs")

    wrapper = experiment / "benchmark_stage.py"
    stage = experiment / "stage_manifest.json"
    bridge = inputs / "n83_onb_poly_bridge.json"
    reps = inputs / "n83_x_representatives.bin"
    reference = experiment / "prior_source_sparse29_reference.json"
    candidate = experiment / "screen_sparse30_rank16.json"

    def command(mode, expected):
        return [str(python), str(wrapper), "--binary", str(binary),
                "--manifest", str(stage), "--protocol", str(experiment / "protocol.json"),
                "--bridge", str(bridge), "--reps", str(reps),
                "--expected", str(expected), "--mode", mode]

    artifacts = [binary, wrapper, experiment / "make_manifest.py",
                 experiment / "verify_screen.py", experiment / "restore_crypto_source.py",
                 experiment / "native_packed_index.rs", experiment / "Cargo.toml",
                 experiment / "Cargo.lock", experiment / "stage_manifest.json",
                 experiment / "workload.json", experiment / "protocol.json",
                 experiment / "README.md", bridge, reps, reference, candidate,
                 experiment / "screen_sparse30_rank16.guard.json",
                 experiment / "screen_sparse29_interruption.json",
                 experiment / "screen_report.json", experiment / "test_record.json",
                 experiment / "test.stdout.txt", experiment / "test.stderr.txt"]
    if any(not path.is_file() for path in artifacts):
        raise FileNotFoundError("missing frozen artifact")
    source_files = sorted(path for path in
                          (experiment / "crypto_source_snapshot").rglob("*")
                          if path.is_file())
    if len(source_files) < 2:
        raise FileNotFoundError("missing pinned crypto source tree")
    artifacts.extend(source_files)
    manifest = {
        "schema": 1,
        "workdir": str(root),
        "isolation": {"cgroup": str(args.cgroup), "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu,
                      "mem_nodes": args.mem_nodes},
        "measurement_boundary": protocol["measurement_boundary"],
        "pair_fields": ["curve_id", "workload_id", "input_sha256", "status",
                        "indexed_states", "target_states", "pair_certificate",
                        "native_source_sha256"],
        "frozen_pair_certificate": protocol["frozen_pair_certificate"],
        "cases": [{"id": "n83-e1-sparse30-rank16-63dd0929cf33",
                   "reference": command(protocol["reference_mode"], reference),
                   "candidate": command(protocol["candidate_mode"], candidate)}],
        "repetitions": protocol["repetitions"],
        "timeout_s": protocol["timeout_s_per_arm"],
        "artifacts": [str(path) for path in artifacts],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(str(args.output))


if __name__ == "__main__":
    main()
