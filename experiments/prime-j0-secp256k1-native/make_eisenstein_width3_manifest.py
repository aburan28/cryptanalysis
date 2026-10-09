#!/usr/bin/env python3
"""Freeze a serial width-two versus width-three Eisenstein scalar panel."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


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
    parser.add_argument("--candidate-kind", choices=("projective", "fixed-affine"),
                        default="projective")
    args = parser.parse_args()
    repo = args.repo_root.resolve(strict=True)
    here = repo / "experiments/prime-j0-secp256k1-native"
    assert Path(__file__).resolve() == here / "make_eisenstein_width3_manifest.py"
    binary = args.binary.resolve(strict=True)
    fixture_path = here / "eisenstein-pair-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1
    assert fixture["kind"] == "paired-fixed-generator-native-scalar"
    assert fixture["edge_cases"] == 22 and fixture["random_cases"] == 64
    assert len(fixture["cases"]) == 86
    assert fixture["reference_sha256"] == sha(here / "lazy_tau_screen.py")
    assert fixture["generator_sha256"] == sha(here / "make_eisenstein_pair_fixture.py")
    candidate_flag = ("--benchmark-scalar-w3-fixed-case"
                      if args.candidate_kind == "fixed-affine"
                      else "--benchmark-scalar-w3-case")
    cases = []
    for index, row in enumerate(fixture["cases"]):
        assert row["index"] == index and not row["expected_identity"]
        cases.append({
            "id": f"generator-scalar-{index}",
            "expected_fields": {
                "curve": "secp256k1",
                "base_x": row["base_x_hex"],
                "base_y": row["base_y_hex"],
                "scalar": row["scalar_hex"],
            },
            "expected_result": row["expected_x_hex"] + ":" + row["expected_y_hex"],
            "reference": [str(binary), "--benchmark-scalar-w2-case",
                          str(fixture_path), str(index)],
            "candidate": [str(binary), candidate_flag,
                          str(fixture_path), str(index)],
        })
    artifacts = [
        here / "Cargo.toml", here / "Cargo.lock", fixture_path,
        here / "make_eisenstein_pair_fixture.py",
        here / "make_eisenstein_width3_manifest.py",
        here / "check_eisenstein_width3.py",
        here / "check_eisenstein_scalar_fixed.py",
        here / "EISENSTEIN_WIDTH3_RESULT.md",
        here / "lazy_tau_screen.py", here / "eisenstein_montgomery.py",
        repo / "suite/src/ct_bignum.rs",
        repo / "scripts/isolated_bench.py",
    ]
    artifacts += sorted((here / "src").glob("*.rs"))
    artifacts += [here / "src/bin/eisenstein_fixed.rs"]
    assert all(path.is_file() for path in artifacts)
    manifest = {
        "schema": 1,
        "workdir": str(repo),
        "isolation": {
            "cgroup": args.cgroup,
            "cpus": args.cpus,
            "execution_cpu": args.execution_cpu,
            "mem_nodes": args.mem_node,
        },
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s,
        "repetitions": args.repetitions,
        "measurement_boundary": (
            "After fixture loading and fixed-generator validation, before scalar "
            "parsing; includes short representative, tau recoding, one-use "
            "orbit and cache preparation, point evaluation, affine inversion, "
            "field conversion, output formatting, and expected-point comparison."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point",
        "comparison_kind": (
            "eisenstein-unit-width2-vs-three-orbit-width3-" + args.candidate_kind),
        "workload_sha256": sha(fixture_path),
        "cases": cases,
    }
    sys.path.insert(0, str(repo / "scripts"))
    import isolated_bench
    isolated_bench.require_manifest(manifest)
    if args.output.exists():
        raise SystemExit("manifest exists; refusing overwrite")
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases),
                      "manifest_sha256": sha(args.output),
                      "workload_sha256": sha(fixture_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
