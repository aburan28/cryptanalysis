#!/usr/bin/env python3
"""Exact dimensions and conditional block-Wiedemann I/O budget for N41 S6."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "ic-ideas-20261007/results/g3_full_rows_followup.json"


def main():
    old = json.loads(SOURCE.read_text())
    assert old["status"] == "COMPLETE"
    n, d = old["boolean_variables"], old["macaulay_degree"]
    histogram = {int(k): int(v) for k, v in old["equations_by_degree"].items()}
    row_formula = lambda degree: sum(count*sum(math.comb(n, i)
        for i in range(degree-eq_degree+1))
        for eq_degree, count in histogram.items())
    col_formula = lambda degree: sum(math.comb(n, i)
                                    for i in range(degree+1))
    assert row_formula(d) == old["expected_rows"] == old["rows_built"]
    assert col_formula(d) == old["full_squarefree_columns"]
    rows, columns, nnz = old["rows_built"], old["full_squarefree_columns"], old["nonzero_entries"]
    # A conventional sequence for the square row Gram operator M M^T has
    # approximately 2R/b block steps.  Each step applies both M^T and M.
    # These are work/I/O budgets, not unconditional complexity lower bounds:
    # compression, rank structure, early termination, and another solver can
    # change the costs.  A 64-bit mask carries all 64 block vectors per edge.
    blocks = []
    for width in (32, 64, 128, 256):
        steps = math.ceil(2*rows/width)
        word_lanes = math.ceil(width/64)
        traversals = 2*steps
        blocks.append({"block_width": width,
                       "nominal_gram_sequence_steps": steps,
                       "edge_traversals": traversals,
                       "edge_word_updates": nnz*traversals*word_lanes,
                       "four_byte_index_stream_bytes": 4*nnz*traversals,
                       "eight_byte_index_stream_bytes": 8*nnz*traversals})
    result = {"schema_version": 1, "proposal_id": "G3",
              "candidate_id": None, "run_id": None,
              "curve_id": old["curve_id"],
              "macaulay_degree": d, "boolean_variables": n,
              "rows": rows, "ambient_columns": columns, "nnz": nnz,
              "degree_four_row_rank_upper_bound": rows,
              "degree_four_quotient_dimension_lower_bound": columns-rows,
              "degree_five_rows_same_construction": row_formula(5),
              "degree_five_ambient_columns": col_formula(5),
              "index_bytes_if_materialized_u32": 4*nnz,
              "index_bytes_if_materialized_u64": 8*nnz,
              "conventional_block_wiedemann_budgets": blocks,
              "scope": "dimension arithmetic and conditional conventional Krylov budget; no rank, solve, or target recovery",
              "source_census_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    dest = HERE / "g3_krylov_budget.json"
    if dest.exists():
        raise FileExistsError(dest)
    dest.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"degree_five_columns": result["degree_five_ambient_columns"],
                      "block64_index_stream_4byte_TB":
                          blocks[1]["four_byte_index_stream_bytes"]/1e12},
                     sort_keys=True))


if __name__ == "__main__":
    main()
