#!/usr/bin/env python3
"""Freeze Q1479 identity, matched Q1476 inputs, executable, and limits."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1476 = PARENT / "q1476_trace_syndrome"
PROTOCOL = HERE / "protocol.json"
NEW_SOURCES = (
    "design_protocol.json", "native_solver.cpp", "build.py",
    "validate_domain.py", "freeze_protocol.py", "run_stage.py", "audit.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def render() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    parent = json.loads((Q1476 / "protocol.json").read_text())
    manifest = json.loads((Q1476 / "input_manifest.json").read_text())
    validation = json.loads((HERE / "domain_validation.json").read_text())
    build = json.loads((HERE / "compile_receipt.json").read_text())
    assert design["proposal_id"] == build["proposal_id"] == "Q1479"
    assert parent["proposal_id"] == "Q1476"
    assert design["run_order"] == parent["run_order"]
    assert validation["status"] == "passed"
    assert validation["source_sha256"] == sha(HERE / "validate_domain.py")
    assert validation["runtime_info_sha256"] == sha(HERE /
                                                   "sage_runtime_info.json")
    assert build["solver_binary_sha256"] == sha(HERE / "native_solver")
    assert build["source_sha256"]["native_solver.cpp"] == sha(
        HERE / "native_solver.cpp")
    source = dict(parent["source_sha256"])
    prefix = "experiments/compact-s3-m4-20261003/q1479_target_mid_domain/"
    source.update({prefix + name: sha(HERE / name) for name in NEW_SOURCES})
    source.update({
        "experiments/compact-s3-m4-20261003/q1476_trace_syndrome/protocol.json":
            sha(Q1476 / "protocol.json"),
        "experiments/compact-s3-m4-20261003/q1476_trace_syndrome/"
        "input_manifest.json": sha(Q1476 / "input_manifest.json"),
    })
    for relative, digest in source.items():
        assert sha(ROOT / relative) == digest, relative
    stages = {}
    for n in (53, 83):
        previous = parent["stages"][str(n)]
        record = json.loads(json.dumps(previous["stage_config_hash_input"]))
        assert record["isogeny"] == "none"
        pdp = record["point_decomposition"]
        assert pdp["stage_code"] == "PDP4hybrid"
        pdp["solver"] = ("Q1479 CaDiCaL compact chained-S3 SAT with "
                         "target-conditioned partial-midpoint domain")
        pdp["solver_binary_sha256"] = sha(HERE / "native_solver")
        pdp["solver_source_sha256"] = sha(HERE / "native_solver.cpp")
        pdp["decision_policy"] = "target_mid_domain_left_then_mid1"
        pdp["partial_left_pair_cap"] = design["method"][
            "partial_left_pair_cap"]
        pdp["domain_cache_entries"] = design["limits"][
            "domain_cache_entries"]
        pdp["domain_rule"] = design["method"]["rule"]
        pdp["domain_guard_rule"] = design["method"]["soundness_boundary"]
        pdp["parent_trace_stage_sha256"] = previous[
            "stage_config_sha256_full"]
        digest = hashlib.sha256(canonical(record)).hexdigest()
        actual_b = record["factor_base"][
            "actual_usable_points_B_before_folding"]
        stages[str(n)] = {
            "stage_config_hash_input": record,
            "stage_config_sha256_full": digest,
            "stage_config_id": f"PS1N{n}Ckb1fb{actual_b}PDP4hybridh{digest[:12]}",
            "curve_manifest_sha256": previous["curve_manifest_sha256"],
        }
    cases = {}
    for name in design["run_order"]:
        old = parent["cases"][name]
        cell = manifest["cases"][name]
        assert old["workload_id"] == cell["workload_id"]
        assert old["input_sha256"] == cell["input_sha256"]
        assert old["curve_id"] == cell["curve_id"]
        for filename, digest in cell["input_sha256"].items():
            assert sha(Q1476 / "inputs" / name / filename) == digest
        stage_id = stages[str(cell["degree_n"])]["stage_config_id"]
        cases[name] = {
            **old,
            "stage_config_id": stage_id,
            "stage_run_id": f"{stage_id}W{cell['workload_id']}R1",
            "parent_q1476_receipt_sha256": sha(Q1476 / "runs" /
                                               name / "receipt.json"),
        }
    return {
        "kind": "q1479_target_conditioned_midpoint_stage_protocol",
        "proposal_id": "Q1479", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "design_protocol_sha256": sha(HERE / "design_protocol.json"),
        "parent_q1476_protocol_sha256": sha(Q1476 / "protocol.json"),
        "input_manifest_sha256": sha(Q1476 / "input_manifest.json"),
        "domain_validation_sha256": sha(HERE / "domain_validation.json"),
        "stages": stages, "cases": cases,
        "run_order": design["run_order"],
        "pair_candidate_cap": design["method"]["joint_exact_pair_cap"],
        "domain_pair_cap": design["method"]["partial_left_pair_cap"],
        "domain_cache_cap": design["limits"]["domain_cache_entries"],
        "conflict_cap": design["limits"]["sat_conflicts_per_case"],
        "native_wall_cap_seconds": design["limits"][
            "native_wall_seconds_per_case"],
        "external_safeguard_seconds": design["limits"][
            "external_safeguard_seconds_per_case"],
        "decision_policy": "target_mid_domain_left_then_mid1",
        "solver_binary_sha256": sha(HERE / "native_solver"),
        "solver_compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "field_file_sha256": parent["field_file_sha256"],
        "source_sha256": source,
        "stop_rule": "run the six frozen Q1476 cells once in order, retaining all statuses",
        "measurement_units": design["measurements"],
        "measurement_scope": design["claim_limit"],
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = render()
    if args.emit:
        assert not PROTOCOL.exists(), "refuse overwrite"
        PROTOCOL.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert result == json.loads(PROTOCOL.read_text())
    print(json.dumps({"status": "pass", "stage_config_ids": [
        result["stages"][str(n)]["stage_config_id"] for n in (53, 83)],
        "protocol_sha256": sha(PROTOCOL)}), flush=True)


if __name__ == "__main__":
    main()
