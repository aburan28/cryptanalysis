#!/usr/bin/env python3
"""Q1427 combinatorial anchor and tracked-assumption solver controls."""

from __future__ import annotations

import json
import math

import run as experiment
from anchor_selection import weight_mask
from stats_bridge import StatsSolver


def main():
    masks = [weight_mask(7, 3, rank) for rank in range(math.comb(7, 3))]
    assert len(set(masks)) == math.comb(7, 3)
    assert all(mask.bit_count() == 3 for mask in masks)
    with StatsSolver(2) as solver:
        assert solver.add_xor([1, 2], True)
        first, first_model, first_stats = solver.solve_assuming(
            [1], seconds=1, conflicts=1000)
        second, second_model, second_stats = solver.solve_assuming(
            [-1], seconds=1, conflicts=1000)
        assert first == second == "SAT"
        assert first_model[1] and not first_model[2]
        assert not second_model[1] and second_model[2]
        assert first_stats["propagations"] > 0
        assert second_stats["propagations"] > 0
    frozen = experiment.check_freeze()
    rows = []
    for n in (53, 83):
        profile, parent, _, _, _ = experiment.prior.load_case(
            n, "ordinary_both_lazy")
        onb = experiment.prior.field.Onb(n)
        curve, keys, key = experiment.read_base(profile, onb)
        for number in (0, 1):
            anchor = experiment.choose(profile, parent, number, onb,
                                       curve, keys, key)
            assert anchor == frozen["cases"][str(n)]["ordinary_anchors"][number]
            rows.append({"n": n, "anchor_number": number,
                         "raw_leaf_x": [leaf["raw_x"] for leaf in anchor["leaves"]],
                         "root_count": len(anchor["roots"]),
                         "candidate_masks": anchor["counts"]["candidate_masks"]})
    receipt = {"schema": "q1427-anchor-control-v1",
               "freeze_sha256": experiment.prior.digest(experiment.HERE / "freeze.json"),
               "combinatorial_masks_checked": len(masks),
               "assumption_solver_status": [first, second],
               "anchor_rows": rows}
    (experiment.HERE / "anchor_check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
