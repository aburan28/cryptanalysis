#!/usr/bin/env python3
"""Freeze one paired full-operation scalar multiplication benchmark job."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "selective-holdout.json"
ROOT = HERE.parent.parent


def files_for_crate(crate):
    files = [
        crate / "Cargo.toml",
        crate / "Cargo.lock",
        crate / "native-bench-overlay.json",
        crate / "src/bin/mixed640_bench_fixture.json",
    ]
    sources = sorted((crate / "src").rglob("*.rs"))
    files.extend(sources)
    for source in sources:
        files.extend(Path(path) for path in re.findall(
            r'include_(?:bytes|str)!\(\s*"(/[^"]+)"\s*\)',
            source.read_text()))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-crate", type=Path, required=True)
    parser.add_argument("--candidate-crate", type=Path, required=True)
    parser.add_argument("--allocation-receipt", type=Path, required=True)
    parser.add_argument("--runner-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--case-index", type=int, action="append",
                        help="fixture case index; repeat for a multi-case panel (default: 0)")
    parser.add_argument("--repetitions", type=int, default=8)
    parser.add_argument("--timeout-s", type=int, default=300)
    args = parser.parse_args()
    if args.repetitions < 5:
        parser.error("Tier 1 requires at least five alternating pairs")
    case_indices = args.case_index or [0]
    if args.cpu < 0 or any(index < 0 for index in case_indices):
        parser.error("CPU and case indices must be nonnegative")
    if len(set(case_indices)) != len(case_indices):
        parser.error("case indices must be distinct")
    panel = json.loads(FIXTURE.read_text())
    if any(index >= len(panel["cases"]) for index in case_indices):
        parser.error("case index exceeds frozen fixture length")
    receipt = json.loads(args.allocation_receipt.read_text())
    if receipt.get("provider") != "runpod" or not receipt.get("instance_id"):
        parser.error("allocation receipt must identify the RunPod Pod")
    fixture_hash = sha256(FIXTURE.read_bytes()).hexdigest()
    reference = args.reference_crate.resolve()
    candidate = args.candidate_crate.resolve()
    executable = lambda crate: crate / "target/release/eisenstein_fixed"
    artifacts = [FIXTURE, HERE / "selective-policy.json",
                 args.allocation_receipt, args.runner_source]
    artifacts += sorted(HERE.glob("*.py"))
    artifacts += sorted((HERE.parent / "prime-j0-mixed-radix640-20261010").glob("*.py"))
    artifacts += sorted((ROOT / "suite/src").rglob("*.rs"))
    artifacts += files_for_crate(reference) + files_for_crate(candidate)
    paths = sorted({str(path.resolve()) for path in artifacts})
    for path in paths + [str(executable(reference)), str(executable(candidate))]:
        if not Path(path).is_file():
            parser.error("missing benchmark artifact: " + path)
    manifest = {
        "schema": 1,
        "isolation": {
            "tier": "tier1",
            "cpus": str(args.cpu),
            "execution_cpu": args.cpu,
            "mem_nodes": "0",
            "cgroup": "/sys/fs/cgroup",
            "allocation": {
                "provider": "runpod",
                "instance_id": receipt["instance_id"],
                "receipt": str(args.allocation_receipt.resolve()),
            },
        },
        "workdir": str(HERE.parent.parent.resolve()),
        "repetitions": args.repetitions,
        "timeout_s": args.timeout_s,
        "measurement_boundary": (
            "Clock begins immediately before the scalar-dependent pre-tau "
            "multiply call and ends after affine point recovery. It includes "
            "recoding, table lookup, point selection, tree evaluation, and "
            "affine recovery. Fixture loading, table preparation, and "
            "independent equality checking are outside the online interval."
        ),
        "pair_fields": ["fixture_sha256", "case_id", "scalar"],
        "result_field": "point",
        "artifacts": paths,
        "cases": [{
            "id": f"selective_holdout_case_{index}",
            "reference": [str(executable(reference)),
                          "--benchmark-mixed640-packet", str(index)],
            "candidate": [str(executable(candidate)),
                          "--benchmark-mixed640-packet", str(index)],
            "expected_fields": {
                "fixture_sha256": fixture_hash,
                "case_id": str(index),
                "scalar": panel["cases"][index]["scalar_hex"],
            },
            "expected_result": panel["cases"][index]["point_hex"],
        } for index in case_indices],
    }
    outputs = []
    for index, case in zip(case_indices, manifest["cases"], strict=True):
        # The pinned Tier 1 runner accepts one frozen case per serial job.
        # A panel is a set of independently receipted one-case manifests.
        output = args.output if len(case_indices) == 1 else args.output.with_name(
            f"{args.output.stem}-case{index}{args.output.suffix}")
        single = {**manifest, "cases": [case]}
        output.write_text(json.dumps(single, indent=2, sort_keys=True) + "\n")
        outputs.append(str(output))
    print(json.dumps({"outputs": outputs, "case_indices": case_indices,
                      "fixture_sha256": fixture_hash,
                      "repetitions": args.repetitions}, sort_keys=True))


if __name__ == "__main__":
    main()
