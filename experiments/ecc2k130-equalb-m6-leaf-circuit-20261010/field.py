"""Small independent polynomial-basis GF(2^131) reference for the leaf gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


DEGREE = 131
MODULUS = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
MASK = (1 << DEGREE) - 1
ROOT = Path(__file__).resolve().parents[2]
EQUAL = ROOT / "experiments/ecc2k130-normal4-equalb-m6-20261010"
NORMAL = ROOT / "experiments/ecc2k130-normal-weight4-base-20261009"
PARENT = ROOT / "experiments/ecc2k130-w24-normal-barrel-20261006/runs/R2/result.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


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
    if not value:
        raise ZeroDivisionError("zero has no field inverse")
    result = 1
    power = value
    exponent = (1 << DEGREE) - 2
    while exponent:
        if exponent & 1:
            result = multiply(result, power)
        power = square(power)
        exponent >>= 1
    return result


def trace(value: int) -> int:
    result = 0
    for _ in range(DEGREE):
        result ^= value
        value = square(value)
    if result not in (0, 1):
        raise ArithmeticError("field trace left GF(2)")
    return result


def halftrace(value: int) -> int:
    result = 0
    for _ in range((DEGREE + 1) // 2):
        result ^= value
        value = square(square(value))
    return result


def words(policy: str) -> list[int]:
    """Freeze the exact trace-zero field-parameter basis, in selector order."""
    if policy == "w24_source":
        return [(1 << j) ^ trace(1 << j) for j in range(1, 25)]
    if policy == "normal4_source":
        config = json.loads((NORMAL / "CONFIG.json").read_text())
        expected = config["parent_normal_basis"]["sha256"]
        if sha(PARENT) != expected:
            raise ValueError("normal-basis parent source hash changed")
        parent = json.loads(PARENT.read_text())
        basis = [int(value) for value in parent["normal_orbit_polynomial_words"]]
        if len(basis) != DEGREE or len(set(basis)) != DEGREE:
            raise ValueError("wrong normal-basis orbit")
        if any(trace(value) != 1 for value in basis):
            raise ValueError("normal-basis trace changed")
        return basis
    raise ValueError("unknown source factor-base policy")


def parameter(basis: list[int], selected: int) -> int:
    result = 0
    while selected:
        low = selected & -selected
        result ^= basis[low.bit_length() - 1]
        selected ^= low
    return result


def leaf_x(basis: list[int], selected: int) -> int:
    value = parameter(basis, selected)
    if not value or trace(value) != 0 or trace(inverse(value)) != 0:
        raise ValueError("mask does not identify a rational source leaf")
    half = halftrace(value)
    if square(half) ^ half != value:
        raise ArithmeticError("halftrace identity failed")
    result = 1 ^ inverse(half)
    if not result:
        raise ArithmeticError("nonzero parameter produced x=0")
    return result


def matrix_rows(columns: list[int]) -> list[int]:
    return [sum(((word >> bit) & 1) << index
                for index, word in enumerate(columns))
            for bit in range(DEGREE)]


def trace_row() -> int:
    return sum(trace(1 << index) << index for index in range(DEGREE))
