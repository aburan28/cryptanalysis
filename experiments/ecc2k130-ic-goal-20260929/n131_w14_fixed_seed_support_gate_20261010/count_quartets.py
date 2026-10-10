#!/usr/bin/env python3
"""Count all compatible XOR-zero source quartets without enumerating quartets."""

import hashlib
import json
import time
from collections import defaultdict
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
W14 = GOAL / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
SCREEN = GOAL / "n41_n131_diagonal_atom_20261010/screen.json"
R131 = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def choose2(value):
    return value * (value - 1) // 2


def counts(mapping, width, cap_seconds):
    lookup = [-1] * (1 << width)
    for mask, column in mapping.items():
        lookup[mask] = column
    masks = sorted(mapping)
    pairs_per_seed = [0] * len(lookup)
    compatible_per_seed = [0] * len(lookup)
    started = time.monotonic_ns()
    for seed in range(1, len(lookup)):
        degree = defaultdict(int)
        multiplicity = defaultdict(int)
        pairs = 0
        for a in masks:
            b = a ^ seed
            if a >= b:
                continue
            cb = lookup[b]
            if cb < 0:
                continue
            ca = lookup[a]
            if ca == cb:
                continue
            pairs += 1
            degree[ca] += 1
            degree[cb] += 1
            lo, hi = (ca, cb) if ca < cb else (cb, ca)
            multiplicity[(lo << width) | hi] += 1
        bad_once = sum(choose2(value) for value in degree.values())
        bad_twice = sum(choose2(value) for value in multiplicity.values())
        compatible = choose2(pairs) - bad_once + bad_twice
        assert compatible >= 0
        pairs_per_seed[seed] = pairs
        compatible_per_seed[seed] = compatible
        if seed % 255 == 0 and time.monotonic_ns() - started > cap_seconds * 10**9:
            return "CENSORED_TIME", pairs_per_seed, compatible_per_seed, seed
    return "COMPLETE", pairs_per_seed, compatible_per_seed, len(lookup) - 1


def ratio(numerator, denominator):
    with localcontext() as context:
        context.prec = 40
        return str(Decimal(numerator) / Decimal(denominator))


def main():
    protocol = json.loads((HERE / "quartet_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_QUARTET_COUNT"
    for name, path in {
        "script": Path(__file__), "w14_support": W14, "n41_screen": SCREEN,
        "bounds": HERE / "result_bounds.json",
        "n41_group_support": HERE / "support_n41.json",
    }.items():
        assert protocol["source_sha256"][name] == sha(path), name
    w14 = {int(a): int(b) for a, b in
           (line.split() for line in W14.read_text().splitlines())}
    screen = json.loads(SCREEN.read_text())
    n41 = {int(row["mask"]): int(row["source_column"])
           for row in screen["slots"][0]}
    n41_status, n41_pairs, n41_compatible, n41_processed = counts(
        n41, 6, protocol["cap_seconds"])
    assert n41_status == "COMPLETE" and n41_processed == 63
    assert sum(n41_compatible) % 3 == 0
    n41_quartets = sum(n41_compatible) // 3
    n41_group = json.loads((HERE / "support_n41.json").read_text())
    assert 16 * n41_quartets == n41_group["all_seed_distinct_group_outputs"]
    assert 16 * n41_compatible[1] == n41_group["fixed_seed_support"][
        "distinct_group_outputs"]
    status, pairs, compatible, processed = counts(
        w14, 14, protocol["cap_seconds"])
    result = {
        "status": status,
        "candidate_id": None,
        "target_count": 0,
        "processed_n131_seed_sums": processed,
        "n41": {
            "curve_id": screen["curve_id"],
            "xor_zero_distinct_column_quartets": n41_quartets,
            "fixed_seed_compatible_mask_pair_pairs": n41_compatible[1],
            "fouratom_group_output_upper": 16 * n41_quartets,
            "actual_distinct_group_outputs":
                n41_group["all_seed_distinct_group_outputs"],
        },
        "n131": {
            "curve_id": "EC1N131Ckb1heb5f1998f20b",
            "signed_points_per_position": 16440,
            "subgroup_order": str(R131),
            "pair_counts_by_seed": pairs,
            "compatible_pair_pairs_by_seed": compatible,
        },
        "source_sha256": {
            "script": sha(Path(__file__)),
            "protocol": sha(HERE / "quartet_protocol.json"),
            "w14_support": sha(W14),
            "n41_screen": sha(SCREEN),
            "bounds": sha(HERE / "result_bounds.json"),
            "n41_group_support": sha(HERE / "support_n41.json"),
        },
    }
    if status == "COMPLETE":
        assert sum(compatible) % 3 == 0
        quartets = sum(compatible) // 3
        fixed_four_upper = 16 * compatible[1]
        variable_four_upper = 16 * quartets
        result["n131"].update({
            "xor_zero_distinct_column_quartets": quartets,
            "fixed_seed_fouratom_group_support_upper": fixed_four_upper,
            "variable_seed_fouratom_group_support_upper": variable_four_upper,
            "arity_bounds": {
                str(m): {
                    "fixed_seed_uniform_target_ratio_upper": ratio(
                        fixed_four_upper * 16440 ** (m - 4), R131),
                    "variable_seed_uniform_target_ratio_upper": ratio(
                        variable_four_upper * 16440 ** (m - 4), R131),
                    "fixed_seed_support_upper":
                        str(fixed_four_upper * 16440 ** (m - 4)),
                    "variable_seed_support_upper":
                        str(variable_four_upper * 16440 ** (m - 4)),
                } for m in (10, 12)
            },
        })
    with (HERE / "quartet_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({
        "status": status,
        "processed_n131_seeds": processed,
        "n41_quartets": n41_quartets,
        "n131_quartets": result["n131"].get("xor_zero_distinct_column_quartets"),
    }))


if __name__ == "__main__":
    main()
