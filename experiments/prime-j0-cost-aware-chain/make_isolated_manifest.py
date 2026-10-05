#!/usr/bin/env python3
"""Bind the frozen scalar workload to one provisioned isolated Linux host."""

import argparse
import json
from pathlib import Path


def make(args):
    root = args.repo_root.resolve()
    experiment = root / "experiments" / "prime-j0-cost-aware-chain"
    atlas = args.candidate_arm == "atlas"
    orbit = args.candidate_arm == "fused-orbit-batch128"
    fused = args.candidate_arm in ("fused-batch128", "fused-orbit-batch128")
    default_prefix = "orbit" if orbit else "fused" if fused else "atlas" if atlas else None
    fixture_name = (f"{default_prefix}-inputs.json"
                    if default_prefix and args.fixture == "inputs.json"
                    else args.fixture)
    input_dir = (f"{default_prefix}-inputs"
                 if default_prefix and args.input_dir == "inputs"
                 else args.input_dir)
    fixture_path = experiment / fixture_name
    fixture = json.loads(fixture_path.read_text())
    bench = args.bench.resolve()
    artifacts = [root / "CMakeLists.txt", experiment / "bench.c",
                 fixture_path]
    if args.candidate_arm == "pos":
        artifacts += [experiment / "POSITIONAL.md",
                      experiment / "make_pos_inputs.py"]
    if args.candidate_arm.startswith("pos-batch"):
        artifacts += [experiment / "BATCH_OUTPUT.md",
                      experiment / "make_batch_inputs.py",
                      experiment / "check_batch_panel.py"]
    if atlas:
        artifacts += [experiment / "RESIDUE_ATLAS.md",
                      experiment / "make_residue_atlas.py",
                      experiment / "run.py",
                      experiment / "make_atlas_inputs.py",
                      root / "src" / "generated" / "tau4_residue_atlas.h"]
    if fused:
        artifacts += [experiment / "FUSED_TAU_PAIRS.md",
                      bench.parent / "CMakeCache.txt",
                      root / "scripts" / "isolated_bench.py",
                      experiment / "make_isolated_manifest.py",
                      experiment / "RESIDUE_ATLAS.md",
                      experiment / "make_tau8_pairs.py",
                      experiment / "make_residue_atlas.py",
                      experiment / "make_fused_inputs.py",
                      experiment / "make_inputs.py",
                      experiment / "check_fused_panel.py",
                      experiment / "check_panel.py",
                      experiment / "run.py",
                      root / "src" / "generated" / "tau4_residue_atlas.h",
                      root / "src" / "generated" / "tau8_pair_map.h"]
    if orbit:
        artifacts += [experiment / "FUSED_TAU_ORBITS.md",
                      experiment / "make_tau8_orbits.py",
                      experiment / "make_orbit_inputs.py",
                      experiment / "check_orbit_panel.py",
                      root / "src" / "generated" / "tau8_orbit_map.h"]
    artifacts += sorted((root / "src").glob("*.c"))
    artifacts += sorted((root / "src").glob("*.h"))
    artifacts += sorted((root / "include" / "cryptanalysis").glob("*.h"))
    cases = []
    for case in fixture["cases"]:
        scalar_path = experiment / input_dir / case["scalar_file"]
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
                      "reference": [base[0],
                                    "fused-batch128" if orbit else
                                    "pos-batch128" if fused else
                                    "pos-global" if args.candidate_arm.startswith(
                                        "pos-batch") else "baseline",
                                    *base[2:]],
                      "candidate": [base[0], args.candidate_arm, *base[2:]]})
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
            "After identical per-point global-batch table preparation: "
            "first public scalar representative selection through last "
            "affine output; includes all recoding, rotations, additions, "
            "candidate scratch allocation and block normalization; excludes "
            "loading, preparation, and independent replay"
            if args.candidate_arm.startswith("pos-batch") else
            "After each arm's per-point table preparation: first scalar "
            "reduction through last affine output; includes atlas lookups, "
            "all point additions, fallback work, output normalization, "
            "scratch allocation, and storage; excludes loading, preparation, "
            "and independent replay; setup is reported separately"
            if fused else
            "After all per-point preparation: first public scalar "
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
    parser.add_argument("--fixture", default="inputs.json")
    parser.add_argument("--input-dir", default="inputs")
    parser.add_argument("--candidate-arm", "--arm", choices=(
        "cost", "pos", "pos-batch32", "pos-batch128",
        "pos-batch512", "pos-batch4096", "atlas", "fused-batch128",
        "fused-orbit-batch128"),
                        default="cost")
    parser.add_argument("--cgroup", required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-nodes", required=True)
    parser.add_argument("--output", type=Path, required=True)
    make(parser.parse_args())
