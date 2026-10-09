#!/usr/bin/env python3
"""Build a paired GLV10/U14, GLV10/U15, or GLV10/U16 CPU manifest."""

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
    parser.add_argument("--unit-receipt", type=Path, required=True)
    parser.add_argument("--glv-receipt", type=Path, required=True)
    parser.add_argument("--candidate-format", type=int, choices=(14, 15, 16), required=True)
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
    if Path(__file__).resolve() != here / "make_unit_orbit_glv_isolated_manifest.py":
        raise SystemExit("generator must belong to the selected source snapshot")
    binary = args.binary.resolve(strict=True)
    unit_receipt = args.unit_receipt.resolve(strict=True)
    glv_receipt = args.glv_receipt.resolve(strict=True)
    unit = json.loads(unit_receipt.read_text())
    glv = json.loads(glv_receipt.read_text())
    fixture_path = here / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    source = here / "src/bin/eisenstein_fixed.rs"
    module = here / "src/bin/eisenstein_fixed/unit_orbit_windows.rs"
    if (unit["status"] != "passed" or unit["formats"] != [14, 15, 16] or
            unit["binary_sha256"] != sha(binary) or
            glv["status"] != "passed" or glv["method"] != "glv_comb10_fixed" or
            glv["fixture_cases"] != 129 or glv["paired_panel_indices"] != list(INDICES) or
            glv["binary_sha256"] != sha(binary) or
            glv["main_source_sha256"] != sha(source) or
            glv["multiply_source_sha256"] != sha(module) or
            glv["fixture_sha256"] != sha(fixture_path) or
            glv["unit_receipt_sha256"] != sha(unit_receipt) or
            glv["protocol_sha256"] != sha(here / "UNIT_ORBIT_GLV_ISOLATED_PROTOCOL.md") or
            glv["checker_sha256"] != sha(here / "check_unit_orbit_glv_isolated_cli.py") or
            fixture["schema"] != 1 or len(fixture["cases"]) != 129):
        raise SystemExit("binary, source, fixture, or GLV10 receipt differs")
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
            "reference": [str(binary), "--benchmark-scalar-glv-comb10-fixed-case"] + common,
            "candidate": [str(binary),
                          f"--benchmark-scalar-unit-orbit-windows{args.candidate_format}-fixed-case"] + common,
        })
    artifacts = [
        binary, source, module, fixture_path, unit_receipt, glv_receipt,
        here / "UNIT_ORBIT_GLV_ISOLATED_PROTOCOL.md",
        here / "UNIT_ORBIT_ISOLATED_TIMING_PROTOCOL.md",
        here / "check_unit_orbit_glv_isolated_cli.py",
        here / "check_unit_orbit_isolated_cli.py",
        here / "make_unit_orbit_glv_isolated_manifest.py",
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
            "and the selected fixed-generator table are initialized. Includes the "
            "target-dependent GLV or Eisenstein decomposition and recoding, all table "
            "lookups, unit maps, point operations, final affine conversion, and the "
            "expected-point assertion. Stops after that assertion; excludes process "
            "launch and reusable table preparation."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point",
        "workload_sha256": sha(fixture_path),
        "comparison_kind": f"single-public-scalar-glv10-vs-u{args.candidate_format}",
        "cases": cases,
    }
    sys.path.insert(0, str(repo / "scripts"))
    from isolated_bench import require_manifest
    require_manifest(manifest)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": args.repetitions,
                      "candidate_format": args.candidate_format,
                      "manifest_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
