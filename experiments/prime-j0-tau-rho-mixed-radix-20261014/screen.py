#!/usr/bin/env python3
"""Bounded operation-cost screen for mixed tau/rho Eisenstein radix chains."""

from collections import Counter
from dataclasses import dataclass
import json
import random
import statistics


Pair = tuple[int, int]  # a + b omega, omega^2 + omega + 1 = 0.
ZERO: Pair = (0, 0)
UNITS: tuple[Pair, ...] = (ZERO, (1, 0), (-1, 0), (0, 1), (0, -1), (-1, -1), (1, 1))
RADICES: dict[str, Pair] = {"tau": (1, -1), "rho": (2, -1)}
NORM: dict[str, int] = {"tau": 3, "rho": 7}
ENDO_COST: dict[str, int] = {"tau": 6, "rho": 13}  # S=M, from supplied formulas.


def add(x: Pair, y: Pair) -> Pair:
    return x[0] + y[0], x[1] + y[1]


def subtract(x: Pair, y: Pair) -> Pair:
    return x[0] - y[0], x[1] - y[1]


def multiply(x: Pair, y: Pair) -> Pair:
    a, b = x
    c, d = y
    return a * c - b * d, a * d + b * c - b * d


def norm(x: Pair) -> int:
    a, b = x
    return a * a - a * b + b * b


def quotient_if_divisible(x: Pair, radix: str) -> Pair | None:
    a, b = x
    if radix == "tau":
        qa, qb, divisor = 2 * a - b, a + b, 3
    elif radix == "rho":
        qa, qb, divisor = 3 * a - b, a + 2 * b, 7
    else:
        raise ValueError(radix)
    if qa % divisor or qb % divisor:
        return None
    result = qa // divisor, qb // divisor
    assert multiply(RADICES[radix], result) == x
    return result


def next_steps(x: Pair, choices: tuple[str, ...]):
    for radix in choices:
        for digit in UNITS:
            q = quotient_if_divisible(subtract(x, digit), radix)
            if q is not None:
                yield radix, digit, q


def replay(path: tuple[tuple[str, Pair], ...]) -> Pair:
    result = ZERO
    for radix, digit in reversed(path):
        result = add(multiply(RADICES[radix], result), digit)
    return result


def path_cost(path: tuple[tuple[str, Pair], ...], add_cost: int) -> int:
    result = 0
    for i, (radix, digit) in enumerate(path):
        result += (ENDO_COST[radix] if i + 1 < len(path) else 0)
        result += add_cost * (digit != ZERO)
    return result


@dataclass(frozen=True)
class Result:
    cost: int
    path: tuple[tuple[str, Pair], ...]
    expanded: int


def beam_recode(start: Pair, choices: tuple[str, ...], add_cost: int,
                width: int = 128, max_steps: int = 190) -> Result | None:
    if start == ZERO:
        return Result(0, (), 0)
    frontier: dict[Pair, tuple[int, tuple[tuple[str, Pair], ...]]] = {start: (0, ())}
    best: Result | None = None
    expanded = 0
    for _ in range(max_steps):
        next_frontier: dict[Pair, tuple[int, tuple[tuple[str, Pair], ...]]] = {}
        for value, (cost, path) in frontier.items():
            expanded += 1
            for radix, digit, q in next_steps(value, choices):
                step = add_cost * (digit != ZERO) + (ENDO_COST[radix] if q != ZERO else 0)
                new_cost = cost + step
                if best is not None and new_cost >= best.cost:
                    continue
                new_path = path + ((radix, digit),)
                if q == ZERO:
                    if best is None or new_cost < best.cost:
                        assert replay(new_path) == start
                        assert path_cost(new_path, add_cost) == new_cost
                        best = Result(new_cost, new_path, expanded)
                    continue
                old = next_frontier.get(q)
                if old is None or new_cost < old[0]:
                    next_frontier[q] = new_cost, new_path
        if not next_frontier:
            break
        # The heuristic affects beam retention only; its score is not a cost claim.
        rank = lambda item: (item[1][0] + 7.5 * (norm(item[0]).bit_length() - 1),
                             item[1][0], item[0])
        frontier = dict(sorted(next_frontier.items(), key=rank)[:width])
    return None if best is None else Result(best.cost, best.path, expanded)


def greedy_recode(start: Pair, choices: tuple[str, ...], add_cost: int,
                  max_steps: int = 190) -> Result | None:
    """One-step choice with at most four divisions at each radix position."""
    if start == ZERO:
        return Result(0, (), 0)
    value = start
    path = []
    expanded = 0
    for _ in range(max_steps):
        current_norm = norm(value)
        candidates = []
        for radix, digit, q in next_steps(value, choices):
            expanded += 1
            qnorm = norm(q)
            if q != ZERO and qnorm >= current_norm:
                continue
            step = add_cost * (digit != ZERO) + (ENDO_COST[radix] if q != ZERO else 0)
            score = step + (7.5 * (qnorm.bit_length() - 1) if q != ZERO else 0)
            candidates.append((score, step, qnorm, radix, digit, q))
        if not candidates:
            return None
        _, _, _, radix, digit, q = min(candidates)
        path.append((radix, digit))
        value = q
        if value == ZERO:
            answer = tuple(path)
            assert replay(answer) == start
            return Result(path_cost(answer, add_cost), answer, expanded)
    return None


def selftest():
    for radix, value in RADICES.items():
        assert norm(value) == NORM[radix]
        for a in range(-12, 13):
            for b in range(-12, 13):
                x = (a, b)
                allowed = list(next_steps(x, (radix,)))
                assert allowed
                expected = 1 if quotient_if_divisible(x, radix) is not None else (
                    3 if radix == "tau" else 1)
                assert len(allowed) == expected, (radix, x, allowed)
                for name, digit, q in allowed:
                    assert add(multiply(RADICES[name], q), digit) == x


def run(seed: int = 20261014, samples: int = 16, bits: int = 128,
        width: int = 128) -> dict:
    selftest()
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
            for name, choices in (("tau", ("tau",)), ("rho", ("rho",)),
                                  ("mixed", ("tau", "rho"))):
                result = beam_recode(x, choices, add_cost, width)
                arms[name] = None if result is None else {
                    "cost": result.cost, "steps": len(result.path),
                    "nonzero_digits": sum(d != ZERO for _, d in result.path),
                    "rho_steps": sum(r == "rho" for r, _ in result.path),
                    "expanded": result.expanded,
                    "replay_ok": replay(result.path) == x}
            rows.append({"index": index, "input": x, "add_cost": add_cost, "arms": arms})
    summary = {}
    for add_cost in (10, 16):
        panel = [row for row in rows if row["add_cost"] == add_cost]
        complete = [row for row in panel if all(row["arms"].values())]
        savings = [min(row["arms"]["tau"]["cost"], row["arms"]["rho"]["cost"])
                   - row["arms"]["mixed"]["cost"] for row in complete]
        summary[str(add_cost)] = {
            "complete": len(complete), "samples": samples,
            "mixed_better_count": sum(value > 0 for value in savings),
            "mean_saved_vs_better_single_radix": statistics.mean(savings) if savings else None,
            "median_saved_vs_better_single_radix": statistics.median(savings) if savings else None,
            "mean_arm_costs": {name: statistics.mean(row["arms"][name]["cost"] for row in complete)
                               if complete else None for name in ("tau", "rho", "mixed")},
            "mixed_rho_steps_histogram": dict(Counter(row["arms"]["mixed"]["rho_steps"]
                                               for row in complete)),
        }
    return {"schema": 1, "seed": seed, "samples": samples, "input_coordinate_bits": bits,
            "beam_width": width, "max_steps": 190, "endomorphism_cost": ENDO_COST,
            "addition_costs": [10, 16], "summary": summary, "rows": rows}


def run_greedy(seed: int = 20261014, samples: int = 16, bits: int = 128) -> dict:
    selftest()
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
            for name, choices in (("tau", ("tau",)), ("rho", ("rho",)),
                                  ("mixed", ("tau", "rho"))):
                result = greedy_recode(x, choices, add_cost)
                arms[name] = None if result is None else {
                    "cost": result.cost, "steps": len(result.path),
                    "nonzero_digits": sum(d != ZERO for _, d in result.path),
                    "rho_steps": sum(r == "rho" for r, _ in result.path),
                    "expanded": result.expanded,
                    "replay_ok": replay(result.path) == x}
            rows.append({"index": index, "input": x, "add_cost": add_cost, "arms": arms})
    summary = {}
    for add_cost in (10, 16):
        panel = [row for row in rows if row["add_cost"] == add_cost]
        complete = [row for row in panel if all(row["arms"].values())]
        savings = [min(row["arms"]["tau"]["cost"], row["arms"]["rho"]["cost"])
                   - row["arms"]["mixed"]["cost"] for row in complete]
        summary[str(add_cost)] = {
            "complete": len(complete), "samples": samples,
            "mixed_better_count": sum(value > 0 for value in savings),
            "mean_saved_vs_better_single_radix": statistics.mean(savings) if savings else None,
            "median_saved_vs_better_single_radix": statistics.median(savings) if savings else None,
            "mean_arm_costs": {name: statistics.mean(row["arms"][name]["cost"] for row in complete)
                               if complete else None for name in ("tau", "rho", "mixed")},
            "mean_mixed_candidate_divisions": statistics.mean(
                row["arms"]["mixed"]["expanded"] for row in complete) if complete else None,
        }
    return {"schema": 1, "strategy": "greedy_one_step", "seed": seed,
            "samples": samples, "input_coordinate_bits": bits,
            "endomorphism_cost": ENDO_COST, "addition_costs": [10, 16],
            "summary": summary, "rows": rows}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
