#!/usr/bin/env python3
"""Bind the frozen scalar workload to one provisioned isolated Linux host."""

import argparse
import json
from pathlib import Path


def make(args):
    root = args.repo_root.resolve()
    experiment = root / "experiments" / "prime-j0-cost-aware-chain"
    fixture = json.loads((experiment / "inputs.json").read_text())
    bench = args.bench.resolve()
    artifacts = [root / "CMakeLists.txt", experiment / "bench.c",
                 experiment / "inputs.json"]
    artifacts += sorted((root / "src").glob("*.c"))
    artifacts += sorted((root / "src").glob("*.h"))
    artifacts += sorted((root / "include" / "cryptanalysis").glob("*.h"))
    cases = []
    for case in fixture["cases"]:
        scalar_path = experiment / "inputs" / case["scalar_file"]
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
                          "input_digest": case["input_digest"]},
                      "expected_result": case["expected_output_digest"],
                      "reference": [base[0], "baseline", *base[2:]],
                      "candidate": [base[0], "cost", *base[2:]]})
    manifest = {
        "schema": 1,
        "workdir": str(root),
        "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu,
                      "mem_nodes": args.mem_nodes},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": 120,
        "repetitions": 5,
        "measurement_boundary": (
            "After per-point tau seed preparation: first public scalar "
            "representative selection through last affine output; includes "
            "all recoding, unit rotations, tripling, additions, conversions, "
            "and output storage; excludes loading, preparation, and replay"),
        "pair_fields": ["curve", "point_index", "count", "base_x",
                        "base_y", "input_digest"],
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
