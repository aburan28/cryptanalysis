#!/usr/bin/env python3
"""Independently check the frozen 64 MiB policy by capacity DP."""

from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def main():
    assert sys.argv[1:] in ([], ["--write"])
    source = HERE / "selective-policy.json"
    policy = json.loads(source.read_bytes())
    cap = (policy["retained_table_cap_bytes"] -
           policy["metadata_reserve_bytes"] -
           policy["baseline_point_and_atlas_bytes"]) // 32
    items = [
        (policy["channel_seed_counts"][index],
         sum(policy["channel_power_counts"][index][exponent][1:]))
        for index in range(14) for exponent in range(2)
    ]
    states = {0: 0}
    for cost, benefit in items:
        updated = states.copy()
        for spent, value in states.items():
            new_cost = spent + cost
            if new_cost <= cap:
                updated[new_cost] = max(updated.get(new_cost, -1),
                                        value + benefit)
        states = updated
    selected = policy["compressed_channels"]
    selected_cost = sum(items[2 * index + exponent][0]
                        for index in range(14) for exponent in range(2)
                        if selected[index][exponent])
    selected_benefit = sum(items[2 * index + exponent][1]
                           for index in range(14) for exponent in range(2)
                           if selected[index][exponent])
    assert selected_cost <= cap
    assert selected_benefit == max(states.values())
    assert selected_benefit == policy["training_rotations_removed"]
    assert selected_cost * 32 == policy["additional_point_bytes"]
    result = {
        "schema": 1,
        "status": "independent_capacity_dp_pass",
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "policy_sha256": sha256(source.read_bytes()).hexdigest(),
        "capacity_slot_units": cap,
        "reachable_cost_states": len(states),
        "selected_slot_units": selected_cost,
        "optimal_rotations_removed": selected_benefit,
    }
    target = HERE / "selective-optimality.json"
    if sys.argv[1:] == ["--write"]:
        target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(target.read_bytes()) == result
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
