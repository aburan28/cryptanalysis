#!/usr/bin/env python3
"""Build a same-binary paired U14-versus-radix-943 CPU manifest."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


INDICES = (0, 16, 32, 48, 64, 80, 96, 112, 128)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--checker-receipt", type=Path, required=True)
    parser.add_argument("--cgroup", required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-node", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--timeout-s", type=int, default=1200)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("manifest exists")
    repo = args.repo_root.resolve(strict=True)
    here = repo / "experiments/prime-j0-secp256k1-native"
    if Path(__file__).resolve() != here / "make_radix943_isolated_manifest.py":
        raise SystemExit("generator must belong to the selected source snapshot")
    binary = args.binary.resolve(strict=True)
    receipt_path = args.checker_receipt.resolve(strict=True)
    receipt = json.loads(receipt_path.read_text())
    fixture_path = here / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    sources = (
        "src/bin/eisenstein_fixed.rs",
        "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
    )
    if (receipt["status"] != "passed" or receipt["cases"] != 4230 or
            receipt["fixture_cases"] != 129 or
            receipt["independent_point_checks"] != 261 or
            receipt["binary_sha256"] != sha(binary) or
            receipt["source_sha256"] != {name: sha(here / name) for name in sources} or
            receipt["screen_sha256"] != sha(here / "radix943-screen-result.json") or
            receipt["fixture_sha256"] != sha(fixture_path) or
            fixture["schema"] != 1 or len(fixture["cases"]) != 129):
        raise SystemExit("binary, source, fixture, or checker receipt differs")
    cases = []
    for index in INDICES:
        row = fixture["cases"][index]
        if row["index"] != index:
            raise SystemExit("fixture case order changed")
        expected = ("identity" if row["expected_identity"] else
                    row["expected_x_hex"] + ":" + row["expected_y_hex"])
        common = [str(fixture_path), str(index)]
        cases.append({
            "id": f"scalar-{index}",
            "expected_fields": {
                "curve": "secp256k1", "base_x": row["base_x_hex"],
                "base_y": row["base_y_hex"], "scalar": row["scalar_hex"],
            },
            "expected_result": expected,
            "reference": [str(binary),
                          "--benchmark-scalar-unit-orbit-windows14-fixed-case"] + common,
            "candidate": [str(binary),
                          "--benchmark-scalar-unit-orbit-radix943-fixed-case"] + common,
        })
    artifacts = [
        binary, fixture_path, receipt_path,
        *(here / name for name in sources),
        here / "radix943_screen.py", here / "radix943_native_verify.py",
        here / "radix943-screen-result.json", here / "RADIX943_PROTOCOL.md",
        here / "RADIX943_RESULT.md", here / "make_radix943_isolated_manifest.py",
        here / "Cargo.toml", here / "Cargo.lock",
        repo / "suite/src/ct_bignum.rs", repo / "scripts/isolated_bench.py",
    ]
    if not all(path.is_file() for path in artifacts):
        raise SystemExit("required artifact missing")
    manifest = {
        "schema": 1,
        "workdir": str(repo),
        "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s,
        "repetitions": args.repetitions,
        "metric_field": "online_ms",
        "measurement_boundary": (
            "Starts after fixture loading, scalar decoding, lattice and field constants, "
            "and the selected fixed-generator table are initialized. Includes scalar "
            "reduction, BigInt recoding and residue lookups, unit maps, point additions, "
            "final affine conversion, and expected-point assertion. Stops after the "
            "assertion; excludes process launch and reusable table preparation."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point",
        "workload_sha256": sha(fixture_path),
        "comparison_kind": "single-public-scalar-u14-vs-radix943-memory-frontier",
        "cases": cases,
    }
    sys.path.insert(0, str(repo / "scripts"))
    from isolated_bench import require_manifest
    require_manifest(manifest)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": args.repetitions,
                      "manifest_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
