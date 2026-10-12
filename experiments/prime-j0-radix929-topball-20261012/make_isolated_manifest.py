#!/usr/bin/env python3
"""Freeze a paired radix-943 versus radix-929 single-scalar CPU panel."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_INDICES = tuple(range(0, 512, 16))


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--overlay-record", type=Path, required=True)
    parser.add_argument("--cgroup", type=Path, required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-node", required=True)
    parser.add_argument("--indices", default=",".join(map(str, DEFAULT_INDICES)))
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve(strict=True)
    if Path(__file__).resolve() != repo / "experiments/prime-j0-radix929-topball-20261012/make_isolated_manifest.py":
        parser.error("generator must belong to the selected repository snapshot")
    binary = args.binary.resolve(strict=True)
    overlay = args.overlay_record.resolve(strict=True)
    cgroup = args.cgroup
    if not cgroup.is_absolute() or not args.output.is_absolute():
        parser.error("cgroup and output must be absolute host paths")
    if args.output.exists():
        parser.error("output manifest already exists")
    indices = tuple(int(item) for item in args.indices.split(","))
    if not indices or len(indices) != len(set(indices)) or any(index < 0 or index >= 512 for index in indices):
        parser.error("indices must be distinct holdout case numbers in [0, 511]")
    if args.repetitions < 5:
        parser.error("at least five paired repetitions are required")
    subprocess.run([sys.executable, str(HERE / "native_replay.py"),
                    "--binary", str(binary), "--overlay-record", str(overlay), "--check"],
                   cwd=repo, check=True, capture_output=True, text=True)
    fixture_path = HERE / "holdout.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 512
    cases = []
    for index in indices:
        row = fixture["cases"][index]
        assert row["index"] == index
        expected_point = ("identity" if row["expected_identity"] else
                          row["expected_x_hex"] + ":" + row["expected_y_hex"])
        common = [str(fixture_path), str(index)]
        cases.append({
            "id": f"scalar-{index}",
            "expected_fields": {
                "curve": "secp256k1", "base_x": row["base_x_hex"],
                "base_y": row["base_y_hex"], "scalar": row["scalar_hex"],
            },
            "expected_result": expected_point,
            "reference": [str(binary),
                "--benchmark-scalar-unit-orbit-u256-radix943-xyzz-gauge-pareto-solinas-fixed-case",
                *common],
            "candidate": [str(binary), "--radix929-case", *common],
        })
    artifacts = [
        binary, overlay, fixture_path,
        overlay.parent / "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs",
        overlay.parent / "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
        HERE / "native-replay.json", HERE / "native-rows.jsonl",
        HERE / "native_overlay.py", HERE / "native_replay.py",
        HERE / "radix929_overlay.rs", HERE / "radix929_cli.rs",
        HERE / "TopBound.lean", HERE / "TopRank.lean", HERE / "PROOF.md",
        HERE / "NATIVE_RESULT.md", HERE / "ISOLATED_PANEL.md", Path(__file__),
        repo / "experiments/prime-j0-pareto-tree-20261012/plans.bin",
        repo / "experiments/prime-j0-secp256k1-native/Cargo.toml",
        repo / "experiments/prime-j0-secp256k1-native/Cargo.lock",
        repo / "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs",
        repo / "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
        repo / "suite/src/ct_bignum.rs", repo / "scripts/isolated_bench.py",
    ]
    if not all(path.is_file() for path in artifacts):
        raise SystemExit("one or more frozen artifacts are missing")
    manifest = {
        "schema": 1,
        "name": "radix929-top-state-versus-radix943-single-scalar",
        "workdir": str(repo),
        "isolation": {
            "cgroup": str(cgroup), "cpus": args.cpus,
            "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node,
        },
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s,
        "repetitions": args.repetitions,
        "metric_field": "online_ms",
        "measurement_boundary": (
            "Both variants start after fixture parsing, scalar decoding, fixed field "
            "constants, and reusable point-table construction. Each interval includes "
            "scalar reduction, Eisenstein recoding, residue and top lookup, unit action, "
            "gauge-tree point combination, affine conversion, and comparison with the "
            "independently supplied public point. Stops after the point assertion. "
            "Launch and fixed-generator preparation are excluded."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point",
        "workload_sha256": digest(fixture_path),
        "comparison_kind": "single-public-scalar-radix943-versus-radix929-top-state",
        "cases": cases,
    }
    sys.path.insert(0, str(repo / "scripts"))
    from isolated_bench import require_manifest
    require_manifest(manifest)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": args.repetitions,
                      "manifest_sha256": digest(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
