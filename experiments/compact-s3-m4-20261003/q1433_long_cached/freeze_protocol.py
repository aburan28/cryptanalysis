#!/usr/bin/env python3
"""Freeze longer Q1432 solver runs on the same ordinary N53/N83 targets."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1432 = PARENT / "q1432_coefficient_cache"
PROTOCOL = HERE / "protocol.json"
SOURCES = ("freeze_protocol.py", "run_stage.py", "verify_archive.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build() -> dict:
    parent_path = Q1432 / "protocol.json"
    parent = json.loads(parent_path.read_text())
    parent_verification_path = Q1432 / "verification.json"
    parent_verification = json.loads(parent_verification_path.read_text())
    assert parent["proposal_id"] == "Q1432"
    assert parent_verification["complete"] is True
    assert parent_verification["protocol_sha256"] == sha(parent_path)
    binary = Q1432 / "theory_solver"
    compile_path = Q1432 / "compile_receipt.json"
    compile_receipt = json.loads(compile_path.read_text())
    assert sha(binary) == parent["solver_binary_sha256"] == (
        compile_receipt["binary_sha256"])
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    sources = {name: sha(HERE / name) for name in SOURCES}
    workloads = {}
    for key in parent["run_order"]:
        matched = parent["workloads"][key]
        matched_receipt_path = Q1432 / "runs" / key / "receipt.json"
        matched_receipt = json.loads(matched_receipt_path.read_text())
        assert matched_receipt["stage_run_id"] == matched["stage_run_id"]
        assert matched_receipt["solver_status"] in ("sat", "censored")
        config = copy.deepcopy(matched["stage_config_hash_input"])
        pdp = config["point_decomposition"]
        pdp["termination_policy"] = (
            "CaDiCaL synchronous 300-second terminator plus "
            "five-million-conflict cap; 330-second process safeguard")
        assert pdp["solver_binary_sha256"] == parent["solver_binary_sha256"]
        full = digest(config)
        n = config["field"]["n"]
        stage = (f"PS1N{n}Ckb1fb{matched['factor_base_actual_B']}"
                 f"PDP4theoryh{full[:12]}")
        workloads[key] = {
            **{name: matched[name] for name in (
                "parent_q1420_key", "parent_q1420_stage_run_id",
                "parent_q1420_receipt_sha256", "curve_id",
                "factor_base_actual_B", "folded_columns_K",
                "factor_base_enumerated_set_sha256", "public_target",
                "input_law", "target_preimage_x_count",
                "target_input_sha256", "removed_partner_pin_units",
                "cnf_variables", "cnf_clauses", "cnf_raw_sha256",
                "cnf_raw_bytes", "workload_record", "workload_id")},
            "matched_q1432_key": key,
            "matched_q1432_stage_run_id": matched["stage_run_id"],
            "matched_q1432_receipt_sha256": sha(matched_receipt_path),
            "stage_config_hash_input": config,
            "stage_config_sha256_full": full,
            "stage_config_id": stage,
            "stage_run_id": f"{stage}W{matched['workload_id']}R1",
        }
    return {
        "kind": "q1433_frozen_long_cached_s3_solver_protocol",
        "proposal_id": "Q1433", "candidate_id": None,
        "isogeny": "none",
        "question": (
            "Can the exact Q1432 cached-span solver recover a verified "
            "ordinary four-point relation on its frozen N53 or N83 "
            "public target within a longer resource cap?"),
        "workloads": workloads,
        "run_order": parent["run_order"],
        "solver_conflict_cap": 5_000_000,
        "solver_wall_cap_seconds": 300,
        "external_process_safeguard_seconds": 330,
        "solver_binary_sha256": parent["solver_binary_sha256"],
        "q1432_protocol_sha256": sha(parent_path),
        "q1432_verification_sha256": sha(parent_verification_path),
        "q1432_compile_receipt_sha256": sha(compile_path),
        "q1432_cache_validation_sha256": sha(
            Q1432 / "cache_validation.json"),
        "sage_runtime_info_sha256": sha(runtime_path),
        "source_sha256": sources,
        "claim_boundary": (
            "The exact solver and ordinary input law are inherited from "
            "Q1432; only the per-run termination cap changes. Preserve "
            "timeouts and failures. The known-witness controls are not "
            "natural-yield measurements. Any ordinary SAT model needs "
            "independent relation verification, and one successful query "
            "does not estimate a typical useful-row rate or complete "
            "degree-131 IC work. CPU wall times are exploratory without "
            "host isolation."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(build(), sort_keys=True, indent=2) + "\n"
    if args.check:
        assert PROTOCOL.read_text() == content
    else:
        assert not PROTOCOL.exists()
        PROTOCOL.write_text(content)
    print(PROTOCOL)


if __name__ == "__main__":
    main()
