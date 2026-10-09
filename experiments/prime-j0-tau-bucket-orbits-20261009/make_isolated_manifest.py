#!/usr/bin/env python3
"""Make a source-bound same-binary U14/tau-bucket comparison."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


INDICES = (0, 16, 32, 48, 64, 80, 96, 112, 128)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    here = repo / "experiments/prime-j0-tau-bucket-orbits-20261009"
    native = repo / "experiments/prime-j0-secp256k1-native"
    if Path(__file__).resolve() != here / "make_isolated_manifest.py":
        raise SystemExit("generator does not belong to the selected snapshot")
    binary = args.binary.resolve(strict=True)
    receipt_path = args.checker_receipt.resolve(strict=True)
    receipt = json.loads(receipt_path.read_text())
    fixture_path = native / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    if (receipt.get("status") != "passed" or
            receipt.get("fixture_cases") != 129 or
            receipt.get("fresh_and_boundary_cases") != 519 or
            receipt.get("independent_fresh_points_in_native_test") != 128 or
            receipt.get("native_tests_passed") != 64 or
            receipt.get("binary_sha256") != sha(binary) or
            receipt.get("scalar_input_sha256") !=
            json.loads((repo / "experiments/prime-j0-radix943-word-20261009/inputs.json").read_text())["scalar_sha256"] or
            fixture.get("schema") != 1 or len(fixture.get("cases", [])) != 129):
        raise SystemExit("checker, binary, input, or fixture differs")
    source_hashes = receipt.get("source_sha256", {})
    if not source_hashes or any(
        sha(repo / name) != digest for name, digest in source_hashes.items()
    ):
        raise SystemExit("checked source snapshot differs")
    runs = receipt.get("runs", {})
    for label in ("release_build", "native_tests", "reference-fixture", "candidate-fixture",
                  "reference-case", "candidate-case"):
        record = runs.get(label, {})
        if record.get("exit_code") != 0:
            raise SystemExit(f"{label} did not pass")
        for stream in ("stdout", "stderr"):
            path = here / record.get(f"{stream}_file", "")
            if not path.is_file() or sha(path) != record.get(f"{stream}_sha256"):
                raise SystemExit(f"{label} {stream} differs")
    cases = []
    for index in INDICES:
        row = fixture["cases"][index]
        if row["index"] != index:
            raise SystemExit("fixture order changed")
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
                          "--benchmark-scalar-unit-orbit-tau-bucket-fixed-case"] + common,
        })
    artifacts = [binary, receipt_path, fixture_path,
                 *(repo / name for name in sorted(source_hashes)),
                 here / "make_isolated_manifest.py", here / "ISOLATED_PANEL.md",
                 here / "RESULT.md", repo / "scripts/isolated_bench.py"]
    for record in runs.values():
        artifacts.extend(here / record[f"{stream}_file"] for stream in ("stdout", "stderr"))
    artifacts = list(dict.fromkeys(artifacts))
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
            "and the selected point table are initialized. Includes scalar reduction, "
            "lattice selection, signed-limb recoding, orbit lookup, unit action, bucket "
            "mixed additions, two tau bucket maps, projective bucket merges, "
            "final affine conversion, and expected-point assertion. Stops after the "
            "assertion; excludes process launch and reusable table preparation."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point",
        "workload_sha256": sha(fixture_path),
        "comparison_kind": "single-public-scalar-u14-vs-tau-bucket-orbit",
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
