#!/usr/bin/env python3
"""Run one frozen Q1467 chained-S3 point-decomposition cell."""

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
sys.path.insert(0, str(PARENT))

from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1467_density_bridge.build_inputs import base, make_case  # noqa: E402

PROTOCOL = HERE / "solver_protocol.json"
BINARY = PARENT / "q1466_leaf_rotation/native_solver"
COMPILE_RECEIPT = PARENT / "q1466_leaf_rotation/compile_receipt.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(name: str) -> None:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1467"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert name in protocol["run_order"]
    cell = protocol["cells"][name]
    folder = HERE / "inputs" / name
    output = HERE / "runs" / name
    assert not output.exists(), "refuse overwrite"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    assert sha(HERE / "protocol.json") == protocol["base_protocol_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "runtime_info_sha256"]
    assert sha(COMPILE_RECEIPT) == protocol["compile_receipt_sha256"]
    assert sha(BINARY) == protocol["binary_sha256"]
    compile_receipt = json.loads(COMPILE_RECEIPT.read_text())
    assert compile_receipt["solver_binary_sha256"] == protocol[
        "binary_sha256"]
    for leaf, digest in cell["input_sha256"].items():
        assert sha(folder / leaf) == digest, (name, leaf)
    meta = json.loads((folder / "meta.json").read_text())
    for key in ("curve_id", "degree_n", "factor_base_actual_B",
                "folded_columns_K", "factor_base_enumerated_set_sha256",
                "workload_id", "public_target", "input_role", "leaves_pinned"):
        assert meta[key] == cell[key], (name, key)
    raw = gzip.decompress((folder / "system.cnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == cell["cnf_sha256"]
    header = next(line for line in raw.splitlines() if line.startswith(b"p cnf "))
    _, _, var_count, clause_count = header.split()
    assert int(var_count) == cell["cnf_variables"]
    assert int(clause_count) == cell["cnf_clauses"]

    output.mkdir(parents=True)
    cnf = output / "system.cnf"
    model = output / "solver.model.txt"
    cnf.write_bytes(raw)
    command = [str(BINARY),
               str(PARENT / f"q1420_root_theory/n{cell['degree_n']}_field.txt"),
               str(cnf), str(folder / "variables.txt"), str(model),
               str(protocol["conflict_cap"]),
               str(protocol["wall_cap_seconds"]),
               str(folder / "targets.txt"),
               str(protocol["pair_candidate_cap"]),
               protocol["decision_policy"]]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=protocol["external_safeguard_seconds"])
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
            assert report["pair_cap"] == protocol["pair_candidate_cap"]
            assert report["cnf_variables"] == cell["cnf_variables"]
            assert report["cnf_clauses"] == cell["cnf_clauses"]
            assert report["decision_policy"] == protocol["decision_policy"]
            assert report["batch_root_inputs"] == sum(
                report["root_cache_misses"])
            for lane, logical in enumerate((
                    report["joint_pair0_root_calls"],
                    report["joint_pair1_root_calls"],
                    report["joint_final_root_calls"])):
                assert logical == (report["root_cache_hits"][lane] +
                                   report["root_cache_misses"][lane] +
                                   report["root_batch_reuses"][lane])
        except Exception as error:
            report_error = repr(error)
            report = None

    replay_start = time.perf_counter_ns()
    relation = relation_error = None
    if status == "sat":
        try:
            regenerated, varmap, targets, built_meta, variables, clauses, formula = (
                make_case(name))
            assert regenerated == raw
            assert varmap == (folder / "variables.txt").read_bytes()
            assert targets == (folder / "targets.txt").read_bytes()
            assert built_meta == meta
            instances = json.loads((PARENT /
                "q1438_dense_base/solver_protocol.json").read_text())[
                    "instances"]
            instance = dict(instances[str(cell["degree_n"])])
            instance["new_weight_bound"] = meta["normal_basis_weight_bound"]
            relation = model_relation(
                raw, formula, meta, variables, clauses, model, instance)
            if relation["status"] == "verified_four_point_relation" and (
                    cell["degree_n"] == 53):
                allowed = set(base(53)["allowed"])
                assert all(mask in allowed for mask in relation["raw_leaf_x"])
        except Exception as error:
            relation_error = repr(error)
    verified = int(relation is not None and relation.get("status") ==
                   "verified_four_point_relation")
    replay_ns = time.perf_counter_ns() - replay_start
    receipt = {
        "proposal_id": "Q1467", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "case": name, "input_role": cell["input_role"],
        "leaves_pinned": cell["leaves_pinned"],
        "curve_id": cell["curve_id"], "degree_n": cell["degree_n"],
        "factor_base_actual_B": cell["factor_base_actual_B"],
        "folded_columns_K": cell["folded_columns_K"],
        "factor_base_enumerated_set_sha256": cell[
            "factor_base_enumerated_set_sha256"],
        "public_target": cell["public_target"],
        "workload_id": cell["workload_id"],
        "cnf_sha256": cell["cnf_sha256"],
        "cnf_variables": cell["cnf_variables"],
        "cnf_clauses": cell["cnf_clauses"],
        "pair_candidate_cap": protocol["pair_candidate_cap"],
        "conflict_cap": protocol["conflict_cap"],
        "wall_cap_seconds": protocol["wall_cap_seconds"],
        "solver_status": status, "solver_exit_code": exit_code,
        "solver_report": report, "solver_report_error": report_error,
        "model_check": relation, "model_check_error": relation_error,
        "verified_relation_count": verified,
        "successful_ordinary_pdp_cost_measured": bool(
            verified and cell["input_role"] == "ordinary"),
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "solver_process_wall_ns_exploratory": wall_ns,
        "recovery_check_wall_ns_exploratory": replay_ns,
        "solver_interval": (
            "frozen materialized CNF and targets; native solver process "
            "launch through model or cap; excludes formula construction, "
            "input loading, and relation replay"),
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_before_raw": before.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "solver_model_sha256": sha(model) if model.exists() else None,
        "binary_sha256": sha(BINARY),
        "compile_receipt_sha256": sha(COMPILE_RECEIPT),
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
                      "verified_relations": verified,
                      "solver_process_wall_seconds": wall_ns / 1e9}),
          flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=(
        "n53_planted", "n83_planted", "n53_planted_unpinned",
        "n83_planted_unpinned", "n53_ordinary", "n83_ordinary"),
        required=True)
    run(parser.parse_args().case)


if __name__ == "__main__":
    main()
