#!/usr/bin/env python3
"""Exact operation and packed-storage counts for one N131 W14 seed bucket."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PAIR = (BASE / "n131_w14_pair_output_join_20261010" /
        "v2_n131_positive_filtered_pair_join.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "projection.json"
    if output.exists():
        raise FileExistsError(output)
    pair = json.loads(PAIR.read_text())
    assert pair["status"] == "COMPLETE_ALGEBRAIC_SCAN"
    assert pair["field_degree"] == 131 and pair["source_dimension"] == 14
    assert pair["allowed_source_pairs"] == 2062
    assert pair["pair_output_entries"] == pair["distinct_pair_outputs"] == 4124
    degree = pair["distinct_pair_outputs"]
    coefficients = degree + 1
    width = max(1, math.isqrt((5*degree+1)//2))
    blocks = (coefficients + width - 1)//width
    horner_products = 2*coefficients + 5
    bsgs_products = 2*width + 5*(blocks-1) + 5
    result = {
        "status": "EXACT_OPERATION_COUNT_PROJECTION", "candidate_id": None,
        "input_pair_receipt_sha256": sha(PAIR), "source_sha256": sha(Path(__file__)),
        "field_degree": 131, "left_bucket_polynomial_degree": degree,
        "right_bucket_polynomial_degree": degree,
        "right_coefficients": coefficients, "bsgs_block_width": width,
        "bsgs_blocks": blocks,
        "horner_modular_polynomial_products": horner_products,
        "bsgs_modular_polynomial_products": bsgs_products,
        "horner_over_bsgs_product_count_ratio": str(horner_products) + "/" + str(bsgs_products),
        "dense_baby_storage_field_elements": 2*width*degree,
        "dense_baby_storage_packed_coefficient_bytes": 2*width*degree*17,
        "block_accumulation_scalar_coefficient_product_upper_bound":
            2*coefficients*degree,
        "independent_seed_pair_assignments": (2**14-1)**2,
        "eight_offset_seed_pair_assignments": 8*(2**14-1),
        "scope": "one exact seed-bucket compatibility query; counts exclude source-root construction, polynomial setup, inversion, GCD, target-driven seed selection, witness replay, and failed buckets",
    }
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({k: result[k] for k in ("left_bucket_polynomial_degree",
                     "bsgs_block_width", "bsgs_modular_polynomial_products",
                     "horner_modular_polynomial_products")}))


if __name__ == "__main__":
    main()
