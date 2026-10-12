#!/usr/bin/env python3
"""Exact-arithmetic screen of one-step policy improvement for linked recoding.

The rollout evaluates each legal high-norm exit by its immediate charged
source operations plus the cost of completing with the frozen greedy policy.
It then repeats at the successor state. The norm-4096 tail remains exact.
This script measures recoding choices, not elliptic-curve CPU time.
"""

import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
import generate_shared_z_tail as tail


HERE = Path(__file__).resolve().parent
PREPARATION_AND_ALIGNMENT = 68 + 57
LIMIT = 4096
NATIVE_BASELINES = {
    "fixture.json": (64, 82_772),
    "fresh-fixture.json": (256, 330_994),
    "coset-fixture.json": (256, 331_038),
    "linked-fresh-fixture.json": (256, 330_962),
    "zero-tau-fixture.json": (256, 331_564),
}


def greedy_action(state):
    a, b, pending_tau = state
    options = tuple(tail.options(a, b))
    has_digit = a % 3 != 0
    even = a % 2 == b % 2 == 0
    if has_digit:
        if even:
            return next(item for item in options if item[0] == "h" and item[1] is None)
        for radix in ("r", "s"):
            for item in options:
                if item[0] == radix and item[1] is None:
                    return item
        return options[0]
    # For N>4096, the Rust coordinate guard in half_exit_wins is equivalent
    # to this norm test: the entire N<=39083 ball is inside that guard.
    if even and not pending_tau and tail.norm(a, b) > 39083:
        return next(item for item in options if item[0] == "h" and item[1] is None)
    return options[0]


def screen_case(case, tail_choices, mode):
    @lru_cache(None)
    def exact_tail_cost(state):
        if state[:2] == (0, 0):
            return 0
        successor, charge = tail.successor(state, tail_choices[state])
        return charge + exact_tail_cost(successor)

    @lru_cache(None)
    def greedy_cost(state):
        if state[:2] == (0, 0):
            return 0
        if tail.norm(*state[:2]) <= LIMIT:
            return exact_tail_cost(state)
        successor, charge = tail.successor(state, greedy_action(state))
        return charge + greedy_cost(successor)

    initial = (int(case["short_a_hex"], 16),
               int(case["short_b_hex"], 16), False)
    state = initial
    actions = []
    charged = PREPARATION_AND_ALIGNMENT
    unit_exits = 0
    while state[:2] != (0, 0):
        old_norm = tail.norm(*state[:2])
        if old_norm <= LIMIT:
            action = tail_choices[state]
        else:
            baseline = greedy_action(state)
            action = baseline
            if mode != "baseline":
                best_next, best_charge = tail.successor(state, baseline)
                best = best_charge + greedy_cost(best_next)
                for alternative in tail.options(*state[:2]):
                    if mode == "unit" and not (
                        alternative[1] is not None and alternative[0] != "t"
                    ):
                        continue
                    successor, charge = tail.successor(state, alternative)
                    if tail.norm(*successor[:2]) >= old_norm:
                        continue
                    score = charge + greedy_cost(successor)
                    if score < best:
                        best, action = score, alternative
        successor, charge = tail.successor(state, action)
        if old_norm > LIMIT and tail.norm(*successor[:2]) >= old_norm:
            raise AssertionError("large-state action did not contract")
        unit_exits += old_norm > LIMIT and action[1] is not None and action[0] != "t"
        actions.append(action)
        charged += charge
        state = successor
        assert len(actions) <= 256
    assert tail.reconstruction(actions) == initial[:2]
    assert actions[-1][1] is not None
    return {"charged": charged, "actions": len(actions),
            "unit_exits": unit_exits,
            "greedy_states_visited": greedy_cost.cache_info().currsize}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=HERE / "fresh-fixture.json")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    fixture_bytes = args.fixture.read_bytes()
    cases = json.loads(fixture_bytes)["cases"]
    if args.limit is not None:
        cases = cases[:args.limit]
    tail.TABLE = digit_table(SEEDS[2])
    choices, states, edges = tail.shortest_paths()
    rows = []
    for index, case in enumerate(cases):
        results = {mode: screen_case(case, choices, mode)
                   for mode in ("baseline", "unit", "all")}
        assert results["unit"]["charged"] <= results["baseline"]["charged"]
        assert results["all"]["charged"] <= results["baseline"]["charged"]
        rows.append({"index": index, **results})
    summary = {
        "fixture": args.fixture.name,
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "screen_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "tail_sha256": hashlib.sha256(
            (HERE / "linked-shared-z-tail4096.bin").read_bytes()
        ).hexdigest(),
        "cases": len(rows), "tail_states": states, "tail_edges": edges,
        "totals": {mode: sum(row[mode]["charged"] for row in rows)
                   for mode in ("baseline", "unit", "all")},
        "wins": {mode: sum(row[mode]["charged"] < row["baseline"]["charged"]
                           for row in rows) for mode in ("unit", "all")},
        "unit_exits": {mode: sum(row[mode]["unit_exits"] for row in rows)
                       for mode in ("unit", "all")},
        "maximum_actions": {mode: max(row[mode]["actions"] for row in rows)
                            for mode in ("baseline", "unit", "all")},
        "greedy_states_visited": {
            mode: sum(row[mode]["greedy_states_visited"] for row in rows)
            for mode in ("unit", "all")},
    }
    if args.limit is None and args.fixture.name in NATIVE_BASELINES:
        expected_cases, expected_cost = NATIVE_BASELINES[args.fixture.name]
        assert (summary["cases"], summary["totals"]["baseline"]) == (
            expected_cases, expected_cost
        ), "greedy source accounting drifted from native replay"
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
