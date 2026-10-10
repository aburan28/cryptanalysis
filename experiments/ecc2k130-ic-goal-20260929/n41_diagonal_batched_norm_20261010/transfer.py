#!/usr/bin/env python3
"""Exact dense-degree boundary for W14 global reciprocal bucket products."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w14_ten_source_gate_20261009"
PROTOCOL = HERE / "transfer_protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads(PROTOCOL.read_text())
    sources = {"transfer": Path(__file__), "freeze": HERE / "freeze_transfer.py",
               "support_protocol": SUPPORT / "support_protocol.json",
               "support_masks": SUPPORT / "support_w14.tsv",
               "runtime": HERE / "sage_runtime_info.json",
               "n41_positive": HERE / "positive_result.json",
               "n41_public": HERE / "public_result.json"}
    assert {key: sha(path) for key, path in sources.items()} == protocol["source_sha256"]
    support = json.loads((SUPPORT / "support_protocol.json").read_text())
    masks = [tuple(map(int, row.split()))
             for row in (SUPPORT / "support_w14.tsv").read_text().splitlines()]
    assert len(masks) == 8220 and len({column for _, column in masks}) == 8160
    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    field = GF(2**131, "a", modulus=t**131+t**13+t**2+t+1)
    w_values = {mask << 1 for mask in range(1 << 14)}
    start = time.monotonic_ns()
    inverse_in_source = []
    for w in sorted(w_values - {0}):
        inverse = int(field.from_integer(w).inverse().to_integer())
        if inverse in w_values:
            inverse_in_source.append({"w": w, "inverse": inverse})
    inverse_check_ns = time.monotonic_ns() - start
    assert not inverse_in_source
    dimension = 14
    bucket_count = (1 << dimension) - 1
    products_per_bucket = 1 << (dimension - 1)
    exact_bucket_degree = 2 * products_per_bucket
    exact_global_left_degree = bucket_count * exact_bucket_degree
    element_bytes = (131 + 7) // 8
    minimum_dense_left_bytes = (exact_global_left_degree + 1) * element_bytes
    n41_positive = json.loads((HERE / "positive_result.json").read_text())
    n41_public = json.loads((HERE / "public_result.json").read_text())
    assert n41_positive["status"] == n41_public["status"] == "COMPLETE"
    assert n41_positive["left_product_degree"] == n41_public["left_product_degree"] == 4032
    result = {"status": "PASS_EXACT_DENSE_LEFT_BOUND", "candidate_id": None,
              "curve_id": support["curve_id"],
              "field_degree": 131, "source_dimension": dimension,
              "rational_source_masks": len(masks),
              "folded_columns_K": len({column for _, column in masks}),
              "all_source_elements": len(w_values),
              "nonzero_seed_sum_buckets": bucket_count,
              "products_per_bucket": products_per_bucket,
              "inverse_in_source_count": len(inverse_in_source),
              "exact_degree_per_bucket": exact_bucket_degree,
              "exact_global_left_degree": exact_global_left_degree,
              "minimum_dense_field_element_bytes": element_bytes,
              "minimum_dense_left_bytes": minimum_dense_left_bytes,
              "four_gib_bytes": 4*1024**3,
              "excess_over_four_gib_bytes": minimum_dense_left_bytes-4*1024**3,
              "right_degree_if_all_quadratic_resultant_leading_terms_survive": 2*exact_global_left_degree,
              "inverse_membership_check_ns": inverse_check_ns,
              "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(PROTOCOL)}
    assert result["excess_over_four_gib_bytes"] > 0
    with (HERE / "transfer_result.json").open("x") as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
