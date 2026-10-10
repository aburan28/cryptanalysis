"""Polynomial-basis GF(2^131) reference for Q1420 circuit construction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INPUT = ROOT / "experiments/ecc2k130-263-equal-w24-workload-20261005"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
CODEGEN = ROOT / "ecc2k130/runner/codegen"
DEGREE = 131
MASK = (1 << DEGREE) - 1
MODULUS = (1 << DEGREE) | (1 << 13) | 7


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def reduce(value: int) -> int:
    while value.bit_length() > DEGREE:
        value ^= MODULUS << (value.bit_length() - DEGREE - 1)
    return value


def multiply(left: int, right: int) -> int:
    product = 0
    while right:
        if right & 1:
            product ^= left
        right >>= 1
        left <<= 1
    return reduce(product)


def square(value: int) -> int:
    spread = 0
    while value:
        low = value & -value
        spread ^= 1 << (2 * (low.bit_length() - 1))
        value ^= low
    return reduce(spread)


def inverse(value: int) -> int:
    if value == 0:
        raise ZeroDivisionError("zero has no inverse")
    result, power = 1, value
    exponent = (1 << DEGREE) - 2
    while exponent:
        if exponent & 1:
            result = multiply(result, power)
        power = square(power)
        exponent >>= 1
    return result


def trace(value: int) -> int:
    total = 0
    for _ in range(DEGREE):
        total ^= value
        value = square(value)
    if total not in (0, 1):
        raise ArithmeticError("trace left GF(2)")
    return total


def halftrace(value: int) -> int:
    total = 0
    for _ in range((DEGREE + 1) // 2):
        total ^= value
        value = square(square(value))
    return total


def basis() -> list[int]:
    return [(1 << j) ^ trace(1 << j) for j in range(1, 25)]


def parameter(words: list[int], selected: int) -> int:
    result = 0
    while selected:
        low = selected & -selected
        result ^= words[low.bit_length() - 1]
        selected ^= low
    return result


def matrix_rows(columns: list[int]) -> list[int]:
    return [sum(((word >> bit) & 1) << index
                for index, word in enumerate(columns))
            for bit in range(DEGREE)]


def trace_row(scale: int) -> int:
    return sum(trace(multiply(scale, 1 << bit)) << bit
               for bit in range(DEGREE))


def coefficients(policy: str) -> tuple[int, int]:
    if policy == "source":
        return 1, 1
    if policy != "descendant_native":
        raise ValueError("unknown policy")
    route = read(ROUTE)
    coeffs = route["curve_nodes"]["target"]["coefficients_a1_a2_a3_a4_a6"]
    a, b_raw = int(coeffs[3]), int(coeffs[4])
    b = b_raw ^ square(a)
    alpha = b
    for _ in range(DEGREE - 2):
        alpha = square(alpha)
    if square(square(alpha)) != b:
        raise ArithmeticError("wrong normalized fourth root")
    return alpha, b


def s3(left: int, middle: int, right: int, b: int) -> int:
    ac = multiply(left, right)
    pair = ac ^ multiply(middle, left ^ right)
    return square(pair) ^ multiply(middle, ac) ^ b


def leaf(mask: int, alpha: int) -> tuple[int, int, int]:
    w = parameter(basis(), mask)
    if w == 0 or trace(w) != 0:
        raise ValueError("invalid W24 parameter")
    u = halftrace(w)
    if square(u) ^ u != w:
        raise ArithmeticError("halftrace identity failed")
    z = inverse(w)
    if trace(multiply(alpha, z)) != 0:
        raise ValueError("mask is outside the rational base")
    x = multiply(alpha, 1 ^ inverse(u))
    if x == 0 or multiply(u, x ^ alpha) != alpha:
        raise ArithmeticError("invalid rational leaf x")
    return x, z, w
