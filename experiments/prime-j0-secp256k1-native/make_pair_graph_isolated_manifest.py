#!/usr/bin/env python3
"""Build a host-specific paired CPU manifest for adaptive tau-path matching."""

import argparse
import hashlib
import json
from pathlib import Path

REFERENCE_SOURCE_SHA256 = "c6c6127557ca475314c58feb7476fd03c62dce3a50c6190bb2071c9d07d76c9f"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--reference-source", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--cgroup", required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-node", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--timeout-s", type=int, default=30)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("manifest exists; refusing overwrite")
    repo = args.repo_root.resolve(strict=True)
    here = repo / "experiments/prime-j0-secp256k1-native"
    if Path(__file__).resolve() != here / "make_pair_graph_isolated_manifest.py":
        raise SystemExit("script must belong to the selected repository snapshot")
    reference_source = args.reference_source.resolve(strict=True)
    reference = args.reference.resolve(strict=True)
    candidate = args.candidate.resolve(strict=True)
    if sha(reference_source) != REFERENCE_SOURCE_SHA256:
        raise SystemExit("six-edge reference source does not match frozen parent")
    verification = json.loads((here / "pair-graph-verify-result.json").read_text())
    screen = json.loads((here / "pair-graph-screen-result.json").read_text())
    if (verification["status"] != "passed" or verification["cases"] != 4444 or
            verification["fixture_expected_points"] != 129 or
            verification["candidate_source_sha256"] != sha(here / "src/bin/eisenstein_fixed.rs") or
            screen["status"] != "screen_passed" or screen["protocol_sha256"] !=
            sha(here / "PAIR_GRAPH_PROTOCOL.md")):
        raise SystemExit("frozen path evidence or source has changed")
    fixture_path = here / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    if fixture["schema"] != 1 or len(fixture["cases"]) != 129:
        raise SystemExit("frozen 129-case fixture is incomplete")
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
            "reference": [str(reference),
                          "--benchmark-scalar-w6-comb13-hex9-paired-fixed-case"] + common,
            "candidate": [str(candidate),
                          "--benchmark-scalar-w6-comb13-hex9-path-fixed-case"] + common,
        })
    artifacts = [
        reference_source, here / "src/bin/eisenstein_fixed.rs", here / "Cargo.toml",
        here / "Cargo.lock", here / "pair_graph_screen.py", here / "pair_graph_verify.py",
        here / "make_pair_graph_isolated_manifest.py", here / "PAIR_GRAPH_PROTOCOL.md",
        here / "PAIR_GRAPH_RESULT.md", here / "pair-graph-screen-result.json",
        here / "pair-graph-verify-result.json", fixture_path,
        repo / "suite/src/ct_bignum.rs", repo / "scripts/isolated_bench.py",
    ]
    if not all(path.is_file() for path in artifacts):
        raise SystemExit("a required artifact is missing")
    manifest = {
        "schema": 1, "workdir": str(repo),
        "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s, "repetitions": args.repetitions,
        "measurement_boundary": (
            "Starts after fixture loading, scalar decoding, lattice constants, and both "
            "fixed-generator edge tables are initialized. Includes all nine representative "
            "constructions and recodings, selection, row matching and table indexing, compact "
            "point decoding, all point operations and terminal repair, affine conversion, and "
            "the independent expected-point assertion. Ends after that assertion; excludes "
            "process launch and reusable table setup."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point", "workload_sha256": sha(fixture_path),
        "comparison_kind": "single-public-scalar-hex9-six-edge-vs-adaptive-path",
        "cases": cases,
    }
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": args.repetitions,
                      "manifest_sha256": sha(args.output),
                      "workload_sha256": manifest["workload_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
