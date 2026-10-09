#!/usr/bin/env python3
"""Classify exact S3 lift parity and support costs for N23 cyclotomic leaves."""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-completion-20261008/n1_gate.json"


def s3(a, b, c):
    return ((a*b ^ a*c ^ b*c) ^ a*b*c ^ 1) & 1


def main():
    out = HERE / "n1_parity_classes.json"
    if out.exists():
        raise FileExistsError(out)
    prior = json.loads(PRIOR.read_text())
    minimum_odd = prior["kernel_parity_repair"]["minimum_odd_kernel_weight"]
    assert minimum_odd == 11
    table = [{"leaf_augmentations": list(bits),
              "s3_augmentation": s3(*bits),
              "exact_lift_parity_allowed": s3(*bits) == 0}
             for bits in itertools.product((0, 1), repeat=3)]
    allowed = [item["leaf_augmentations"] for item in table
               if item["exact_lift_parity_allowed"]]
    assert allowed == [[0, 1, 1], [1, 0, 1], [1, 1, 0]]
    answer = {"schema_version": 1, "proposal_id": "N1",
              "candidate_id": None, "run_id": None,
              "group_algebra": "GF(2)[Z/47]",
              "exact_s3_parity_table": table,
              "minimum_odd_projection_kernel_weight": minimum_odd,
              "homogeneous_weight_two": {
                  "fixed_sparse_sections_exact_lift_possible": False,
                  "minimum_leaf_parity_repairs": 2,
                  "support_lower_bound_per_repaired_leaf": minimum_odd - 2},
              "homogeneous_weight_three": {
                  "fixed_sparse_sections_exact_lift_possible": False,
                  "minimum_leaf_parity_repairs": 1,
                  "support_lower_bound_per_repaired_leaf": minimum_odd - 3},
              "mixed_weight_two_three_three": {
                  "augmentation_allows_exact_lift": True,
                  "remaining_condition": "second degree-23 CRT component must vanish"},
              "proof": "augmentation is a ring homomorphism and S3 over GF(2) vanishes exactly when two of three inputs are one; changing leaf parity requires an odd projection-kernel word",
              "prior_receipt_sha256": hashlib.sha256(PRIOR.read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"allowed_parities": allowed,
                      "repair_support_floor_w2": minimum_odd - 2,
                      "repair_support_floor_w3": minimum_odd - 3}))


if __name__ == "__main__":
    main()
