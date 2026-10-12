#!/usr/bin/env python3
"""Build a paired BigInt-versus-word unit-orbit CPU manifest."""

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
    parser.add_argument("--format", type=int, choices=(14, 15, 16), required=True)
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
    if Path(__file__).resolve() != here / "make_unit_orbit_word_isolated_manifest.py":
        raise SystemExit("generator must belong to the selected source snapshot")
    binary = args.binary.resolve(strict=True)
    checker_receipt = args.checker_receipt.resolve(strict=True)
    checked = json.loads(checker_receipt.read_text())
    fixture_path = here / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    source = here / "src/bin/eisenstein_fixed.rs"
    module = here / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    if (checked["status"] != "passed" or checked["formats"] != [14, 15, 16] or
            checked["fixture_cases_per_format"] != 129 or
            checked["single_case_dispatch_per_format"] != 1 or
            checked["baseline_case_dispatch_per_format"] != 1 or
            checked["paired_panel_indices"] != list(INDICES) or
            checked["binary_sha256"] != sha(binary) or
            checked["main_source_sha256"] != sha(source) or
            checked["multiply_source_sha256"] != sha(module) or
            checked["fixture_sha256"] != sha(fixture_path) or
            checked["protocol_sha256"] != sha(here / "UNIT_ORBIT_WORD_PROTOCOL.md") or
            checked["checker_sha256"] != sha(here / "check_unit_orbit_word_cli.py") or
            fixture["schema"] != 1 or len(fixture["cases"]) != 129):
        raise SystemExit("binary, source, fixture, or word checker receipt differs")
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
                          f"--benchmark-scalar-unit-orbit-windows{args.format}-fixed-case"] + common,
            "candidate": [str(binary),
                          f"--benchmark-scalar-unit-orbit-word{args.format}-fixed-case"] + common,
        })
    artifacts = [
        binary, source, module, fixture_path, checker_receipt,
        here / "check_unit_orbit_word_cli.py",
        here / "make_unit_orbit_word_isolated_manifest.py",
        here / "UNIT_ORBIT_WORD_PROTOCOL.md",
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
            "and the selected fixed-generator table are initialized. Includes target-dependent "
            "lattice reduction, BigInt or signed-word residue and exact-quotient recoding, "
            "all residue lookups, unit maps, point additions, final affine conversion, "
            "and expected-point assertion. Stops after that assertion; excludes process "
            "launch and reusable table preparation."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point",
        "workload_sha256": sha(fixture_path),
        "comparison_kind": f"single-public-scalar-unit-orbit-bigint-vs-word-u{args.format}",
        "cases": cases,
    }
    sys.path.insert(0, str(repo / "scripts"))
    from isolated_bench import require_manifest
    require_manifest(manifest)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": args.repetitions,
                      "format": args.format, "manifest_sha256": sha(args.output)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
