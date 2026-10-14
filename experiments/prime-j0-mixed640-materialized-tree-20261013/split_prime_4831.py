#!/usr/bin/env python3
"""Exact twenty-step Eisenstein radix screen for pi = 71 - tau."""

from collections import Counter
from hashlib import sha256
import json
from math import isqrt
from pathlib import Path

import model


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "selective-holdout.json"
PI = (71, -1)
NORM = 4831
STEPS = 20
DIGIT_BOUND = 1564
RADIUS = 56


def norm(a: int, b: int) -> int:
    return a*a + 3*a*b + 3*b*b


def multiply(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    a, b = left
    c, d = right
    return a*c-3*b*d, a*d+b*c+3*b*d


def unit_images(seed: int) -> tuple[tuple[int, int], ...]:
    return ((seed, 0), (-seed, 0), (seed, -seed), (-seed, seed),
            (-2*seed, seed), (2*seed, -seed))


def pair_images(a: int, b: int) -> tuple[tuple[int, int], ...]:
    return ((a, b), (-a, -b), (a+3*b, -a-2*b),
            (-a-3*b, a+2*b), (-2*a-3*b, a+b),
            (2*a+3*b, -a-b))


def build_digits() -> tuple[list[tuple[int, int, int, int]], list[int]]:
    codes: list[tuple[int, int, int, int] | None] = [None] * NORM
    codes[0] = (0, 0, 0, 0)
    seeds = [0]
    for seed in range(1, NORM):
        if codes[seed] is not None:
            continue
        index = len(seeds)
        seeds.append(seed)
        for unit, (da, db) in enumerate(unit_images(seed)):
            residue = (da + 71*db) % NORM
            assert codes[residue] is None
            codes[residue] = (index, unit, da, db)
    assert all(code is not None for code in codes)
    return [code for code in codes if code is not None], seeds


def step(pair: tuple[int, int],
         codes: list[tuple[int, int, int, int]]) -> tuple[tuple[int, int], tuple[int, int, int, int]]:
    a, b = pair
    digit = codes[(a + 71*b) % NORM]
    _, _, da, db = digit
    shifted_b = b - db
    numerator = a - da + 71*shifted_b
    k, remainder = divmod(numerator, NORM)
    assert remainder == 0
    quotient = (68*k-shifted_b, k)
    assert pair == tuple(x+y for x, y in zip((da, db), multiply(PI, quotient), strict=True))
    return quotient, digit


def run() -> dict:
    assert norm(*PI) == NORM
    assert all(NORM % d for d in range(2, isqrt(NORM)+1))
    assert 71*71 - 3*71 + 3 == NORM
    codes, seeds = build_digits()
    assert len(seeds) == 806 and seeds[-1] == DIGIT_BOUND
    assert all(norm(da, db) == seeds[index]**2
               for index, _, da, db in codes)
    assert len({(da+71*db) % NORM for _, _, da, db in codes}) == NORM

    order = model.mixed.screen.ORDER
    radii = [33*69**STEPS]
    assert order < 3*radii[0]**2
    for _ in range(STEPS):
        radii.append((radii[-1] + DIGIT_BOUND + 68)//69)
    assert radii[-1] == RADIUS
    assert all((radii[i]+DIGIT_BOUND)**2 < NORM*radii[i+1]**2
               for i in range(STEPS))

    terminal_points = [(a, b) for a in range(-2*RADIUS, 2*RADIUS+1)
                       for b in range(-2*RADIUS, 2*RADIUS+1)
                       if norm(a, b) < RADIUS**2]
    assert all(all(norm(*image) == norm(a, b)
                   for image in pair_images(a, b)) for a, b in terminal_points)
    terminal_orbits = {min(pair_images(a, b))
                       for a, b in terminal_points}
    assert len(terminal_points) == 11_359
    assert len(terminal_orbits) == 1_894
    # The orbit count is diagnostic; all points are checked by the norm test.
    cases = json.loads(FIXTURE.read_text())["cases"]
    assert len(cases) == 128
    max_terminal_norm = 0
    max_terminal_abs = [0, 0]
    counts = Counter()
    replay = sha256()
    for case in cases:
        scalar = int(case["scalar_hex"], 16) % order
        pair = model.mixed.screen.representative(scalar)
        state = pair
        digits = []
        for _ in range(STEPS):
            state, digit = step(state, codes)
            digits.append(digit)
        terminal = state
        for _, _, da, db in reversed(digits):
            x, y = multiply(PI, state)
            state = (x+da, y+db)
        assert state == pair
        assert (pair[0] + pair[1]*model.reference.LAMBDA_TAU-scalar) % order == 0
        assert norm(*terminal) < RADIUS**2
        max_terminal_norm = max(max_terminal_norm, norm(*terminal))
        max_terminal_abs = [max(max_terminal_abs[0], abs(terminal[0])),
                            max(max_terminal_abs[1], abs(terminal[1]))]
        counts[sum(index != 0 for index, _, _, _ in digits)] += 1
        replay.update(pair[0].to_bytes(17, "big", signed=True))
        replay.update(pair[1].to_bytes(17, "big", signed=True))
    return {
        "schema": 1,
        "pi": list(PI), "norm": NORM, "steps": STEPS,
        "canonical_seed_count_including_zero": len(seeds),
        "max_canonical_seed": max(seeds),
        "radius_bound": RADIUS,
        "radius_sequence": radii,
        "terminal_ball_points": len(terminal_points),
        "terminal_orbit_representatives": len(terminal_orbits),
        "direct_two_x_digit_bytes": STEPS*len(seeds)*96,
        "holdout_cases": len(cases),
        "holdout_max_terminal_norm": max_terminal_norm,
        "holdout_max_abs_terminal_coordinates": max_terminal_abs,
        "holdout_nonzero_digit_counts": dict(sorted(counts.items())),
        "fixture_sha256": sha256(FIXTURE.read_bytes()).hexdigest(),
        "replay_sha256": replay.hexdigest(),
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "exact quotient and radius screen; native evaluator pending",
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
