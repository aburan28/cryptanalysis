#!/usr/bin/env python3
"""Build a paired selective-vs-mixed-radix one-scalar isolated manifest."""

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
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--timeout-s", type=int, default=30)
    args = parser.parse_args()
    repo = args.repo_root.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    here = repo / "experiments/prime-j0-secp256k1-native"
    assert Path(__file__).resolve() == here / "make_mixed_radix_manifest.py"
    workload_path = here / "mixed-radix-fixture.json"
    fixture = json.loads(workload_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 256
    scores = json.loads((here / "mixed-radix-scalar-result.json").read_text())
    panel = next(item for item in scores["panels"] if item["fixture"] == workload_path.name)
    assert panel["fixture_sha256"] == sha(workload_path)
    cases = []
    for index, (row, score) in enumerate(zip(fixture["cases"], panel["rows"])):
        assert row["index"] == index == score["index"]
        assert row["expected_identity"] is False
        point = row["expected_x_hex"] + ":" + row["expected_y_hex"]
        cases.append({
            "id": f"fresh-single-scalar-{index}",
            "expected_fields": {
                "curve": "secp256k1", "base_x": row["base_x_hex"],
                "base_y": row["base_y_hex"], "scalar": row["scalar_hex"],
            },
            "expected_result": point,
            "reference": [str(binary), "--benchmark-selective-case",
                          str(workload_path), str(index)],
            "candidate": [str(binary), "--benchmark-mixed-radix-case",
                          str(workload_path), str(index)],
        })
    artifacts = [here / name for name in (
        "Cargo.toml", "Cargo.lock", "src/main.rs", "src/selective.rs",
        "src/mixed_radix.rs", "MIXED_RADIX_SCALAR_PROTOCOL.md",
        "MIXED_RADIX_NATIVE_PROTOCOL.md", "MIXED_RADIX_SCALAR_RESULT.md",
        "mixed_radix_scalar.py", "make_mixed_radix_fixture.py",
        "make_mixed_radix_manifest.py", "mixed-radix-scalar-result.json",
        "mixed-radix-runtime-info.json", "mixed-radix-sage-replay.json",
        "mixed-radix-seed-fixture.json", "mixed-radix-action-fingerprints.json",
        "native-mixed-radix-checks-v2.json", "mixed-radix-fixture.json")]
    artifacts += [repo / "suite/src/ct_bignum.rs",
                  repo / "suite/src/ecc/secp256k1_field.rs"]
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
            "comparison; both arms include native lattice reduction, recoding, "
            "selector work where applicable, seed preparation, orbit/cache "
            "setup, point evaluation, affine inversion, and formatting; "
            "excludes process launch, JSON loading, and curve-wide constants"),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point",
        "comparison_kind": "conditional-radix-two-vs-selective-mixed-tau-one-scalar",
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
