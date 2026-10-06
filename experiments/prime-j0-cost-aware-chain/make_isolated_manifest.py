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
    adapt2 = args.candidate_arm == "fused-hot-adapt2-batch128"
    gated = args.candidate_arm == "fused-hot-gated-batch128"
    steer = args.candidate_arm == "fused-hot-steer-batch128"
    gated2 = args.candidate_arm == "fused-hot-steer-gated2-batch128"
    graph = args.candidate_arm == "tapered-residue-graph-batch128"
    tapered = args.candidate_arm in ("tapered-residue-orbit-batch128",
                                     "tapered-residue-graph-batch128")
    hot = args.candidate_arm == "fused-hot-batch128" or adapt2 or gated or steer or gated2 or tapered
    fused = args.candidate_arm in ("fused-batch128", "fused-orbit-batch128",
                                   "fused-hot-batch128",
                                   "fused-hot-adapt2-batch128",
                                   "fused-hot-gated-batch128",
                                   "fused-hot-steer-batch128",
                                   "fused-hot-steer-gated2-batch128",
                                   "tapered-residue-orbit-batch128",
                                   "tapered-residue-graph-batch128")
    if args.reference_arm and not (gated or gated2 or tapered):
        raise ValueError("--reference-arm is only supported for gated or tapered candidates")
    default_prefix = ("orbit-graph" if graph else "tapered" if tapered else
                      "gated2-steer" if gated2 else
                      "steer" if steer else "gated" if gated else
                      "adapt2" if adapt2 else "hot" if hot else
                      "orbit" if orbit else "fused"
                      if fused else "atlas" if atlas else None)
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
    if orbit or hot:
        artifacts += [experiment / "FUSED_TAU_ORBITS.md",
                      experiment / "make_tau8_orbits.py",
                      experiment / "make_orbit_inputs.py",
                      experiment / "check_orbit_panel.py",
                      root / "src" / "generated" / "tau8_orbit_map.h"]
    if hot:
        artifacts += [experiment / "HOT_ORBIT_TABLE.md",
                      experiment / "screen_hot_orbits.py",
                      experiment / "hot-orbit-screen.json",
                      experiment / "make_tau8_hot.py",
                      experiment / "make_hot_inputs.py",
                      experiment / "check_hot_panel.py",
                      root / "src" / "generated" / "tau8_hot_map.h"]
    if adapt2 or gated:
        artifacts += [experiment / "README.md",
                      experiment / "INTEGRATION.md",
                      experiment / "TABLE_AWARE_HOT.md",
                      experiment / "screen_table_aware.py",
                      experiment / "table-aware-screen.json",
                      experiment / "make_adapt_inputs.py",
                      experiment / "check_adapt_panel.py"]
    if gated:
        artifacts += [experiment / "GATED_TABLE_AWARE.md",
                      experiment / "screen_gated_table_aware.py",
                      experiment / "gated-table-aware-screen.json",
                      experiment / "make_gated_inputs.py",
                      experiment / "check_gated_panel.py"]
    if steer or gated2 or tapered:
        artifacts += [experiment / "README.md", experiment / "INTEGRATION.md",
                      experiment / "CARRY_STEERED_TAU8.md",
                      experiment / "make_tau8_steer.py",
                      experiment / "screen_carry_steer.py",
                      experiment / "carry-steer-screen.json",
                      experiment / "make_steer_inputs.py",
                      experiment / "check_steer_panel.py",
                      experiment / "steer-panel.json",
                      root / "src" / "generated" / "tau8_steer_map.h"]
    if gated2 or tapered:
        artifacts += [experiment / "GATED_DUAL_STEER.md",
                      experiment / "screen_gated_dual_steer.py",
                      experiment / "gated-dual-steer-screen.json",
                      experiment / "runpod-isolation-preflight-20261004.json",
                      experiment / "make_gated2_steer_inputs.py",
                      experiment / "check_gated2_steer_panel.py",
                      experiment / "gated2-steer-panel.json"]
    if tapered:
        artifacts += [experiment / "TAPERED_RESIDUE_ORBITS.md",
                      experiment / "make_tau_wide_orbits.py",
                      experiment / "screen_tapered_residue.py",
                      experiment / "tapered-residue-screen.json",
                      experiment / "make_tapered_inputs.py",
                      experiment / "check_tapered_panel.py",
                      experiment / "tapered-panel.json",
                      root / "src" / "generated" / "tau_wide_orbits.h"]
    if graph:
        artifacts += [experiment / "ORBIT_GRAPH_PRECOMPUTE.md",
                      experiment / "make_tau_wide_graph.py",
                      experiment / "orbit-graph-screen.json",
                      experiment / "make_graph_inputs.py",
                      experiment / "check_orbit_graph_panel.py",
                      experiment / "orbit-graph-panel.json",
                      root / "src" / "generated" / "tau_wide_graph.h"]
    artifacts += sorted((root / "src").glob("*.c"))
    artifacts += sorted((root / "src").glob("*.h"))
    artifacts += sorted((root / "include" / "cryptanalysis").glob("*.h"))
    cases = []
    default_reference = ("tapered-residue-orbit-batch128" if graph else
                         "fused-hot-steer-gated2-batch128" if tapered else
                         "fused-hot-steer-batch128" if gated2 else
                         "fused-hot-adapt2-batch128" if gated else
                         "fused-hot-batch128" if adapt2 or steer else
                         "fused-orbit-batch128" if hot else
                         "fused-batch128" if orbit else
                         "pos-batch128" if fused else
                         "pos-global" if args.candidate_arm.startswith("pos-batch") else
                         "baseline")
    for case in fixture["cases"]:
        scalar_path = (experiment / case["scalar_file"] if graph else
                       experiment / input_dir / case["scalar_file"])
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
                      "reference": [base[0], args.reference_arm or default_reference,
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
            "all candidate recoding, point additions, fallback work, output normalization, "
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
        "fused-orbit-batch128", "fused-hot-batch128",
        "fused-hot-adapt2-batch128", "fused-hot-gated-batch128",
        "fused-hot-steer-batch128", "fused-hot-steer-gated2-batch128",
        "tapered-residue-orbit-batch128", "tapered-residue-graph-batch128"),
                        default="cost")
    parser.add_argument("--reference-arm", choices=(
        "fused-hot-batch128", "fused-hot-adapt2-batch128",
        "fused-hot-steer-batch128", "fused-hot-steer-gated2-batch128",
        "tapered-residue-orbit-batch128"))
    parser.add_argument("--cgroup", required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-nodes", required=True)
    parser.add_argument("--output", type=Path, required=True)
    make(parser.parse_args())
