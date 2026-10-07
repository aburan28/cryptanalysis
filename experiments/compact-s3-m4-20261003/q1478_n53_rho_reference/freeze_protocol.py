#!/usr/bin/env python3
"""Freeze the Q1478 same-point rho source and workload."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
OUT = HERE / "protocol.json"
Q1477 = PARENT / "q1477_n53_online_target"
SOURCES = (
    "experiments/compact-s3-m4-20261003/protocol.json",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/n53_field.txt",
    "experiments/compact-s3-m4-20261003/q1420_root_theory/root_field.hpp",
    "experiments/compact-s3-m4-20261003/q1468_n53_pair_oracle/pair_oracle.cpp",
    "experiments/compact-s3-m4-20261003/q1477_n53_online_target/target.txt",
    "experiments/compact-s3-m4-20261003/q1477_n53_online_target/audit_fixture.json",
    "experiments/compact-s3-m4-20261003/q1477_n53_online_target/protocol.json",
    "experiments/compact-s3-m4-20261003/q1478_n53_rho_reference/design_protocol.json",
    "experiments/compact-s3-m4-20261003/q1478_n53_rho_reference/rho_reference.cpp",
    "experiments/compact-s3-m4-20261003/q1478_n53_rho_reference/build.py",
    "experiments/compact-s3-m4-20261003/q1478_n53_rho_reference/control.py",
    "experiments/compact-s3-m4-20261003/q1478_n53_rho_reference/run_stage.py",
    "experiments/compact-s3-m4-20261003/q1478_n53_rho_reference/audit.py",
    "experiments/compact-s3-m4-20261003/q1478_n53_rho_reference/freeze_protocol.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def render() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    build = json.loads((HERE / "compile_receipt.json").read_text())
    fixture = json.loads((Q1477 / "audit_fixture.json").read_text())
    q1477_protocol = json.loads((Q1477 / "protocol.json").read_text())
    parent = json.loads((PARENT / "protocol.json").read_text())
    profile = next(row for row in parent["profiles"] if row["curve"][
        "curve_id"] == design["exact_instance"]["curve_id"])
    assert design["proposal_id"] == control["proposal_id"] == "Q1478"
    assert control["status"] == "passed"
    assert control["collision_equation_checks"] == 6560
    assert build["binary_sha256"] == sha(HERE / "rho_reference")
    assert fixture["workload_id"] == q1477_protocol["workload_id"] == \
        design["exact_instance"]["workload_id"]
    assert sha(Q1477 / "target.txt") == q1477_protocol["target_file_sha256"]
    assert fixture["workload_record"]["curve_id"] == profile["curve"][
        "curve_id"]
    source_hashes = {relative: sha(ROOT / relative) for relative in SOURCES}
    rho_record = {
        "field": profile["field"], "curve": profile["curve"],
        "method": design["rho_method"],
        "native_source_sha256": sha(HERE / "rho_reference.cpp"),
        "arithmetic_source_sha256": sha(PARENT /
            "q1468_n53_pair_oracle/pair_oracle.cpp"),
        "native_binary_sha256": sha(HERE / "rho_reference"),
    }
    rho_id = "RHO1N53Ckb1h" + hashlib.sha256(canonical(
        rho_record)).hexdigest()[:12]
    return {
        "kind": "q1478_n53_one_target_rho_protocol",
        "proposal_id": "Q1478", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "curve_id": profile["curve"]["curve_id"],
        "rho_reference_id": rho_id,
        "rho_run_id": f"{rho_id}W{fixture['workload_id']}R1",
        "rho_record": rho_record,
        "workload_id": fixture["workload_id"],
        "workload_record": fixture["workload_record"],
        "worker_count": 1, "partition_count": 16,
        "distinguished_bits": 10,
        "random_seed": 14780053,
        "step_cap": 50000000,
        "native_online_wall_cap_seconds": 1800,
        "external_safeguard_seconds": 1850,
        "measurement_scope": design["claim_scope"],
        "measurement": design["measurement"],
        "source_sha256": source_hashes,
        "target_file_sha256": sha(Q1477 / "target.txt"),
        "target_fixture_sha256": sha(Q1477 / "audit_fixture.json"),
        "q1477_protocol_sha256": sha(Q1477 / "protocol.json"),
        "control_result_sha256": sha(HERE / "control_result.json"),
        "compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "native_binary_sha256": sha(HERE / "rho_reference"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "controlled_online_speedup": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = render()
    if args.emit:
        assert not OUT.exists(), "refuse overwrite"
        OUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert result == json.loads(OUT.read_text())
    print(json.dumps({"status": "pass", "rho_reference_id":
                      result["rho_reference_id"], "workload_id":
                      result["workload_id"]}), flush=True)


if __name__ == "__main__":
    main()
