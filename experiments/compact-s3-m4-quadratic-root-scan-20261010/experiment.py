#!/usr/bin/env python3
"""Freeze and execute the Q20261010111900 native fixed-output scan grid."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-fixed-output-20261010"
OLD = ROOT / "experiments/compact-s3-m4-20261003"
BASELINE = ROOT / "experiments/compact-s3-m4-fixed-output-root-scan-20261010"
SOURCES = ("scan.rs", "Cargo.toml", "Cargo.lock", "build.py",
           "experiment.py", "verify.py", "replay_sage.py", "analysis.py",
           "PROTOCOL.md")
WINDOWS = (4096, 16384)
DEGREES = (53, 83)
KINDS = ("control", "ordinary")
WALL_CAP_SECONDS = 120
PEAK_RSS_CAP_MIB = 512
MAX_RECORDED_HITS = 16


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), path
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def xor_images(mask: int, images: list[int]) -> int:
    result = 0
    while mask:
        bit = mask & -mask
        result ^= int(images[bit.bit_length() - 1])
        mask ^= bit
    return result


def cell_name(n: int, kind: str, window: int) -> str:
    assert n in DEGREES and kind in KINDS and window in WINDOWS
    return f"n{n}_{kind}_w{window}"


def parent_paths(n: int, kind: str) -> tuple[Path, Path]:
    return (PARENT / "freeze.json",
            PARENT / f"n{n}_{kind}_fixed_factored.json")


def build_input(n: int, kind: str, window: int,
                build: dict, parent: dict) -> tuple[dict, dict]:
    frozen_path, receipt_path = parent_paths(n, kind)
    source = parent["cases"][str(n)]
    selected = source["selected"][kind]["branch"]
    receipt = json.loads(receipt_path.read_text())
    bridge_path = OLD / "field_bridges" / f"n{n}_onb_poly.json"
    bridge = json.loads(bridge_path.read_text())
    output_onb = int(selected["right_output_x"])
    output_poly = xor_images(output_onb,
                             bridge["onb_to_poly_basis_images"])
    assert bridge["field_degree"] == n
    assert source["curve_id"] == bridge["curve_id"] == receipt["curve_id"]
    assert output_onb == receipt["right_output_x"]
    assert source["B"] == receipt["factor_base_actual_B"]
    assert source["K"] == receipt["factor_base_folded_columns_K"]
    assert source["base_digest"] == receipt[
        "factor_base_enumerated_set_sha256"]
    assert xor_images(output_poly,
                      bridge["poly_to_onb_basis_images"]) == output_onb
    weight = source["normal_basis_weight_bound"]
    masks = sum(math.comb(n, k) for k in range(1, weight + 1))
    workload = {
        "schema": "q20261010103500-workload-v1",
        "curve_id": source["curve_id"],
        "target_group": "exact_frozen_parent_subgroup",
        "public_target": receipt["public_target"],
        "input_law": receipt["input_law"],
        "source_receipt_sha256": sha(receipt_path),
        "selected_anchor": receipt["selected_anchor"],
        "selected_branch": selected,
        "fixed_output_onb_decimal": str(output_onb),
        "target_generation_seed": None,
        "target_generation_record": "frozen_parent_receipt",
        "cold_or_warm_target_count": 1,
    }
    workload_id = hashlib.sha256(compact(workload)).hexdigest()[:12]
    row = {
        "schema": "q20261010111900-fixed-output-input-v1",
        "proposal_id": "Q20261010111900",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "field_degree": n, "curve_id": source["curve_id"],
        "kind": kind, "workload_id": workload_id,
        "parent_workload_id": receipt["workload_id"],
        "input_law": receipt["input_law"],
        "public_target": receipt["public_target"],
        "selected_anchor": receipt["selected_anchor"],
        "selected_branch": selected,
        "right_output_x_onb_decimal": str(output_onb),
        "right_output_x_poly_decimal": str(output_poly),
        "normal_basis_weight_bound": weight,
        "polynomial_low_terms": bridge["target_implementation_basis"]["low_terms"],
        "factor_base_actual_B": source["B"],
        "factor_base_folded_columns_K": source["K"],
        "factor_base_enumerated_set_sha256": source["base_digest"],
        "scan_mask_cap": masks,
        "scan_window_size": window,
        "scan_wall_cap_seconds": WALL_CAP_SECONDS,
        "peak_rss_cap_mib": PEAK_RSS_CAP_MIB,
        "max_recorded_hits": MAX_RECORDED_HITS,
        "parent_freeze_sha256": sha(frozen_path),
        "parent_receipt_sha256": sha(receipt_path),
        "bridge_sha256": sha(bridge_path),
        "binary_sha256": build["binary_sha256"],
        "native_source_sha256": build["source_sha256"],
    }
    return row, workload


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    build = json.loads((HERE / "build_receipt.json").read_text())
    assert build["status"] == "PASS"
    assert build["source_sha256"] == sha(HERE / "scan.rs")
    assert build["binary_sha256"] == sha(Path(build["binary_path"]))
    parent = json.loads((PARENT / "freeze.json").read_text())
    assert parent["proposal_id"] == "Q1429"
    inputs: dict[str, str] = {}
    workloads: dict[str, dict] = {}
    baseline_scans: dict[str, str] = {}
    baseline_receipts: dict[str, str] = {}
    for n in DEGREES:
        for kind in KINDS:
            for window in WINDOWS:
                name = cell_name(n, kind, window)
                row, workload = build_input(n, kind, window, build, parent)
                path = HERE / "inputs" / f"{name}.json"
                baseline_input = json.loads((BASELINE / "inputs" /
                                            f"{name}.json").read_text())
                for key in ("curve_id", "kind", "workload_id", "public_target",
                            "selected_anchor", "selected_branch",
                            "right_output_x_poly_decimal",
                            "factor_base_actual_B",
                            "factor_base_folded_columns_K",
                            "factor_base_enumerated_set_sha256",
                            "scan_mask_cap", "scan_window_size"):
                    assert row[key] == baseline_input[key], (name, key)
                write_json(path, row)
                inputs[name] = sha(path)
                workloads[name] = workload
                baseline_scans[name] = sha(BASELINE / "runs" /
                                           f"{name}.scan.json")
                baseline_receipts[name] = sha(BASELINE / "runs" /
                                              f"{name}.receipt.json")
    frozen = {
        "schema": "q20261010111900-freeze-v1",
        "proposal_id": "Q20261010111900",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "source_sha256": {name: sha(HERE / name) for name in SOURCES},
        "build_receipt_sha256": sha(HERE / "build_receipt.json"),
        "parent_freeze_sha256": sha(PARENT / "freeze.json"),
        "matched_baseline_freeze_sha256": sha(BASELINE / "freeze.json"),
        "matched_baseline_scan_sha256": baseline_scans,
        "matched_baseline_receipt_sha256": baseline_receipts,
        "bridge_sha256": {str(n): sha(OLD / "field_bridges" /
                                       f"n{n}_onb_poly.json") for n in DEGREES},
        "input_sha256": inputs,
        "workload_records": workloads,
        "limits": {"native_scan_wall_seconds": WALL_CAP_SECONDS,
                   "native_peak_rss_mib": PEAK_RSS_CAP_MIB,
                   "max_recorded_hits": MAX_RECORDED_HITS},
    }
    write_json(HERE / "freeze.json", frozen)
    print(json.dumps({"freeze_sha256": sha(HERE / "freeze.json"),
                      "cells": len(inputs)}))


def check_freeze() -> dict:
    frozen = json.loads((HERE / "freeze.json").read_text())
    assert frozen["schema"] == "q20261010111900-freeze-v1"
    assert frozen["source_sha256"] == {
        name: sha(HERE / name) for name in SOURCES}
    assert frozen["build_receipt_sha256"] == sha(HERE / "build_receipt.json")
    assert frozen["parent_freeze_sha256"] == sha(PARENT / "freeze.json")
    assert frozen["matched_baseline_freeze_sha256"] == sha(
        BASELINE / "freeze.json")
    build = json.loads((HERE / "build_receipt.json").read_text())
    binary = Path(build["binary_path"])
    if binary.is_file():
        assert build["binary_sha256"] == sha(binary)
    parent = json.loads((PARENT / "freeze.json").read_text())
    for n in DEGREES:
        bridge = OLD / "field_bridges" / f"n{n}_onb_poly.json"
        assert frozen["bridge_sha256"][str(n)] == sha(bridge)
        for kind in KINDS:
            for window in WINDOWS:
                name = cell_name(n, kind, window)
                path = HERE / "inputs" / f"{name}.json"
                expected, workload = build_input(n, kind, window,
                                                 build, parent)
                assert json.loads(path.read_text()) == expected
                assert frozen["input_sha256"][name] == sha(path)
                assert frozen["workload_records"][name] == workload
                assert frozen["matched_baseline_scan_sha256"][name] == sha(
                    BASELINE / "runs" / f"{name}.scan.json")
                assert frozen["matched_baseline_receipt_sha256"][name] == sha(
                    BASELINE / "runs" / f"{name}.receipt.json")
    return frozen


def run_case(n: int, kind: str, window: int) -> None:
    check_freeze()
    name = cell_name(n, kind, window)
    input_path = HERE / "inputs" / f"{name}.json"
    bridge = OLD / "field_bridges" / f"n{n}_onb_poly.json"
    result_path = HERE / "runs" / f"{name}.scan.json"
    receipt_path = HERE / "runs" / f"{name}.receipt.json"
    assert not result_path.exists() and not receipt_path.exists()
    result_path.parent.mkdir(exist_ok=True)
    build = json.loads((HERE / "build_receipt.json").read_text())
    assert sha(Path(build["binary_path"])) == build["binary_sha256"]
    command = [build["binary_path"], str(input_path), str(bridge),
               str(result_path)]
    started = time.perf_counter_ns()
    try:
        completed = subprocess.run(command, capture_output=True,
                                   text=True, timeout=WALL_CAP_SECONDS + 15,
                                   check=False)
        exit_code = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
        producer_status = "PASS" if exit_code == 0 else "PRODUCER_FAILURE"
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = (exc.stdout or b"").decode(errors="replace")
        stderr = (exc.stderr or b"").decode(errors="replace")
        producer_status = "PRODUCER_TIMEOUT"
    elapsed = time.perf_counter_ns() - started
    result = json.loads(result_path.read_text()) if result_path.exists() else None
    receipt = {
        "schema": "q20261010111900-run-receipt-v1",
        "proposal_id": "Q20261010111900",
        "candidate_id": None, "run_id": None,
        "cell": name,
        "curve_id": json.loads(input_path.read_text())["curve_id"],
        "workload_id": json.loads(input_path.read_text())["workload_id"],
        "input_sha256": sha(input_path),
        "bridge_sha256": sha(bridge),
        "freeze_sha256": sha(HERE / "freeze.json"),
        "binary_sha256": build["binary_sha256"],
        "command": command,
        "producer_status": producer_status,
        "exit_code": exit_code,
        "process_wall_ns": str(elapsed),
        "stdout": stdout, "stderr": stderr,
        "result_sha256": sha(result_path) if result is not None else None,
        "scan_status": result["status"] if result is not None else None,
    }
    write_json(receipt_path, receipt)
    print(json.dumps({"cell": name, "producer_status": producer_status,
                      "scan_status": receipt["scan_status"],
                      "process_wall_seconds": elapsed / 1e9}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run", "all"))
    parser.add_argument("--degree", type=int, choices=DEGREES)
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--window", type=int, choices=WINDOWS)
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    elif args.action == "check":
        check_freeze()
        print(json.dumps({"status": "PASS", "freeze_sha256":
                          sha(HERE / "freeze.json")}))
    elif args.action == "run":
        assert args.degree and args.kind and args.window
        run_case(args.degree, args.kind, args.window)
    else:
        for n in DEGREES:
            for kind in KINDS:
                for window in WINDOWS:
                    run_case(n, kind, window)


if __name__ == "__main__":
    main()
