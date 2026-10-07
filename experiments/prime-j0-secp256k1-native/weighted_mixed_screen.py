#!/usr/bin/env python3
"""Vector-cost screen for the fixed selective mixed τ alphabet."""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import digit_table, planned_pairs
from atlas_portfolio import SEEDS, baseline_scan, norm
from mixed_atlas_screen import make_options
from selective_mixed_atlas import DEPENDENCIES, TAIL_HORIZON, reconstruct


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixture.json"
WEIGHTS = (500, 750, 1000)
DOUBLE = (2, 5)
MIXED = (8, 3)
GENERAL = (11, 3)
CACHE = (1, 1)
STEP = (4, 2)
PAIR_SAVING = (2, 0)


def weighted(vector, squaring_weight):
    return 1000 * vector[0] + squaring_weight * vector[1]


def preparation_vector(used_mask):
    if not used_mask:
        return (0, 0)
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
    doubles = sum(seed in required for seed in (1, 2, 4, 6, 9, 10, 11))
    additions = sum(seed in required for seed in (3, 5, 7, 8))
    rotations = int(3 in required) + int(8 in required)
    images = used_mask.bit_count()
    assert doubles + additions + 1 == len(required)
    return (doubles * DOUBLE[0] + additions * MIXED[0] + rotations + images,
            doubles * DOUBLE[1] + additions * MIXED[1])


def recount(digits):
    if not digits:
        return (0, 0), (0, 0), (0, 0)
    seeds = [digit[2] if digit is not None else None for digit in digits]
    pairs = planned_pairs(seeds)
    charged = [seed for seed in seeds if seed is not None][:-1]
    mixed = sum(seed == 0 for seed in charged)
    general = len(charged) - mixed
    cache = len({seed for seed in charged if seed > 0})
    steps = len(digits) - 1
    evaluation = (steps * STEP[0] - pairs * PAIR_SAVING[0]
                  + mixed * MIXED[0] + general * GENERAL[0] + cache * CACHE[0],
                  steps * STEP[1] - pairs * PAIR_SAVING[1]
                  + mixed * MIXED[1] + general * GENERAL[1] + cache * CACHE[1])
    used = sum(1 << seed for seed in set(seed for seed in seeds if seed is not None))
    preparation = preparation_vector(used)
    return evaluation, preparation, tuple(sum(x) for x in zip(evaluation, preparation))


def recode(short, table, options, squaring_weight):
    baseline = baseline_scan(short, table)
    current = {((0, 0), -1, -1, 0, 0): (0, ())}
    for position in range(len(baseline) + TAIL_HORIZON):
        (ra, rb), old = (baseline[position] if position < len(baseline)
                         else ((0, 0), None))
        da, db = old[0] if old is not None else (0, 0)
        following = {}
        for (carry, last, high, cache_mask, used_mask), (cost, path) in current.items():
            residue = ((ra + carry[0]) % 9, (rb + carry[1]) % 9)
            for coefficient, seed in options[residue]:
                ea, eb = coefficient if coefficient is not None else (0, 0)
                x = da + carry[0] - ea
                y = db + carry[1] - eb
                assert x % 3 == 0
                successor = (x + y, -x // 3)
                assert norm(successor) <= 432
                if coefficient is None:
                    next_last, next_high = last, high
                    next_cache, next_used, extra = cache_mask, used_mask, 0
                    digit = None
                elif last < 0:
                    next_last, next_high = position, seed
                    next_cache, next_used = cache_mask, used_mask | (1 << seed)
                    extra = weighted(STEP, squaring_weight) * position
                    extra -= weighted(PAIR_SAVING, squaring_weight) * (position // 2)
                    digit = (ea, eb, seed)
                else:
                    gap = position - last - 1
                    needs_cache = high > 0 and not cache_mask & (1 << high)
                    next_last, next_high = position, seed
                    next_cache = cache_mask | ((1 << high) if high > 0 else 0)
                    next_used = used_mask | (1 << seed)
                    extra = weighted(STEP, squaring_weight) * (position - last)
                    extra -= weighted(PAIR_SAVING, squaring_weight) * ((gap + 1) // 2)
                    extra += weighted(MIXED if high == 0 else GENERAL, squaring_weight)
                    if needs_cache:
                        extra += weighted(CACHE, squaring_weight)
                    digit = (ea, eb, seed)
                key = (successor, next_last, next_high, next_cache, next_used)
                value = cost + extra
                if key not in following or value < following[key][0]:
                    following[key] = (value, path + (digit,))
        current = following
    terminal = [(cost + weighted(preparation_vector(state[4]), squaring_weight),
                 cost, state, path)
                for state, (cost, path) in current.items() if state[0] == (0, 0)]
    assert terminal
    _, evaluator_cost, state, path = min(terminal, key=lambda row: row[:3])
    digits = list(path)
    while digits and digits[-1] is None:
        digits.pop()
    evaluation, preparation, total = recount(digits)
    assert weighted(evaluation, squaring_weight) == evaluator_cost
    assert state[4] == sum(1 << seed for seed in
                           {digit[2] for digit in digits if digit is not None})
    assert reconstruct(digits) == short
    return digits, evaluation, preparation, total


def main():
    fixture_raw = FIXTURE.read_bytes()
    cases = json.loads(fixture_raw)["cases"]
    assert len(cases) == 64
    tables = [digit_table(seeds) for seeds in SEEDS]
    options = make_options(tables, True)
    panels = {weight: [] for weight in WEIGHTS}
    for case in cases:
        short = (int(case["short_a_hex"], 16), int(case["short_b_hex"], 16))
        for weight in WEIGHTS:
            digits, evaluation, preparation, total = recode(short, tables[0], options, weight)
            encoded = json.dumps(digits, separators=(",", ":")).encode()
            panels[weight].append({"index": case["index"],
                                   "digit_sha256": hashlib.sha256(encoded).hexdigest(),
                                   "evaluation_MS": evaluation,
                                   "preparation_MS": preparation,
                                   "total_MS": total,
                                   "weighted_cost": weighted(total, weight)})
    assert sum(sum(row["total_MS"]) for row in panels[1000]) == 87298
    result = []
    for weight in WEIGHTS:
        incumbent = {row["index"]: row for row in panels[1000]}
        rows = []
        for row in panels[weight]:
            old = incumbent[row["index"]]
            old_weighted = weighted(old["total_MS"], weight)
            assert row["weighted_cost"] <= old_weighted
            rows.append({**row,
                         "incumbent_weighted_cost": old_weighted,
                         "saving_weighted": old_weighted - row["weighted_cost"],
                         "changed_stream": row["digit_sha256"] != old["digit_sha256"]})
        result.append({"squaring_weight_per_1000M": weight,
                       "cases": len(rows),
                       "incumbent_weighted_total": sum(row["incumbent_weighted_cost"] for row in rows),
                       "weighted_total": sum(row["weighted_cost"] for row in rows),
                       "changed_streams": sum(row["changed_stream"] for row in rows),
                       "wins": sum(row["saving_weighted"] > 0 for row in rows),
                       "rows": rows})
    payload = {"schema": 1,
               "fixture_sha256": hashlib.sha256(fixture_raw).hexdigest(),
               "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "source_dependency_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                            for name in ("selective_mixed_atlas.py", "mixed_atlas_screen.py",
                                                         "alternate_digit_atlas.py", "atlas_portfolio.py")},
               "panels": result,
               "cpu_speedup_claim": None,
               "academic_novelty_claim": None}
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
