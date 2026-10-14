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


def short_variant_screen(cases: list[dict], screen, initial_bound: int) -> dict:
    """Exact 20-digit norm-5113 screen with the same frozen representatives."""
    short_norm = 5113
    short_pi = (70, 1)
    steps = 20
    digit_limit = short_norm // 2
    assert norm(short_pi) == short_norm
    assert all(short_norm % d for d in range(2, isqrt(short_norm) + 1))
    assert 35**2 * screen.ORDER < 3 * 682**2 * 71**40
    assert 2 * (70 * initial_bound + digit_limit * 71**steps) < (
        499 * 70 * 71**steps)
    pair_digits = [(a, b) for a in range(112) for b in range(-65, 66)
                   if norm((a, b)) < 56**2 and (a > 0 or b >= 0)]
    assert len(pair_digits) == 5680 and pair_digits[0] == (0, 0)
    max_terminal_norm = 0
    max_terminal_coords = [0, 0]
    term_counts = Counter()
    for case in cases:
        scalar = int(case["scalar_hex"], 16) % screen.ORDER
        pair = screen.representative(scalar)
        digits = []
        quotient = pair
        for _ in range(steps):
            a, b = quotient
            digit = (a - 70 * b) % short_norm
            if digit > digit_limit:
                digit -= short_norm
            numerator = a - 70 * b - digit
            assert numerator % short_norm == 0
            k = numerator // short_norm
            quotient = 73 * k + b, -k
            digits.append(digit)
        recovered = quotient
        for digit in reversed(digits):
            recovered = multiply(short_pi, recovered)
            recovered = recovered[0] + digit, recovered[1]
        assert recovered == pair
        assert norm(quotient) < 56**2
        max_terminal_norm = max(max_terminal_norm, norm(quotient))
        max_terminal_coords = [max(max_terminal_coords[i], abs(quotient[i]))
                               for i in (0, 1)]
        term_counts[str(sum(d != 0 for d in digits)
                        + (quotient != (0, 0)))] += 1
    entries = steps * (digit_limit + 1) + 2 * 500 + len(pair_digits)
    return {
        "pi_tau_coordinates": list(short_pi),
        "pi_norm": short_norm,
        "steps": steps,
        "digit_bound": digit_limit,
        "terminal_axis_coordinate_bound": 499,
        "fused_terminal_norm_bound_exclusive": 56**2,
        "fused_terminal_canonical_pairs": len(pair_digits),
        "table_entries_including_zero": entries,
        "table_point_bytes": entries * 64,
        "holdout_max_terminal_norm": max_terminal_norm,
        "holdout_max_abs_terminal_coordinates": max_terminal_coords,
        "holdout_nonzero_point_terms": dict(sorted(term_counts.items())),
    }


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
        "short_variant": short_variant_screen(cases, screen, initial_magnitude_bound),
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
