#!/usr/bin/env python3
"""Build a frozen, host-specific path-versus-radius-two CPU manifest."""

import argparse
import hashlib
import json
from pathlib import Path


REFERENCE_SOURCE_SHA256 = "036f504580933c0959d87e89975b4f69bb14bcdd275d41b49755fe614826e1b0"


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
    parser.add_argument("--timeout-s", type=int, default=300)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("manifest exists; refusing overwrite")
    if args.repetitions < 1 or args.timeout_s < 1:
        raise SystemExit("repetitions and timeout must be positive")
    repo = args.repo_root.resolve(strict=True)
    here = repo / "experiments/prime-j0-secp256k1-native"
    if Path(__file__).resolve() != here / "make_radius2_graph_isolated_manifest.py":
        raise SystemExit("script must belong to the selected repository snapshot")
    reference_source = args.reference_source.resolve(strict=True)
    reference = args.reference.resolve(strict=True)
    candidate = args.candidate.resolve(strict=True)
    if sha(reference_source) != REFERENCE_SOURCE_SHA256:
        raise SystemExit("adaptive path source does not match frozen parent")
    verification = json.loads((here / "radius2-graph-verify-result.json").read_text())
    screen = json.loads((here / "radius2-graph-screen-result.json").read_text())
    if (verification["status"] != "passed" or verification["cases"] != 8540 or
            verification["fixture_expected_points"] != 129 or
            verification["candidate_source_sha256"] != sha(here / "src/bin/eisenstein_fixed.rs") or
            screen["status"] != "screen_passed" or
            screen["protocol_sha256"] != sha(here / "RADIUS2_GRAPH_PROTOCOL.md")):
        raise SystemExit("frozen radius-two evidence or source has changed")
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
                          "--benchmark-scalar-w6-comb13-hex9-path-fixed-case"] + common,
            "candidate": [str(candidate),
                          "--benchmark-scalar-w6-comb13-hex9-radius2-fixed-case"] + common,
        })
    artifacts = [
        reference_source, reference, candidate, here / "src/bin/eisenstein_fixed.rs",
        here / "Cargo.toml", here / "Cargo.lock", here / "radius2_graph_screen.py",
        here / "radius2_graph_verify.py", here / "make_radius2_graph_isolated_manifest.py",
        here / "RADIUS2_GRAPH_PROTOCOL.md", here / "RADIUS2_GRAPH_RESULT.md",
        here / "radius2-graph-screen-result.json", here / "radius2-graph-verify-result.json",
        fixture_path, repo / "suite/src/ct_bignum.rs", repo / "scripts/isolated_bench.py",
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
            "fixed-generator graph tables are initialized. Includes all nine representative "
            "constructions and recodings, selection, maximum-matching atlas lookup and table "
            "indexing, compact point decoding, all point operations and terminal repair, "
            "affine conversion, and the independent expected-point assertion. Ends after "
            "that assertion; excludes process launch and reusable table setup."),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point", "workload_sha256": sha(fixture_path),
        "comparison_kind": "single-public-scalar-hex9-path-vs-radius-two-matching",
        "cases": cases,
    }
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": args.repetitions,
                      "manifest_sha256": sha(args.output),
                      "workload_sha256": manifest["workload_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
