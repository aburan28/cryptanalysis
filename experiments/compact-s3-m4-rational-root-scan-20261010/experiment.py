#!/usr/bin/env python3
"""Freeze, execute, and audit matched rational-orbit S3 root scans."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-quadratic-root-scan-20261010"
BASE = ROOT / "experiments/compact-s3-m4-20261003"
PROPOSAL = "Q20261010120000"
DEGREES = (53, 83)
KINDS = ("control", "ordinary")
WINDOWS = (4096, 16384)
BINARY = HERE / "target/release/compact_s3_rational_root_scan"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cell_name(n: int, kind: str, window: int) -> str:
    return f"n{n}_{kind}_w{window}"


def write_json(path: Path, value: dict) -> None:
    assert not path.exists(), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def freeze() -> None:
    assert BINARY.is_file(), "build the release binary before freezing"
    assert not (HERE / "freeze.json").exists()
    binary_hash = sha(BINARY)
    source_hash = sha(HERE / "scan.rs")
    inputs = {}
    for n in DEGREES:
        for kind in KINDS:
            for window in WINDOWS:
                cell = cell_name(n, kind, window)
                parent_path = PARENT / "inputs" / f"{cell}.json"
                parent = json.loads(parent_path.read_text())
                assert parent["proposal_id"] == "Q20261010111900"
                assert parent["scan_mask_cap"] == sum(
                    math.comb(n, k) for k in range(1, parent[
                        "normal_basis_weight_bound"] + 1))
                child = dict(parent)
                child.update({"schema": "q20261010120000-matched-input-v1",
                              "proposal_id": PROPOSAL,
                              "native_source_sha256": source_hash,
                              "binary_sha256": binary_hash,
                              "parent_input_sha256": sha(parent_path)})
                child_path = HERE / "inputs" / f"{cell}.json"
                write_json(child_path, child)
                inputs[cell] = {
                    "input_sha256": sha(child_path),
                    "parent_input_sha256": sha(parent_path),
                    "parent_scan_sha256": sha(PARENT / "runs" /
                                               f"{cell}.scan.json"),
                }
    frozen = {
        "schema": "q20261010120000-freeze-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "source_sha256": source_hash, "binary_sha256": binary_hash,
        "cargo_manifest_sha256": sha(HERE / "Cargo.toml"),
        "cargo_lock_sha256": sha(HERE / "Cargo.lock"),
        "experiment_source_sha256": sha(HERE / "experiment.py"),
        "protocol_sha256": sha(HERE / "PROTOCOL.md"),
        "crypto_semaev_source_sha256": sha(
            Path("/Volumes/SSD990/crypto/src/cryptanalysis/semaev_decomp.rs")),
        "n131_base_sha256": sha(BASE / "runs/n131_q1413_projected_x_w6.json"),
        "n131_query_bound_sha256": sha(
            BASE / "runs/n131_q1414_exact_uniform_query_bound.json"),
        "inputs": inputs,
        "caps": {"per_cell_scan_seconds": 120,
                 "per_cell_process_seconds": 180,
                 "per_cell_peak_rss_mib": 512,
                 "workers": 1},
        "required_decisions": {
            "control": "same complete pair set as matched predecessor",
            "ordinary": "same complete pair set as matched predecessor"},
    }
    write_json(HERE / "freeze.json", frozen)
    print(json.dumps({"status": "FROZEN", "cells": len(inputs),
                      "freeze_sha256": sha(HERE / "freeze.json")}))


def check_freeze() -> dict:
    frozen = json.loads((HERE / "freeze.json").read_text())
    assert frozen["source_sha256"] == sha(HERE / "scan.rs")
    assert frozen["binary_sha256"] == sha(BINARY)
    assert frozen["cargo_manifest_sha256"] == sha(HERE / "Cargo.toml")
    assert frozen["cargo_lock_sha256"] == sha(HERE / "Cargo.lock")
    assert frozen["experiment_source_sha256"] == sha(HERE / "experiment.py")
    assert frozen["protocol_sha256"] == sha(HERE / "PROTOCOL.md")
    for cell, hashes in frozen["inputs"].items():
        assert hashes["input_sha256"] == sha(HERE / "inputs" / f"{cell}.json")
        assert hashes["parent_scan_sha256"] == sha(
            PARENT / "runs" / f"{cell}.scan.json")
    return frozen


def prepare() -> None:
    frozen = check_freeze()
    for n in DEGREES:
        cell = cell_name(n, "control", 4096)
        input_path = HERE / "inputs" / f"{cell}.json"
        bridge_path = BASE / "field_bridges" / f"n{n}_onb_poly.json"
        representatives = HERE / "census" / f"n{n}_representatives.bin"
        output_path = HERE / "census" / f"n{n}.json"
        receipt_path = HERE / "census" / f"n{n}.receipt.json"
        assert not representatives.exists() and not output_path.exists()
        assert not receipt_path.exists()
        representatives.parent.mkdir(parents=True, exist_ok=True)
        command = [str(BINARY), "prepare", str(input_path), str(bridge_path),
                   str(representatives), str(output_path)]
        start = time.perf_counter_ns()
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=frozen["caps"]["per_cell_process_seconds"])
            status = "EXITED" if completed.returncode == 0 else "PRODUCER_FAILURE"
            code = completed.returncode
            stdout, stderr = completed.stdout, completed.stderr
        except subprocess.TimeoutExpired as exc:
            status, code = "BOUNDED_UNKNOWN", None
            stdout = (exc.stdout or b"").decode(errors="replace")
            stderr = (exc.stderr or b"").decode(errors="replace")
        receipt = {"schema": "q20261010120000-census-receipt-v1",
                   "proposal_id": PROPOSAL, "field_degree": n,
                   "status": status, "exit_code": code,
                   "elapsed_ns": str(time.perf_counter_ns() - start),
                   "stdout": stdout, "stderr": stderr,
                   "representatives_sha256": (
                       sha(representatives) if representatives.exists() else None),
                   "output_sha256": sha(output_path) if output_path.exists() else None,
                   "input_sha256": sha(input_path),
                   "binary_sha256": frozen["binary_sha256"],
                   "freeze_sha256": sha(HERE / "freeze.json")}
        write_json(receipt_path, receipt)
        print(json.dumps({"n": n, "status": status,
                          "elapsed_seconds": int(receipt["elapsed_ns"])/1e9,
                          "output": stdout.strip()}), flush=True)
        if status != "EXITED":
            raise RuntimeError(f"N{n} census: {status}: {stderr[-500:]}")


def check_census(n: int) -> dict:
    path = HERE / "census" / f"n{n}_representatives.bin"
    output = HERE / "census" / f"n{n}.json"
    receipt = json.loads((HERE / "census" / f"n{n}.receipt.json").read_text())
    assert receipt["status"] == "EXITED" and receipt["exit_code"] == 0
    assert receipt["representatives_sha256"] == sha(path)
    assert receipt["output_sha256"] == sha(output)
    result = json.loads(output.read_text())
    assert result["proposal_id"] == PROPOSAL
    assert result["rational_raw_x_orbits"] * n == result["rational_raw_x_masks"]
    return receipt


def run() -> None:
    frozen = check_freeze()
    for cell in frozen["inputs"]:
        input_path = HERE / "inputs" / f"{cell}.json"
        n = json.loads(input_path.read_text())["field_degree"]
        census = check_census(n)
        output_path = HERE / "runs" / f"{cell}.scan.json"
        receipt_path = HERE / "runs" / f"{cell}.receipt.json"
        assert not output_path.exists() and not receipt_path.exists()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [str(BINARY), "scan", str(input_path),
                   str(BASE / "field_bridges" / f"n{n}_onb_poly.json"),
                   str(HERE / "census" / f"n{n}_representatives.bin"),
                   str(output_path)]
        start = time.perf_counter_ns()
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=frozen["caps"]["per_cell_process_seconds"])
            status = "EXITED" if completed.returncode == 0 else "PRODUCER_FAILURE"
            code = completed.returncode
            stdout, stderr = completed.stdout, completed.stderr
        except subprocess.TimeoutExpired as exc:
            status, code = "BOUNDED_UNKNOWN", None
            stdout = (exc.stdout or b"").decode(errors="replace")
            stderr = (exc.stderr or b"").decode(errors="replace")
        receipt = {"schema": "q20261010120000-run-receipt-v1",
                   "proposal_id": PROPOSAL, "cell": cell, "status": status,
                   "exit_code": code, "elapsed_ns": str(time.perf_counter_ns()-start),
                   "stdout": stdout, "stderr": stderr,
                   "input_sha256": sha(input_path),
                   "census_sha256": census["representatives_sha256"],
                   "output_sha256": sha(output_path) if output_path.exists() else None,
                   "binary_sha256": frozen["binary_sha256"],
                   "freeze_sha256": sha(HERE / "freeze.json")}
        write_json(receipt_path, receipt)
        print(json.dumps({"cell": cell, "status": status,
                          "elapsed_seconds": int(receipt["elapsed_ns"])/1e9,
                          "output": stdout.strip()}), flush=True)
        if status != "EXITED":
            raise RuntimeError(f"{cell}: {status}: {stderr[-500:]}")


def audit() -> dict:
    frozen = check_freeze()
    rows = []
    for cell, hashes in frozen["inputs"].items():
        inp = json.loads((HERE / "inputs" / f"{cell}.json").read_text())
        census = check_census(inp["field_degree"])
        census_result = json.loads((HERE / "census" /
                                    f"n{inp['field_degree']}.json").read_text())
        new_path = HERE / "runs" / f"{cell}.scan.json"
        row = json.loads(new_path.read_text())
        old = json.loads((PARENT / "runs" / f"{cell}.scan.json").read_text())
        receipt = json.loads((HERE / "runs" / f"{cell}.receipt.json").read_text())
        assert receipt["status"] == "EXITED" and receipt["exit_code"] == 0
        assert receipt["output_sha256"] == sha(new_path)
        assert receipt["census_sha256"] == census["representatives_sha256"]
        assert hashes["parent_scan_sha256"] == sha(
            PARENT / "runs" / f"{cell}.scan.json")
        assert row["proposal_id"] == PROPOSAL
        assert row["curve_id"] == old["curve_id"] == inp["curve_id"]
        assert row["workload_id"] == old["workload_id"] == inp["workload_id"]
        assert row["factor_base_actual_B"] == old["factor_base_actual_B"]
        assert row["rational_raw_x_masks"] * 2 == inp["factor_base_actual_B"]
        assert row["rational_raw_x_masks"] == census_result["rational_raw_x_masks"]
        assert row["rational_raw_x_orbits"] == census_result["rational_raw_x_orbits"]
        assert row["scanned_masks"] == row["rational_raw_x_masks"]
        assert row["status"] == old["status"]
        assert row["unique_unordered_weight_pairs"] == old[
            "unique_unordered_weight_pairs"]
        def pair_set(value):
            return {tuple(sorted((hit["left_cycle_mask_decimal"],
                                  hit["right_cycle_mask_decimal"])))
                    for hit in value["recorded_hits"]}
        assert pair_set(row) == pair_set(old)
        rows.append({"cell": cell, "curve_id": row["curve_id"],
                     "workload_id": row["workload_id"],
                     "status": row["status"],
                     "baseline_root_calls": old["operation_counts"]["scan"][
                         "s3_root_calls"],
                     "root_calls": row["operation_counts"]["scan"][
                         "s3_root_calls"],
                     "baseline_field_mul": old["operation_counts"]["scan"][
                         "field_mul_calls"],
                     "field_mul": row["operation_counts"]["scan"][
                         "field_mul_calls"],
                     "census_field_inv": census_result["operation_counts"][
                         "field_inv_calls"],
                     "baseline_scan_ns": int(old["timing_ns"]["scan"]),
                     "scan_ns": int(row["timing_ns"]["scan"]),
                     "census_ns": int(census_result["elapsed_ns"]),
                     "expand_ns": int(row["timing_ns"]["rational_mask_expand"]),
                     "peak_rss_bytes": row["peak_rss_bytes"],
                     "pairs": row["unique_unordered_weight_pairs"]})
    return {"schema": "q20261010120000-audit-v1",
            "proposal_id": PROPOSAL, "freeze_sha256": sha(HERE/"freeze.json"),
            "rows": rows, "status": "PASS"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "prepare", "run", "audit"))
    mode = parser.parse_args().mode
    if mode == "freeze": freeze()
    elif mode == "prepare": prepare()
    elif mode == "run": run()
    else:
        result = audit()
        write_json(HERE / "audit.json", result)
        print(json.dumps({"status": result["status"],
                          "cells": len(result["rows"])}))


if __name__ == "__main__":
    main()
