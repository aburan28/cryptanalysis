#!/usr/bin/env python3
"""Build a paired CPU manifest for graph33 versus graph-aware selection."""

import argparse
import hashlib
import json
from pathlib import Path


BASELINE_SOURCE_SHA256 = "007205d4697855fab13ed4a0af45e7b199faaa79926f8543b0588cadb69c75ee"
BASELINE_BINARY_SHA256 = "a7a43630b2435daee293d9888b76527d345c56dec21bac500a8e91f5712b35e8"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--baseline-source", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--cgroup", required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-node", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--timeout-s", type=int, default=600)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("manifest exists")
    repo = args.repo_root.resolve(strict=True)
    here = repo / "experiments/prime-j0-secp256k1-native"
    if Path(__file__).resolve() != here / "make_graph_aware_isolated_manifest.py":
        raise SystemExit("generator must belong to the selected source snapshot")
    baseline_source = args.baseline_source.resolve(strict=True)
    baseline = args.baseline.resolve(strict=True)
    candidate = args.candidate.resolve(strict=True)
    if sha(baseline_source) != BASELINE_SOURCE_SHA256 or sha(baseline) != BASELINE_BINARY_SHA256:
        raise SystemExit("baseline source or binary differs from frozen graph33")
    verification = json.loads((here / "graph-aware-cover-verify.json").read_text())
    panels = {name: json.loads((here / f"graph-aware-cover-{name}.json").read_text())
              for name in ("design", "holdout")}
    if (verification["status"] != "passed" or verification["cases"] != 4444 or
            verification["fixture_expected_points"] != 129 or
            verification["candidate_source_sha256"] != sha(here / "src/bin/eisenstein_fixed.rs") or
            verification["candidate_binary_sha256"] != sha(candidate) or
            verification["baseline_binary_sha256"] != sha(baseline) or
            any(panel["status"] != "screen_passed" or panel["count"] != 2048 or
                panel["protocol_sha256"] != sha(here / "GRAPH_AWARE_COVER_PROTOCOL.md") or
                panel["screen_sha256"] != sha(here / "graph_aware_cover_screen.py") or
                verification["screen_sha256"][name] != sha(here / f"graph-aware-cover-{name}.json")
                for name, panel in panels.items())):
        raise SystemExit("graph-aware screen, correctness, or source receipt differs")
    fixture_path = here / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    if fixture["schema"] != 1 or len(fixture["cases"]) != 129:
        raise SystemExit("fixture is incomplete")
    cases = []
    for index, row in enumerate(fixture["cases"]):
        if row["index"] != index or row["expected_identity"]:
            raise SystemExit("invalid fixture case")
        common = [str(fixture_path), str(index)]
        cases.append({
            "id": row["panel"] + "-" + str(index),
            "expected_fields": {"curve": "secp256k1", "base_x": row["base_x_hex"],
                                "base_y": row["base_y_hex"], "scalar": row["scalar_hex"]},
            "expected_result": row["expected_x_hex"] + ":" + row["expected_y_hex"],
            "reference": [str(baseline),
                          "--benchmark-scalar-w6-comb13-hex9-graph33-fixed-case"] + common,
            "candidate": [str(candidate),
                          "--benchmark-scalar-w6-comb13-hex9-graphaware33-fixed-case"] + common,
        })
    artifacts = [
        baseline_source, baseline, candidate, here / "src/bin/eisenstein_fixed.rs",
        here / "Cargo.toml", here / "Cargo.lock", here / "GRAPH_AWARE_COVER_PROTOCOL.md",
        here / "GRAPH_AWARE_COVER_RESULT.md", here / "graph_aware_cover_screen.py",
        here / "graph_aware_cover_verify.py", here / "make_graph_aware_isolated_manifest.py",
        here / "graph-aware-cover-design.json", here / "graph-aware-cover-holdout.json",
        here / "graph-aware-cover-verify.json", fixture_path,
        repo / "suite/src/ct_bignum.rs", repo / "scripts/isolated_bench.py",
    ]
    if not all(path.is_file() for path in artifacts):
        raise SystemExit("required artifact missing")
    manifest = {
        "schema": 1, "workdir": str(repo),
        "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s, "repetitions": args.repetitions,
        "measurement_boundary": (
            "Starts after fixture loading, scalar decoding, lattice constants, and the "
            "fixed-generator graph33 tables and atlas are initialized. Includes all nine "
            "representative constructions and recodings, graph-aware mask scoring and "
            "selection, table lookup, compact-point decoding, all point operations and "
            "terminal repair, affine conversion, and expected-point assertion. Ends after "
            "that assertion; excludes process launch and reusable table setup."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point", "workload_sha256": sha(fixture_path),
        "comparison_kind": "single-public-scalar-graph33-vs-graph-aware-cover",
        "cases": cases,
    }
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": args.repetitions,
                      "manifest_sha256": sha(args.output),
                      "workload_sha256": manifest["workload_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
