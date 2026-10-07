#!/usr/bin/env python3
"""Bind the frozen one-target rho fixture to the strict isolated runner."""

import argparse
import json
from pathlib import Path


EXPERIMENT = Path("experiments/prime-j0-paired-rho-startup")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--cgroup", type=Path, required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-nodes", required=True)
    parser.add_argument("--repetitions", type=int, default=21)
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(not path.is_absolute() for path in
           (args.binary, args.workdir, args.cgroup, args.output)):
        parser.error("all paths must be absolute paths on the benchmark host")
    if not args.binary.is_file() or not args.workdir.is_dir():
        parser.error("binary and workdir must exist on the benchmark host")
    if not 1 <= args.repetitions <= 1000 or not 0 < args.timeout_s <= 86400:
        parser.error("repetitions or timeout outside isolated runner limits")
    if args.binary.parent.joinpath("CMakeCache.txt").is_file() is False:
        parser.error("binary build directory must contain CMakeCache.txt")

    root = args.workdir
    folder = root / EXPERIMENT
    fixture_path = folder / "fixture.json"
    fixture = json.loads(fixture_path.read_text())
    if fixture.get("schema") != 1 or fixture.get("curve") != "glv-j0-32":
        parser.error("unexpected frozen target fixture")
    command = [str(args.binary)]
    point_and_seed = [str(fixture[key]) for key in
                      ("target_x", "target_y", "rho_seed")]
    sources = [root / "CMakeLists.txt", root / "AGENTS.md",
               root / "scripts/isolated_bench.py",
               args.binary.parent / "CMakeCache.txt"]
    for location in (root / "src", root / "include/cryptanalysis", folder):
        sources.extend(path for path in location.rglob("*") if path.is_file()
                       and path.suffix in (".c", ".h", ".py", ".json", ".md"))
    # A prior local panel is evidence, not an input to the measured binary.
    sources = [path for path in sources if path.name not in
               ("panel_local.json", "panel_ubsan.json")]
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        parser.error("missing provenance artifact: " + missing[0])
    manifest = {
        "schema": 1,
        "workdir": str(root),
        "isolation": {"cgroup": str(args.cgroup), "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu,
                      "mem_nodes": args.mem_nodes},
        "artifacts": [str(path) for path in sorted(set(sources))],
        "timeout_s": args.timeout_s,
        "repetitions": args.repetitions,
        "measurement_boundary": (
            "Inside ca_curve_solve_startup/glv_rho_solve: from first "
            "target-dependent computation after input/subgroup validation "
            "through collision recovery and internal scalar replay; excludes "
            "process launch, curve construction, fixture generation, and "
            "the separately timed post-solve replay"),
        "pair_fields": ["curve", "target_x", "target_y", "seed"],
        "result_field": "scalar",
        "cases": [{
            "id": "frozen-public-target",
            "expected_fields": {
                "curve": fixture["curve"],
                "target_x": str(fixture["target_x"]),
                "target_y": str(fixture["target_y"]),
                "seed": str(fixture["rho_seed"]),
            },
            "expected_result": str(fixture["expected_scalar"]),
            "reference": command + ["reference"] + point_and_seed,
            "candidate": command + ["paired2"] + point_and_seed,
        }],
    }
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
