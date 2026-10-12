#!/usr/bin/env python3
"""Bind the frozen first-word pair panel to an isolated Linux host."""

import argparse
import hashlib
import json
from pathlib import Path


FIXTURE_SHA256 = "d144189c6b53317c9380515baecb3ea3aec41fc00d8b82b367dba808eb0eaaf5"
REFERENCE = "tail-pair-periodic-canonical"
CANDIDATE = "tail-pair-periodic-firstword27"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make(args):
    repo = args.repo_root.resolve()
    experiment = repo / "experiments" / "prime-j0-cost-aware-chain"
    fixture_path = experiment / "firstword-pair-inputs.json"
    if sha256(fixture_path) != FIXTURE_SHA256:
        raise ValueError("first-word fixture differs from its published hash")
    fixture = json.loads(fixture_path.read_text())
    if fixture["status"] != "frozen_firstword_pair_disjoint_fixture" or len(fixture["cases"]) != 8:
        raise ValueError("unexpected first-word fixture cases")
    bench = args.bench.resolve(strict=True)
    cache = bench.parent / "CMakeCache.txt"
    artifacts = [repo / "CMakeLists.txt", repo / "scripts" / "isolated_bench.py",
                 experiment / "make_firstword_pair_isolated_manifest.py", experiment / "bench.c",
                 experiment / "FIRSTWORD_PAIR_GATE.md", fixture_path, cache, bench]
    artifacts += sorted((repo / "src").glob("*.c"))
    artifacts += sorted((repo / "src").glob("*.h"))
    artifacts += sorted((repo / "src" / "generated").glob("*.h"))
    artifacts += sorted((repo / "include" / "cryptanalysis").glob("*.h"))
    cases = []
    seen = set()
    for case in fixture["cases"]:
        if case["id"] in seen or case["scalars"] != 4096:
            raise ValueError("duplicate case or unexpected scalar count")
        seen.add(case["id"])
        scalar_path = experiment / case["scalar_file"]
        if sha256(scalar_path) != case["scalar_file_sha256"]:
            raise ValueError("scalar file differs from fixture: " + case["id"])
        artifacts.append(scalar_path)
        common = [case["curve"]["name"], str(case["point_index"]), str(scalar_path)]
        cases.append({"id": case["id"],
                      "expected_fields": {
                          "curve": case["curve"]["name"],
                          "point_index": str(case["point_index"]),
                          "count": "4096", "base_x": case["base_x"],
                          "base_y": case["base_y"],
                          "input_digest": case["input_digest"]},
                      "expected_result": case["expected_output_digest"],
                      "reference": [str(bench), REFERENCE, *common],
                      "candidate": [str(bench), CANDIDATE, *common]})
    if len(seen) != 8:
        raise ValueError("missing first-word fixture case")
    artifacts = sorted(set(artifacts))
    for path in artifacts:
        if not path.is_file():
            raise ValueError("missing source or build artifact: " + str(path))
    manifest = {
        "schema": 1, "workdir": str(repo),
        "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_nodes},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": 120, "repetitions": 5,
        "measurement_boundary": (
            "After input loading and 726-point preparation: first scalar reduction "
            "through last affine output; includes the candidate's first-word gate, "
            "one full recoder, group operations, conversion, and storage; excludes "
            "process startup, loading, preparation, and independent replay"),
        "pair_fields": ["curve", "point_index", "count", "base_x", "base_y",
                        "input_digest"],
        "result_field": "output_digest", "cases": cases,
    }
    output = args.output.resolve()
    data = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text() != data:
        raise ValueError("manifest already frozen with different contents: " + str(output))
    output.write_text(data)
    print(json.dumps({"cases": len(cases), "pairs": len(cases) * 5,
                      "manifest": str(output)}, sort_keys=True))


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
