#!/usr/bin/env python3
"""Replay an actual Boolean F4 derivation DAG on frozen N31 target systems.

The producer is round5/native_f4.cpp: degree-batched S-pairs, symbolic
preprocessing, and sparse matrix elimination. Its proof DAG retains the exact
input multiples and XORs used for the output basis. Replaying those operations
on a new target is a strict learned trace: it never invokes fresh reduction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRIOR = REPO / "experiments/ic-ideas-20261007"
F4_SOURCE = REPO / "experiments/groebner-perf-20260924/round5/native_f4.cpp"
sys.path.insert(0, str(PRIOR))
from sage_probes import bits, candidate_x_points, curve, field, planted_targets  # noqa: E402
from boolean_core import ANFField, evaluate  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize(poly):
    terms = set()
    for term in poly:
        if term in terms:
            terms.remove(term)
        else:
            terms.add(term)
    return sorted(terms)


def systems(arity, target_count):
    K, modulus = field(31)
    E = curve(K)
    dimension = 3
    basis, points = candidate_x_points(E, K, dimension)
    targets = planted_targets(points, arity, target_count)
    anf = ANFField(31, modulus)
    leaves = [anf.linear(list(range(i * dimension, (i + 1) * dimension)),
                         [bits(value) for value in basis]) for i in range(arity)]
    result = []
    for Q, _ in targets:
        target = anf.constant(bits(Q[0]))
        equations = (anf.s3(leaves[0], leaves[1], target) if arity == 2
                     else anf.s4(leaves[0], leaves[1], leaves[2], target))
        result.append((bits(Q[0]), [normalize(poly) for poly in equations]))
    return modulus, result


def native_f4(binary, equations, nvars, proof):
    # Shape is nvars, generators, work, proof nodes, rows, batch, proof flag.
    shape = [nvars, len(equations), 1_000_000_000, 5_000_000,
             100_000, 100_000, int(proof)]
    data = " ".join(map(str, shape)) + "\n"
    data += "\n".join(" ".join(map(str, [len(row), *row])) for row in equations) + "\n"
    start = time.perf_counter_ns()
    proc = subprocess.run([str(binary)], input=data, text=True,
                          capture_output=True, timeout=180)
    elapsed = time.perf_counter_ns() - start
    if not proc.stdout.strip():
        raise RuntimeError((proc.returncode, proc.stderr))
    output = json.loads(proc.stdout)
    output["wall_ns_exploratory"] = elapsed
    output["exit_code"] = proc.returncode
    return output


def replay(proof, equations):
    nodes = []
    for entry in proof["nodes"]:
        op, a, *rest = entry
        if op == "input":
            value = set(equations[a])
        elif op == "mul":
            value = set(normalize(term | rest[0] for term in nodes[a]))
        elif op == "xor":
            value = nodes[a] ^ nodes[rest[0]]
        else:
            raise ValueError(entry)
        nodes.append(value)
    return [sorted(nodes[i]) for i in proof["outputs"]]


def solution_set(equations, nvars):
    return [assignment for assignment in range(1 << nvars)
            if all(evaluate(poly, assignment) == 0 for poly in equations)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--targets", type=int, default=16)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    cells = []
    partial = args.output.with_suffix(".partial.json")
    for arity in (2, 3):
        modulus, cases = systems(arity, args.targets)
        first = native_f4(args.binary, cases[0][1], 3 * arity, True)
        if first["status"] != "gb":
            raise RuntimeError((arity, first))
        proof = first["proof"]
        target_rows = []
        for index, (target_x, equations) in enumerate(cases):
            start = time.perf_counter_ns()
            learned = replay(proof, equations)
            replay_ns = time.perf_counter_ns() - start
            fresh = first if index == 0 else native_f4(args.binary, equations,
                                                       3 * arity, False)
            completed = fresh["status"] == "gb"
            exact = learned == fresh["basis"] if completed else None
            # The truth table is independent of the F4 implementation.
            solutions = solution_set(equations, 3 * arity)
            learned_zero_set = solution_set(learned, 3 * arity)
            target_rows.append({"target_index": index, "target_x_bits": target_x,
                                "fresh_status": fresh["status"],
                                "fresh_reason": fresh.get("reason"),
                                "fresh_basis_count": len(fresh["basis"]) if completed else None,
                                "replay_basis_count": len(learned),
                                "exact_basis_equal": exact,
                                "solution_count": len(solutions),
                                "replay_solution_set_equal": solutions == learned_zero_set,
                                "fresh_stats": fresh.get("stats"),
                                "fresh_wall_ns_exploratory": fresh["wall_ns_exploratory"],
                                "replay_wall_ns_exploratory": replay_ns})
            partial.write_text(json.dumps({"completed_cells": cells,
                                           "current_arity": arity,
                                           "current_targets": target_rows},
                                          sort_keys=True, indent=2) + "\n")
        cells.append({"arity": arity, "boolean_variables": 3 * arity,
                      "field_modulus_bits": modulus,
                      "proof_nodes": len(proof["nodes"]),
                      "proof_output_count": len(proof["outputs"]),
                      "exact_basis_equal_count": sum(row["exact_basis_equal"] is True for row in target_rows),
                      "solution_set_equal_count": sum(row["replay_solution_set_equal"] for row in target_rows),
                      "targets": target_rows})
    receipt = {"schema_version": 1, "proposal_id": "G1", "candidate_id": None,
               "run_id": None, "target_law": "frozen planted N31 target sequence",
               "method": "Boolean F4 proof DAG replay; no fresh reductions in replay",
               "targets_per_arity": args.targets, "source_sha256": digest(Path(__file__)),
               "native_f4_source_sha256": digest(F4_SOURCE),
               "cells": cells}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"counts": [(c["arity"], c["exact_basis_equal_count"],
                                  c["solution_set_equal_count"]) for c in cells]}))


if __name__ == "__main__":
    main()
