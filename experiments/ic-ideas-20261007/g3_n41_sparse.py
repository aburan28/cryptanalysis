#!/usr/bin/env python3
"""Stream degree-four rows of the frozen N41 six-summand Boolean system.

This measures sparsity of the actual descended equations.  It deliberately
does not call dense M4RI or claim a block-Wiedemann solve from row sparsity.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import resource
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXISTING = REPO / "experiments/ecc2k130-ic-goal-20260929"
sys.path.insert(0, str(EXISTING))
import run_n41_lowpower_w8_s6_f4 as frozen  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def multipliers(nvars, degree):
    for weight in range(degree + 1):
        for indices in combinations(range(nvars), weight):
            yield sum(1 << i for i in indices)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=2_000_000)
    parser.add_argument("--max-distinct-columns", type=int, default=2_000_000)
    parser.add_argument("--skip-distinct-columns", action="store_true",
                        help="count all rows without retaining active column masks")
    parser.add_argument("--max-rss-bytes", type=int, default=3_500_000_000)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve previous receipt")
    if args.max_rows < 1 or args.max_distinct_columns < 1 or args.max_rss_bytes < 1:
        parser.error("limits must be positive")
    started = time.perf_counter_ns()
    common = frozen.load_common()
    system = frozen.make_system("ordinary", started, common)
    # Hashes of frozensets of integer masks are deterministic here.  Sorting
    # every large polynomial's terms only to establish row order is costly.
    equations = sorted(system["equations"], key=lambda eq: (len(eq), hash(eq)))
    nvars = system["variable_count"]
    degree = 4
    equation_degrees = Counter(max((term.bit_count() for term in equation), default=0)
                               for equation in equations)
    if max(equation_degrees) > degree:
        raise ValueError("input exceeds requested Macaulay degree")
    expected_rows = sum(count * sum(math.comb(nvars, i) for i in range(degree-d+1))
                        for d, count in equation_degrees.items())
    row_nnz = []
    distinct_columns = set()
    zero_rows = 0
    total_nnz = 0
    status = "COMPLETE"
    for equation in equations:
        d = max((term.bit_count() for term in equation), default=0)
        if args.skip_distinct_columns and len(equation) == 1:
            # A singleton remains one monomial under every Boolean multiple.
            # This covers the large low-degree one-hot constraint exactly.
            count = sum(math.comb(nvars, weight) for weight in range(degree-d+1))
            take = min(count, args.max_rows-len(row_nnz))
            row_nnz.extend([1]*take)
            total_nnz += take
            if take < count:
                status = "ROW_LIMIT"
                break
            continue
        for multiplier in multipliers(nvars, degree-d):
            row = set()
            for term in equation:
                product = term | multiplier
                if product in row:
                    row.remove(product)
                else:
                    row.add(product)
            size = len(row)
            row_nnz.append(size)
            total_nnz += size
            zero_rows += size == 0
            if not args.skip_distinct_columns:
                distinct_columns.update(row)
            if len(row_nnz) >= args.max_rows:
                status = "ROW_LIMIT" if len(row_nnz) < expected_rows else "COMPLETE"
                break
            if not args.skip_distinct_columns and len(distinct_columns) >= args.max_distinct_columns:
                status = "COLUMN_LIMIT"
                break
            if len(row_nnz) % 1000 == 0 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > args.max_rss_bytes:
                status = "RSS_LIMIT"
                break
        if status != "COMPLETE":
            break
    full_columns = sum(math.comb(nvars, d) for d in range(degree+1))
    sorted_nnz = sorted(row_nnz)
    answer = {"schema_version": 1, "proposal_id": "G3", "candidate_id": None,
              "run_id": None, "status": status, "curve_id": common["public"]["curve_id"],
              "target_point": common["public"]["target_q"],
              "factor_base_actual_B": common["manifest"]["actual_usable_union_points_B"],
              "folded_columns": common["manifest"]["signed_frobenius_folded_columns_K"],
              "summand_count": 6, "boolean_variables": nvars,
              "input_equations": len(equations),
              "equations_by_degree": {str(k): v for k, v in sorted(equation_degrees.items())},
              "macaulay_degree": degree, "expected_rows": expected_rows,
              "rows_built": len(row_nnz), "zero_rows": zero_rows,
              "full_squarefree_columns": full_columns,
              "observed_distinct_columns": None if args.skip_distinct_columns else len(distinct_columns),
              "nonzero_entries": total_nnz,
              "nnz_per_row_min": sorted_nnz[0] if sorted_nnz else None,
              "nnz_per_row_median": statistics.median(sorted_nnz) if sorted_nnz else None,
              "nnz_per_row_p95": sorted_nnz[(95*len(sorted_nnz))//100] if sorted_nnz else None,
              "nnz_per_row_max": sorted_nnz[-1] if sorted_nnz else None,
              "columns_times_nnz": full_columns * total_nnz,
              "sparse_index_lower_bound_bytes": 8*total_nnz,
              "dense_packed_bytes": len(row_nnz)*((full_columns+7)//8),
              "peak_self_ru_maxrss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "max_rss_bytes": args.max_rss_bytes,
              "distinct_column_count_skipped": args.skip_distinct_columns,
              "stage_wall_ns": time.perf_counter_ns()-started,
              "source_sha256": digest(Path(__file__)),
              "frozen_builder_sha256": digest(EXISTING / "run_n41_lowpower_w8_s6_f4.py"),
              "frozen_manifest_sha256": digest(frozen.MANIFEST),
              "scope": "actual N41 S6 degree-four Macaulay row support; no rank, block Wiedemann completion, target recovery, or speedup"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({k: answer[k] for k in (
        "status", "rows_built", "expected_rows", "full_squarefree_columns",
        "observed_distinct_columns", "nonzero_entries", "nnz_per_row_p95",
        "stage_wall_ns")}, sort_keys=True))


if __name__ == "__main__":
    main()
