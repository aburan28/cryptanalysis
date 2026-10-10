#!/usr/bin/env python3
"""Build a source-bound paired manifest for hybrid versus binary-GCD U14."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
NATIVE = ROOT / "experiments/prime-j0-secp256k1-native"
INDICES = (0, 16, 32, 48, 64, 80, 96, 112, 128)


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--cgroup", required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-node", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("manifest exists")
    binary = args.binary.resolve(strict=True)
    receipt_path = HERE / "verification.json"
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get("status") != "passed" or receipt.get("problems") or
            receipt.get("binary_sha256") != sha(binary) or
            receipt.get("native_tests_passed") != 74):
        raise SystemExit("verified executable or native suite differs")
    artifacts = [binary, receipt_path, HERE / "PROTOCOL.md",
                 HERE / "RESULT.md", Path(__file__),
                 ROOT / "scripts/isolated_bench.py"]
    for name, digest in receipt["source_sha256"].items():
        path = ROOT / name
        if sha(path) != digest:
            raise SystemExit("verified source or input differs: " + name)
        artifacts.append(path)
    for run in receipt["runs"].values():
        if run["exit_code"] != 0:
            raise SystemExit("fixture check failed")
        for stream in ("stdout", "stderr"):
            path = HERE / run[f"{stream}_file"]
            if sha(path) != run[f"{stream}_sha256"]:
                raise SystemExit("fixture output differs")
            artifacts.append(path)
    fixture_path = NATIVE / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    if fixture["schema"] != 1 or len(fixture["cases"]) != 129:
        raise SystemExit("fixture differs")
    cases = []
    for index in INDICES:
        row = fixture["cases"][index]
        if row["index"] != index:
            raise SystemExit("fixture order differs")
        expected = ("identity" if row["expected_identity"] else
                    row["expected_x_hex"] + ":" + row["expected_y_hex"])
        common = [str(fixture_path), str(index)]
        cases.append({
            "id": f"scalar-{index}",
            "expected_fields": {"curve": "secp256k1", "base_x": row["base_x_hex"],
                                "base_y": row["base_y_hex"], "scalar": row["scalar_hex"]},
            "expected_result": expected,
            "reference": [str(binary),
                          "--benchmark-scalar-unit-orbit-hybrid-fixed-case"] + common,
            "candidate": [str(binary),
                          "--benchmark-scalar-unit-orbit-binary-inverse-fixed-case"] + common,
        })
    manifest = {
        "schema": 1, "workdir": str(ROOT),
        "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node},
        "artifacts": [str(path) for path in dict.fromkeys(artifacts)],
        "timeout_s": 1200, "repetitions": args.repetitions,
        "metric_field": "online_ms",
        "measurement_boundary": (
            "Starts after fixture loading, scalar decoding, reciprocal and fixed-basis "
            "verification, shared U14 table preparation, hybrid field constants, and "
            "the binary-inverse Montgomery correction constant. "
            "Includes scalar reduction, "
            "both reciprocal products, certified corner selection, coordinate construction "
            "or exact fallback, signed-word recoding, orbit lookups, unit actions, mixed "
            "additions, field representation conversion, inversion, affine formatting, "
            "and expected-point verification. Stops after "
            "that verification."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point", "workload_sha256": sha(fixture_path),
        "comparison_kind": "single-public-scalar-u14-hybrid-vs-binary-inverse",
        "cases": cases,
    }
    sys.path.insert(0, str(ROOT / "scripts"))
    from isolated_bench import require_manifest
    require_manifest(manifest)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": args.repetitions,
                      "manifest_sha256": sha(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
