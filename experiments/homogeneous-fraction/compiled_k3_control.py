#!/usr/bin/env python3
"""Run and independently replay compiled ordinary-target collection on n=13,k=3.

The same six frozen scalar streams used by the k=2 compiled direct control are
used here. The collector derives the canonical k=2 subgroup generator so that
the target *points* match across the two base sizes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

from factor_base_yield import CURVE_ORDER_FACTORS, construct_base, digest, make_field  # noqa: E402
from math_model import GF2n  # noqa: E402
from relation_gate import (  # noqa: E402
    K as BASELINE_K,
    MODULUS,
    N,
    ORDER,
    Rank,
    mul,
    negative,
    relation_vector,
)


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_collector(executable: Path) -> int:
    executable.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter_ns()
    subprocess.run(["cc", "-O3", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-DK=3", "-o", str(executable),
                    str(HERE / "direct_collector.c")], check=True)
    return time.perf_counter_ns() - start


def relation_s4(field: GF2n, points: list[tuple[int, int]], target: tuple[int, int]) -> None:
    xs = [p[0] for p in points]
    assert field.s4(xs[0], xs[1], xs[2], target[0]) == 0


def one(executable: Path, reference: dict, control: dict, base_audit: dict,
        raw_dir: Path) -> dict:
    target_scalars = reference["targets"]
    assert reference["workload_sha256"] == control["workload_sha256"]
    assert reference["seed"] == control["seed"]
    assert reference.get("repeat", 0) == control.get("repeat", 0)
    audit_base = base_audit["factor_base"]
    original = [tuple(p) for p in audit_base["original_points"]]
    projected_points = [tuple(p) for p in audit_base["projected_nonidentity_points"]]
    representatives = [tuple(p) for p in audit_base["signed_representatives"]]
    generator = tuple(audit_base["generator"])
    assert audit_base["field_degree"] == N and audit_base["fraction_k"] == 3
    assert generator == tuple(control["base"]["generator"])
    assert len(original) == 115 and len(projected_points) == 56
    assert len(representatives) == 28

    field = GF2n(N, MODULUS)
    projected = {p: mul(field, p, 4) for p in original}
    assert sorted(set(projected.values()) - {None}) == projected_points
    signed_column = {
        p: (j, sign)
        for j, rep in enumerate(representatives)
        for p, sign in ((rep, 1), (negative(rep), -1))
    }
    assert len(signed_column) == len(projected_points)
    input_text = f"{len(target_scalars)} 8\n" + "\n".join(map(str, target_scalars)) + "\n"

    wall_start = time.perf_counter_ns()
    subprocess_start = time.perf_counter_ns()
    proc = subprocess.run([str(executable)], input=input_text, capture_output=True,
                          text=True, check=True, timeout=120)
    subprocess_wall_ns = time.perf_counter_ns() - subprocess_start
    parse_start = time.perf_counter_ns()
    lines = proc.stdout.splitlines()
    assert len(lines) > 2 and lines[0].startswith("B ") and lines[-1].startswith("T ")
    base_tokens = list(map(int, lines[0].split()[1:]))
    assert base_tokens[0] == len(original)
    assert base_tokens[1:3] == list(generator)
    c_original = list(zip(base_tokens[3::2], base_tokens[4::2]))
    assert c_original == original

    rank = Rank(len(representatives))
    attempts = []
    for line in lines[1:-1]:
        tokens = line.split()
        assert tokens[0] == "A" and len(tokens) == 15 + len(representatives)
        values = list(map(int, tokens[1:15]))
        (idx, scalar, x, y, code, candidates, repeated, other_dep,
         before, after, i, j, k, solve_ns) = values
        coefficients = list(map(int, tokens[15:]))
        assert idx == len(attempts) and scalar == target_scalars[idx]
        assert before == rank.value
        target = mul(field, generator, scalar)
        assert target == (x, y)
        relation = None
        if code == 1:
            points = [original[z] for z in (i, j, k)]
            exact = field.add(field.add(points[0], points[1]), points[2])
            assert exact == target
            relation_s4(field, points, target)
            projected_sum = field.add(
                field.add(projected[points[0]], projected[points[1]]),
                projected[points[2]])
            assert projected_sum == mul(field, target, 4)
            expected_row = relation_vector(points, projected, signed_column)
            assert tuple(coefficients) == expected_row
            novel, was_repeated = rank.add(coefficients)
            assert novel and not was_repeated and after == rank.value
            relation = {
                "points": [list(p) for p in points],
                "coefficients": coefficients,
                "projected_rhs_scalar": 4 * scalar % ORDER,
            }
        else:
            assert code in (0, 2)
            assert (i, j, k) == (-1, -1, -1)
            assert after == before
        assert (code == 0) == (candidates == 0)
        attempts.append({
            "target_index": idx,
            "target_scalar": scalar,
            "target_point": [x, y],
            "status": ("new_independent_relation" if code == 1 else
                       "dependent_relation" if code == 2 else "no_relation"),
            "rank_before": before,
            "rank_after": after,
            "relation_candidates_exactly_verified_in_C": candidates,
            "repeated_rows": repeated,
            "other_dependent_rows": other_dep,
            "relation": relation,
            "C_target_query_verify_rank_ns": solve_ns,
        })
    assert rank.value == 8 and attempts[-1]["rank_after"] == 8
    assert len(attempts) == sum(a["status"] != "no_relation" for a in attempts) + \
        sum(a["status"] == "no_relation" for a in attempts)
    total_tokens = list(map(int, lines[-1].split()[1:]))
    assert len(total_tokens) == 2
    setup_ns, c_internal_ns = total_tokens
    c_attempt_ns = sum(a["C_target_query_verify_rank_ns"] for a in attempts)
    assert c_internal_ns >= setup_ns + c_attempt_ns
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"k3_seed{reference['seed']}_repeat{reference.get('repeat', 0)}.txt"
    raw_path.write_text(proc.stdout)
    independent_replay_ns = time.perf_counter_ns() - parse_start
    total_wall_ns = time.perf_counter_ns() - wall_start
    process_and_io_ns = subprocess_wall_ns - c_internal_ns
    assert process_and_io_ns >= 0
    assert total_wall_ns >= c_internal_ns + independent_replay_ns
    counts = {
        "attempt_budget": len(target_scalars),
        "ordinary_targets_processed_until_rank8": len(attempts),
        "new_independent_verified_relations": rank.value,
        "failed_targets": sum(a["status"] == "no_relation" for a in attempts),
        "dependent_targets": sum(a["status"] == "dependent_relation" for a in attempts),
        "verified_relation_candidates": sum(a["relation_candidates_exactly_verified_in_C"]
                                             for a in attempts),
        "repeated_rows": sum(a["repeated_rows"] for a in attempts),
        "other_dependent_rows": sum(a["other_dependent_rows"] for a in attempts),
        "final_rank": rank.value,
        "effective_signed_columns": len(representatives),
        "original_fraction_points": len(original),
        "projected_nonidentity_points": len(projected_points),
        "pair_entries": len(original) * (len(original) + 1) // 2,
    }
    timing = {
        "C_base_and_pair_index_construction_ns": setup_ns,
        "C_target_query_exact_check_and_rank_ns": c_attempt_ns,
        "C_output_and_unattributed_ns": c_internal_ns - setup_ns - c_attempt_ns,
        "process_launch_input_and_external_overhead_ns": process_and_io_ns,
        "independent_python_parse_and_replay_ns": independent_replay_ns,
        "fully_charged_driver_wall_ns": total_wall_ns,
        "fully_charged_ms_per_new_independent_row": total_wall_ns / 8e6,
    }
    raw_sha = hashlib.sha256(proc.stdout.encode()).hexdigest()
    target_points = [list(mul(field, generator, scalar)) for scalar in target_scalars]
    result = {
        "schema": "homogeneous-fraction-compiled-k3-control.v1",
        "scope": "ordinary_relation_collection_screen; not a homogeneous-solver result or full IC run",
        "candidate_id": None,
        "seed": reference["seed"],
        "repeat": reference.get("repeat", 0),
        "target_distribution": "uniform nonidentity multiples of the fixed prime-subgroup generator",
        "target_stream_sha256": reference["workload_sha256"],
        "target_points_sha256": digest(target_points),
        "matched_k2_target_points": True,
        "factor_base": audit_base,
        "factor_base_sha256": base_audit["base_sha256"],
        "counts": counts,
        "timings": timing,
        "attempts": attempts,
        "C_source_sha256": source_hash(HERE / "direct_collector.c"),
        "independent_verifier_sha256": source_hash(HERE / "math_model.py"),
        "driver_source_sha256": source_hash(Path(__file__)),
        "raw_stdout_sha256": raw_sha,
        "raw_stdout_path": str(raw_path.relative_to(REPO)),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "matched_k2_control_fully_charged_ms_per_row":
            control["driver_seconds_per_new_row"] * 1000,
        "k2_control_over_k3_cost_ratio":
            control["driver_seconds_per_new_row"] * 8e9 / total_wall_ns,
        "k2_comparison_interpretation":
            "base-size/yield sensitivity only; not a solver speedup comparison",
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=HERE / "relation_gate_results.json")
    parser.add_argument("--k2-control", type=Path, default=HERE / "compiled_control_results.json")
    parser.add_argument("--base-audit", type=Path, default=HERE / "factor_base_yield_results.json")
    parser.add_argument("--executable", type=Path, default=HERE / "strict_runs" / "direct_collector_k3")
    parser.add_argument("--raw-dir", type=Path, default=HERE / "compiled_k3_raw")
    parser.add_argument("--out", type=Path, default=HERE / "compiled_k3_control_results.json")
    args = parser.parse_args()
    references = json.loads(args.reference.read_text())["runs"]
    controls = json.loads(args.k2_control.read_text())["runs"]
    base_audits = json.loads(args.base_audit.read_text())["runs"]
    base_audit = next(r for r in base_audits
                      if r["factor_base"]["field_degree"] == N
                      and r["factor_base"]["fraction_k"] == 3)
    compilation_ns = compile_collector(args.executable)
    control_map = {(r["seed"], r.get("repeat", 0)): r for r in controls}
    results = []
    for reference in references:
        key = (reference["seed"], reference.get("repeat", 0))
        result = one(args.executable, reference, control_map[key], base_audit, args.raw_dir)
        results.append(result)
        args.out.write_text(json.dumps({
            "schema": "homogeneous-fraction-compiled-k3-control-batch.v1",
            "compilation_ns_excluded": compilation_ns,
            "runs": results,
        }, indent=2) + "\n")
        print(json.dumps({
            "seed": result["seed"], "repeat": result["repeat"],
            "targets": result["counts"]["ordinary_targets_processed_until_rank8"],
            "misses": result["counts"]["failed_targets"],
            "rank": result["counts"]["final_rank"],
            "ms_per_row": result["timings"]["fully_charged_ms_per_new_independent_row"],
            "k2_over_k3": result["k2_control_over_k3_cost_ratio"],
        }), flush=True)


if __name__ == "__main__":
    main()
