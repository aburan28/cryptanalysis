#!/usr/bin/env python3
"""Generate a frozen one-target j=0 rho panel for isolated_bench.py."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ORDERS = {"j0-36": 51131959441, "j0-37": 157632877033,
          "j0-46": 42111239174233}


def scalar(curve, index):
    key = f"j0-covariant-panel-v1:{curve}:{index}".encode()
    return 1 + int.from_bytes(hashlib.sha256(key).digest(), "big") % (ORDERS[curve] - 1)


def frozen_target(binary, curve, secret_scalar):
    result = subprocess.run(
        [str(binary), "--print-target", curve, str(secret_scalar)],
        check=True, capture_output=True, text=True)
    fields = {}
    for word in result.stdout.strip().split():
        key, value = word.split("=", 1)
        if key in fields:
            raise ValueError("duplicate fixture field: " + key)
        fields[key] = value
    required = ("curve", "p", "b", "order", "base_x", "base_y",
                "target_x", "target_y", "fixture_scalar")
    if any(not fields.get(key) for key in required):
        raise ValueError("fixture output is missing required fields")
    if fields["curve"] != curve or fields["fixture_scalar"] != str(secret_scalar):
        raise ValueError("fixture scalar or curve differs from frozen input")
    return fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--cgroup", type=Path, required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-nodes", required=True)
    parser.add_argument("--targets-36", type=int, default=64)
    parser.add_argument("--targets-37", type=int, default=64)
    parser.add_argument("--targets-46", type=int, default=32)
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(not path.is_absolute() for path in (args.reference, args.candidate,
                                               args.workdir, args.cgroup, args.output)):
        parser.error("all paths must be absolute paths on the benchmark host")
    counts = {"j0-36": args.targets_36, "j0-37": args.targets_37,
              "j0-46": args.targets_46}
    if any(n < 0 for n in counts.values()) or not any(counts.values()):
        parser.error("target counts must be nonnegative and not all zero")
    cases = []
    for curve, count in counts.items():
        for index in range(count):
            secret_scalar = scalar(curve, index)
            reference = frozen_target(args.reference, curve, secret_scalar)
            candidate = frozen_target(args.candidate, curve, secret_scalar)
            if reference != candidate:
                raise ValueError("reference and candidate fixture points differ")
            seed = "20261002"
            expected_fields = {key: reference[key] for key in
                               ("curve", "p", "b", "order", "base_x", "base_y",
                                "target_x", "target_y")}
            expected_fields["seed"] = seed
            run_args = ["--public-target", curve, "1", reference["target_x"],
                        reference["target_y"], seed]
            cases.append({"id": f"{curve}-target-{index}",
                          "expected_fields": expected_fields,
                          "expected_result": str(secret_scalar),
                          "reference": [str(args.reference)] + run_args,
                          "candidate": [str(args.candidate)] + run_args})
    manifest = {"schema": 1, "name": "j0-covariant-rho-isolated-replay",
                "workdir": str(args.workdir), "isolation": {"cgroup": str(args.cgroup),
                "cpus": args.cpus, "execution_cpu": args.execution_cpu,
                "mem_nodes": args.mem_nodes},
                "build": {"common": ["Release", "CA_CUPQC=OFF", "CA_WERROR=ON",
                                     "CA_J0_TAU_RHO_WIDTH=2", "bench_rho_large.c:-O3:-std=c11"],
                          "reference": "CA_J0_RHO_COVARIANT_WALK=OFF",
                          "candidate": "CA_J0_RHO_COVARIANT_WALK=ON"},
                "artifacts": [str(args.workdir / path) for path in
                              ("CMakeLists.txt", "src/curve.c", "src/ec_tau.c",
                               "experiments/prime-j0-tau-20260930/large-rho-20261002/bench_rho_large.c",
                               "scripts/make_j0_isolated_manifest.py", "scripts/isolated_bench.py")],
                "timeout_s": args.timeout_s, "repetitions": 1,
                "measurement_boundary": "benchmark online_ms: first ca_curve_solve step through independent point replay; fixture generation excluded",
                "pair_fields": ["curve", "p", "b", "order", "base_x", "base_y",
                                "target_x", "target_y", "seed"],
                "result_field": "found",
                "cases": cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(f"wrote {len(cases)} frozen targets to {args.output}")


if __name__ == "__main__":
    main()
