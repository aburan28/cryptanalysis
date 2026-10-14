#!/usr/bin/env python3
"""Choose compressed orbit channels under a 64 MiB retained-table cap."""

from bisect import bisect_right
from hashlib import sha256
import json
from pathlib import Path
import sys

import model

HERE = Path(__file__).resolve().parent
TRAIN = HERE.parent / "prime-j0-mixed-radix640-20261010/fresh-inputs.json"
CAP_BYTES = 64 * 1024 * 1024
METADATA_RESERVE = 1024


def channel_counts(scalars, atlases):
    counts = [[[0, 0, 0] for _ in range(2)] for _ in model.mixed.RADICES]
    for value in scalars:
        a, b = model.mixed.screen.representative(
            int(value, 16) % model.mixed.screen.ORDER)
        for index, radix in enumerate(model.mixed.RADICES):
            label = "512" if index < 6 else "391" if index == 13 else "640"
            digit, seed_id, exponent, unit = atlases[label][0].decode(a, b)
            if seed_id:
                counts[index][exponent][unit // 2] += 1
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
        assert (a, b) == (0, 0)
    return counts


def subsets(items):
    values = []
    for mask in range(1 << len(items)):
        cost = benefit = 0
        for index, (slots, rotations) in enumerate(items):
            if mask & (1 << index):
                cost += slots
                benefit += rotations
        values.append((cost, benefit, mask))
    return values


def optimal(items, capacity):
    half = len(items) // 2
    left, right = subsets(items[:half]), subsets(items[half:])
    right.sort(key=lambda row: (row[0], -row[1], row[2]))
    costs = []
    best = []
    maximum = (-1, 0, 0)
    for row in right:
        if row[1] > maximum[0] or (row[1] == maximum[0] and row[0] < maximum[1]):
            maximum = (row[1], row[0], row[2])
        if costs and costs[-1] == row[0]:
            best[-1] = maximum
        else:
            costs.append(row[0])
            best.append(maximum)
    answer = (-1, 0, 0)
    for cost, benefit, mask in left:
        if cost > capacity:
            continue
        position = bisect_right(costs, capacity - cost) - 1
        if position < 0:
            continue
        other_benefit, other_cost, other_mask = best[position]
        candidate = (benefit + other_benefit, cost + other_cost,
                     mask | (other_mask << half))
        if candidate[0] > answer[0] or (
                candidate[0] == answer[0] and candidate[1] < answer[1]):
            answer = candidate
    assert answer[0] >= 0
    return answer


def policy():
    raw = TRAIN.read_bytes()
    scalars = json.loads(raw)["scalars_hex"]
    atlases = model.atlas_records()
    counts = channel_counts(scalars, atlases)
    seed_counts = [
        atlases["512"][1]["seed_count"] if index < 6 else
        atlases["391"][1]["seed_count"] if index == 13 else
        atlases["640"][1]["seed_count"]
        for index in range(14)
    ]
    atlas_bytes = sum(path.stat().st_size for path in
                      (model.mixed.ATLAS512, model.mixed.ATLAS640,
                       model.mixed.ATLAS391))
    baseline_point_atlas = sum(seed_counts) * 128 + atlas_bytes
    capacity_slots = (CAP_BYTES - METADATA_RESERVE - baseline_point_atlas) // 32
    items = [(seed_counts[index], sum(counts[index][exponent][1:]))
             for index in range(14) for exponent in range(2)]
    benefit, used_slots, mask = optimal(items, capacity_slots)
    selected = [[bool(mask & (1 << (2 * index + exponent)))
                 for exponent in range(2)] for index in range(14)]
    selected_benefit = sum(items[i][1] for i in range(28) if mask & (1 << i))
    assert selected_benefit == benefit
    baseline_rotations = sum(item[1] for item in items)
    result = {
        "schema": 1,
        "status": "training_only_exact_knapsack_policy",
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "training_sha256": sha256(raw).hexdigest(),
        "atlas_sha256": {name: value[1]["sha256"] for name, value in atlases.items()},
        "training_cases": len(scalars),
        "retained_table_cap_bytes": CAP_BYTES,
        "metadata_reserve_bytes": METADATA_RESERVE,
        "baseline_point_and_atlas_bytes": baseline_point_atlas,
        "channel_seed_counts": seed_counts,
        "channel_power_counts": counts,
        "compressed_channels": selected,
        "compressed_channel_count": sum(map(sum, selected)),
        "additional_point_bytes": 32 * used_slots,
        "point_and_atlas_bytes": baseline_point_atlas + 32 * used_slots,
        "training_baseline_rotations": baseline_rotations,
        "training_predicted_rotations": baseline_rotations - benefit,
        "training_rotations_removed": benefit,
    }
    assert result["point_and_atlas_bytes"] + METADATA_RESERVE <= CAP_BYTES
    return result


def main():
    assert sys.argv[1:] in ([], ["--write"])
    result = policy()
    target = HERE / "selective-policy.json"
    if sys.argv[1:] == ["--write"]:
        target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(target.read_bytes()) == result
    print(json.dumps({name: result[name] for name in
                      ("compressed_channels", "compressed_channel_count",
                       "point_and_atlas_bytes", "training_baseline_rotations",
                       "training_predicted_rotations")}, sort_keys=True))


if __name__ == "__main__":
    main()
