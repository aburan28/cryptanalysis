#!/usr/bin/env python3
"""Run one frozen Q1465 wide batched-root solver cell."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1455 = PARENT / "q1455_joint_tail"
Q1458 = PARENT / "q1458_batch_roots"
Q1464 = PARENT / "q1464_joint_cap250k"
BINARY = HERE / "native_solver"
sys.path.insert(0, str(PARENT))

from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1455_joint_tail.native_inputs import make_case  # noqa: E402

PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(name: str) -> None:
    protocol = json.loads(PROTOCOL.read_text())
    cell = protocol["cells"][name]
    output = HERE / "runs" / name
    assert not output.exists(), "refuse overwrite"
    assert protocol["proposal_id"] == "Q1465"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert name in protocol["run_order"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["input_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    binary = BINARY
    assert sha(binary) == protocol["binary_sha256"]
    assert sha(Q1464 / "runs" / name / "receipt.json") == cell[
        "baseline_q1464_receipt_sha256"]
    parent_run = Q1455 / "runs" / name
    parent_receipt = json.loads((parent_run / "receipt.json").read_text())
    assert parent_receipt["workload_id"] == cell["workload_id"]
    assert sha(parent_run / "receipt.json") == cell[
        "parent_receipt_sha256"]
    assert sha(Q1458 / "runs" / name / "receipt.json") == cell[
        "baseline_q1458_receipt_sha256"]
    assert sha(parent_run / "system.cnf.gz") == cell[
        "parent_cnf_archive_sha256"]
    assert sha(parent_run / "variables.txt") == cell[
        "variable_map_sha256"]
    assert sha(parent_run / "targets.txt") == cell["targets_sha256"]
    raw = gzip.decompress((parent_run / "system.cnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == cell["cnf_sha256"]

    output.mkdir(parents=True)
    cnf = output / "system.cnf"
    model = output / "solver.model.txt"
    cnf.write_bytes(raw)
    command = [str(binary),
               str(PARENT / f"q1420_root_theory/n{cell['degree_n']}_field.txt"),
               str(cnf), str(parent_run / "variables.txt"), str(model),
               str(cell["conflict_cap"]), str(cell["wall_cap_seconds"]),
               str(parent_run / "targets.txt"),
               str(cell["pair_candidate_cap"]),
               "joint_tail_leaf_interleave"]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=cell["external_safeguard_seconds"])
        stdout, stderr = completed.stdout, completed.stderr
        exit_code = completed.returncode
        status = {0: "sat", 10: "censored", 20: "unsat"}.get(
            exit_code, "error")
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        exit_code, status = None, "external_timeout"
    wall_ns = time.perf_counter_ns() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path = output / "solver.stdout.txt"
    stderr_path = output / "solver.stderr.txt"
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    cnf.unlink()
    report = report_error = None
    if stdout.strip():
        try:
            report = json.loads(stdout)
            assert report["status"] == {"sat": 10, "censored": 0,
                                         "unsat": 20}[status]
            assert report["pair_cap"] == cell["pair_candidate_cap"]
            assert report["cnf_variables"] == cell["cnf_variables"]
            assert report["cnf_clauses"] == cell["cnf_clauses"]
            assert report["decision_policy"] == "joint_tail_leaf_interleave"
            assert report["batch_root_inputs"] == sum(
                report["root_cache_misses"])
            for lane, logical in enumerate((
                    report["joint_pair0_root_calls"],
                    report["joint_pair1_root_calls"],
                    report["joint_final_root_calls"])):
                assert logical == (report["root_cache_hits"][lane] +
                                   report["root_cache_misses"][lane] +
                                   report["root_batch_reuses"][lane])
            assert report["root_cache_entries"] <= report[
                "root_cache_entry_cap"]
            assert report["batch_inverse_batches"] <= report[
                "batch_denominators"]
        except Exception as error:
            report_error = repr(error)
            report = None
    replay_start = time.perf_counter_ns()
    relation = relation_error = None
    if status == "sat":
        try:
            original, _, _, formula, meta, variables, clauses = make_case(name)
            assert original == raw
            parent = json.loads((PARENT /
                "q1438_dense_base/solver_protocol.json").read_text())
            relation = model_relation(
                raw, formula, meta, variables, clauses, model,
                parent["instances"][str(cell["degree_n"])])
        except Exception as error:
            relation_error = repr(error)
    verified = int(relation is not None and relation.get("status") ==
                   "verified_four_point_relation")
    replay_ns = time.perf_counter_ns() - replay_start
    receipt = {
        "proposal_id": "Q1465", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "case": name, "input_role": cell["input_role"],
        "degree_n": cell["degree_n"],
        "curve_id": cell["curve_id"],
        "factor_base_actual_B": cell["factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": cell[
            "factor_base_enumerated_set_sha256"],
        "normal_basis_weight_bound": cell["normal_basis_weight_bound"],
        "public_target": cell["public_target"],
        "workload_id": cell["workload_id"],
        "cnf_sha256": cell["cnf_sha256"],
        "cnf_variables": cell["cnf_variables"],
        "cnf_clauses": cell["cnf_clauses"],
        "pair_candidate_cap": cell["pair_candidate_cap"],
        "conflict_cap": cell["conflict_cap"],
        "wall_cap_seconds": cell["wall_cap_seconds"],
        "solver_status": status, "solver_exit_code": exit_code,
        "solver_report": report, "solver_report_error": report_error,
        "model_check": relation, "model_check_error": relation_error,
        "verified_relation_count": verified,
        "successful_ordinary_pdp_cost_measured": bool(
            verified and cell["input_role"] == "ordinary_full_target"),
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "solver_process_wall_ns_exploratory": wall_ns,
        "recovery_check_wall_ns_exploratory": replay_ns,
        "solver_interval": (
            "reuses frozen materialized CNF and target list; from native "
            "solver launch through first model or cap, excludes formula "
            "construction, input loading, and relation replay"),
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "solver_model_sha256": sha(model) if model.exists() else None,
        "binary_sha256": sha(binary),
        "parent_receipt_sha256": sha(parent_run / "receipt.json"),
        "baseline_q1458_receipt_sha256": sha(Q1458 / "runs" / name /
                                              "receipt.json"),
        "baseline_q1464_receipt_sha256": sha(Q1464 / "runs" / name /
                                              "receipt.json"),
        "protocol_sha256": sha(PROTOCOL),
        "runner_source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"case": name, "status": status,
                      "joint_checks": (report or {}).get(
                          "joint_eligible_checks"),
                      "joint_rejections": (report or {}).get(
                          "joint_no_chain_rejections"),
                      "verified_relations": verified,
                      "solver_process_wall_seconds": wall_ns / 1e9}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("n53_known_sat_unpinned",
                                          "n53_ordinary", "n83_ordinary"),
                        required=True)
    run(parser.parse_args().case)


if __name__ == "__main__":
    main()
