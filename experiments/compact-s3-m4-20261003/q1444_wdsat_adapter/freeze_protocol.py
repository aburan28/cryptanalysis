#!/usr/bin/env python3
"""Freeze exact Q1444 WDSat adapter inputs before bounded solver cells."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from build_wdsat import UPSTREAM
from verify_factor_xcnf import audit


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
REPO = HERE.parents[2]
CELLS = ("n53_choice_pinned", "n53_ordinary",
         "n83_choice_pinned", "n83_ordinary")
SOURCES = ("factor_xcnf.py", "verify_factor_xcnf.py", "build_wdsat.py",
           "run_cell.py", "replay_relation.py", "freeze_protocol.py",
           "validate_solver.py", "wdsat_adapter.patch")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(scratch):
    cells = {}
    builds = {}
    for n in (53, 83):
        receipt_path = scratch / f"n{n}_wdsat_build" / "build_receipt.json"
        builds[str(n)] = json.loads(receipt_path.read_text())
        assert builds[str(n)]["upstream_commit"] == UPSTREAM
        assert builds[str(n)]["patch_sha256"] == sha(HERE / "wdsat_adapter.patch")
    for cell in CELLS:
        n = int(cell[1:3])
        is_control = cell.endswith("choice_pinned")
        folder = "q1440_witness_anchor" if is_control else "q1439_fixed_leaf"
        source_relative = (f"experiments/compact-s3-m4-20261003/{folder}/"
                           f"runs/{cell}/system.xcnf.gz")
        source = REPO / source_relative
        parent = json.loads((PARENT / folder / "protocol.json").read_text())
        record = parent["cells"][cell]
        source_raw_sha = hashlib.sha256(gzip.open(source, "rb").read()).hexdigest()
        if is_control:
            assert source_raw_sha == record["formula_raw_sha256"]
        else:
            archived = json.loads((PARENT / folder / "runs" / cell /
                                   "receipt.json").read_text())
            assert source_raw_sha == archived["formula_raw_sha256"]
        converted = scratch / f"{cell}.factored.xcnf"
        verified = audit(source, converted)
        assert verified["status"] == "pass"
        control_verified = None
        if is_control:
            control_model = (PARENT / "q1439_fixed_leaf" / "runs" /
                             f"n{n}_control" / "solver.stdout.txt")
            control_verified = audit(source, converted, control_model)
            assert control_verified["archived_control_model_satisfies_both"]
        cells[cell] = {
            "degree": str(n),
            "curve_id": record["curve_id"],
            "factor_base_actual_B": record["factor_base_actual_B"],
            "folded_columns_K": record["folded_columns_K"],
            "factor_base_enumerated_set_sha256": record[
                "factor_base_enumerated_set_sha256"],
            "workload_id": record["workload_id"],
            "public_target": record["public_target"],
            "input_law": record["input_law"],
            "ordinary_query": not is_control,
            "witness_informed_control": is_control,
            "source_formula": source_relative,
            "source_gzip_sha256": sha(source),
            "source_raw_sha256": source_raw_sha,
            "source_variables": verified["source_variables"],
            "factored_sha256": sha(converted),
            "factored_variables": verified["converted_variables"],
            "audit": verified,
            "known_control_model_audit": control_verified,
        }
        assert verified["converted_variables"] <= builds[str(n)]["source_variables"]
        assert verified["xor_rows_preserved"] <= builds[str(n)]["xor_rows"]
        assert verified["converted_rows"] - verified["xor_rows_preserved"] <= builds[str(n)]["cnf_rows"]
    assert cells["n53_choice_pinned"]["curve_id"] == "EC1N53Ckb1hf77aab617904"
    assert cells["n83_choice_pinned"]["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    return {
        "proposal_id": "Q1444",
        "candidate_id": None,
        "isogeny": "none",
        "method": "sound factored-CNF adapter for WDSat on frozen compact S3 formulas",
        "claim_scope": "solver-stage diagnostic; no natural-yield or complete-work inference from censored cells",
        "wdsat_upstream_commit": UPSTREAM,
        "wdsat_patch_sha256": sha(HERE / "wdsat_adapter.patch"),
        "source_sha256": {name: sha(HERE / name) for name in SOURCES},
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "solver_validation_sha256": sha(HERE / "solver_validation.json"),
        "binaries": builds,
        "cells": cells,
        "run_order": list(CELLS),
        "wall_cap_seconds": 60,
        "solver_options": ["-i"],
        "solver_xor_gaussian_elimination": False,
        "branch_counter_checkpoint_interval": 65536,
        "cpu_isolation_receipt": None,
        "online_single_target_speedup": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = frozen(args.scratch)
    path = HERE / "protocol.json"
    if args.check:
        assert json.loads(path.read_text()) == expected
        print("Q1444 frozen protocol: PASS")
    else:
        assert not path.exists(), "refuse to overwrite protocol"
        path.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
        print(path)
