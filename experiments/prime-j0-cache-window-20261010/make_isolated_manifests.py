#!/usr/bin/env python3
"""Create paired U14/U15 and U14/U16 manifests from one verified host build."""

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "experiments/prime-j0-host-replay-20261010"))
import host_replay as replay
sys.path.insert(0, str(ROOT / "scripts"))
from isolated_bench import require_manifest

INDICES = (0, 16, 32, 48, 64, 80, 96, 112, 128)
BOUNDARY = (
    "Starts after fixture loading, scalar decoding, both point-table preparations, "
    "field and unit constants, and binary-inverse correction setup. Includes scalar "
    "reduction, certified Voronoi selection, signed-word recoding, canonical-sector "
    "digit and orbit computation, point lookup, grouped-gauge additions, final "
    "inversion, affine formatting, and expected-point verification. Stops after "
    "that verification."
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--cgroup", required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-node", required=True)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    receipt_path = args.receipt.resolve(strict=True)
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get("status") != "passed" or receipt.get("native_tests_passed") != 90 or
            set(receipt.get("runs", {})) != {"u14", "u15", "u16"} or
            set(receipt.get("resources", {})) != {"u14", "u15", "u16"} or
            receipt.get("fixture_cases_per_mode") != 129):
        raise SystemExit("host correctness receipt is incomplete")
    binary = Path(receipt["binary"]).resolve(strict=True)
    if replay.sha(binary) != receipt["binary_sha256"]:
        raise SystemExit("verified executable changed")
    artifacts = [binary, receipt_path]
    for name, expected in receipt["source_sha256"].items():
        path = ROOT / name
        if replay.sha(path) != expected:
            raise SystemExit("verified source changed: " + name)
        artifacts.append(path)
    for name, expected in receipt["raw_sha256"].items():
        path = receipt_path.parent / name
        if replay.sha(path) != expected:
            raise SystemExit("raw correctness output changed: " + name)
        artifacts.append(path)
    fixture = json.loads(replay.FIXTURE.read_text())
    if fixture.get("schema") != 1 or len(fixture.get("cases", [])) != 129:
        raise SystemExit("fixture changed")
    targets = (("u15", "u256-sector15"), ("u16", "u256-sector16"))
    for label, flag in targets:
        cases = []
        for index in INDICES:
            case = fixture["cases"][index]
            if case["index"] != index:
                raise SystemExit("fixture order changed")
            expected = replay.expected(case)
            common = [str(replay.FIXTURE), str(index)]
            cases.append({
                "id": f"scalar-{index}",
                "expected_fields": {key: expected[key] for key in
                                    ("curve", "base_x", "base_y", "scalar")},
                "expected_result": expected["point"],
                "reference": [str(binary),
                              "--benchmark-scalar-unit-orbit-u256-sector-fixed-case", *common],
                "candidate": [str(binary),
                              f"--benchmark-scalar-unit-orbit-{flag}-fixed-case", *common],
            })
        manifest = {
            "schema": 1, "workdir": str(ROOT),
            "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                          "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node},
            "artifacts": [str(path) for path in dict.fromkeys(artifacts)],
            "timeout_s": 1200, "repetitions": args.repetitions,
            "metric_field": "online_ms", "measurement_boundary": BOUNDARY,
            "pair_fields": ["curve", "base_x", "base_y", "scalar"],
            "result_field": "point", "workload_sha256": replay.sha(replay.FIXTURE),
            "comparison_kind": f"single-public-scalar-u14-sector-vs-{label}-cache-window",
            "cases": cases,
        }
        require_manifest(manifest)
        output = args.output_prefix.resolve().with_name(args.output_prefix.name + f"-{label}.json")
        if output.exists():
            raise SystemExit("manifest already exists: " + str(output))
        output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"candidate": label, "output": str(output),
                          "sha256": replay.sha(output), "cases": len(cases),
                          "repetitions": args.repetitions}, sort_keys=True))


if __name__ == "__main__":
    main()
