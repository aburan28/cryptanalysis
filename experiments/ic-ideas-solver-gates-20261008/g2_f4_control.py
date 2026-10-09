#!/usr/bin/env python3
"""Bounded native F4 control for the invariant N19 S3 barrel system."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-completion-20261008"
sys.path.insert(0, str(PRIOR))
from g2_degree3_blocks import equations, shift  # noqa: E402


def cyclic_rows(seed, n):
    current = set(seed)
    for _ in range(n):
        yield frozenset(current)
        current = {shift(term, n) for term in current}


def main():
    out = HERE / "g2_f4_control.json"
    if out.exists():
        raise FileExistsError(out)
    n = 19
    modulus, s3, linear, pair_reps = equations(n)
    rows = set(cyclic_rows(s3, n))
    rows.add(frozenset(linear))
    for pair in pair_reps:
        rows.update(cyclic_rows(pair, n))
    inputs = [sorted(row) for row in sorted(rows, key=lambda row: (len(row), sorted(row)))]
    assert len(inputs) == n + 1 + n*(n-1)//2
    shape = [3*n, len(inputs), 50_000_000, 2_000_000, 100_000, 256, 1]
    data = " ".join(map(str, shape)) + "\n"
    data += "\n".join(" ".join(map(str, [len(row), *row])) for row in inputs) + "\n"
    started = time.perf_counter_ns()
    try:
        proc = subprocess.run([str(HERE / "native_f4")], input=data, text=True,
                              capture_output=True, timeout=120)
        status = json.loads(proc.stdout)
        status["exit_code"] = proc.returncode
    except subprocess.TimeoutExpired:
        status = {"status": "timeout", "timeout_seconds": 120}
    answer = {"schema_version": 1, "proposal_id": "G2",
              "candidate_id": None, "run_id": None,
              "field_degree": n, "field_modulus_bits": modulus,
              "boolean_variables": 3*n, "invariant_input_generators": len(inputs),
              "input_equation_degrees": {str(d): sum(max((term.bit_count() for term in row),
                                                          default=-1) == d for row in inputs)
                                         for d in range(5)},
              "native_f4_limits": {"work": shape[2], "proof_nodes": shape[3],
                                   "rows": shape[4], "batch": shape[5],
                                   "wall_seconds": 120},
              "native_f4_result": status,
              "wall_ns_exploratory": time.perf_counter_ns()-started,
              "prior_block_receipt_sha256": hashlib.sha256(
                  (PRIOR / "g2_n19.json").read_bytes()).hexdigest(),
              "native_f4_source_sha256": hashlib.sha256(
                  (HERE.parent / "groebner-perf-20260924/round5/native_f4.cpp").read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"status": status["status"],
                      "reason": status.get("reason"),
                      "generators": len(inputs)}))


if __name__ == "__main__":
    main()
