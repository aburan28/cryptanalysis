#!/usr/bin/env python3
"""Learn and replay the F4 symbolic reducer-multiple schedule at N31."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from g1_f4_trace import solution_set, systems  # noqa: E402

BINARY = HERE / "native_f4_symbolic"
SOURCE = HERE / "native_f4_symbolic.cpp"


def run(equations, nvars, trace=None):
    mode = trace is not None
    shape = [nvars, len(equations), 1_000_000_000, 5_000_000,
             100_000, 100_000, 0, int(mode)]
    data = " ".join(map(str, shape)) + "\n"
    data += "\n".join(" ".join(map(str, [len(row), *row])) for row in equations) + "\n"
    if mode:
        data += str(len(trace)) + "\n"
        data += "\n".join(" ".join(map(str, [len(schedule),
                                                  *(item for pair in schedule for item in pair)]))
                           for schedule in trace) + "\n"
    started = time.perf_counter_ns()
    try:
        proc = subprocess.run([str(BINARY)], input=data, text=True,
                              capture_output=True, timeout=180)
        result = json.loads(proc.stdout)
        result["exit_code"] = proc.returncode
    except subprocess.TimeoutExpired:
        result = {"status": "timeout", "timeout_seconds": 180}
    result["wall_ns_exploratory"] = time.perf_counter_ns() - started
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--targets", type=int, default=16)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    cells = []
    for arity in (2, 3):
        _, cases = systems(arity, args.targets)
        first = run(cases[0][1], 3*arity)
        if first["status"] != "gb":
            raise RuntimeError((arity, first))
        schedule = first["symbolic_trace"]
        schedule_digest = hashlib.sha256(json.dumps(schedule,
            separators=(",", ":")).encode()).hexdigest()
        targets = []
        for index, (target_x, equations) in enumerate(cases):
            replay = run(equations, 3*arity, schedule)
            fresh = first if index == 0 else run(equations, 3*arity)
            truth = solution_set(equations, 3*arity)
            replay_truth = (solution_set(replay["basis"], 3*arity) == truth
                            if replay["status"] == "gb" else None)
            fresh_truth = (solution_set(fresh["basis"], 3*arity) == truth
                           if fresh["status"] == "gb" else None)
            basis_equal = (replay["basis"] == fresh["basis"]
                           if replay["status"] == fresh["status"] == "gb" else None)
            targets.append({"target_index": index, "target_x_bits": target_x,
                            "fresh_status": fresh["status"],
                            "fresh_reason": fresh.get("reason"),
                            "fresh_truth_set_equal": fresh_truth,
                            "replay_status": replay["status"],
                            "replay_reason": replay.get("reason"),
                            "replay_truth_set_equal": replay_truth,
                            "basis_equal": basis_equal,
                            "fresh_matrices": fresh.get("stats", {}).get("matrices"),
                            "replay_matrices": replay.get("stats", {}).get("matrices"),
                            "fresh_wall_ns_exploratory": fresh["wall_ns_exploratory"],
                            "replay_wall_ns_exploratory": replay["wall_ns_exploratory"]})
        cells.append({"arity": arity, "boolean_variables": 3*arity,
                      "target_count": len(targets),
                      "learned_matrix_count": len(schedule),
                      "learned_symbolic_multiples": sum(len(v) for v in schedule),
                      "symbolic_schedule_sha256": schedule_digest,
                      "fresh_completed": sum(t["fresh_status"] == "gb" for t in targets),
                      "replay_completed": sum(t["replay_status"] == "gb" for t in targets),
                      "exact_basis_equal_count": sum(t["basis_equal"] is True for t in targets),
                      "replay_truth_set_equal_count": sum(t["replay_truth_set_equal"] is True
                                                          for t in targets),
                      "targets": targets})
    answer = {"schema_version": 1, "proposal_id": "G1",
              "candidate_id": None, "run_id": None,
              "trace_definition": "per-F4-matrix ordered (basis reducer index, squarefree multiplier) rows; same pair batching and fresh elimination on replay",
              "target_law": "frozen planted N31 target sequence",
              "cells": cells,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "native_symbolic_source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "native_symbolic_binary_sha256": hashlib.sha256(BINARY.read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"cells": [(c["arity"], c["fresh_completed"],
                                  c["replay_completed"], c["exact_basis_equal_count"],
                                  c["replay_truth_set_equal_count"])
                                 for c in cells]}))


if __name__ == "__main__":
    main()
