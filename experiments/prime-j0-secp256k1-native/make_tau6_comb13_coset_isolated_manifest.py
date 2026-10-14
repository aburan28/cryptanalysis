#!/usr/bin/env python3
"""Pair sparse tau13 and coset3 on one strictly isolated Linux CPU."""

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
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--timeout-s", type=int, default=30)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("manifest exists; refusing overwrite")
    repo = args.repo_root.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    here = repo / "experiments/prime-j0-secp256k1-native"
    if Path(__file__).resolve() != here / "make_tau6_comb13_coset_isolated_manifest.py":
        raise SystemExit("script must be run from the selected repository snapshot")
    fixture_path = here / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    result_path = here / "tau6-comb13-coset-result.json"
    result = json.loads(result_path.read_text())
    if (fixture["schema"] != 1 or len(fixture["cases"]) != 129 or
            fixture["holdout_cases"] != 128 or fixture["deliberate_fallback_cases"] != 1 or
            result["schema"] != 1 or result["status"] != "passed" or
            result["native_verified_cases"] != 471):
        raise SystemExit("frozen fixture or coset result is incomplete")
    for expected, path in (
        (fixture["source_sha256"], here / "tau6-comb13-sparse-result.json"),
        (fixture["original_source_sha256"], here / "tau6-comb-result.json"),
        (fixture["reference_sha256"], here / "lazy_tau_screen.py"),
        (fixture["generator_sha256"], here / "make_tau6_comb13_bench_fixture.py"),
        (result["source_result_sha256"], here / "tau6-comb13-sparse-result.json"),
        (result["native_source_sha256"], here / "src/bin/eisenstein_fixed.rs"),
        (result["source_sha256"], here / "tau6_comb13_coset_screen.py"),
    ):
        if sha(path) != expected:
            raise SystemExit("source hash mismatch: " + str(path))

    cases = []
    for index, row in enumerate(fixture["cases"]):
        if row["index"] != index or row["expected_identity"]:
            raise SystemExit("invalid fixture case index or identity")
        panel = "holdout_random" if index < 128 else "deliberate_fallback"
        if row["panel"] != panel:
            raise SystemExit("fixture panel order changed")
        common = [str(fixture_path), str(index)]
        cases.append({
            "id": panel + "-" + str(index),
            "expected_fields": {"curve": "secp256k1", "base_x": row["base_x_hex"],
                                "base_y": row["base_y_hex"], "scalar": row["scalar_hex"]},
            "expected_result": row["expected_x_hex"] + ":" + row["expected_y_hex"],
            "reference": [str(binary), "--benchmark-scalar-w6-comb13-sparse-fixed-case"] + common,
            "candidate": [str(binary), "--benchmark-scalar-w6-comb13-coset3-fixed-case"] + common,
        })
    artifacts = [
        here / "Cargo.toml", here / "Cargo.lock", here / "src/bin/eisenstein_fixed.rs",
        here / "tau6-comb-result.json", here / "tau6-comb13-sparse-result.json",
        here / "tau6-comb13-coset-result.json", here / "tau6_comb13_sparse_screen.py",
        here / "tau6_comb13_coset_screen.py", here / "lazy_tau_screen.py",
        here / "make_tau6_comb13_bench_fixture.py",
        here / "make_tau6_comb13_coset_isolated_manifest.py",
        here / "TAU6_COMB13_COSET_RESULT.md", fixture_path,
        repo / "suite/src/ct_bignum.rs", repo / "suite/src/ecc/secp256k1_field.rs",
        repo / "scripts/isolated_bench.py",
    ]
    if not all(path.is_file() for path in artifacts):
        raise SystemExit("a required source artifact is missing")
    manifest = {
        "schema": 1,
        "workdir": str(repo),
        "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s,
        "repetitions": args.repetitions,
        "measurement_boundary": (
            "Starts after fixture loading, scalar decoding, lattice constants, and the shared "
            "fixed-generator table are initialized. Includes scalar reduction, representative "
            "search, all candidate digit recodings, selected point evaluation, affine "
            "conversion, and independent expected-point assertion. Ends after that assertion; "
            "excludes process launch, fixture loading, and table construction."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point",
        "comparison_kind": "single-public-scalar-fixed-generator-sparse-tau13-vs-coset3",
        "workload_sha256": sha(fixture_path),
        "cases": cases,
    }
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": args.repetitions,
                      "manifest_sha256": sha(args.output),
                      "workload_sha256": manifest["workload_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
