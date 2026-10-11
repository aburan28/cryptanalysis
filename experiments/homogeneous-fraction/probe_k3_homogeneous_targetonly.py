#!/usr/bin/env python3
"""One-target n=13 probe using packed homogeneous degree-one row reduction."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from block_fraction_solver import MODULI, equations, search  # noqa: E402
from homogeneous_bitset import MonomialDegreeOrder, degree_one_layer  # noqa: E402
from math_model import FastGF2n, GF2n  # noqa: E402
from probe_k3_homogeneous import verify_witness  # noqa: E402
from relation_gate import ORDER, mul  # noqa: E402


def emit(record: dict) -> None:
    print(json.dumps(record, separators=(",", ":")), flush=True)


def worker(target_point: list[int], deduction_degree: int) -> None:
    started = time.perf_counter_ns()
    n, k, width = 13, 3, 8
    field = FastGF2n(n, MODULI[n])
    target = tuple(target_point)
    emit({"stage": "input_ready", "n": n, "k": k,
          "target_point": target_point, "target_x": target[0],
          "homogeneous_base_degree": [4, 4, 4],
          "elapsed_ns": time.perf_counter_ns() - started})

    begin = time.perf_counter_ns()
    eqs = equations(field, k, target[0])
    equation_build_ns = time.perf_counter_ns() - begin
    emit({"stage": "equations_built", "equation_build_ns": equation_build_ns,
          "equation_count": len(eqs), "equation_terms": sum(map(len, eqs)),
          "peak_rss_kib": __import__("resource").getrusage(
              __import__("resource").RUSAGE_SELF).ru_maxrss,
          "elapsed_ns": time.perf_counter_ns() - started})

    order = MonomialDegreeOrder(3 * width, HERE / "monomial_degree_order.c")
    emit({"stage": "graded_monomial_order_ready",
          "compile_seconds": order.compile_seconds,
          "initialize_seconds": order.initialize_seconds,
          "elapsed_ns": time.perf_counter_ns() - started})

    begin = time.perf_counter_ns()
    deductions, matrix = degree_one_layer(
        eqs[:n], width, (4, 4, 4), deduction_degree=deduction_degree,
        degree_order=order)
    matrix_ns = time.perf_counter_ns() - begin
    emit({"stage": "homogeneous_blocks_reduced", "matrix_ns": matrix_ns,
          "matrix": matrix, "deduction_count": len(deductions),
          "elapsed_ns": time.perf_counter_ns() - started,
          "peak_rss_kib": __import__("resource").getrusage(
              __import__("resource").RUSAGE_SELF).ru_maxrss})

    begin = time.perf_counter_ns()
    outcome = search(eqs, deductions, field, width, k, target[0])
    search_ns = time.perf_counter_ns() - begin
    witness = outcome.pop("witness")
    if witness:
        witness["homogeneous_deduction_count"] = len(deductions)
        witness["homogeneous_deduction_sha256"] = hashlib.sha256(
            json.dumps(sorted([sorted(poly) for poly in deductions]),
                       separators=(",", ":")).encode()).hexdigest()
    emit({"stage": "signed_points_extracted", "status": outcome["status"],
          "witness": witness, "search": outcome, "search_ns": search_ns,
          "elapsed_ns": time.perf_counter_ns() - started,
          "peak_rss_kib": __import__("resource").getrusage(
              __import__("resource").RUSAGE_SELF).ru_maxrss})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--seed", type=int, default=20260927)
    parser.add_argument("--target-index", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--deduction-degree", type=int, default=4)
    parser.add_argument("--out", type=Path,
                        default=HERE / "k3_homogeneous_targetonly_results.json")
    parser.add_argument("--raw-dir", type=Path,
                        default=HERE / "k3_homogeneous_targetonly_raw")
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.raw_dir = args.raw_dir.resolve()
    if args.worker:
        raw_target = json.loads(sys.stdin.readline())
        worker(raw_target["point"], args.deduction_degree)
        return

    references = json.loads((HERE / "relation_gate_results.json").read_text())["runs"]
    controls = json.loads((HERE / "compiled_k3_control_results.json").read_text())["runs"]
    base_audit = json.loads((HERE / "factor_base_yield_results.json").read_text())["runs"]
    base_row = next(r for r in base_audit if r["factor_base"]["field_degree"] == 13
                    and r["factor_base"]["fraction_k"] == 3)
    base = base_row["factor_base"]
    reference = next(r for r in references if r["seed"] == args.seed)
    control = next(r for r in controls if r["seed"] == args.seed and r["repeat"] == 0)
    scalar = reference["targets"][args.target_index]
    target = control["attempts"][args.target_index]["target_point"]
    assert target == list(mul(GF2n(13, MODULI[13]), tuple(base["generator"]), scalar))
    # The solver process receives only the ordinary target point. The fixture
    # scalar is retained by the parent for the RHS label and replay only.
    target_input = json.dumps({"point": target}) + "\n"
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--deduction-degree", str(args.deduction_degree)]

    begin = time.perf_counter_ns()
    try:
        process = subprocess.run(command, input=target_input, capture_output=True,
                                 text=True, timeout=args.timeout, check=False)
        raw_output = process.stdout
        process_wall_ns = time.perf_counter_ns() - begin
        status = "complete" if process.returncode == 0 else "error"
        stderr = process.stderr[-2000:]
    except subprocess.TimeoutExpired as exc:
        process_wall_ns = time.perf_counter_ns() - begin
        status = "timeout"
        raw_output = exc.stdout or ""
        if isinstance(raw_output, bytes):
            raw_output = raw_output.decode(errors="replace")
        stderr = None

    stages = [json.loads(line) for line in raw_output.splitlines() if line.startswith("{")]
    raw_path = args.raw_dir / f"seed{args.seed}_target{args.target_index}.jsonl"
    paired_baseline = [r["timings"]["fully_charged_ms_per_new_independent_row"]
                       for r in controls if r["seed"] == args.seed]
    assert paired_baseline
    result = {
        "schema": "homogeneous-fraction-k3-homogeneous-targetonly-probe.v1",
        "scope": "one ordinary target; degree-one multihomogeneous layer, packed GF(2) elimination and signed-point extraction",
        "solver_input_fields": ["target_point"],
        "candidate_id": None,
        "seed": args.seed, "target_index": args.target_index,
        "target_scalar": scalar, "target_point": target,
        "target_stream_sha256": reference["workload_sha256"],
        "factor_base_sha256": base_row["base_sha256"],
        "matched_compiled_k3_control_median_ms_per_row": statistics.median(paired_baseline),
        "timeout_seconds_per_target": args.timeout,
        "degree_profile": "(4,4,4) plus (5,4,4), (4,5,4), (4,4,5)",
        "matrix_input_equations": "target S4 coordinate equations only",
        "denominator_constraints": "retained in exact Boolean search and independent replay",
        "deduction_degree": args.deduction_degree,
        "status": status, "process_wall_ns": process_wall_ns,
        "independent_verified_relations": 0,
        "stages": stages, "stderr_tail": stderr,
        "raw_stdout_sha256": hashlib.sha256(raw_output.encode()).hexdigest(),
        "raw_stdout_path": str(raw_path.relative_to(REPO)),
        "worker_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "homogeneous_source_sha256": hashlib.sha256(
            (HERE / "homogeneous_bitset.py").read_bytes()).hexdigest(),
        "monomial_order_source_sha256": hashlib.sha256(
            (HERE / "monomial_degree_order.c").read_bytes()).hexdigest(),
        "field_source_sha256": hashlib.sha256((HERE / "math_model.py").read_bytes()).hexdigest(),
    }
    if status == "complete" and stages and stages[-1].get("witness"):
        verify_start = time.perf_counter_ns()
        replay_record = copy.deepcopy(result)
        replay_record["stages"][-1]["witness"]["projected_rhs_scalar"] = (
            4 * scalar % ORDER)
        result["independent_replay"] = verify_witness(replay_record, reference, base)
        result["independent_replay_ns"] = time.perf_counter_ns() - verify_start
        result["independent_verified_relations"] = 1
    parse_replay_ns = time.perf_counter_ns() - begin - process_wall_ns
    total_wall_ns = process_wall_ns + parse_replay_ns
    result["parse_and_independent_replay_ns"] = parse_replay_ns
    result["charged_wall_ns_including_process_and_input"] = total_wall_ns
    result["charged_wall_seconds"] = total_wall_ns / 1e9
    result["seconds_per_independent_relation"] = (
        total_wall_ns / 1e9 if result["independent_verified_relations"] else None)
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw_output)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result.get(key) for key in
                      ("status", "charged_wall_seconds", "independent_verified_relations",
                       "raw_stdout_path")}), flush=True)


if __name__ == "__main__":
    main()
