#!/usr/bin/env python3
"""Bind 256-repeat positional table preparation to an isolated Linux host."""

import argparse
import json
from pathlib import Path


def make(args):
    root = args.repo_root.resolve()
    experiment = root / "experiments" / "prime-j0-cost-aware-chain"
    fixture_path = experiment / "global-inputs.json"
    fixture = json.loads(fixture_path.read_text())
    bench = args.bench.resolve()
    artifacts = [root / "CMakeLists.txt", root / "scripts" / "isolated_bench.py",
                 experiment / "bench.c", experiment / "GLOBAL_BATCH.md",
                 experiment / "make_global_inputs.py", fixture_path]
    artifacts += sorted((root / "src").glob("*.c"))
    artifacts += sorted((root / "src").glob("*.h"))
    artifacts += sorted((root / "include" / "cryptanalysis").glob("*.h"))
    cases = []
    for case in fixture["cases"]:
        scalar_path = experiment / "global-inputs" / case["scalar_file"]
        artifacts.append(scalar_path)
        base = [str(bench), None, case["curve"]["name"],
                str(case["point_index"]), str(scalar_path)]
        cases.append({"id": case["id"],
                      "expected_fields": {
                          "curve": case["curve"]["name"],
                          "point_index": str(case["point_index"]),
                          "count": str(case["scalars"]),
                          "base_x": case["base_x"],
                          "base_y": case["base_y"],
                          "input_digest": case["input_digest"],
                          "prep_repeats": "256"},
                      "expected_result": case["expected_output_digest"],
                      "reference": [base[0], "pos-prep", *base[2:]],
                      "candidate": [base[0], "pos-global-prep", *base[2:]]})
    manifest = {
        "schema": 1,
        "workdir": str(root),
        "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu,
                      "mem_nodes": args.mem_nodes},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": 120,
        "repetitions": 5,
        "metric_field": "prep_ms",
        "measurement_kind": "table_preparation_256_repeats",
        "measurement_boundary": (
            "256 sequential constructions of the same 1152-point table, "
            "starting before the first builder call and ending after the "
            "last return; includes heap allocation, projective tripling, "
            "batch normalization, and table storage; excludes process "
            "launch, curve setup, input loading, scalar evaluation, and "
            "independent replay"),
        "pair_fields": ["curve", "point_index", "count", "base_x",
                        "base_y", "input_digest", "prep_repeats"],
        "result_field": "output_digest",
        "cases": cases,
    }
    if not bench.is_file():
        raise ValueError(f"benchmark binary missing: {bench}")
    for path in artifacts:
        if not path.is_file():
            raise ValueError(f"artifact missing: {path}")
    data = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.output.exists() and args.output.read_text() != data:
        raise ValueError(f"manifest already frozen with different contents: {args.output}")
    args.output.write_text(data)
    print(json.dumps({"cases": len(cases), "repetitions": 5,
                      "preparation_repeats": 256,
                      "manifest": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--bench", type=Path, required=True)
    parser.add_argument("--cgroup", required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-nodes", required=True)
    parser.add_argument("--output", type=Path, required=True)
    make(parser.parse_args())
