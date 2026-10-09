#!/usr/bin/env python3
"""Check adaptive F4 symbolic preprocessing on frozen N31 target systems."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-solver-gates-20261008"
sys.path.insert(0, str(PRIOR))
from g1_f4_trace import replay, solution_set, systems  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def solve(binary: Path, equations: list[list[int]], nvars: int,
          trace: list[list[list[int]]] | None = None) -> dict:
    shape = [nvars, len(equations), 1_000_000_000, 5_000_000,
             100_000, 100_000, 1, int(trace is not None)]
    words = [*shape]
    for row in equations:
        words.extend([len(row), *row])
    if trace is not None:
        words.append(len(trace))
        for matrix in trace:
            words.append(len(matrix))
            for reducer, multiplier in matrix:
                words.extend([reducer, multiplier])
    data = " ".join(map(str, words)) + "\n"
    start = time.perf_counter_ns()
    process = subprocess.run([str(binary)], input=data, text=True,
                             capture_output=True, timeout=180)
    result = json.loads(process.stdout)
    result["wall_ns_exploratory"] = time.perf_counter_ns() - start
    result["exit_code"] = process.returncode
    return result


def main() -> None:
    output = HERE / "g1_adaptive.json"
    if output.exists():
        raise FileExistsError(output)
    adaptive = HERE / "native_f4_adaptive"
    control = HERE / "native_f4_symbolic_control"
    cells = []
    for arity in (2, 3):
        modulus, cases = systems(arity, 16)
        learned = solve(adaptive, cases[0][1], 3 * arity)
        assert learned["status"] == "gb"
        trace = learned["symbolic_trace"]
        rows = []
        for index, (target_x, equations) in enumerate(cases):
            # Alternate order to reduce one-sided drift in exploratory timings.
            if index % 2:
                attempt = solve(adaptive, equations, 3 * arity, trace)
                fresh = solve(control, equations, 3 * arity)
            else:
                fresh = solve(control, equations, 3 * arity)
                attempt = solve(adaptive, equations, 3 * arity, trace)
            completed = fresh["status"] == attempt["status"] == "gb"
            exact = completed and fresh["basis"] == attempt["basis"]
            proof = completed and replay(attempt["proof"], equations) == attempt["basis"]
            truth = completed and solution_set(equations, 3 * arity) == solution_set(
                attempt["basis"], 3 * arity)
            rows.append({"target_index": index, "target_x_bits": target_x,
                         "fresh_status": fresh["status"],
                         "adaptive_status": attempt["status"],
                         "basis_equal": exact, "proof_replays": proof,
                         "truth_set_equal": truth,
                         "fresh_stats": fresh.get("stats"),
                         "adaptive_stats": attempt.get("stats"),
                         "fresh_wall_ns_exploratory": fresh["wall_ns_exploratory"],
                         "adaptive_wall_ns_exploratory": attempt["wall_ns_exploratory"]})
        cells.append({"arity": arity, "field_modulus_bits": modulus,
                      "learned_matrices": len(trace),
                      "learned_multiples": sum(map(len, trace)),
                      "targets": rows})
    answer = {"schema_version": 1, "proposal_id": "G1",
              "candidate_id": None, "run_id": None,
              "method": "adaptive symbolic trace followed by complete fresh coverage",
              "source_sha256": sha(Path(__file__)),
              "adaptive_source_sha256": sha(HERE / "native_f4_adaptive.cpp"),
              "control_source_sha256": sha(PRIOR / "native_f4_symbolic.cpp"),
              "adaptive_binary_sha256": sha(adaptive),
              "control_binary_sha256": sha(control), "cells": cells}
    output.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"counts": [(c["arity"],
        sum(r["basis_equal"] for r in c["targets"]),
        sum(r["proof_replays"] for r in c["targets"]),
        sum(r["truth_set_equal"] for r in c["targets"])) for c in cells]}))


if __name__ == "__main__":
    main()
