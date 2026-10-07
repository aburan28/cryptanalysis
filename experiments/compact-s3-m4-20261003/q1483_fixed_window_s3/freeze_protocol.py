#!/usr/bin/env python3
"""Freeze Q1483 restricted-window stage IDs and byte-exact inputs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1482 = PARENT / "q1482_window_s3"
Q1480 = PARENT / "q1480_conditioned_join"
PROTOCOL = HERE / "protocol.json"
NEW_SOURCES = (
    "design_protocol.json", "build_formula.py", "verify_model.py",
    "prepare_inputs.py", "freeze_protocol.py", "run_stage.py", "audit.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def render() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    parent = json.loads((Q1482 / "protocol.json").read_text())
    assert design["proposal_id"] == "Q1483"
    assert parent["proposal_id"] == "Q1482"
    assert design["candidate_id"] is None
    assert design["isogeny"] == parent["isogeny"] == "none"
    for name in ("solver_wall_cap_seconds", "solver_conflict_cap"):
        assert design["point_decomposition"][name] == parent[{
            "solver_wall_cap_seconds": "native_wall_cap_seconds",
            "solver_conflict_cap": "conflict_cap"}[name]]
    assert design["point_decomposition"][
        "external_process_safeguard_seconds"] == parent[
            "external_safeguard_seconds"]
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    assert sha(Q1480 / "native_solver") == parent["solver_binary_sha256"]

    source = dict(parent["source_sha256"])
    prefix = "experiments/compact-s3-m4-20261003/q1483_fixed_window_s3/"
    source.update({prefix + name: sha(HERE / name)
                   for name in NEW_SOURCES})
    source["experiments/compact-s3-m4-20261003/q1482_window_s3/"
           "protocol.json"] = sha(Q1482 / "protocol.json")
    for relative, digest in source.items():
        assert sha(ROOT / relative) == digest, relative

    stages = {}
    for n in (53, 83):
        item = design["instances"][str(n)]
        original = parent["stages"][str(n)][
            "stage_config_hash_input"]
        record = json.loads(json.dumps(original))
        assert record["curve"]["curve_id"] == item["curve_id"]
        assert record["factor_base"][
            "actual_usable_points_B_before_folding"] == item[
                "actual_usable_B"]
        assert record["factor_base"]["signed_frobenius_columns"] == item[
            "folded_K"]
        assert record["factor_base"]["enumerated_set_sha256"] == item[
            "enumerated_set_sha256"]
        point = record["point_decomposition"]
        point["formula_policy"] = (
            "Q1482 cyclic-window leaf clauses plus four positive unit "
            "clauses fixing each selected window start to zero")
        point["formula_source_sha256"] = sha(HERE / "build_formula.py")
        point["fixed_window_starts"] = design["fixed_window_starts"][str(n)]
        point["restricted_orientation_slice"] = True
        digest = hashlib.sha256(canonical(record)).hexdigest()
        stages[str(n)] = {
            "stage_config_hash_input": record,
            "stage_config_sha256_full": digest,
            "stage_config_id": (
                f"PS1N{n}Ckb1fb{item['actual_usable_B']}"
                f"PDP4hybridh{digest[:12]}"),
        }

    cases = {}
    for case in design["run_order"]:
        n_text, role = case.split("_", 1)
        n = int(n_text[1:])
        item = design["instances"][str(n)]
        folder = HERE / "inputs" / case
        input_path = folder / "input.json"
        inp = json.loads(input_path.read_text())
        assert inp["proposal_id"] == "Q1483"
        assert inp["candidate_id"] is None
        assert inp["case"] == case
        assert inp["curve_id"] == item["curve_id"]
        assert inp["factor_base_actual_B"] == item["actual_usable_B"]
        assert inp["folded_columns_K"] == item["folded_K"]
        assert inp["factor_base_enumerated_set_sha256"] == item[
            "enumerated_set_sha256"]
        assert inp["design_sha256"] == sha(HERE / "design_protocol.json")
        for name, digest in inp["input_sha256"].items():
            assert sha(folder / name) == digest
        raw = gzip.decompress((folder / "system.cnf.gz").read_bytes())
        assert hashlib.sha256(raw).hexdigest() == inp[
            "cnf_raw_sha256"]
        old = parent["cases"][case]
        assert inp["input_sha256"]["targets.txt"] == old[
            "input_sha256"]["targets.txt"]
        assert inp["public_target"] == old["public_target"]
        if role == "ordinary":
            workload_id = old["workload_id"]
            assert workload_id == item["ordinary_parent_workload_id"]
            parent_workload_id = workload_id
        else:
            workload_record = {
                "curve_id": item["curve_id"],
                "public_target": inp["public_target"],
                "target_preimage_x_count": inp[
                    "target_preimage_x_count"],
                "fixture_sha256": inp["planted_fixture_sha256"],
                "input_law": role,
                "fixed_window_starts": design[
                    "fixed_window_starts"][str(n)],
                "target_count": 1,
            }
            workload_id = hashlib.sha256(canonical(workload_record))\
                .hexdigest()[:12]
            parent_workload_id = old["workload_id"]
        stage_id = stages[str(n)]["stage_config_id"]
        cases[case] = {
            "degree_n": n, "role": role,
            "curve_id": item["curve_id"],
            "factor_base_actual_B": item["actual_usable_B"],
            "folded_columns_K": item["folded_K"],
            "factor_base_enumerated_set_sha256": item[
                "enumerated_set_sha256"],
            "public_target": inp["public_target"],
            "target_preimage_x_count": inp["target_preimage_x_count"],
            "workload_id": workload_id,
            "parent_workload_id": parent_workload_id,
            "stage_config_id": stage_id,
            "stage_run_id": f"{stage_id}W{workload_id}R1",
            "input_dir": str(folder.relative_to(ROOT)),
            "input_receipt_sha256": sha(input_path),
            "input_sha256": inp["input_sha256"],
            "cnf_raw_sha256": inp["cnf_raw_sha256"],
            "cnf_variables": inp["cnf_variables"],
            "cnf_clauses": inp["cnf_clauses"],
        }
    return {
        "kind": "q1483_frozen_fixed_window_compact_s3_stage_protocol",
        "proposal_id": "Q1483", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "design_sha256": sha(HERE / "design_protocol.json"),
        "parent_q1482_protocol_sha256": sha(Q1482 / "protocol.json"),
        "stages": stages, "cases": cases,
        "run_order": design["run_order"],
        "pair_candidate_cap": parent["pair_candidate_cap"],
        "domain_pair_cap": parent["domain_pair_cap"],
        "domain_cache_cap": parent["domain_cache_cap"],
        "conflict_cap": parent["conflict_cap"],
        "native_wall_cap_seconds": parent["native_wall_cap_seconds"],
        "external_safeguard_seconds": parent[
            "external_safeguard_seconds"],
        "decision_policy": parent["decision_policy"],
        "solver_binary_sha256": parent["solver_binary_sha256"],
        "solver_compile_receipt_sha256": parent[
            "solver_compile_receipt_sha256"],
        "runtime_info_sha256": sha(runtime_path),
        "field_file_sha256": parent["field_file_sha256"],
        "source_sha256": source,
        "stop_rule": "run six frozen cells once in design order, retaining all statuses",
        "measurement_units": parent["measurement_units"],
        "measurement_scope": design["claim_scope"],
        "restricted_orientation_slice": True,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = render()
    if args.check or PROTOCOL.exists():
        assert json.loads(PROTOCOL.read_text()) == data
        print("Q1483 stage protocol verified")
    else:
        PROTOCOL.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        print("Q1483 stage protocol frozen")


if __name__ == "__main__":
    main()
