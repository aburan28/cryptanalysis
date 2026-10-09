#!/usr/bin/env python3
"""Exact N23 selector-encoding dimensions for the cyclotomic base claim."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-20261007/results"
ENCODING = PRIOR / "a2_encoding_followup_final.json"
COVERAGE = PRIOR / "a2_final.json"


def columns(variables, degree):
    return sum(math.comb(variables, j) for j in range(degree+1))


def main():
    encoded = json.loads(ENCODING.read_text())
    coverage = json.loads(COVERAGE.read_text())
    assert encoded["field_degree"] == coverage["field_degree"] == 23
    # One exact support selector per root exponent (47) versus one per ONB
    # coordinate (23), for each of three summands.  Both chain S3 systems add
    # one 23-bit intermediate at this arity.
    m, cyclo_width, onb_width, intermediate = 3, 47, 23, 23
    direct = {"cyclotomic_selector_bits": m*cyclo_width,
              "normal_basis_selector_bits": m*onb_width,
              "cyclotomic_with_chain_bits": m*cyclo_width+intermediate,
              "normal_basis_with_chain_bits": m*onb_width+intermediate}
    direct.update({"cyclotomic_degree4_ambient_columns":
                       columns(direct["cyclotomic_with_chain_bits"], 4),
                   "normal_basis_degree4_ambient_columns":
                       columns(direct["normal_basis_with_chain_bits"], 4)})
    direct["degree4_column_ratio"] = (
        direct["cyclotomic_degree4_ambient_columns"] /
        direct["normal_basis_degree4_ambient_columns"])
    assert encoded["weight2_x"] == math.comb(47, 2)
    assert encoded["weight3_x"] == math.comb(47, 3)
    assert encoded["distinct_x"] == (math.comb(47, 2)+
                                     math.comb(47, 3))
    result = {"schema_version": 1, "proposal_id": "A2",
              "candidate_id": None, "run_id": None,
              "field_degree": 23,
              "weight_two_or_three_distinct_x": encoded["distinct_x"],
              "x47_membership_hits": encoded["x47_equals_1"],
              "x263_membership_hits": encoded["x263_equals_1"],
              "direct_selector_dimensions": direct,
              "matched_coverage_receipt_sha256":
                  hashlib.sha256(COVERAGE.read_bytes()).hexdigest(),
              "encoding_receipt_sha256":
                  hashlib.sha256(ENCODING.read_bytes()).hexdigest(),
              "scope": "direct-selector encoding dimensions; no optimized compact lookup encoding or F4/WDSat solving degree",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    output = HERE / "a2_selector_frontier.json"
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps(direct, sort_keys=True))


if __name__ == "__main__":
    main()
