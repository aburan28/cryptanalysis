#!/usr/bin/env python3
"""Generate a strict same-binary U14/deferred-XYZZ comparison manifest."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


INDICES = (0, 16, 32, 48, 64, 80, 96, 112, 128)
SOURCE_NAMES = frozenset({
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs",
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
    "experiments/prime-j0-xyzz-20261009/Cargo.lock",
    "experiments/prime-j0-xyzz-20261009/Cargo.toml",
    "experiments/prime-j0-xyzz-20261009/DEFERRED_PROTOCOL.md",
    "experiments/prime-j0-xyzz-20261009/build.rs",
    "experiments/prime-j0-xyzz-20261009/check_deferred_xyzz.py",
    "experiments/prime-j0-xyzz-20261009/src/main.rs",
    "experiments/prime-j0-xyzz-20261009/src/unit_orbit_append.rs",
    "experiments/prime-j0-xyzz-20261009/src/xyzz_append.rs",
    "suite/src/ct_bignum.rs",
})
MODES = {
    "jacobian": ("--benchmark-scalar-unit-orbit-windows14-fixed-case",
                 "unit_orbit_windows14_fixed"),
    "balanced": ("--benchmark-scalar-unit-orbit-u14-xyzz-fixed-case",
                 "unit_orbit_u14_xyzz_fixed"),
}
CANDIDATE = ("--benchmark-scalar-unit-orbit-u14-xyzz-deferred-fixed-case",
             "unit_orbit_u14_xyzz_deferred_fixed")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fields(raw):
    return dict(part.split("=", 1) for part in raw.split() if "=" in part)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--checker-receipt", type=Path, required=True)
    parser.add_argument("--reference-mode", choices=tuple(MODES), required=True)
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
    here = repo / "experiments/prime-j0-xyzz-20261009"
    upstream = repo / "experiments/prime-j0-secp256k1-native"
    if Path(__file__).resolve() != here / "make_deferred_isolated_manifest.py":
        raise SystemExit("generator must belong to the selected source snapshot")
    binary = args.binary.resolve(strict=True)
    receipt_path = args.checker_receipt.resolve(strict=True)
    receipt = json.loads(receipt_path.read_text())
    fixture_path = upstream / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    if (receipt.get("schema") != 1 or receipt.get("status") != "passed" or
            receipt.get("fixture_cases") != 129 or
            receipt.get("boundary_cases") != 4 or
            receipt.get("holdout_cases") != 512 or
            receipt.get("total_cases") != 645 or
            receipt.get("benchmark_dispatch_cases_per_mode") != 1 or
            receipt.get("cpu_timing_used") is not False or
            receipt.get("binary_sha256") != sha(binary) or
            receipt.get("fixture_sha256") != sha(fixture_path) or
            fixture.get("schema") != 1 or len(fixture.get("cases", [])) != 129):
        raise SystemExit("binary, fixture, or checker receipt differs")

    source_hashes = receipt.get("source_sha256", {})
    if (set(source_hashes) != SOURCE_NAMES or
            any(source_hashes[name] != sha(repo / name) for name in SOURCE_NAMES)):
        raise SystemExit("executed source snapshot differs from checker receipt")
    input_path = receipt_path.with_name(receipt_path.stem + "-input.txt")
    if receipt.get("input_sha256") != sha(input_path):
        raise SystemExit("checker input differs")
    raw_paths = {}
    for mode in ("jacobian", "balanced", "deferred"):
        path = receipt_path.with_name(receipt_path.stem + f"-{mode}-raw.jsonl")
        if receipt.get("raw_output_sha256", {}).get(mode) != sha(path):
            raise SystemExit(f"{mode} raw output differs")
        raw_paths[mode] = path
    benchmark_paths = {}
    for mode, expected_mode in (("jacobian", MODES["jacobian"][1]),
                                ("balanced", MODES["balanced"][1]),
                                ("deferred", CANDIDATE[1])):
        path = receipt_path.with_name(receipt_path.stem + f"-{mode}-benchmark.txt")
        if receipt.get("benchmark_output_sha256", {}).get(mode) != sha(path):
            raise SystemExit(f"{mode} benchmark output differs")
        parsed = fields(path.read_text())
        if (parsed.get("verified") != "1" or parsed.get("curve") != "secp256k1" or
                parsed.get("mode") != expected_mode or
                parsed.get("scalar") != fixture["cases"][0]["scalar_hex"]):
            raise SystemExit(f"{mode} benchmark dispatch differs")
        benchmark_paths[mode] = path

    cases = []
    reference_flag, reference_name = MODES[args.reference_mode]
    for index in INDICES:
        row = fixture["cases"][index]
        if row["index"] != index:
            raise SystemExit("fixture case order differs")
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
            "reference": [str(binary), reference_flag] + common,
            "candidate": [str(binary), CANDIDATE[0]] + common,
        })
    artifacts = [binary, receipt_path, fixture_path, input_path,
                 *(repo / name for name in sorted(SOURCE_NAMES)),
                 *raw_paths.values(), *benchmark_paths.values(),
                 here / "make_deferred_isolated_manifest.py",
                 here / "DEFERRED_RESULT.md", here / "ISOLATED_PANEL.md",
                 here / "README.md",
                 repo / "scripts/isolated_bench.py"]
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
            "and the U14 fixed-generator table are initialized. Includes scalar reduction, "
            "Eisenstein recoding, orbit lookups and unit actions, all mixed additions, "
            "final affine conversion, and expected-point assertion. Stops after the "
            "assertion; excludes process launch and reusable table preparation."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point",
        "workload_sha256": sha(fixture_path),
        "comparison_kind": f"single-public-scalar-u14-{args.reference_mode}-vs-xyzz-deferred",
        "reference_mode": reference_name,
        "candidate_mode": CANDIDATE[1],
        "cases": cases,
    }
    sys.path.insert(0, str(repo / "scripts"))
    from isolated_bench import require_manifest
    require_manifest(manifest)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": args.repetitions,
                      "reference_mode": args.reference_mode,
                      "manifest_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
