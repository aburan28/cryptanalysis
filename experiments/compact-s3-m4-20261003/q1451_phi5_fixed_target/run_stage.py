#!/usr/bin/env python3
"""Run one frozen ordinary phi5 query with fixed target preimage zero."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from q1451_phi5_fixed_target.build_formula import build  # noqa: E402
from q1448_torsion_phi5.verify_model import model_from_file, replay  # noqa: E402
from q1449_phi5_native_xor.common import (  # noqa: E402
    blocked_assignment, sha, sha_bytes, xcnf_bytes)

PROTOCOL = HERE / "protocol.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1451"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["point_decomposition_stage_code"] == "PDP4phi5"
    assert sha(HERE / "controls.json") == protocol["controls_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    assert sha(Path(protocol["cms_binary_path"])) == protocol[
        "cms_binary_sha256"]
    for name, digest in protocol["source_sha256"].items():
        assert sha(ROOT / name) == digest, name
    for name, digest in protocol["input_sha256"].items():
        assert sha(ROOT / name) == digest, name
    cell = protocol["cells"][str(args.degree)]
    output = HERE / "runs" / f"n{args.degree}_ordinary"
    if output.exists():
        raise FileExistsError(f"refuse overwrite of {output}")

    stage_start = time.perf_counter_ns()
    build_start = stage_start
    formula, meta = build(args.degree)
    raw_initial = xcnf_bytes(formula)
    for name in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                 "factor_base_enumerated_set_sha256", "public_target"):
        assert meta[name] == cell[name], name
    assert meta["target_preimage_index"] == cell["target_preimage_index"] == 0
    assert meta["raw_target_x_values"] == [cell["selected_raw_target_x"]]
    assert meta["target_preimage_x_count"] == cell[
        "target_preimage_x_count"] == 1
    assert meta["full_target_preimage_x_count"] == cell[
        "full_target_preimage_x_count"]
    assert formula.variables == cell["xcnf_variables"]
    assert len(formula.clauses) == cell["cnf_clauses"]
    assert len(formula.xors) == cell["native_xor_rows"]
    assert len(formula.and_cache) == cell["and_gates"]
    assert sha_bytes(raw_initial) == cell["initial_xcnf_sha256"]
    assert len(raw_initial) == cell["initial_xcnf_bytes"]
    output.mkdir(parents=True)
    xcnf_path = output / "system.xcnf"
    xcnf_path.write_bytes(raw_initial)
    build_ns = time.perf_counter_ns() - build_start

    attempts = []
    solver_ns_total = 0
    check_ns_total = 0
    blocked = []
    final_status = "solver_censored"
    verified_relation = None
    for number in range(protocol["max_models"]):
        remaining = protocol["solver_wall_cap_seconds"] - solver_ns_total / 1e9
        if remaining < 1:
            break
        raw = xcnf_path.read_bytes()
        assert raw == xcnf_bytes(formula)
        seconds = max(1, math.ceil(remaining))
        command = [protocol["cms_binary_path"], "--verb", "1",
                   "--threads", "1", "--maxtime", str(seconds),
                   "--maxconfl", str(protocol["solver_conflict_cap"]),
                   "--maxmatrixcols", str(protocol["max_matrix_columns"]),
                   "--maxmatrixrows", str(protocol["max_matrix_rows"]),
                   "--maxnummatrices", str(protocol["max_matrices"]),
                   "--autodisablegauss", "0",
                   str(xcnf_path)]
        solver_start = time.perf_counter_ns()
        try:
            result = subprocess.run(
                command, capture_output=True, text=True,
                timeout=min(remaining + 5,
                            protocol["external_process_safeguard_seconds"]),
                check=False)
            stdout, stderr, code = (result.stdout, result.stderr,
                                    result.returncode)
            status = {10: "sat", 20: "unsat", 0: "censored"}.get(
                code, "error")
        except subprocess.TimeoutExpired as error:
            stdout = (error.stdout or b"").decode(errors="replace")
            stderr = (error.stderr or b"").decode(errors="replace")
            code, status = None, "external_timeout"
        solver_ns = time.perf_counter_ns() - solver_start
        solver_ns_total += solver_ns
        prefix = f"attempt_{number:03d}"
        stdout_path = output / f"{prefix}.stdout.txt"
        stderr_path = output / f"{prefix}.stderr.txt"
        model_path = output / f"{prefix}.model.txt"
        stdout_path.write_text(stdout)
        stderr_path.write_text(stderr)
        check = error_text = block = None
        if status == "sat":
            model_path.write_text(stdout)
            check_start = time.perf_counter_ns()
            try:
                check = replay(formula, meta, model_path, cell["instance"])
            except Exception as error:
                error_text = repr(error)
            check_ns_total += time.perf_counter_ns() - check_start
            if check is None:
                final_status = "model_replay_error"
            elif check["status"] == "verified_four_point_relation":
                verified_relation = check
                final_status = "verified_relation"
            else:
                model = model_from_file(model_path)
                block = blocked_assignment(formula, meta, model)
                assert block["raw_leaf_x"] == check["raw_leaf_x"]
                assert block["target_selector_choice"] == check[
                    "target_selector_choice"]
                blocked.append(block)
                xcnf_path.write_bytes(xcnf_bytes(formula))
                final_status = "invalid_model_cap"
        elif status == "unsat":
            final_status = "algebraic_unsat"
        elif status == "error":
            final_status = "solver_error"
        else:
            final_status = "solver_censored"
        matrix_match = re.search(
            r"^c \[matrix\] Using (\d+) matrices recovered from ",
            stdout, re.M)
        attempts.append({
            "number": number, "input_xcnf_sha256": sha_bytes(raw),
            "input_xcnf_bytes": len(raw),
            "input_cnf_clauses": len(formula.clauses) - int(block is not None),
            "native_xor_rows": len(formula.xors),
            "command": command, "exit_code": code,
            "solver_status": status,
            "solver_process_wall_ns_exploratory": solver_ns,
            "stdout_sha256": sha(stdout_path),
            "stderr_sha256": sha(stderr_path),
            "model_sha256": sha(model_path) if model_path.exists() else None,
            "model_check": check, "model_check_error": error_text,
            "blocked_assignment": block,
            "initial_gaussian_matrices_used": (
                int(matrix_match.group(1)) if matrix_match else None),
        })
        if final_status != "invalid_model_cap":
            break
    stage_ns = time.perf_counter_ns() - stage_start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    archive = output / "initial_system.xcnf.gz"
    archive_start = time.perf_counter_ns()
    archive.write_bytes(gzip.compress(raw_initial, mtime=0))
    archive_ns = time.perf_counter_ns() - archive_start
    xcnf_path.unlink()

    receipt = {
        "kind": "q1451_phi5_fixed_target_ordinary_stage_run",
        "proposal_id": "Q1451", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4phi5",
        "degree_n": args.degree,
        "curve_id": cell["curve_id"],
        "workload_id": cell["workload_id"],
        "factor_base_actual_B": cell["factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": cell[
            "factor_base_enumerated_set_sha256"],
        "public_target": cell["public_target"],
        "target_preimage_index": cell["target_preimage_index"],
        "selected_raw_target_x": cell["selected_raw_target_x"],
        "target_preimage_x_count": cell["target_preimage_x_count"],
        "full_target_preimage_x_count": cell[
            "full_target_preimage_x_count"],
        "status": final_status, "attempts": attempts,
        "blocked_assignments": blocked,
        "verified_relation": verified_relation,
        "verified_relation_count": int(verified_relation is not None),
        "initial_xcnf_sha256": sha_bytes(raw_initial),
        "initial_xcnf_archive_sha256": sha(archive),
        "initial_xcnf_bytes": len(raw_initial),
        "xcnf_variables": cell["xcnf_variables"],
        "cnf_clauses": cell["cnf_clauses"],
        "native_xor_rows": cell["native_xor_rows"],
        "and_gates": cell["and_gates"],
        "formula_build_wall_ns_exploratory": build_ns,
        "solver_process_wall_ns_exploratory": solver_ns_total,
        "model_replay_wall_ns_exploratory": check_ns_total,
        "target_dependent_stage_wall_ns_exploratory": stage_ns,
        "archive_wall_ns_outside_stage": archive_ns,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "cpu_isolation_receipt": None,
        "protocol_sha256": sha(PROTOCOL),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "cms_binary_sha256": sha(Path(protocol["cms_binary_path"])),
        "runner_source_sha256": sha(Path(__file__)),
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"degree_n": args.degree, "status": final_status,
                      "attempts": len(attempts),
                      "verified_relation_count": int(
                          verified_relation is not None),
                      "solver_seconds": solver_ns_total / 1e9}), flush=True)


if __name__ == "__main__":
    main()
