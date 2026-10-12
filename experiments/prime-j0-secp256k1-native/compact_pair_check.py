#!/usr/bin/env python3
"""Replay compact orbit-pair tables against the frozen full-width table."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
import lazy_tau_screen as curve
from screen_coset_representatives import N

HERE = Path(__file__).resolve().parent
SEED = 20261009131
COUNT = 2048
REFERENCE_SOURCE_SHA256 = "280de1b3ff243c21e3e6b77d15128aba65491b62022402d2045f6a1f2d5d7fd3"
REFERENCE_BINARY_SHA256 = "285e29a661105e63a290c9c45d9df63b36d6cf6f4f65fed27e9a9d4250d4a236"
MODE = "--scalar-w6-comb13-hex9-paired-fixed"
CASE_MODE = "--benchmark-scalar-w6-comb13-hex9-paired-fixed-case"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(binary, scalars):
    request = "".join(scalar_text(value) + "\n" for value in scalars)
    process = subprocess.run([str(binary), MODE], input=request, text=True,
                             capture_output=True, check=True, timeout=600)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def write_manifest(args, reference, candidate, result_path):
    if args.manifest is None:
        return
    required = (args.reference_source, args.cgroup, args.cpus,
                args.execution_cpu, args.mem_node)
    if any(value is None for value in required):
        raise SystemExit("manifest needs reference source and isolation parameters")
    if args.manifest.exists():
        raise SystemExit("manifest exists; refusing overwrite")
    reference_source = args.reference_source.resolve(strict=True)
    if sha(reference_source) != REFERENCE_SOURCE_SHA256:
        raise SystemExit("reference source does not match frozen parent")
    repo = HERE.parents[1]
    fixture_path = HERE / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 129
    cases = []
    for index, row in enumerate(fixture["cases"]):
        common = [str(fixture_path), str(index)]
        cases.append({"id": row["panel"] + "-" + str(index),
                      "expected_fields": {"curve": "secp256k1", "base_x": row["base_x_hex"],
                                          "base_y": row["base_y_hex"], "scalar": row["scalar_hex"]},
                      "expected_result": row["expected_x_hex"] + ":" + row["expected_y_hex"],
                      "reference": [str(reference), CASE_MODE] + common,
                      "candidate": [str(candidate), CASE_MODE] + common})
    artifacts = [reference_source, HERE / "src/bin/eisenstein_fixed.rs",
                 HERE / "Cargo.toml", HERE / "Cargo.lock", HERE / "compact_pair_check.py",
                 HERE / "COMPACT_PAIR_PROTOCOL.md", HERE / "PAIR_COMB_RESULT.md",
                 fixture_path, result_path, repo / "suite/src/ct_bignum.rs",
                 repo / "scripts/isolated_bench.py"]
    manifest = {"schema": 1, "workdir": str(repo),
                "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                              "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node},
                "artifacts": [str(path) for path in artifacts],
                "timeout_s": args.timeout_s, "repetitions": args.repetitions,
                "measurement_boundary": (
                    "Both variants start after fixture loading, scalar decoding, lattice constants, "
                    "and fixed-generator tables are initialized. Includes nine candidate "
                    "constructions and recodings, selection, pair-table indexing, compact-slot "
                    "decoding where applicable, point evaluation, affine conversion, and "
                    "expected-point assertion. Ends after that assertion."),
                "pair_fields": ["curve", "base_x", "base_y", "scalar"],
                "result_field": "point", "workload_sha256": sha(fixture_path),
                "comparison_kind": "single-public-scalar-pair-table-full-vs-compact",
                "cases": cases}
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"manifest": str(args.manifest), "sha256": sha(args.manifest),
                      "cases": len(cases), "repetitions": args.repetitions}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--reference-source", type=Path)
    parser.add_argument("--cgroup")
    parser.add_argument("--cpus")
    parser.add_argument("--execution-cpu", type=int)
    parser.add_argument("--mem-node")
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--timeout-s", type=int, default=30)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("result exists; refusing overwrite")
    reference = args.reference.resolve(strict=True)
    candidate = args.candidate.resolve(strict=True)
    assert sha(reference) == REFERENCE_BINARY_SHA256
    frozen = json.loads((HERE / "hex9-cover-result.json").read_text())
    assert frozen["status"] == "passed"
    fixture = json.loads((HERE / "tau6-comb13-bench-fixture.json").read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 129
    edges = [0, 1, N - 1, N, N + 1]
    previous = [int(row["scalar_hex"], 16) for row in frozen["frozen"]["rows"]]
    fixture_scalars = [int(row["scalar_hex"], 16) for row in fixture["cases"]]
    rng = random.Random(SEED)
    fresh = [rng.randrange(N) for _ in range(COUNT)]
    scalars = edges + previous + fixture_scalars + fresh
    before = run(reference, scalars)
    after = run(candidate, scalars)
    fixture_start = len(edges) + len(previous)
    fresh_start = fixture_start + len(fixture_scalars)
    independent = set(range(len(edges)))
    independent.update(range(fresh_start, fresh_start + 256))
    for index, (scalar, old, new) in enumerate(zip(scalars, before, after)):
        assert old == new, index
        if index in independent:
            assert affine_from_native(new["point"]) == curve.point_multiply(scalar % N), index
        if fixture_start <= index < fresh_start:
            row = fixture["cases"][index - fixture_start]
            expected = (int(row["expected_x_hex"], 16), int(row["expected_y_hex"], 16))
            assert affine_from_native(new["point"]) == expected, index
    result = {"schema": 1, "status": "passed", "seed": SEED,
              "matched_outputs": len(scalars), "edge_cases": len(edges),
              "frozen_cases": len(previous), "fixture_cases": len(fixture_scalars),
              "fresh_cases": COUNT, "independent_points": len(independent),
              "reference_binary_sha256": sha(reference),
              "candidate_binary_sha256": sha(candidate),
              "candidate_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
              "checker_sha256": sha(Path(__file__))}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "matched_outputs": len(scalars),
                      "independent_points": len(independent),
                      "result_sha256": sha(args.output)}, sort_keys=True))
    write_manifest(args, reference, candidate, args.output)


if __name__ == "__main__":
    main()
