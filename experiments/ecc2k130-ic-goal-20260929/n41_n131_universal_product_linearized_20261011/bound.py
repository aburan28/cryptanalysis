"""Exact uniform trace-zero counting bounds for the product-span oracle."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    n = 131
    source_dimension = 18
    product_span_dimension = 2 * source_dimension - 1
    seed_branch_dimension = source_dimension + 1
    trace_zero_nonzero = (1 << (n - 1)) - 1
    # Rank loss implies e=c*d for nonzero e in the 19-dimensional
    # halftrace/branch span and nonzero d in the 35-dimensional product span.
    rank_loss_numerator = ((1 << seed_branch_dimension) - 1) * ((1 << product_span_dimension) - 1)
    # For each nonzero source seed and every product in the 35-dimensional
    # superset, the pair quadratic has at most two nonzero roots.
    span_pass_numerator = 2 * ((1 << source_dimension) - 1) * (1 << product_span_dimension)
    assert rank_loss_numerator * (1 << 76) < trace_zero_nonzero
    assert span_pass_numerator * (1 << 76) < trace_zero_nonzero
    result = {"status": "EXACT_COUNT_BOUND", "field_degree": n,
              "source_dimension": source_dimension,
              "product_span_dimension": product_span_dimension,
              "seed_branch_dimension": seed_branch_dimension,
              "uniform_law": "nonzero uniformly sampled trace-zero GF(2^131) coordinate",
              "denominator": trace_zero_nonzero,
              "rank_loss_union_numerator": rank_loss_numerator,
              "product_span_pass_union_numerator": span_pass_numerator,
              "both_upper_bounds_below_two_to_minus_76": True}
    (HERE / "bound.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "both_upper_bounds_below_two_to_minus_76": True}))


if __name__ == "__main__":
    main()
