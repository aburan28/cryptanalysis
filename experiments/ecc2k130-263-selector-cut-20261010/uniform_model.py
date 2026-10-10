#!/usr/bin/env python3
"""Exact combinatorial counts for a stated uniform-group-sum branch model."""

from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
import hashlib
import json
from math import comb
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "experiments/ecc2k130-263-equal-w24-workload-20261005/base_selection.json"
WORKLOAD = ROOT / "experiments/ecc2k130-263-equal-w24-workload-20261005/primary_workload.json"
MASKS = HERE / "runs/R1/masks.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    base = json.loads(BASE.read_text())
    workload = json.loads(WORKLOAD.read_text())
    masks = json.loads(MASKS.read_text())
    selected = base["source"]["selected_signed_columns"]
    if (base["descendant_native"]["selected_signed_columns"] != selected
            or base["source"]["selected_usable_points_B"] != 2 * selected
            or base["descendant_native"]["selected_usable_points_B"]
            != 2 * selected
            or selected != 8386414
            or workload["workload_id"] != "eee7f6ee5f6b"
            or masks["schema"] != "ecc2k130-263-selector-cut-masks-v1"
            or len(masks["masks"]) != 8
            or len({row["mask"] for row in masks["masks"]}) != 8):
        raise ValueError("base, workload, or eight-mask panel changed")
    order = int(workload["subgroup_order"])
    if order <= 0:
        raise ValueError("invalid subgroup order")
    # Four raw target lifts out of an order-4r group give probability 1/r
    # under the stated uniform group-sum model.  A sorted six-mask tuple
    # has at most 2^6 sign choices.  With its first mask fixed, the other
    # five can be chosen with repetition from at most M mask classes.
    total_numerator = 64 * comb(selected + 5, 6)
    first_mask_numerator = 64 * comb(selected + 4, 5)
    panel_numerator = len(masks["masks"]) * first_mask_numerator
    with localcontext() as ctx:
        ctx.prec = 26
        decimal = lambda numerator: str(Decimal(numerator) / Decimal(order))
        total, first, panel = map(decimal, (
            total_numerator, first_mask_numerator, panel_numerator))
    result = {
        "schema": "ecc2k130-263-selector-cut-uniform-model-v1",
        "status": "EXACT_COMBINATORIAL_COUNTS_UNDER_STATED_MODEL",
        "assumption": "each signed raw six-leaf sum is marginally uniform in the order-4r curve group; four raw lifts represent the fixed public point",
        "interpretation": "expected representation counts, not measured relation yield or a theorem about the fixed target",
        "mask_classes_M": selected,
        "usable_points_B": 2 * selected,
        "subgroup_order_r": str(order),
        "raw_target_lifts": 4,
        "sign_choices_per_six_tuple_upper": 64,
        "panel_fixed_first_masks": len(masks["masks"]),
        "total_sorted_six_tuple_expected_numerator": str(total_numerator),
        "fixed_first_mask_expected_upper_numerator": str(first_mask_numerator),
        "eight_mask_expected_upper_numerator": str(panel_numerator),
        "common_denominator": str(order),
        "total_expected_decimal": total,
        "fixed_first_mask_expected_upper_decimal": first,
        "eight_mask_expected_upper_decimal": panel,
        "eight_mask_success_probability_upper_by_markov_under_model": panel,
        "base_selection_sha256": sha(BASE),
        "primary_workload_sha256": sha(WORKLOAD),
        "masks_sha256": sha(MASKS),
        "analysis_source_sha256": sha(Path(__file__)),
    }
    data = json.dumps(result, sort_keys=True, indent=2) + "\n"
    path = HERE / "runs/R1/uniform_model.json"
    if args.write:
        if path.exists() and path.read_text() != data:
            raise ValueError("existing analysis differs")
        if not path.exists():
            path.write_text(data)
    print(json.dumps({key: result[key] for key in (
        "total_expected_decimal", "fixed_first_mask_expected_upper_decimal",
        "eight_mask_expected_upper_decimal")}, sort_keys=True))


if __name__ == "__main__":
    main()
