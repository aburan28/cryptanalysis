#!/usr/bin/env python3
"""Bound an n=13,k=2 homogeneous-component attempt on a frozen positive query.

A completed Macaulay matrix alone does not certify a subgroup relation. This
diagnostic keeps its rank and collection yield null until an exact lifted point
triple and projected subgroup row are independently checked.
"""

import argparse
import collections
import itertools
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

from block_fraction_solver import fraction_pair
from homogeneous_components import eliminate, tagged_rows
from relation_gate import (COFACTOR, ORDER, SEED, Rank, mul, prepare_base,
                           relation_vector)


def extract_by_exact_s4(field, original, projected, column, target, eqs,
                        deductions, width):
    """Exact fallback: search distinct block x-values, then lift all signs.

    This enumerator does not use the matrix's pivots to prune. Keep its work
    separate, so a verified fallback never masquerades as a graded-solver win.
    """
    points_by_x = collections.defaultdict(list)
    for point in original:
        points_by_x[point[0]].append(point)
    words_by_x = collections.defaultdict(list)
    for word in range(1 << width):
        a, b = fraction_pair(word, 2, field)
        if b:
            x = field.mul(a, field.inv(b))
            if x in points_by_x:
                words_by_x[x].append(word)
    tested = signed = 0
    start = time.perf_counter_ns()
    for xs in itertools.product(sorted(words_by_x), repeat=3):
        tested += 1
        if field.s4(*xs, target[0]):
            continue
        for points in itertools.product(*(points_by_x[x] for x in xs)):
            signed += 1
            if field.add(field.add(points[0], points[1]), points[2]) != target:
                continue
            words = [words_by_x[x][0] for x in xs]
            bits = sum(word << (i * width) for i, word in enumerate(words))
            def root(poly):
                return sum((mon & bits) == mon for mon in poly) % 2 == 0
            assert all(root(poly) for poly in eqs)
            assert all(root(poly) for poly in deductions)
            assert field.add(field.add(*(projected[p] for p in points[:2])),
                             projected[points[2]]) == mul(field, target, COFACTOR)
            row = relation_vector(points, projected, column)
            rank = Rank(len(column) // 2)
            novel, repeat = rank.add(row)
            assert novel and not repeat and rank.value == 1
            return {
                "points": points, "words": words, "abscissas": xs,
                "coefficients": row, "rank": rank.value,
                "boolean_equations_checked": len(eqs),
                "graded_consequences_checked": len(deductions),
                "s4_x_triples_tested": tested, "signed_triples_tested": signed,
                "fallback_extraction_ns": time.perf_counter_ns() - start,
                "attribution": "exact S4 enumerator; no graded pivot pruning",
            }
    return {"status": "no_relation", "s4_x_triples_tested": tested,
            "signed_triples_tested": signed,
            "fallback_extraction_ns": time.perf_counter_ns() - start}


def worker(target_index, seed):
    t = time.perf_counter_ns()
    field, original, projected, column, generator, base, setup_ns = prepare_base()
    import random
    rng = random.Random(seed)
    scalar = [rng.randrange(1, ORDER) for _ in range(target_index + 1)][-1]
    point = mul(field, generator, scalar)
    target_x = point[0]
    print(json.dumps({"stage": "input_ready", "target_index": target_index,
                      "target_scalar": scalar, "target_point": point,
                      "base_points": len(base["projected_points"]),
                      "base_setup_ns": setup_ns,
                      "elapsed_ns": time.perf_counter_ns() - t}), flush=True)
    begin = time.perf_counter_ns()
    _, width, eqs, groups = tagged_rows(13, 2, target_x, (4, 4, 4))
    print(json.dumps({"stage": "rows_built",
                      "row_construction_ns": time.perf_counter_ns() - begin,
                      "degree_components": len(groups),
                      "rows": sum(map(len, groups.values())),
                      "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "elapsed_ns": time.perf_counter_ns() - t}), flush=True)
    begin = time.perf_counter_ns()
    deductions, matrix = eliminate(groups, True, 4)
    print(json.dumps({"stage": "matrix_reduced",
                      "elimination_ns": time.perf_counter_ns() - begin,
                      "matrix": matrix,
                      "elapsed_ns": time.perf_counter_ns() - t,
                      "subgroup_relation": None, "independent_rank": None}), flush=True)
    witness = extract_by_exact_s4(field, original, projected, column, point,
                                  eqs, deductions, width)
    if "points" in witness:
        witness["projected_rhs_scalar"] = COFACTOR * scalar % ORDER
    print(json.dumps({"stage": "exact_fallback_extracted", "witness": witness,
                      "elapsed_ns": time.perf_counter_ns() - t}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--worker", action="store_true")
    p.add_argument("--target-index", type=int, default=16)
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--out", type=Path, default=Path("relation_probe_results.json"))
    args = p.parse_args()
    if args.worker:
        worker(args.target_index, args.seed)
        return
    command = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--target-index", str(args.target_index), "--seed", str(args.seed)]
    started = time.perf_counter()
    try:
        process = subprocess.run(command, capture_output=True, timeout=args.timeout,
                                 text=True, check=False)
        output = process.stdout
        status = "homogeneous_stage_followed_by_exact_fallback" if process.returncode == 0 else "error"
        stderr_tail = process.stderr[-1000:]
    except subprocess.TimeoutExpired as exc:
        status = "timeout"
        output = exc.stdout or b""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        stderr_tail = None
    stages = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    independent_replay = None
    independent_replay_seconds = None
    if (status == "homogeneous_stage_followed_by_exact_fallback" and stages
            and stages[-1].get("witness", {}).get("rank") == 1):
        from verify_probe import verify
        begin = time.perf_counter()
        reference = json.loads((Path(__file__).resolve().parent /
                                "relation_gate_results.json").read_text())
        independent_replay = verify({"stages": stages, "seed": args.seed,
                                     "target_index": args.target_index},
                                    reference["runs"][0]["base"])
        independent_replay_seconds = time.perf_counter() - begin
    wall = time.perf_counter() - started
    result = {
        "schema": "homogeneous-fraction-large-probe.v1",
        "status": status,
        "target_selection": (
            "selected positive diagnostic; not a natural yield estimate"
            if args.seed == SEED and args.target_index == 16 else
            "predeclared ordinary target index of frozen seed"),
        "seed": args.seed, "target_index": args.target_index,
        "timeout_seconds": args.timeout, "charged_wall_seconds": wall,
        "stages": stages, "stderr_tail": stderr_tail,
        "independent_verified_relations": (
            1 if independent_replay and independent_replay["status"] == "PASS" else
            0 if status == "homogeneous_stage_followed_by_exact_fallback"
            and stages[-1].get("witness", {}).get("status") == "no_relation" else None),
        "independent_replay": independent_replay,
        "independent_replay_seconds_charged": independent_replay_seconds,
        "seconds_per_independent_relation": None,
        "cost_ratio_to_control": None,
    }
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "charged_wall_seconds", "timeout_seconds",
                       "independent_verified_relations")}), flush=True)


if __name__ == "__main__":
    main()
