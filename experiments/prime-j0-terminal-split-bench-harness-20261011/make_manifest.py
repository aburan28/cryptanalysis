#!/usr/bin/env python3
"""Freeze a paired full scalar multiplication manifest for the serial runner."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = "--benchmark-scalar-unit-orbit-u256-tau-dual-rho0-direct-gauge-xyzz-tau-fixed-case"
CANDIDATE = "--benchmark-scalar-unit-orbit-u256-tau-split-terminal-fixed-case"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--crate-root", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--native-receipt-name", choices=("benchmark-materialization.json",
                                                          "selector-materialization.json"),
                        default="benchmark-materialization.json")
    parser.add_argument("--tier", choices=("tier0_host", "tier1_instance"), required=True)
    parser.add_argument("--cpus", required=True)
    parser.add_argument("--execution-cpu", type=int, required=True)
    parser.add_argument("--mem-nodes")
    parser.add_argument("--cgroup")
    parser.add_argument("--allocation-receipt", type=Path)
    parser.add_argument("--provider")
    parser.add_argument("--instance-id")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--timeout-s", type=int, default=1200)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite frozen manifest")
    repo, crate = args.repo_root.resolve(strict=True), args.crate_root.resolve(strict=True)
    binary, fixture, runner = (path.resolve(strict=True) for path in
                               (args.binary, args.fixture, args.runner))
    if fixture != repo / "experiments/prime-j0-terminal-split-bench-harness-20261011/prospective-fixture.json":
        raise SystemExit("unexpected prospective fixture")
    data = json.loads(fixture.read_text())
    if data["schema"] != 1 or data["kind"] != "prospective-terminal-split" or len(data["cases"]) != 9:
        raise SystemExit("unexpected fixture contents")
    receipt_path = crate / args.native_receipt_name
    receipt = json.loads(receipt_path.read_text())
    if (receipt["status"] != "materialized" or
            receipt["top_sha256"] != digest(crate / "src/bin/eisenstein_fixed.rs") or
            receipt["window_sha256"] != digest(crate / "src/bin/eisenstein_fixed/unit_orbit_windows.rs")):
        raise SystemExit("native source differs from pinned materialization")
    isolation = {"cpus": args.cpus, "execution_cpu": args.execution_cpu}
    allocation = None
    artifacts = [binary, fixture, runner, receipt_path,
                 crate / "src/bin/eisenstein_fixed.rs",
                 crate / "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
                 crate / "Cargo.toml", crate / "Cargo.lock",
                 repo / "suite/src/ct_bignum.rs", HERE / "make_manifest.py"]
    if args.native_receipt_name == "selector-materialization.json":
        selector = repo / "experiments/prime-j0-terminal-split-selector-20261011"
        canonical_receipt = selector / "selector-materialization.json"
        if (digest(receipt_path) != digest(canonical_receipt) or
                receipt["input_sha256"] != digest(crate / "split-terminal-inputs.json") or
                receipt["certificate_sha256"] != digest(crate / "split-terminal-paths.jsonl") or
                receipt["patch_sha256"] != digest(selector / "native.patch") or
                receipt["materializer_sha256"] != digest(selector / "materialize.py")):
            raise SystemExit("selector materialization differs from pinned artifacts")
        artifacts += [canonical_receipt, selector / "native.patch",
                      selector / "materialize.py", crate / "split-terminal-inputs.json",
                      crate / "split-terminal-paths.jsonl"]
    if args.tier == "tier0_host":
        if not args.mem_nodes or not args.cgroup:
            raise SystemExit("Tier 0 requires NUMA node and exclusive cgroup")
        isolation.update({"mem_nodes": args.mem_nodes, "cgroup": args.cgroup})
    else:
        if not (args.allocation_receipt and args.provider and args.instance_id):
            raise SystemExit("Tier 1 requires allocation provenance")
        allocation_receipt = args.allocation_receipt.resolve(strict=True)
        allocation = {"provider": args.provider, "instance_id": args.instance_id,
                      "receipt": str(allocation_receipt)}
        artifacts.append(allocation_receipt)
    cases = []
    for index, row in enumerate(data["cases"]):
        if row["index"] != index:
            raise SystemExit("fixture case order changed")
        point = ("identity" if row["expected_identity"] else
                 row["expected_x_hex"] + ":" + row["expected_y_hex"])
        suffix = [str(fixture), str(index)]
        cases.append({"id": f"scalar-{index}",
                      "expected_fields": {"curve": "secp256k1",
                                          "base_x": row["base_x_hex"],
                                          "base_y": row["base_y_hex"],
                                          "scalar": row["scalar_hex"]},
                      "expected_result": point,
                      "reference": [str(binary), REFERENCE] + suffix,
                      "candidate": [str(binary), CANDIDATE] + suffix})
    name = ("secp256k1-split-terminal-selector-prospective" if
            args.native_receipt_name == "selector-materialization.json" else
            "secp256k1-split-terminal-prospective")
    manifest = {"schema": 1, "name": name,
                "measurement_tier": args.tier, "workdir": str(repo),
                "isolation": isolation,
                "artifacts": [str(path) for path in artifacts],
                "timeout_s": args.timeout_s, "repetitions": args.repetitions,
                "measurement_boundary": "After fixture decoding and reusable table preparation; includes fixed-limb lattice decomposition, four recodings and selection, point operations, affine conversion, and expected-point assertion through scalar replay",
                "pair_fields": ["curve", "base_x", "base_y", "scalar"],
                "result_field": "point", "workload_sha256": digest(fixture),
                "native_receipt_sha256": digest(receipt_path), "cases": cases}
    if allocation:
        manifest["allocation"] = allocation
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "manifest_sha256": digest(args.output)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
