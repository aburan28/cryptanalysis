#!/usr/bin/env python3
"""Bounded homogeneous-block solve and exact signed-point extraction on n=13,k=3."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from block_fraction_solver import MODULI, equations, fraction_pair, search  # noqa: E402
from homogeneous_components import eliminate, tagged_rows  # noqa: E402
from math_model import FastGF2n, GF2n  # noqa: E402
from relation_gate import ORDER, Rank, mul, negative, relation_vector  # noqa: E402


def emit(record: dict) -> None:
    print(json.dumps(record, separators=(",", ":")), flush=True)


def worker(target_scalar: int, target_point: list[int], deduction_degree: int,
           cap: tuple[int, int, int], max_multiplier_degree: int) -> None:
    started = time.perf_counter_ns()
    n, k = 13, 3
    field = FastGF2n(n, MODULI[n])
    target = tuple(target_point)
    emit({"stage": "input_ready", "n": n, "k": k, "scalar": target_scalar,
          "target_point": target_point, "target_x": target[0], "cap": cap,
          "elapsed_ns": time.perf_counter_ns() - started})

    begin = time.perf_counter_ns()
    eqs = equations(field, k, target[0])
    equation_build_ns = time.perf_counter_ns() - begin
    emit({"stage": "equations_built", "equation_build_ns": equation_build_ns,
          "equation_count": len(eqs), "equation_terms": sum(map(len, eqs)),
          "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          "elapsed_ns": time.perf_counter_ns() - started})

    begin = time.perf_counter_ns()
    _, width, eqs, groups = tagged_rows(
        n, k, target[0], cap, field=field, include_denominators=False,
        max_multiplier_degree=max_multiplier_degree, validate_rows=False,
        equations_override=eqs)
    row_build_ns = time.perf_counter_ns() - begin
    emit({"stage": "rows_built", "row_construction_ns": row_build_ns,
          "equation_count": len(eqs),
          "degree_components": len(groups), "rows": sum(map(len, groups.values())),
          "max_multiplier_degree": max_multiplier_degree,
          "component_rows": [[list(d), len(rows)] for d, rows in sorted(groups.items())],
          "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          "elapsed_ns": time.perf_counter_ns() - started})

    begin = time.perf_counter_ns()
    deductions, matrix = eliminate(groups, True, deduction_degree,
                                   canonical_row_order=False)
    eliminate_ns = time.perf_counter_ns() - begin
    emit({"stage": "homogeneous_blocks_reduced", "elimination_ns": eliminate_ns,
          "matrix": matrix, "deduction_count": len(deductions),
          "deduction_sha256": matrix["derived_sha256"],
          "elapsed_ns": time.perf_counter_ns() - started,
          "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})

    begin = time.perf_counter_ns()
    outcome = search(eqs, deductions, field, width, k, target[0])
    search_ns = time.perf_counter_ns() - begin
    witness = outcome.pop("witness")
    if witness:
        witness["projected_rhs_scalar"] = 4 * target_scalar % ORDER
        witness["homogeneous_deduction_count"] = len(deductions)
        witness["homogeneous_deduction_sha256"] = matrix["derived_sha256"]
    emit({"stage": "signed_points_extracted", "status": outcome["status"],
          "witness": witness, "search": outcome, "search_ns": search_ns,
          "elapsed_ns": time.perf_counter_ns() - started,
          "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})


def verify_witness(record: dict, reference: dict, base: dict) -> dict:
    field = GF2n(13, MODULI[13])
    target = tuple(record["target_point"])
    assert mul(field, tuple(base["generator"]), record["target_scalar"]) == target
    witness = record["stages"][-1]["witness"]
    assert witness and record["stages"][-1]["status"] == "verified"
    width, k = 2 * (3 + 1), 3
    words = witness["words"]
    assert len(words) == 3
    bits = sum(word << (i * width) for i, word in enumerate(words))
    eqs = equations(field, k, target[0])
    assert all(sum((mon & bits) == mon for mon in poly) % 2 == 0 for poly in eqs)
    abscissae = []
    for word in words:
        numerator, denominator = fraction_pair(word, k, field)
        assert denominator != 0
        abscissae.append(field.mul(numerator, field.inv(denominator)))
    assert abscissae == witness["abscissas"]
    points = [tuple(p) for p in witness["points"]]
    original = {tuple(p) for p in base["original_points"]}
    assert all(point in original for point in points)
    assert [p[0] for p in points] == abscissae
    assert field.add(field.add(points[0], points[1]), points[2]) == target
    assert field.s4(*(p[0] for p in points), target[0]) == 0
    projected = {p: mul(field, p, 4) for p in original}
    projected_sum = field.add(
        field.add(projected[points[0]], projected[points[1]]), projected[points[2]])
    assert projected_sum == mul(field, target, 4)
    reps = [tuple(p) for p in base["signed_representatives"]]
    column = {p: (j, sign) for j, rep in enumerate(reps)
              for p, sign in ((rep, 1), (negative(rep), -1))}
    row = relation_vector(points, projected, column)
    assert any(row) and list(row) == witness["coefficients"]
    rank = Rank(len(reps))
    novel, repeated = rank.add(row)
    assert novel and not repeated and rank.value == 1
    assert witness["rank"] == rank.value
    assert witness["projected_rhs_scalar"] == 4 * record["target_scalar"] % ORDER
    return {"status": "PASS", "curve_sum": list(target),
            "s4_zero": True, "subgroup_projected_sum": True,
            "signed_row": list(row), "independent_rank": 1,
            "independent_implementation": "pure-Python GF(2^13) and exact curve arithmetic"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--seed", type=int, default=20260927)
    parser.add_argument("--target-index", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--deduction-degree", type=int, choices=(2, 3, 4), default=4)
    parser.add_argument("--cap", nargs=3, type=int, default=(5, 5, 5))
    parser.add_argument("--max-multiplier-degree", type=int, default=1)
    parser.add_argument("--out", type=Path,
                        default=HERE / "k3_homogeneous_degree1_results.json")
    parser.add_argument("--raw-dir", type=Path,
                        default=HERE / "k3_homogeneous_degree1_raw")
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.raw_dir = args.raw_dir.resolve()
    if args.worker:
        raw_target = json.loads(sys.stdin.readline())
        worker(raw_target["scalar"], raw_target["point"], args.deduction_degree,
               tuple(raw_target["cap"]), raw_target["max_multiplier_degree"])
        return

    references = json.loads((HERE / "relation_gate_results.json").read_text())["runs"]
    controls = json.loads((HERE / "compiled_k3_control_results.json").read_text())["runs"]
    base_audit = json.loads((HERE / "factor_base_yield_results.json").read_text())["runs"]
    base_row = next(r for r in base_audit if r["factor_base"]["field_degree"] == 13
                    and r["factor_base"]["fraction_k"] == 3)
    base = base_row["factor_base"]
    reference = next(r for r in references if r["seed"] == args.seed)
    control = next(r for r in controls if r["seed"] == args.seed
                   and r["repeat"] == 0)
    scalar = reference["targets"][args.target_index]
    target = control["attempts"][args.target_index]["target_point"]
    assert target == list(mul(GF2n(13, MODULI[13]), tuple(base["generator"]), scalar))
    target_input = json.dumps({"scalar": scalar, "point": target,
                               "cap": args.cap,
                               "max_multiplier_degree": args.max_multiplier_degree}) + "\n"
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--deduction-degree", str(args.deduction_degree),
               "--cap", *map(str, args.cap),
               "--max-multiplier-degree", str(args.max_multiplier_degree)]
    begin = time.perf_counter_ns()
    try:
        process = subprocess.run(command, input=target_input, capture_output=True,
                                 text=True, timeout=args.timeout, check=False)
        raw_output = process.stdout
        process_wall_ns = time.perf_counter_ns() - begin
        status = ("complete" if process.returncode == 0 else "error")
        stderr = process.stderr[-2000:]
    except subprocess.TimeoutExpired as exc:
        process_wall_ns = time.perf_counter_ns() - begin
        status = "timeout"
        raw_output = exc.stdout or ""
        if isinstance(raw_output, bytes):
            raw_output = raw_output.decode(errors="replace")
        stderr = None
    parse_start = time.perf_counter_ns()
    stages = [json.loads(line) for line in raw_output.splitlines() if line.startswith("{")]
    raw_path = args.raw_dir / f"seed{args.seed}_target{args.target_index}.jsonl"
    controls = json.loads((HERE / "compiled_k3_control_results.json").read_text())["runs"]
    paired_baseline = [r["timings"]["fully_charged_ms_per_new_independent_row"]
                       for r in controls if r["seed"] == args.seed]
    assert paired_baseline
    result = {
        "schema": "homogeneous-fraction-k3-homogeneous-probe.v2",
        "scope": "one ordinary target; degree-one multihomogeneous Macaulay layer with signed-point extraction",
        "candidate_id": None,
        "seed": args.seed, "target_index": args.target_index,
        "target_scalar": scalar, "target_point": target,
        "target_stream_sha256": reference["workload_sha256"],
        "factor_base_sha256": base_row["base_sha256"],
        "matched_compiled_k3_control_median_ms_per_row": statistics.median(paired_baseline),
        "timeout_seconds_per_target": args.timeout,
        "cap": list(args.cap), "max_multiplier_degree": args.max_multiplier_degree,
        "matrix_input_equations": "target S4 coordinates only",
        "denominator_constraints": "retained in exact Boolean search and independent replay",
        "deduction_degree": args.deduction_degree,
        "status": status, "process_wall_ns": process_wall_ns,
        "independent_verified_relations": 0,
        "stages": stages, "stderr_tail": stderr,
        "raw_stdout_sha256": hashlib.sha256(raw_output.encode()).hexdigest(),
        "raw_stdout_path": str(raw_path.relative_to(REPO)),
        "worker_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "field_source_sha256": hashlib.sha256((HERE / "math_model.py").read_bytes()).hexdigest(),
        "homogeneous_source_sha256": hashlib.sha256(
            (HERE / "homogeneous_components.py").read_bytes()).hexdigest(),
    }
    if status == "complete" and stages and stages[-1].get("witness"):
        verify_start = time.perf_counter_ns()
        result["independent_replay"] = verify_witness(result, reference, base)
        result["independent_replay_ns"] = time.perf_counter_ns() - verify_start
        result["independent_verified_relations"] = 1
    parse_replay_ns = time.perf_counter_ns() - parse_start
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
