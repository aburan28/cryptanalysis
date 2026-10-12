#!/usr/bin/env python3
"""Replay orbit-quotiented pair comb against the frozen hex9 evaluator."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess

from check_eisenstein_scalar_fixed import affine_from_native, scalar_text
import lazy_tau_screen as curve
from screen_coset_representatives import N
from tau6_comb_screen import digit_stream
from width6_tau_screen import build_width_six_table

HERE = Path(__file__).resolve().parent
SEED = 20261009113
COUNT = 2048
PAIRS = ((0, 1), (2, 3), (4, 5), (6, 7), (8, 9), (10, 11))
REFERENCE_SOURCE_SHA256 = "ed24a77a761ccaa9cbf4dfb66724a2783ad2b78ab41578bee84c5a24c0869c8a"
REFERENCE_BINARY_SHA256 = "b806901d286cc82f0c2af75d6f28e0f27b10fabcc5e77a0fe2adbc012ed52159"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(binary, mode, scalars):
    request = "".join(scalar_text(value) + "\n" for value in scalars)
    process = subprocess.run([str(binary), f"--scalar-w6-comb13-{mode}-fixed"],
                             input=request, text=True, capture_output=True,
                             check=True, timeout=600)
    rows = [json.loads(line) for line in process.stdout.splitlines()]
    assert len(rows) == len(scalars)
    return rows


def expected_fusions(representative, table):
    digits = digit_stream(tuple(map(int, representative)), table, 162)
    total = 0
    for column in range(13):
        for left, right in PAIRS:
            li, ri = left * 13 + column, right * 13 + column
            total += int(li < len(digits) and ri < len(digits)
                         and digits[li] is not None and digits[ri] is not None)
    return total


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
                      "reference": [str(reference), "--benchmark-scalar-w6-comb13-hex9-fixed-case"] + common,
                      "candidate": [str(candidate), "--benchmark-scalar-w6-comb13-hex9-paired-fixed-case"] + common})
    artifacts = [reference_source, HERE / "src/bin/eisenstein_fixed.rs",
                 HERE / "Cargo.toml", HERE / "Cargo.lock", HERE / "pair_comb_screen.py",
                 HERE / "PAIR_COMB_PROTOCOL.md", HERE / "hex9-cover-result.json",
                 fixture_path, result_path, repo / "suite/src/ct_bignum.rs",
                 repo / "scripts/isolated_bench.py"]
    manifest = {"schema": 1, "workdir": str(repo),
                "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                              "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node},
                "artifacts": [str(path) for path in artifacts],
                "timeout_s": args.timeout_s, "repetitions": args.repetitions,
                "measurement_boundary": (
                    "Both variants start after fixture loading, scalar decoding, lattice constants, "
                    "and fixed-generator tables are initialized. Includes all nine candidate "
                    "constructions and recodings, selection, pair indexing and table access "
                    "where applicable, point evaluation, affine conversion, and expected-point "
                    "assertion. Ends after that assertion."),
                "pair_fields": ["curve", "base_x", "base_y", "scalar"],
                "result_field": "point", "workload_sha256": sha(fixture_path),
                "comparison_kind": "single-public-scalar-hex9-vs-orbit-paired-hex9",
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
    frozen_path = HERE / "hex9-cover-result.json"
    frozen = json.loads(frozen_path.read_text())
    assert frozen["status"] == "passed" and sha(reference) == REFERENCE_BINARY_SHA256
    edges = [0, 1, N - 1, N, N + 1]
    previous = [int(row["scalar_hex"], 16) for row in frozen["frozen"]["rows"]]
    fixture = json.loads((HERE / "tau6-comb13-bench-fixture.json").read_text())
    assert fixture["schema"] == 1 and len(fixture["cases"]) == 129
    fixture_scalars = [int(row["scalar_hex"], 16) for row in fixture["cases"]]
    rng = random.Random(SEED)
    fresh = [rng.randrange(N) for _ in range(COUNT)]
    scalars = edges + previous + fixture_scalars + fresh
    old = run(reference, "hex9", scalars)
    new = run(candidate, "hex9-paired", scalars)
    table, seeds, max_norm = build_width_six_table()
    assert len(seeds) == 81 and max_norm == 217
    totals = {"edge": Counter(), "frozen": Counter(), "fixture": Counter(),
              "fresh": Counter()}
    independent = set(range(len(edges)))
    fixture_start = len(edges) + len(previous)
    fresh_start = fixture_start + len(fixture_scalars)
    independent.update(range(fresh_start, fresh_start + 256))
    for index, (scalar, before, after) in enumerate(zip(scalars, old, new)):
        panel = ("edge" if index < len(edges) else
                 "frozen" if index < fixture_start else
                 "fixture" if index < fresh_start else "fresh")
        assert before["representative"] == after["representative"], index
        assert before["tau_steps"] == after["tau_steps"], index
        assert affine_from_native(before["point"]) == affine_from_native(after["point"]), index
        old_work, new_work = before["recoding_work"], after["recoding_work"]
        assert all(new_work[k] == value for k, value in old_work.items()), index
        fusions = expected_fusions(after["representative"], table)
        assert new_work["pair_fusions"] == fusions, index
        assert before["nonzero_digits"] == after["nonzero_digits"] + fusions, index
        if index in independent:
            assert affine_from_native(after["point"]) == curve.point_multiply(scalar % N), index
        if panel == "fixture":
            row = fixture["cases"][index - fixture_start]
            expected = (int(row["expected_x_hex"], 16), int(row["expected_y_hex"], 16))
            assert affine_from_native(after["point"]) == expected, index
        totals[panel].update({"cases": 1, "pair_fusions": fusions,
                              "reference_additions": before["nonzero_digits"],
                              "candidate_additions": after["nonzero_digits"],
                              "tau_steps": after["tau_steps"],
                              "reference_proxy": 5 * before["tau_steps"] + 11 * before["nonzero_digits"],
                              "candidate_proxy": 5 * after["tau_steps"] + 11 * after["nonzero_digits"],
                              "top_repairs": int(new_work["top_repaired"])})
    result = {"schema": 1, "status": "passed", "seed": SEED,
              "fresh_cases": COUNT, "edge_cases": len(edges), "frozen_cases": len(previous),
              "fixture_cases": len(fixture_scalars),
              "independent_points": len(independent),
              "totals": {panel: dict(counts) for panel, counts in totals.items()},
              "reference_binary_sha256": sha(reference),
              "candidate_binary_sha256": sha(candidate),
              "candidate_source_sha256": sha(HERE / "src/bin/eisenstein_fixed.rs"),
              "checker_sha256": sha(Path(__file__)),
              "reference_result_sha256": sha(frozen_path)}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "totals": result["totals"],
                      "result_sha256": sha(args.output)}, sort_keys=True))
    write_manifest(args, reference, candidate, args.output)


if __name__ == "__main__":
    main()
