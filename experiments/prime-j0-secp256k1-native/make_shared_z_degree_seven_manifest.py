#!/usr/bin/env python3
"""Prepare paired shared-Z scalar jobs for the isolated benchmark service.

The executable and fixture paths refer to files on the benchmark host. This
script only prepares a manifest; it does not run or certify a measurement.
"""

import argparse
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REFERENCE = "--benchmark-shared-z-zero-tau-case"
CANDIDATE = "--benchmark-shared-z-degree-seven-tail-case"


def manifest(args):
    linked = getattr(args, "linked_atlas", False)
    fixture = json.loads(args.fixture.read_text())
    if fixture.get("curve") != "secp256k1":
        raise ValueError("the frozen fixture must identify secp256k1")
    rows = fixture["cases"]
    if not rows:
        raise ValueError("the frozen fixture has no scalar cases")
    reference = ("--benchmark-shared-z-degree-seven-tail-case"
                 if linked else REFERENCE)
    candidate = ("--benchmark-shared-z-linked-degree-seven-tail-case"
                 if linked else CANDIDATE)
    cases = []
    for index, row in enumerate(rows):
        point = ("identity" if row.get("expected_identity") else
                 row["expected_x_hex"] + ":" + row["expected_y_hex"])
        cases.append({
            "id": f"secp256k1-scalar-{index}",
            "reference": [str(args.binary), reference, str(args.fixture), str(index)],
            "candidate": [str(args.binary), candidate, str(args.fixture), str(index)],
            "expected_fields": {
                "curve": "secp256k1",
                "base_x": row["base_x_hex"],
                "base_y": row["base_y_hex"],
                "scalar": row["scalar_hex"],
            },
            "expected_result": point,
        })
    artifacts = [
        args.fixture, args.binary,
        args.workdir / "experiments/prime-j0-secp256k1-native/Cargo.toml",
        args.workdir / "experiments/prime-j0-secp256k1-native/src/main.rs",
        args.workdir / "experiments/prime-j0-secp256k1-native/src/mixed_radix.rs",
        args.workdir / "experiments/prime-j0-secp256k1-native/shared-z-tail4096.bin",
        args.workdir / "experiments/prime-j0-secp256k1-native/generate_shared_z_tail.py",
    ]
    if linked:
        artifacts.extend([
            args.workdir / "experiments/prime-j0-secp256k1-native/linked-shared-z-tail4096.bin",
            args.workdir / "experiments/prime-j0-secp256k1-native/generate_linked_shared_z_tail.py",
        ])
    return {
        "schema": 1,
        "name": ("secp256k1-shared-z-linked-degree-seven-tail-v1"
                 if linked else "secp256k1-shared-z-degree-seven-tail-v1"),
        "workdir": str(args.workdir),
        "isolation": {
            "cgroup": str(args.cgroup),
            "cpus": args.cpus,
            "execution_cpu": args.execution_cpu,
            "mem_nodes": args.mem_nodes,
        },
        "build": {"profile": "release", "crate": "prime-j0-secp256k1-native-replay",
                  "reference_mode": reference, "candidate_mode": candidate},
        "artifacts": [str(path) for path in artifacts],
        "timeout_s": args.timeout_s,
        "repetitions": args.repetitions,
        "measurement_boundary": (
            "online_ms starts before scalar and base parsing; includes lattice reduction, "
            "recoding, seed preparation, shared-Z alignment, scalar evaluation, "
            "affine conversion, and independent frozen-point check; excludes "
            "process launch, fixture loading, and lazy constant-table initialization"),
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point",
        "cases": cases,
    }


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
    parser.add_argument("--linked-atlas", action="store_true",
                        help="compare the original and linked exact-tail digit atlases")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(not path.is_absolute() for path in (args.binary, args.fixture, args.workdir,
                                               args.cgroup, args.output)):
        parser.error("all paths must be absolute paths on the benchmark host")
    if not args.binary.is_file() or not args.fixture.is_file():
        parser.error("binary and fixture must exist on the benchmark host")
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
