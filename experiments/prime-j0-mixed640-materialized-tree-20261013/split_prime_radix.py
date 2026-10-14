#!/usr/bin/env python3
"""Exact split-prime radix model for the secp256k1 tau lattice."""

from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from math import isqrt
from pathlib import Path
import sys

import model


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "selective-holdout.json"
PI = (86, -21)
NORM = 3301
TAU_RESIDUE = 1576
STEPS = 21
TERMINAL_LIMIT = 663


def multiply(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    a, b = left
    c, d = right
    return a * c - 3 * b * d, a * d + b * c + 3 * b * d


def norm(pair: tuple[int, int]) -> int:
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def step(pair: tuple[int, int]) -> tuple[tuple[int, int], int]:
    a, b = pair
    digit = (a + TAU_RESIDUE * b) % NORM
    if digit > NORM // 2:
        digit -= NORM
    shifted = a - digit
    numerator = 23 * shifted - 63 * b, 21 * shifted + 86 * b
    assert numerator[0] % NORM == numerator[1] % NORM == 0
    quotient = numerator[0] // NORM, numerator[1] // NORM
    assert (a, b) == tuple(x + y for x, y in zip(
        multiply(PI, quotient), (digit, 0), strict=True))
    return quotient, digit


def recode(pair: tuple[int, int]) -> tuple[list[int], tuple[int, int]]:
    digits = []
    for _ in range(STEPS):
        pair, digit = step(pair)
        digits.append(digit)
    return digits, pair


def evaluate() -> dict:
    assert norm(PI) == NORM
    assert all(NORM % d for d in range(2, isqrt(NORM) + 1))
    assert (TAU_RESIDUE * TAU_RESIDUE - 3 * TAU_RESIDUE + 3) % NORM == 0
    assert (PI[0] + PI[1] * TAU_RESIDUE) % NORM == 0
    screen = model.mixed.screen
    det = screen.W[0] * screen.V[1] - screen.W[1] * screen.V[0]
    assert det == screen.ORDER
    coordinate_bound = [abs(screen.W[i]) + abs(screen.V[i]) for i in (0, 1)]
    initial_magnitude_bound = coordinate_bound[0] + 2 * coordinate_bound[1]
    # |tau|=sqrt(3)<2 and |pi|=sqrt(3301)>57. The representative is
    # selected from the four floor/ceil corners of the determinant-one
    # lattice cell, so each initial coordinate obeys coordinate_bound.
    terminal_magnitude_bound = (Fraction(initial_magnitude_bound, 57**STEPS)
                                + Fraction(NORM // 2, 56))
    # N(a+b*tau) >= a^2/4 and >= 3b^2/4, hence either coordinate is
    # strictly smaller than twice the complex magnitude.
    assert 2 * terminal_magnitude_bound < TERMINAL_LIMIT

    raw = FIXTURE.read_bytes()
    cases = json.loads(raw)["cases"]
    counts = Counter()
    terminal_max = [0, 0]
    maximum_digit = 0
    replay = sha256()
    for case in cases:
        scalar = int(case["scalar_hex"], 16) % screen.ORDER
        pair = screen.representative(scalar)
        digits, terminal = recode(pair)
        recovered = terminal
        for digit in reversed(digits):
            recovered = multiply(PI, recovered)
            recovered = recovered[0] + digit, recovered[1]
        assert recovered == pair
        assert (pair[0] + pair[1] * model.reference.LAMBDA_TAU - scalar) % screen.ORDER == 0
        assert all(abs(x) <= TERMINAL_LIMIT for x in terminal)
        terminal_max = [max(terminal_max[i], abs(terminal[i])) for i in (0, 1)]
        maximum_digit = max(maximum_digit, *(abs(d) for d in digits))
        counts[str(sum(d != 0 for d in digits) + sum(t != 0 for t in terminal))] += 1
        replay.update(pair[0].to_bytes(17, "big", signed=True))
        replay.update(pair[1].to_bytes(17, "big", signed=True))
        replay.update(b"".join(d.to_bytes(2, "big", signed=True) for d in digits))
        replay.update(terminal[0].to_bytes(2, "big", signed=True))
        replay.update(terminal[1].to_bytes(2, "big", signed=True))

    # The second terminal row stores tau([m]B), avoiding a runtime tau map.
    entries = STEPS * (NORM // 2 + 1) + 2 * (TERMINAL_LIMIT + 1)
    return {
        "schema": 1,
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_sha256": sha256(raw).hexdigest(),
        "pi_tau_coordinates": list(PI),
        "pi_norm": NORM,
        "tau_mod_pi": TAU_RESIDUE,
        "steps": STEPS,
        "digit_bound": NORM // 2,
        "terminal_coordinate_bound": TERMINAL_LIMIT,
        "initial_coordinate_bounds": coordinate_bound,
        "initial_magnitude_upper_bound": initial_magnitude_bound,
        "terminal_magnitude_upper_bound_numerator": terminal_magnitude_bound.numerator,
        "terminal_magnitude_upper_bound_denominator": terminal_magnitude_bound.denominator,
        "table_entries_including_zero": entries,
        "table_point_bytes": 64 * entries,
        "atlas_bytes": 0,
        "holdout_cases": len(cases),
        "holdout_max_abs_digit": maximum_digit,
        "holdout_terminal_max_abs_coordinates": terminal_max,
        "holdout_nonzero_point_terms": dict(sorted(counts.items())),
        "holdout_recode_sha256": replay.hexdigest(),
    }


if __name__ == "__main__":
    result = evaluate()
    path = HERE / "split-prime-radix.json"
    if sys.argv[1:] == ["--write"]:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    elif sys.argv[1:] == []:
        assert json.loads(path.read_text()) == result
    else:
        raise SystemExit("usage: split_prime_radix.py [--write]")
    print(json.dumps({key: result[key] for key in (
        "table_entries_including_zero", "table_point_bytes", "atlas_bytes",
        "holdout_terminal_max_abs_coordinates", "holdout_nonzero_point_terms")},
        sort_keys=True))
