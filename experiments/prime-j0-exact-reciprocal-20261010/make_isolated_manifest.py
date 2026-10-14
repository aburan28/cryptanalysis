#!/usr/bin/env python3
"""Make a source-bound same-binary U14/exact-reciprocal comparison."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

INDICES = (0, 16, 32, 48, 64, 80, 96, 112, 128)


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


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
    here = repo / "experiments/prime-j0-exact-reciprocal-20261010"
    native = repo / "experiments/prime-j0-secp256k1-native"
    if Path(__file__).resolve() != here / "make_isolated_manifest.py":
        raise SystemExit("generator differs from selected snapshot")
    binary = args.binary.resolve(strict=True)
    receipt_path = args.checker_receipt.resolve(strict=True)
    receipt = json.loads(receipt_path.read_text())
    if (receipt_path != here / "verification.json" or
            receipt.get("status") != "passed" or receipt.get("problems") != [] or
            receipt.get("binary_sha256") != sha(binary)):
        raise SystemExit("native verification receipt or binary differs")
    build_receipt_path = here / "build-receipt.json"
    build_receipt = json.loads(build_receipt_path.read_text())
    if (build_receipt.get("status") != "passed" or
            build_receipt.get("binary_sha256") != sha(binary) or
            build_receipt.get("verification_sha256") != sha(receipt_path)):
        raise SystemExit("build receipt differs")
    for label in ("native_release_build", "x86_cross_check"):
        record = build_receipt[label]
        if (record["exit_code"] != 0 or
                sha(here / record["combined_output_file"]) != record["combined_output_sha256"]):
            raise SystemExit(f"{label} output differs")
    source_hashes = receipt.get("source_sha256", {})
    if not source_hashes or any(sha(repo / name) != digest
                                for name, digest in source_hashes.items()):
        raise SystemExit("checked source snapshot differs")
    screen = json.loads((here / "screen-result.json").read_text())
    if screen.get("status") != "passed":
        raise SystemExit("exact quotient screen did not pass")
    runs = receipt.get("runs", {})
    if (runs.get("native_tests", {}).get("exit_code") != 0 or
            runs["native_tests"].get("passed") != 68):
        raise SystemExit("native suite did not pass")
    artifacts = [binary, receipt_path, build_receipt_path,
                 here / "release-build.log", here / "x86-cross-check.log",
                 here / "screen-result.json",
                 here / "make_isolated_manifest.py", here / "ISOLATED_PANEL.md",
                 here / "RESULT.md", repo / "scripts/isolated_bench.py",
                 *(repo / name for name in sorted(source_hashes))]
    for label, record in runs.items():
        if record.get("exit_code") != 0:
            raise SystemExit(f"{label} failed")
        if label == "native_tests":
            path = here / record["combined_output_file"]
            if sha(path) != record["combined_output_sha256"]:
                raise SystemExit("native suite output changed")
            artifacts.extend((path, here / record["exit_file"]))
        else:
            for stream in ("stdout", "stderr"):
                path = here / record[f"{stream}_file"]
                if sha(path) != record[f"{stream}_sha256"]:
                    raise SystemExit(f"{label} {stream} changed")
                artifacts.append(path)
    fixture_path = native / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    if fixture.get("schema") != 1 or len(fixture.get("cases", [])) != 129:
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
            "reference": [str(binary), "--benchmark-scalar-unit-orbit-word14-fixed-case"] + common,
            "candidate": [str(binary), "--benchmark-scalar-unit-orbit-reciprocal-fixed-case"] + common,
        })
    artifacts = list(dict.fromkeys(artifacts))
    if not all(path.is_file() for path in artifacts):
        raise SystemExit("required artifact missing")
    manifest = {
        "schema": 1, "workdir": str(repo),
        "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s, "repetitions": args.repetitions,
        "metric_field": "online_ms",
        "measurement_boundary": (
            "Starts after fixture loading, scalar decoding, lattice/reciprocal verification, "
            "and shared U14 table preparation. Includes scalar reduction, lattice-cell "
            "selection by division or fixed products, four-corner scoring, signed-word "
            "recoding, orbit lookup, unit action, mixed additions, affine conversion, and "
            "expected-point assertion. Stops after that assertion."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point", "workload_sha256": sha(fixture_path),
        "comparison_kind": "single-public-scalar-u14-word-vs-exact-reciprocal",
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
