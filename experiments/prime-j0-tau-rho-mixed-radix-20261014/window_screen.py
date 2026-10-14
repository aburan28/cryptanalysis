#!/usr/bin/env python3
"""Bounded recoding screen: width-four tau digits plus unit-digit rho steps."""

from collections import Counter
from dataclasses import dataclass
import json
import random
import statistics

from screen import (Pair, ZERO, UNITS, RADICES, add, multiply, norm,
                    quotient_if_divisible, subtract)


TAU4: Pair = (-9, -9)
assert norm(TAU4) == 81
assert multiply(multiply(RADICES["tau"], RADICES["tau"]),
                multiply(RADICES["tau"], RADICES["tau"])) == TAU4


def tau4_key(x: Pair) -> tuple[int, int]:
    return x[0] % 9, x[1] % 9


def tau4_quotient(x: Pair) -> Pair | None:
    # tau^4 = 9 omega^2; its inverse is omega / 9.
    a, b = x
    if a % 9 or b % 9:
        return None
    # omega*(a+b omega) = -b + (a-b) omega.
    q = -b // 9, (a - b) // 9
    assert multiply(TAU4, q) == x
    return q


def build_tau4_digit_table() -> tuple[dict[tuple[int, int], Pair], tuple[Pair, ...]]:
    table = {}
    seeds = []
    # This bound is verified by the complete 54-class coverage assertion.
    candidates = sorted(((a, b) for a in range(-12, 13) for b in range(-12, 13)
                         if (a, b) != ZERO), key=lambda z: (norm(z), z))
    for seed in candidates:
        if quotient_if_divisible(seed, "tau") is not None:
            continue
        key = tau4_key(seed)
        if key in table:
            continue
        orbit = [multiply(unit, seed) for unit in UNITS[1:]]
        keys = [tau4_key(digit) for digit in orbit]
        assert len(set(keys)) == 6
        assert all(key not in table for key in keys)
        seeds.append(seed)
        table.update(zip(keys, orbit, strict=True))
        if len(table) == 54:
            break
    assert len(table) == 54 and len(seeds) == 9
    for a in range(9):
        for b in range(9):
            x = a, b
            key = tau4_key(x)
            if quotient_if_divisible(x, "tau") is None:
                digit = table[key]
                assert tau4_quotient(subtract(x, digit)) is not None
            else:
                assert key not in table
    return table, tuple(seeds)


TAU4_DIGITS, TAU4_SEEDS = build_tau4_digit_table()
RHO_UNITS = {}
for unit in UNITS[1:]:
    residue = (unit[0] + 2 * unit[1]) % 7
    assert residue not in RHO_UNITS and residue
    RHO_UNITS[residue] = unit
assert len(RHO_UNITS) == 6


@dataclass(frozen=True)
class Action:
    radix: str
    power: int
    digit: Pair
    quotient: Pair


def actions(x: Pair, choices: tuple[str, ...]):
    for name in choices:
        if name == "tau4":
            q0 = quotient_if_divisible(x, "tau")
            if q0 is not None:
                yield Action("tau", 1, ZERO, q0)
            else:
                digit = TAU4_DIGITS[tau4_key(x)]
                q = tau4_quotient(subtract(x, digit))
                assert q is not None
                yield Action("tau", 4, digit, q)
        elif name == "rho1":
            residue = (x[0] + 2 * x[1]) % 7
            digit = RHO_UNITS[residue] if residue else ZERO
            q = quotient_if_divisible(subtract(x, digit), "rho")
            assert q is not None
            yield Action("rho", 1, digit, q)
        else:
            raise ValueError(name)


def factor_cost(action: Action) -> int:
    if action.radix == "tau":
        return 6 if action.power == 1 else 21  # tau^4 = 9 omega^2: two 3P plus omega.
    return 13


def cost(path: tuple[Action, ...], add_cost: int) -> int:
    return sum((factor_cost(action) if i + 1 < len(path) else 0)
               + add_cost * (action.digit != ZERO)
               for i, action in enumerate(path))


def replay(path: tuple[Action, ...]) -> Pair:
    value = ZERO
    for action in reversed(path):
        radix = RADICES[action.radix] if action.power == 1 else TAU4
        value = add(multiply(radix, value), action.digit)
    return value


def beam(start: Pair, choices: tuple[str, ...], add_cost: int,
         width: int = 8, max_actions: int = 180):
    if start == ZERO:
        return 0, (), 0
    frontier = {start: (0, ())}
    best = None
    expanded = 0
    for _ in range(max_actions):
        following = {}
        for value, (spent, path) in frontier.items():
            expanded += 1
            for action in actions(value, choices):
                q = action.quotient
                next_cost = spent + (factor_cost(action) if q != ZERO else 0)
                next_cost += add_cost * (action.digit != ZERO)
                if best is not None and next_cost >= best[0]:
                    continue
                next_path = path + (action,)
                if q == ZERO:
                    if best is None or next_cost < best[0]:
                        assert replay(next_path) == start
                        assert cost(next_path, add_cost) == next_cost
                        best = next_cost, next_path, expanded
                else:
                    old = following.get(q)
                    if old is None or next_cost < old[0]:
                        following[q] = next_cost, next_path
        if not following:
            break
        rank = lambda item: (item[1][0] + 7.5 * (norm(item[0]).bit_length() - 1),
                             item[1][0], item[0])
        frontier = dict(sorted(following.items(), key=rank)[:width])
    return best


def run(seed: int = 20261014, samples: int = 16, bits: int = 128,
        width: int = 8) -> dict:
    rng = random.Random(seed)
    inputs = []
    for _ in range(samples):
        a = rng.getrandbits(bits) * (-1 if rng.randrange(2) else 1)
        b = rng.getrandbits(bits) * (-1 if rng.randrange(2) else 1)
        inputs.append((a, b))
    rows = []
    for add_cost in (10, 16):
        for index, x in enumerate(inputs):
            arms = {}
            for name, choices in (("tau4", ("tau4",)),
                                  ("tau4_rho1", ("tau4", "rho1"))):
                result = beam(x, choices, add_cost, width)
                arms[name] = None if result is None else {
                    "cost": result[0], "actions": len(result[1]),
                    "tau4_digits": sum(action.power == 4 for action in result[1]),
                    "rho_steps": sum(action.radix == "rho" for action in result[1]),
                    "expanded": result[2], "replay_ok": replay(result[1]) == x}
            rows.append({"index": index, "input": x, "add_cost": add_cost, "arms": arms})
    summary = {}
    for add_cost in (10, 16):
        panel = [row for row in rows if row["add_cost"] == add_cost]
        complete = [row for row in panel if all(row["arms"].values())]
        savings = [row["arms"]["tau4"]["cost"] - row["arms"]["tau4_rho1"]["cost"]
                   for row in complete]
        summary[str(add_cost)] = {
            "complete": len(complete), "samples": samples,
            "mixed_better_count": sum(x > 0 for x in savings),
            "mean_saved": statistics.mean(savings) if savings else None,
            "median_saved": statistics.median(savings) if savings else None,
            "mean_tau4_cost": statistics.mean(row["arms"]["tau4"]["cost"]
                                         for row in complete) if complete else None,
            "mean_mixed_cost": statistics.mean(row["arms"]["tau4_rho1"]["cost"]
                                          for row in complete) if complete else None,
            "mean_mixed_rho_steps": statistics.mean(row["arms"]["tau4_rho1"]["rho_steps"]
                                               for row in complete) if complete else None,
            "mean_mixed_expanded": statistics.mean(row["arms"]["tau4_rho1"]["expanded"]
                                              for row in complete) if complete else None,
        }
    return {"schema": 1, "seed": seed, "samples": samples, "coordinate_bits": bits,
            "beam_width": width, "tau4_seed_count": len(TAU4_SEEDS),
            "tau4_digit_count": len(TAU4_DIGITS),
            "tau4_seeds": TAU4_SEEDS, "cost_model": {"tau1": 6, "tau4": 21,
                                                    "rho1": 13, "addition": [10, 16]},
            "summary": summary, "rows": rows}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
