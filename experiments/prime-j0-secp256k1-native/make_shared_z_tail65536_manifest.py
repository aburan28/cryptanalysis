#!/usr/bin/env python3
"""Prepare paired norm-4096 versus norm-65536 isolated scalar jobs."""

import argparse
import json
from pathlib import Path

from make_shared_z_degree_seven_manifest import manifest as base_manifest


HERE = Path(__file__).resolve().parent
REFERENCE = "--benchmark-shared-z-degree-seven-tail-case"
CANDIDATE = "--benchmark-shared-z-degree-seven-tail65536-case"


def manifest(args):
    plan = base_manifest(args)
    plan["name"] = "secp256k1-shared-z-tail65536-v1"
    plan["build"]["reference_mode"] = REFERENCE
    plan["build"]["candidate_mode"] = CANDIDATE
    for case in plan["cases"]:
        case["reference"][1] = REFERENCE
        case["candidate"][1] = CANDIDATE
    plan["artifacts"].extend(str(args.workdir / "experiments/prime-j0-secp256k1-native" / name)
                             for name in ("shared-z-tail65536.bin",
                                          "generate_shared_z_tail65536.py"))
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=HERE / "fresh-fixture.json")
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--cgroup", type=Path, required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-nodes", required=True)
    parser.add_argument("--timeout-s", type=int, default=30)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(not path.is_absolute() for path in (args.binary, args.fixture, args.workdir,
                                               args.cgroup, args.output)):
        parser.error("all paths must be absolute paths on the benchmark host")
    if args.repetitions < 1 or args.timeout_s < 1:
        parser.error("repetitions and timeout must be positive")
    plan = manifest(args)
    missing = [path for path in plan["artifacts"] if not Path(path).is_file()]
    if missing:
        parser.error("missing benchmark artifacts: " + ", ".join(missing))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n")
    print(f"wrote {len(plan['cases'])} frozen scalar pairs to {args.output}")


if __name__ == "__main__":
    main()
