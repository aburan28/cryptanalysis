#!/usr/bin/env python3
"""Freeze an isolated-service panel for the exact N83 canonicalization pair."""

import argparse
import json
import sys
from pathlib import Path

from benchmark_stage import PAIR_FIELDS, digest


RELATIVE = Path("experiments/koblitz-n83-index-design-20260929")
CANONICAL = RELATIVE / "packed_index_e1_canonical_20261009"
PARENT = RELATIVE / "adaptive_all_orientations_20261004" / "inputs"
ADAPTER = RELATIVE / "packed_index_e1_isolated_replay_20261010"


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
    stage = root / CANONICAL / "stage_manifest.json"
    protocol = root / CANONICAL / "protocol.json"
    source = root / CANONICAL / "native_packed_index.rs"
    bridge = root / PARENT / "n83_onb_poly_bridge.json"
    reps = root / PARENT / "n83_x_representatives.bin"
    reference = root / CANONICAL / "run_1_packed_bucket22.json"
    candidate = root / CANONICAL / "run_2_packed_bucket22_fastcanon.json"
    wrapper = root / ADAPTER / "benchmark_stage.py"
    frozen = json.loads(stage.read_text())
    receipt = json.loads(protocol.read_text())
    expected_reference = json.loads(reference.read_text())
    expected_candidate = json.loads(candidate.read_text())
    if digest(protocol) != frozen["stage_protocol_sha256"]:
        raise ValueError("stage-manifest protocol digest mismatch")
    for path, key in ((source, "native_source"), (bridge, "bridge"),
                      (reps, "representatives")):
        if digest(path) != receipt["inputs_sha256"][key]:
            raise ValueError("frozen input digest mismatch: " + str(path))
    if expected_reference["index_mode"] != "packed_bucket22":
        raise ValueError("reference fixture mode mismatch")
    if expected_candidate["index_mode"] != "packed_bucket22_fastcanon":
        raise ValueError("candidate fixture mode mismatch")
    if any(expected_reference[name] != expected_candidate[name] for name in PAIR_FIELDS):
        raise ValueError("frozen arms differ in paired correctness fields")

    def command(mode, expected):
        return [str(python), str(wrapper), "--binary", str(binary),
                "--manifest", str(stage), "--protocol", str(protocol),
                "--bridge", str(bridge), "--reps", str(reps),
                "--expected", str(expected), "--mode", mode]

    artifacts = [binary, wrapper, root / ADAPTER / "make_manifest.py",
                 source, root / CANONICAL / "run.py",
                 root / CANONICAL / "Cargo.toml",
                 root / CANONICAL / "Cargo.lock", stage, protocol,
                 bridge, reps, reference, candidate,
                 root / CANONICAL / "crypto_source_snapshot" / "Cargo.toml"]
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
            "N83 bounded one-target point-decomposition stage: native online_start "
            "after reusable factor-base/index construction and lookup sample, through "
            "target-dependent query preparation, batched S3, exact root lookup, and "
            "native relation checks; stage verification by the wrapper is outside "
            "the native interval."
        ),
        "pair_fields": ["curve_id", "workload_id", "input_sha256", "status",
                        "indexed_states", "target_states", "pair_certificate",
                        "native_source_sha256"],
        "cases": [{
            "id": "n83-e1-canonical-981ac530e67e",
            "reference": command("packed_bucket22", reference),
            "candidate": command("packed_bucket22_fastcanon", candidate),
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
