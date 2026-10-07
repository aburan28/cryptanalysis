#!/usr/bin/env python3
"""Build a paired one-use joint-atlas manifest for an isolated host."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--cgroup", required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-node", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout-s", type=int, default=30)
    args = parser.parse_args()
    repo = args.repo_root.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    here = repo / "experiments/prime-j0-secp256k1-native"
    assert Path(__file__).resolve() == here / "make_joint_manifest.py"
    workload_path = here / "bench-workload.json"
    workload = json.loads(workload_path.read_text())
    assert workload["schema"] == 1 and len(workload["cases"]) == 64
    assert sha(here / "fixture.json") == workload["source_fixture_sha256"]
    assert sha(here / "make_bench_workload.py") == workload["script_sha256"]
    cases = []
    for index, row in enumerate(workload["cases"]):
        assert row["index"] == index and row["expected_identity"] is False
        point = row["expected_x_hex"] + ":" + row["expected_y_hex"]
        base = [str(binary), "--benchmark-case"]
        cases.append({
            "id": f"single-use-{index}",
            "expected_fields": {
                "curve": "secp256k1", "base_x": row["base_x_hex"],
                "base_y": row["base_y_hex"], "scalar": row["scalar_hex"],
            },
            "expected_result": point,
            "reference": base + ["cached_projective", str(workload_path), str(index)],
            "candidate": base + ["joint_atlas", str(workload_path), str(index)],
        })
    artifacts = [
        here / "Cargo.toml", here / "Cargo.lock", here / "src/main.rs",
        here / "FORMAT_PROTOCOL.md", here / "JOINT_ATLAS_PROTOCOL.md",
        here / "make_bench_workload.py", here / "make_joint_manifest.py",
        workload_path,
        repo / "suite/src/ct_bignum.rs",
        repo / "suite/src/ecc/secp256k1_field.rs",
    ]
    assert all(path.is_file() for path in artifacts)
    manifest = {
        "schema": 1, "workdir": str(repo),
        "isolation": {
            "cgroup": args.cgroup, "cpus": args.cpus,
            "execution_cpu": args.execution_cpu,
            "mem_nodes": args.mem_node,
        },
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s, "repetitions": args.repetitions,
        "measurement_boundary": (
            "Before base/scalar decoding through independent expected-point "
            "comparison; includes native reduction, recoding, one-use seed "
            "preparation, orbit/cache setup, point evaluation, "
            "and affine output; excludes launch, JSON loading, and curve-wide "
            "constant initialization"),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point",
        "comparison_kind": "joint-two-orbit-width-four-tau-atlas-vs-original-cached-projective",
        "workload_sha256": sha(workload_path),
        "cases": cases,
    }
    if args.output.exists():
        raise SystemExit("manifest exists; refusing overwrite")
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases),
                      "manifest_sha256": sha(args.output),
                      "workload_sha256": manifest["workload_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
