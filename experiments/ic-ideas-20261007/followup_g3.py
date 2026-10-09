#!/usr/bin/env python3
"""Matrix-free N41 S6 degree-four Macaulay operator control.

Only representative rows are materialized.  The full degree-four row census
is performed separately by g3_n41_sparse.py with --skip-distinct-columns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXISTING = REPO / "experiments/ecc2k130-ic-goal-20260929"
sys.path.insert(0, str(EXISTING))
import run_n41_lowpower_w8_s6_f4 as frozen  # noqa: E402

from g3_n41_sparse import multipliers


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def splitmix_bit(value):
    mask = (1 << 64)-1
    value = (value + 0x9E3779B97F4A7C15) & mask
    value = ((value ^ (value >> 30))*0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27))*0x94D049BB133111EB) & mask
    return ((value ^ (value >> 31)) >> 63) & 1


def row_support(equation, multiplier):
    result = set()
    for term in equation:
        column = term | multiplier
        if column in result:
            result.remove(column)
        else:
            result.add(column)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-equation", type=int, default=8)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve previous receipt")
    if args.per_equation < 1:
        parser.error("per-equation must be positive")
    started = time.perf_counter_ns()
    common = frozen.load_common()
    system = frozen.make_system("ordinary", started, common)
    equations = system["equations"]
    nvars = system["variable_count"]
    degree = 4
    degrees = Counter(max((term.bit_count() for term in equation), default=0)
                      for equation in equations)
    expected_rows = sum(count*sum(math.comb(nvars, k) for k in range(degree-d+1))
                        for d, count in degrees.items())
    columns = sum(math.comb(nvars, k) for k in range(degree+1))
    selected = []
    for d in sorted(degrees):
        bucket = [eq for eq in equations
                  if max((term.bit_count() for term in eq), default=0) == d]
        bucket.sort(key=lambda eq: len(eq))
        selected.extend((bucket[0], bucket[len(bucket)//2], bucket[-1]))
    rows = []
    row_sources = []
    for equation in selected:
        d = max((term.bit_count() for term in equation), default=0)
        for multiplier in list(multipliers(nvars, degree-d))[:args.per_equation]:
            rows.append(row_support(equation, multiplier))
            row_sources.append([d, len(equation), multiplier])
    seed = 20261008
    x = {column: splitmix_bit(column ^ seed)
         for row in rows for column in row}
    y = [splitmix_bit(i ^ (seed << 1)) for i in range(len(rows))]
    Ax = [sum(x[column] for column in row) & 1 for row in rows]
    ATy = set()
    for bit, row in zip(y, rows):
        if bit:
            ATy.symmetric_difference_update(row)
    lhs = sum(a*b for a, b in zip(Ax, y)) & 1
    rhs = sum(x[column] for column in ATy) & 1
    assert lhs == rhs
    answer = {
        "schema_version": 1, "proposal_id": "G3", "candidate_id": None,
        "run_id": None, "curve_id": common["public"]["curve_id"],
        "target_point": common["public"]["target_q"],
        "boolean_variables": nvars, "macaulay_degree": degree,
        "full_squarefree_columns": columns, "expected_rows": expected_rows,
        "rows_less_than_columns": expected_rows < columns,
        "sampled_rows": len(rows), "sampled_nnz": sum(map(len, rows)),
        "sampled_active_columns": len(x), "sampled_row_sources": row_sources,
        "sampled_nnz_min": min(map(len, rows)),
        "sampled_nnz_max": max(map(len, rows)),
        "operator_transpose_bilinear_check": lhs == rhs,
        "operator_output_ones": sum(Ax), "transpose_output_ones": len(ATy),
        "source_sha256": sha(Path(__file__)),
        "frozen_builder_sha256": sha(EXISTING / "run_n41_lowpower_w8_s6_f4.py"),
        "stage_wall_ns": time.perf_counter_ns()-started,
        "scope": "representative actual N41 sparse rows; no full block Wiedemann solve, solving-degree proof, or target recovery",
        "interpretation": "The degree-four matrix has fewer rows than ambient columns; this alone does not rule out deriving low-degree consequences by sparse elimination.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"sampled_rows": len(rows), "sampled_nnz": answer["sampled_nnz"],
                      "bilinear_check": lhs == rhs, "output": str(args.output)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
