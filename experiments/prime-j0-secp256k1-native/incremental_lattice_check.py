#!/usr/bin/env python3
"""Differentially replay incremental hexagonal candidates against the frozen binary."""

import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
import lazy_tau_screen as curve
from screen_coset_representatives import LAMBDA_TAU, N

HERE = Path(__file__).resolve().parent
SEED = 2026100979
COUNT = 2048
INDEPENDENT_FRESH = 128


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(binary, mode, scalars):
    request = "".join(scalar_text(value) + "\n" for value in scalars)
    process = subprocess.run([str(binary), f"--scalar-w6-comb13-{mode}-fixed"],
                             input=request, text=True, capture_output=True,
                             check=True, timeout=300)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def write_manifests(args, reference, candidate, frozen):
    required = (args.reference_source, args.cgroup, args.cpus,
                args.execution_cpu, args.mem_node)
    if any(value is None for value in required):
        raise SystemExit("manifest needs reference source and isolation parameters")
    reference_source = args.reference_source.resolve(strict=True)
    candidate_source = HERE / "src/bin/eisenstein_fixed.rs"
    if sha(reference_source) != frozen["native_source_sha256"]:
        raise SystemExit("reference source does not match frozen source")
    fixture_path = HERE / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 129
    repo = HERE.parents[1]
    artifacts = [reference_source, candidate_source,
                 HERE / "Cargo.toml", HERE / "Cargo.lock",
                 HERE / "incremental_lattice_check.py", fixture_path,
                 HERE / "hex9-cover-result.json", args.output,
                 repo / "suite/src/ct_bignum.rs", repo / "scripts/isolated_bench.py"]
    for mode in ("hex4", "hex9"):
        cases = []
        for index, row in enumerate(fixture["cases"]):
            common = [str(fixture_path), str(index)]
            case = {"id": row["panel"] + "-" + str(index),
                    "expected_fields": {"curve": "secp256k1", "base_x": row["base_x_hex"],
                                        "base_y": row["base_y_hex"], "scalar": row["scalar_hex"]},
                    "expected_result": row["expected_x_hex"] + ":" + row["expected_y_hex"],
                    "reference": [str(reference), f"--benchmark-scalar-w6-comb13-{mode}-fixed-case"] + common,
                    "candidate": [str(candidate), f"--benchmark-scalar-w6-comb13-{mode}-fixed-case"] + common}
            cases.append(case)
        manifest = {"schema": 1, "workdir": str(repo),
                    "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                                  "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node},
                    "artifacts": [str(path) for path in artifacts],
                    "timeout_s": args.timeout_s, "repetitions": args.repetitions,
                    "measurement_boundary": (
                        "For both variants, starts after fixture loading, scalar decoding, "
                        "lattice constants and shared fixed-generator table initialization. "
                        "Includes scalar reduction, full candidate construction and ranking, "
                        "all recodings and selection, point evaluation, affine conversion, "
                        "and expected-point assertion. Ends after that assertion."),
                    "pair_fields": ["curve", "base_x", "base_y", "scalar"],
                    "result_field": "point", "workload_sha256": sha(fixture_path),
                    "comparison_kind": f"single-public-scalar-{mode}-direct-vs-incremental",
                    "cases": cases}
        path = args.manifest_prefix.with_name(args.manifest_prefix.name + f"-{mode}.json")
        if path.exists():
            raise SystemExit("manifest exists; refusing overwrite: " + str(path))
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"manifest": str(path), "sha256": sha(path),
                          "cases": len(cases), "repetitions": args.repetitions}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-prefix", type=Path)
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
    frozen_path = HERE / "hex9-cover-result.json"
    frozen = json.loads(frozen_path.read_text())
    assert frozen["status"] == "passed" and frozen["binary_sha256"] == sha(reference)
    edges = [0, 1, N - 1, N, N + 1, 1 << 255,
             int(frozen["deliberate_fallback"]["scalar_hex"], 16)]
    previous = [int(row["scalar_hex"], 16) for row in frozen["frozen"]["rows"]]
    rng = random.Random(SEED)
    fresh = [rng.randrange(N) for _ in range(COUNT)]
    scalars = edges + previous + fresh
    independent = set(range(len(edges)))
    independent.update(range(len(edges) + len(previous),
                             len(edges) + len(previous) + INDEPENDENT_FRESH))
    for mode in ("hex4", "hex9"):
        old = run(reference, mode, scalars)
        new = run(candidate, mode, scalars)
        for index, (scalar, before, after) in enumerate(zip(scalars, old, new)):
            assert before == after, (mode, index, scalar)
            a, b = map(int, after["representative"])
            assert (a + b * LAMBDA_TAU - scalar) % N == 0, (mode, index)
            if index in independent:
                assert affine_from_native(after["point"]) == curve.point_multiply(scalar % N), (mode, index)
    result = {"schema": 1, "status": "passed", "seed": SEED, "fresh_cases": COUNT,
              "edge_cases": len(edges), "frozen_cases": len(previous),
              "matched_cases_per_mode": len(scalars), "modes": ["hex4", "hex9"],
              "independent_points_per_mode": len(independent),
              "reference_binary_sha256": sha(reference), "candidate_binary_sha256": sha(candidate),
              "reference_result_sha256": sha(frozen_path),
              "candidate_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
              "checker_sha256": sha(Path(__file__))}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "matched_outputs": len(scalars) * len(result["modes"]),
                      "independent_points": len(independent) * len(result["modes"]),
                      "result_sha256": sha(args.output)}, sort_keys=True))
    if args.manifest_prefix is not None:
        write_manifests(args, reference, candidate, frozen)


if __name__ == "__main__":
    main()
