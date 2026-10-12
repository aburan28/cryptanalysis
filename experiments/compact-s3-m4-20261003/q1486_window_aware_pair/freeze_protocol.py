#!/usr/bin/env python3
"""Freeze Q1486 exact-window stages on byte-identical Q1482 CNFs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent
Q1482 = PARENT / "q1482_window_s3"
Q1485 = PARENT / "q1485_coupled_domains"
PROTOCOL = HERE / "protocol.json"
OWN_SOURCES = (
    "design_protocol.json", "native_solver.cpp", "build.py",
    "prepare_window_maps.py", "validate_window_completion.py",
    "freeze_protocol.py", "run_stage.py", "audit.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def render() -> dict:
    design = json.loads((HERE / "design_protocol.json").read_text())
    parent = json.loads((Q1482 / "protocol.json").read_text())
    compile_receipt = json.loads((HERE / "compile_receipt.json").read_text())
    validation = json.loads((HERE / "window_validation.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert design["proposal_id"] == "Q1486"
    assert parent["proposal_id"] == "Q1482"
    assert compile_receipt["proposal_id"] == "Q1486"
    assert compile_receipt["solver_binary_sha256"] == sha(
        HERE / "native_solver")
    assert validation["status"] == "passed"
    assert validation["runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    assert runtime["status"] == "verified"
    assert design["run_order"] == parent["run_order"]
    assert design["point_decomposition"]["solver_wall_cap_seconds"] == (
        parent["native_wall_cap_seconds"])
    assert design["point_decomposition"][
        "external_process_safeguard_seconds"] == parent[
            "external_safeguard_seconds"]
    assert design["point_decomposition"]["solver_conflict_cap"] == parent[
        "conflict_cap"]

    source = dict(parent["source_sha256"])
    prefix = "experiments/compact-s3-m4-20261003/q1486_window_aware_pair/"
    source.update({prefix + name: sha(HERE / name) for name in OWN_SOURCES})
    source["experiments/compact-s3-m4-20261003/q1482_window_s3/"
           "protocol.json"] = sha(Q1482 / "protocol.json")
    source["experiments/compact-s3-m4-20261003/q1485_coupled_domains/"
           "protocol.json"] = sha(Q1485 / "protocol.json")
    for relative, digest in source.items():
        assert sha(ROOT / relative) == digest, relative

    stages = {}
    for n in (53, 83):
        instance = design["instances"][str(n)]
        record = copy.deepcopy(parent["stages"][str(n)][
            "stage_config_hash_input"])
        assert record["curve"]["curve_id"] == instance["curve_id"]
        base = record["factor_base"]
        assert base["actual_usable_points_B_before_folding"] == instance[
            "actual_usable_B"]
        assert base["signed_frobenius_columns"] == instance["folded_K"]
        assert base["enumerated_set_sha256"] == instance[
            "enumerated_set_sha256"]
        map_cases = [case for case in design["run_order"]
                     if case.startswith(f"n{n}_")]
        map_digests = {sha(HERE / "inputs" / case / "windows.map")
                       for case in map_cases}
        assert len(map_digests) == 1
        window_map_digest = next(iter(map_digests))
        pdp = record["point_decomposition"]
        pdp.update({
            "solver": "Q1486 native SAT plus exact cyclic-window S3 domains",
            "solver_source_sha256": sha(HERE / "native_solver.cpp"),
            "solver_binary_sha256": sha(HERE / "native_solver"),
            "decision_policy": "target_exact_window_pair_domain_intersection",
            "theory_delta": design["point_decomposition"]["theory_delta"],
            "window_selector_sidecar_sha256": window_map_digest,
            "window_selector_sidecar_source_sha256": sha(HERE /
                "prepare_window_maps.py"),
            "coupled_left_pair_cap": design["point_decomposition"][
                "left_pair_domain_cap"],
            "coupled_right_pair_cap": design["point_decomposition"][
                "right_pair_domain_cap"],
            "coupled_cache_cap": 64,
            "small_field_validation_sha256": sha(HERE /
                                                 "window_validation.json"),
        })
        digest = hashlib.sha256(canonical(record)).hexdigest()
        stages[str(n)] = {
            "stage_config_hash_input": record,
            "stage_config_sha256_full": digest,
            "stage_config_id": (
                f"PS1N{n}Ckb1fb{instance['actual_usable_B']}"
                f"PDP4hybridh{digest[:12]}"),
        }

    cases = {}
    for case in design["run_order"]:
        inherited = copy.deepcopy(parent["cases"][case])
        n = inherited["degree_n"]
        stage_id = stages[str(n)]["stage_config_id"]
        inherited["stage_config_id"] = stage_id
        inherited["stage_run_id"] = (
            f"{stage_id}W{inherited['workload_id']}R1")
        map_dir = HERE / "inputs" / case
        sidecar = map_dir / "windows.map"
        sidecar_receipt = map_dir / "map_receipt.json"
        map_record = json.loads(sidecar_receipt.read_text())
        assert map_record["proposal_id"] == "Q1486"
        assert map_record["case"] == case
        assert map_record["q1482_cnf_raw_sha256"] == inherited[
            "cnf_raw_sha256"]
        assert map_record["q1482_target_sha256"] == inherited[
            "input_sha256"]["targets.txt"]
        assert map_record["sidecar_map_sha256"] == sha(sidecar)
        assert map_record["source_sha256"] == sha(HERE /
                                                  "prepare_window_maps.py")
        inherited["window_sidecar_dir"] = str(map_dir.relative_to(ROOT))
        inherited["window_sidecar_sha256"] = sha(sidecar)
        inherited["window_sidecar_receipt_sha256"] = sha(sidecar_receipt)
        cases[case] = inherited
    return {
        "kind": "q1486_frozen_exact_window_domain_stage_protocol",
        "proposal_id": "Q1486", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "design_sha256": sha(HERE / "design_protocol.json"),
        "parent_q1482_protocol_sha256": sha(Q1482 / "protocol.json"),
        "comparator_q1485_protocol_sha256": sha(Q1485 / "protocol.json"),
        "solver_compile_receipt_sha256": sha(HERE / "compile_receipt.json"),
        "small_field_validation_sha256": sha(HERE /
                                              "window_validation.json"),
        "solver_binary_sha256": sha(HERE / "native_solver"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "source_sha256": source,
        "stages": stages, "cases": cases,
        "run_order": design["run_order"],
        "pair_candidate_cap": design["point_decomposition"][
            "final_conditioned_pair_cap"],
        "domain_pair_cap": design["point_decomposition"][
            "left_pair_domain_cap"],
        "domain_cache_cap": parent["domain_cache_cap"],
        "coupled_pair_cap": design["point_decomposition"][
            "right_pair_domain_cap"],
        "coupled_cache_cap": 64,
        "conflict_cap": design["point_decomposition"][
            "solver_conflict_cap"],
        "native_wall_cap_seconds": design["point_decomposition"][
            "solver_wall_cap_seconds"],
        "external_safeguard_seconds": design["point_decomposition"][
            "external_process_safeguard_seconds"],
        "decision_policy": "target_exact_window_pair_domain_intersection",
        "field_file_sha256": parent["field_file_sha256"],
        "stop_rule": "run six inherited frozen Q1482 cells once in design order",
        "claim_limit": "stage-only diagnostics; complete N131 work and challenge gate unknown",
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = render()
    if args.check:
        assert json.loads(PROTOCOL.read_text()) == current
    else:
        assert not PROTOCOL.exists(), "refuse overwrite"
        PROTOCOL.write_text(json.dumps(current, indent=2, sort_keys=True) +
                            "\n")
    print(json.dumps({"proposal_id": "Q1486",
                      "stage_ids": {n: item["stage_config_id"]
                                    for n, item in current["stages"].items()},
                      "status": "checked" if args.check else "frozen"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
