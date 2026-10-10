#!/usr/bin/env python3
"""Exact mask-pair support ceilings for a shared-seed four-atom block."""

import hashlib
import json
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
W14 = GOAL / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
N41 = GOAL / "n41_n131_diagonal_atom_20261010/screen.json"
R131 = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pair_counts(masks_to_columns, width):
    items = sorted(masks_to_columns.items())
    counts = [0] * (1 << width)
    for i, (a, column) in enumerate(items):
        for b, other_column in items[i + 1:]:
            if column != other_column:
                counts[a ^ b] += 1
    assert counts[0] == 0
    return counts


def ratio(numerator, denominator):
    with localcontext() as context:
        context.prec = 40
        return str(Decimal(numerator) / Decimal(denominator))


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_SUPPORT_GATE"
    for name, path in {
        "count_bound": Path(__file__),
        "w14_support": W14,
        "n41_screen": N41,
    }.items():
        assert protocol["source_sha256"][name] == sha(path), name

    w14 = {int(a): int(b) for a, b in
           (line.split() for line in W14.read_text().splitlines())}
    assert len(w14) == 8220
    counts = pair_counts(w14, 14)
    assert sum(counts) <= 8220 * 8219 // 2
    signed_choices = 2 * len(w14)
    fixed_four_upper = 16 * counts[1] ** 2
    variable_four_upper = 16 * sum(value * value for value in counts[1:])

    screen = json.loads(N41.read_text())
    n41 = {int(row["mask"]): int(row["source_column"])
           for row in screen["slots"][0]}
    assert len(n41) == 32
    n41_counts = pair_counts(n41, 6)
    assert n41_counts[1] == 8
    result = {
        "status": "PASS_EXACT_MASK_PAIR_SUPPORT_BOUND",
        "candidate_id": None,
        "target_count": 0,
        "source_sha256": {
            "script": sha(Path(__file__)),
            "protocol": sha(HERE / "protocol.json"),
            "w14_support": sha(W14),
            "n41_screen": sha(N41),
        },
        "n41": {
            "curve_id": screen["curve_id"],
            "source_masks": len(n41),
            "fixed_seed_mask": 1,
            "unordered_usable_mask_pairs": n41_counts[1],
            "fixed_seed_fouratom_group_support_upper": 16 * n41_counts[1] ** 2,
            "variable_seed_fouratom_group_support_upper":
                16 * sum(value * value for value in n41_counts[1:]),
            "seed_pair_count_min": min(n41_counts[1:]),
            "seed_pair_count_max": max(n41_counts[1:]),
        },
        "n131": {
            "curve_id": "EC1N131Ckb1heb5f1998f20b",
            "subgroup_order": str(R131),
            "source_masks": len(w14),
            "signed_points_per_position": signed_choices,
            "seed_count": len(counts) - 1,
            "usable_unordered_mask_pairs": sum(counts),
            "seed_pair_count_min": min(counts[1:]),
            "seed_pair_count_max": max(counts[1:]),
            "fixed_seed_mask": 1,
            "fixed_seed_unordered_mask_pairs": counts[1],
            "fixed_seed_fouratom_group_support_upper": fixed_four_upper,
            "variable_seed_fouratom_group_support_upper": variable_four_upper,
            "arity_bounds": {
                str(m): {
                    "remaining_unrestricted_leaves": m - 4,
                    "fixed_seed_support_upper":
                        str(fixed_four_upper * signed_choices ** (m - 4)),
                    "fixed_seed_uniform_target_ratio_upper":
                        ratio(fixed_four_upper * signed_choices ** (m - 4), R131),
                    "variable_seed_support_upper":
                        str(variable_four_upper * signed_choices ** (m - 4)),
                    "variable_seed_uniform_target_ratio_upper":
                        ratio(variable_four_upper * signed_choices ** (m - 4), R131),
                } for m in (10, 12)
            },
        },
    }
    with (HERE / "result_bounds.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({
        "status": result["status"],
        "n41_seed1_pairs": n41_counts[1],
        "n131_seed1_pairs": counts[1],
        "n131_m10_fixed_ratio": result["n131"]["arity_bounds"]["10"][
            "fixed_seed_uniform_target_ratio_upper"],
    }))


if __name__ == "__main__":
    main()
