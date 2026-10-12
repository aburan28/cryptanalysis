#!/usr/bin/env python3
"""Exact bounded-horizon mixed-alphabet τ recoder with selective seed prep."""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import HERE, digit_table, planned_pairs
from atlas_portfolio import SEEDS, baseline_scan, norm, score_fixture
from mixed_atlas_screen import make_options
from seed_chain_bound import tau


TAIL_HORIZON = 16
FIXTURES = [HERE / "fixture.json", HERE / "selective-fixture.json"]
UNION_SEEDS = SEEDS[0] + [SEEDS[2][5], SEEDS[2][6], SEEDS[2][7]]

# Each point is built once in the existing one-result double/mixed-add graph.
DEPENDENCIES = {
    1: (0,), 2: (1,), 3: (1,), 4: (3,), 5: (4,), 6: (5,),
    7: (3,), 8: (1,), 9: (8,), 10: (9,), 11: (4,),
}
POINT_COST = {
    1: 7, 2: 7, 3: 11, 4: 7, 5: 11, 6: 7,
    7: 11, 8: 11, 9: 7, 10: 7, 11: 7,
}


def preparation_cost(used_mask):
    if used_mask == 0:
        return 0, set()
    required = set()

    def include(seed):
        if seed in required:
            return
        required.add(seed)
        for parent in DEPENDENCIES.get(seed, ()):
            include(parent)

    for seed in range(12):
        if used_mask & (1 << seed):
            include(seed)
    point_cost = sum(POINT_COST.get(seed, 0) for seed in required)
    rotations = int(3 in required) + int(8 in required)
    orbit_images = used_mask.bit_count()
    return point_cost + rotations + orbit_images, required


assert preparation_cost(sum(1 << seed for seed in range(9)))[0] == 83
assert preparation_cost(sum(1 << seed for seed in
                            (0, 1, 2, 3, 4, 8, 9, 10, 11)))[0] == 75
assert preparation_cost((1 << 12) - 1)[0] == 107


def evaluator_cost(digits):
    if not digits:
        return 0
    seeds = [digit[2] if digit is not None else None for digit in digits]
    pairs = planned_pairs(seeds)
    steps = len(digits) - 1
    charged = [seed for seed in seeds if seed is not None][:-1]
    mixed = sum(seed == 0 for seed in charged)
    general = len(charged) - mixed
    cache = len({seed for seed in charged if seed > 0})
    return 6 * steps - 2 * pairs + 11 * mixed + 14 * general + 2 * cache


def reconstruct(digits):
    value = (0, 0)
    for digit in reversed(digits):
        value = tau(value)
        if digit is not None:
            value = value[0] + digit[0], value[1] + digit[1]
    return value


def recode(short, tables, options):
    states = baseline_scan(short, tables[0])
    # state: carry, last nonzero position, highest seed, cache mask,
    #        and all digit seeds used. The path stores an independent
    # coefficient witness for the winning state.
    current = {((0, 0), -1, -1, 0, 0): (0, ())}
    peak_states = 1
    for position in range(len(states) + TAIL_HORIZON):
        (ra, rb), old = states[position] if position < len(states) else ((0, 0), None)
        da, db = (0, 0) if old is None else old[0]
        following = {}
        for (carry, last, high, cache_mask, used_mask), (cost, path) in current.items():
            residue = ((ra + carry[0]) % 9, (rb + carry[1]) % 9)
            for coefficient, seed in options[residue]:
                ea, eb = (0, 0) if coefficient is None else coefficient
                x = da + carry[0] - ea
                y = db + carry[1] - eb
                assert x % 3 == 0
                next_carry = (x + y, -x // 3)
                assert norm(next_carry) <= 896
                if coefficient is None:
                    next_last, next_high = last, high
                    next_cache, next_used, extra = cache_mask, used_mask, 0
                    digit = None
                elif last < 0:
                    next_last, next_high = position, seed
                    next_cache, next_used = cache_mask, used_mask | (1 << seed)
                    extra = 6 * position - 2 * (position // 2)
                    digit = (ea, eb, seed)
                else:
                    gap = position - last - 1
                    cache = 2 if high > 0 and not cache_mask & (1 << high) else 0
                    next_last, next_high = position, seed
                    next_cache = cache_mask | ((1 << high) if high > 0 else 0)
                    next_used = used_mask | (1 << seed)
                    extra = (6 * (position - last) - 2 * ((gap + 1) // 2)
                             + (11 if high == 0 else 14) + cache)
                    digit = (ea, eb, seed)
                key = (next_carry, next_last, next_high, next_cache, next_used)
                value = cost + extra
                if key not in following or value < following[key][0]:
                    following[key] = (value, path + (digit,))
        current = following
        peak_states = max(peak_states, len(current))
    terminal = [
        (cost + preparation_cost(state[4])[0], cost, state, path)
        for state, (cost, path) in current.items() if state[0] == (0, 0)
    ]
    assert terminal, "no bounded-horizon reconstruction"
    total, evaluator, state, path = min(terminal, key=lambda row: (row[0], row[1], row[2]))
    digits = list(path)
    while digits and digits[-1] is None:
        digits.pop()
    used_mask = state[4]
    preparation, required = preparation_cost(used_mask)
    assert total == evaluator + preparation
    assert evaluator == evaluator_cost(digits)
    assert reconstruct(digits) == short
    assert {digit[2] for digit in digits if digit is not None} == {
        seed for seed in range(12) if used_mask & (1 << seed)}
    return digits, {"preparation_M_plus_S": preparation,
                    "evaluator_M_plus_S": evaluator,
                    "total_M_plus_S": total,
                    "used_seed_ids": sorted(seed for seed in range(12)
                                            if used_mask & (1 << seed)),
                    "built_seed_ids": sorted(required),
                    "peak_dp_states": peak_states}


def score_panel(path, tables, options):
    raw = path.read_bytes()
    fixture = json.loads(raw)
    reference = score_fixture(path, tables,
                              [{5, 6}, {5, 6, 7}])
    rows = []
    for case, baseline in zip(fixture["cases"], reference["rows"]):
        assert case["index"] == baseline["index"]
        short = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
        digits, report = recode(short, tables, options)
        serialized = json.dumps(digits, separators=(",", ":")).encode()
        rows.append({"index": case["index"],
                     "digit_sha256": hashlib.sha256(serialized).hexdigest(),
                     "digit_positions": len(digits),
                     "portfolio_M_plus_S": baseline["selected_cost"],
                     "saving_M_plus_S": baseline["selected_cost"] - report["total_M_plus_S"],
                     **report})
    return {"fixture": path.name,
            "fixture_sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(rows),
            "portfolio_total": sum(row["portfolio_M_plus_S"] for row in rows),
            "selective_total": sum(row["total_M_plus_S"] for row in rows),
            "wins": sum(row["saving_M_plus_S"] > 0 for row in rows),
            "ties": sum(row["saving_M_plus_S"] == 0 for row in rows),
            "max_dp_states": max(row["peak_dp_states"] for row in rows),
            "rows": rows}


def main():
    tables = [digit_table(seeds) for seeds in SEEDS]
    options = make_options(tables, True)
    panels = [score_panel(path, tables, options) for path in FIXTURES]
    assert [panel["cases"] for panel in panels] == [64, 256]
    assert panels[0]["portfolio_total"] == 87632
    result = {
        "schema": 1, "tail_horizon": TAIL_HORIZON,
        "alphabet_seed_coefficients": UNION_SEEDS,
        "point_cost": POINT_COST, "dependencies": DEPENDENCIES,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_dependency_sha256": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ("atlas_portfolio.py", "mixed_atlas_screen.py",
                         "alternate_digit_atlas.py", "seed_chain_bound.py")},
        "panels": panels,
        "cpu_speedup_claim": None,
        "academic_novelty_claim": None,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
