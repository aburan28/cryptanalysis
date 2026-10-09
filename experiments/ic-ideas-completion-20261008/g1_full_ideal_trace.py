#!/usr/bin/env python3
"""Replay rank-increasing Boolean ideal multiples across N31 target systems.

For six or nine Boolean variables the complete function ring has dimension
2^v.  The ideal of an equation system has dimension 2^v minus its exact
solution count.  That gives an independent stopping certificate for streamed
Macaulay multiples and for a learned subset of useful multiples.  This is a
complete finite-ring linear-algebra trace, not a production F4 trace.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-20261007"
sys.path.insert(0, str(PRIOR))
from boolean_core import ANFField, evaluate  # noqa: E402
from sage_probes import bits, candidate_x_points, curve, field, planted_targets  # noqa: E402


def multiply_row(poly, monomial: int) -> int:
    result = 0
    for term in poly:
        result ^= 1 << (term | monomial)
    return result


def insert(row: int, pivots: dict[int, int]) -> bool:
    while row:
        lead = row.bit_length()-1
        prior = pivots.get(lead)
        if prior is None:
            pivots[lead] = row
            return True
        row ^= prior
    return False


def solutions(equations, nvars):
    return [assignment for assignment in range(1 << nvars)
            if all(evaluate(poly, assignment) == 0 for poly in equations)]


def run_cell(K, modulus, E, arity: int, target_count: int):
    dimension = 3
    basis, points = candidate_x_points(E, K, dimension)
    targets = planted_targets(points, arity, target_count)
    anf = ANFField(31, modulus)
    leaves = [anf.linear(list(range(i*dimension, (i+1)*dimension)),
                         [bits(value) for value in basis])
              for i in range(arity)]
    nvars = arity*dimension
    sources = sorted(itertools.product(range(31), range(1 << nvars)),
                     key=lambda pair: (pair[1].bit_count(), pair[0], pair[1]))
    learned_sources = None
    cells = []
    for Q, _ in targets:
        target = anf.constant(bits(Q[0]))
        equations = (anf.s3(leaves[0], leaves[1], target) if arity == 2
                     else anf.s4(leaves[0], leaves[1], leaves[2], target))
        exact_solutions = solutions(equations, nvars)
        assert exact_solutions
        needed_rank = (1 << nvars)-len(exact_solutions)
        if learned_sources is not None:
            start = time.perf_counter_ns()
            learned_pivots = {}
            for i, multiplier in learned_sources:
                insert(multiply_row(equations[i], multiplier), learned_pivots)
            learned_ns = time.perf_counter_ns()-start
            learned_rank = len(learned_pivots)
        else:
            learned_ns = None
            learned_rank = None
        start = time.perf_counter_ns()
        pivots = {}
        useful = []
        attempts = 0
        for i, multiplier in sources:
            attempts += 1
            if insert(multiply_row(equations[i], multiplier), pivots):
                useful.append((i, multiplier))
                if len(pivots) == needed_rank:
                    break
        fresh_ns = time.perf_counter_ns()-start
        assert len(pivots) == needed_rank
        if learned_sources is None:
            learned_sources = useful
            learned_rank = needed_rank
            learned_ns = None
        # Every replayed row is an ideal multiple, so matching full rank is a
        # certificate that its span equals the whole finite Boolean ideal.
        passed = learned_rank == needed_rank
        cells.append({"target_x_bits": bits(Q[0]),
                      "solution_count": len(exact_solutions),
                      "full_ideal_dimension": needed_rank,
                      "fresh_source_attempts": attempts,
                      "fresh_useful_sources": len(useful),
                      "learned_source_count": len(learned_sources),
                      "learned_rank": learned_rank,
                      "learned_spans_full_ideal": passed,
                      "fresh_stream_ns_exploratory": fresh_ns,
                      "learned_stream_ns_exploratory": learned_ns})
    return {"arity": arity, "boolean_variables": nvars,
            "target_count": len(targets),
            "all_replays_span_complete_ideal": all(c["learned_spans_full_ideal"]
                                                    for c in cells),
            "learned_sources": learned_sources,
            "cells": cells}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--targets", type=int, default=16)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    K, modulus = field(31)
    E = curve(K)
    cells = [run_cell(K, modulus, E, arity, args.targets)
             for arity in (2, 3)]
    result = {"schema_version": 1, "proposal_id": "G1",
              "candidate_id": None, "run_id": None,
              "field_degree": 31, "field_modulus_bits": modulus,
              "cells": cells,
              "scope": "exact finite Boolean ideal rank trace on planted N31 targets; production F4 trace and natural-query solve speed remain unmeasured",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "prior_sources_sha256": {
                  name: hashlib.sha256((PRIOR / name).read_bytes()).hexdigest()
                  for name in ("boolean_core.py", "sage_probes.py")}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"cells": [
        {"arity": c["arity"], "all_pass": c["all_replays_span_complete_ideal"],
         "learned_sources": len(c["learned_sources"])} for c in cells]},
        sort_keys=True))


if __name__ == "__main__":
    main()
