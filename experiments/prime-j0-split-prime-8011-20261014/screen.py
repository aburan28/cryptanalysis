#!/usr/bin/env python3
"""Exact 19-position screen for the Eisenstein radix 91 - tau."""

from collections import Counter
from hashlib import sha256
import json
from math import isqrt
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-mixed640-materialized-tree-20261013"
sys.path.insert(0, str(PARENT))
import model  # noqa: E402


PI = (91, -1)
Q = 8011
STEPS = 19
DIGIT_BOUND = 2640
TERMINAL_RADIUS = 46
FIXTURE = PARENT / "selective-holdout.json"


def norm(a: int, b: int) -> int:
    return a * a + 3 * a * b + 3 * b * b


def multiply(x: tuple[int, int], y: tuple[int, int]) -> tuple[int, int]:
    a, b = x
    c, d = y
    return a * c - 3 * b * d, a * d + b * c + 3 * b * d


def unit_images(seed: int) -> tuple[tuple[int, int], ...]:
    return ((seed, 0), (-seed, 0), (seed, -seed), (-seed, seed),
            (-2 * seed, seed), (2 * seed, -seed))


def digits() -> tuple[list[tuple[int, int, int, int]], list[int]]:
    codes: list[tuple[int, int, int, int] | None] = [None] * Q
    codes[0] = (0, 0, 0, 0)
    seeds = [0]
    for seed in range(1, Q):
        if codes[seed] is not None:
            continue
        index = len(seeds)
        seeds.append(seed)
        for unit, (da, db) in enumerate(unit_images(seed)):
            residue = (da + 91 * db) % Q
            assert codes[residue] is None
            codes[residue] = (index, unit, da, db)
    assert all(code is not None for code in codes)
    return [code for code in codes if code is not None], seeds


def step(pair: tuple[int, int],
         codes: list[tuple[int, int, int, int]]) -> tuple[tuple[int, int], tuple[int, int, int, int]]:
    a, b = pair
    digit = codes[(a + 91 * b) % Q]
    _, _, da, db = digit
    shifted_b = b - db
    k, remainder = divmod(a - da + 91 * shifted_b, Q)
    assert remainder == 0
    nxt = (88 * k - shifted_b, k)
    product = multiply(PI, nxt)
    assert (a, b) == (da + product[0], db + product[1])
    return nxt, digit


def radii(order: int) -> list[int]:
    result = [isqrt(order // 3) + 1]
    for _ in range(STEPS):
        previous = result[-1]
        result.append(isqrt((previous + DIGIT_BOUND) ** 2 // Q) + 1)
    assert order < 3 * result[0] ** 2
    assert all((result[i] + DIGIT_BOUND) ** 2 < Q * result[i+1] ** 2
               for i in range(STEPS))
    return result


def run() -> dict:
    assert norm(*PI) == Q
    assert all(Q % d for d in range(2, isqrt(Q) + 1))
    codes, seeds = digits()
    assert len(seeds) == 1336 and seeds[-1] == DIGIT_BOUND
    assert len({(da + 91 * db) % Q for _, _, da, db in codes}) == Q
    assert all(norm(da, db) == seeds[index] ** 2
               for index, _, da, db in codes)
    radius = radii(model.mixed.screen.ORDER)
    assert radius[-1] == TERMINAL_RADIUS
    terminal_pairs = [(a, b) for a in range(2 * TERMINAL_RADIUS)
                      for b in range(-2 * TERMINAL_RADIUS, 2 * TERMINAL_RADIUS + 1)
                      if (a > 0 or b >= 0) and norm(a, b) < TERMINAL_RADIUS ** 2]
    assert len(terminal_pairs) == 3838
    cases = json.loads(FIXTURE.read_text())["cases"]
    assert len(cases) == 128
    counts = Counter()
    max_terminal_norm = 0
    replay = sha256()
    for case in cases:
        scalar = int(case["scalar_hex"], 16) % model.mixed.screen.ORDER
        pair = model.mixed.screen.representative(scalar)
        state = pair
        trace = []
        for _ in range(STEPS):
            state, digit = step(state, codes)
            trace.append(digit)
        terminal = state
        for _, _, da, db in reversed(trace):
            product = multiply(PI, state)
            state = (product[0] + da, product[1] + db)
        assert state == pair
        assert (pair[0] + pair[1] * model.reference.LAMBDA_TAU - scalar) % model.mixed.screen.ORDER == 0
        assert norm(*terminal) < TERMINAL_RADIUS ** 2
        max_terminal_norm = max(max_terminal_norm, norm(*terminal))
        counts[sum(index != 0 for index, _, _, _ in trace)] += 1
        replay.update(pair[0].to_bytes(17, "big", signed=True))
        replay.update(pair[1].to_bytes(17, "big", signed=True))
    digit_bytes = STEPS * len(seeds) * 64
    terminal_bytes = len(terminal_pairs) * 64
    return {
        "schema": 1,
        "pi": list(PI), "norm": Q, "steps": STEPS,
        "canonical_seed_count_including_zero": len(seeds),
        "max_canonical_seed": seeds[-1],
        "radius_sequence": radius,
        "terminal_radius": TERMINAL_RADIUS,
        "terminal_sign_canonical_pairs": len(terminal_pairs),
        "digit_point_bytes_at_64_each": digit_bytes,
        "terminal_point_bytes_at_64_each": terminal_bytes,
        "six_byte_residue_lut_bytes": Q * 6,
        "minimum_payload_bytes_before_metadata": digit_bytes + terminal_bytes + Q * 6,
        "fixture_cases": len(cases),
        "fixture_max_terminal_norm": max_terminal_norm,
        "fixture_nonzero_digit_counts": dict(sorted(counts.items())),
        "fixture_sha256": sha256(FIXTURE.read_bytes()).hexdigest(),
        "representative_replay_sha256": replay.hexdigest(),
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "integer radix, exact norm bound and frozen scalar replay; native field operations pending",
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
