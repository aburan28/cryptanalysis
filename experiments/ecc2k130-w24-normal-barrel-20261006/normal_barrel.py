"""Normal-basis conversion and an eight-layer GF(2^131) Frobenius barrel."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

PARENT = Path(__file__).resolve().parent.parent / "ecc2k130-orbit-closed-w24-seed-20261006"
sys.path.insert(0, str(PARENT))
from orbit_seed import DEGREE, FIELD_MASK, Span, square, w24_basis

LAYERS = (1, 2, 4, 8, 16, 32, 64, 128)


def rotate(code: int, shift: int) -> int:
    if not 0 <= code <= FIELD_MASK:
        raise ValueError("normal-basis code out of range")
    shift %= DEGREE
    if shift == 0:
        return code
    return ((code << shift) | (code >> (DEGREE - shift))) & FIELD_MASK


def barrel(code: int, exponent: int) -> int:
    if not 0 <= exponent < DEGREE:
        raise ValueError("Frobenius exponent must be in 0..130")
    if not 0 <= code <= FIELD_MASK:
        raise ValueError("normal-basis code out of range")
    for bit, shift in enumerate(LAYERS):
        if exponent & (1 << bit):
            code = rotate(code, shift)
    return code


def linear_xor_gates(columns: tuple[int, ...]) -> int:
    """Two-input XORs in a direct row-wise binary linear transform."""
    if not columns:
        return 0
    return sum(max(0, sum((column >> bit) & 1 for column in columns) - 1)
               for bit in range(DEGREE))


@dataclass(frozen=True)
class NormalBasis:
    element: int
    search_counter: int
    orbit: tuple[int, ...]
    reducer: Span
    w24_to_normal_columns: tuple[int, ...]

    @classmethod
    def first(cls, domain: str, max_counter: int) -> "NormalBasis":
        for counter in range(max_counter + 1):
            material = f"{domain}|{counter}".encode()
            element = int.from_bytes(hashlib.sha256(material).digest()[:17], "big") & FIELD_MASK
            if element == 0:
                continue
            values = [element]
            for _ in range(1, DEGREE):
                values.append(square(values[-1]))
            if square(values[-1]) != element:
                raise ArithmeticError("candidate Frobenius orbit has wrong period")
            try:
                reducer = Span.from_vectors(tuple(values))
            except ArithmeticError:
                continue
            object_basis = cls(element, counter, tuple(values), reducer, ())
            columns = tuple(object_basis.to_normal(word) for word in w24_basis())
            return cls(element, counter, tuple(values), reducer, columns)
        raise ArithmeticError("no full-rank normal element in frozen search range")

    def to_normal(self, polynomial_word: int) -> int:
        if not 0 <= polynomial_word <= FIELD_MASK:
            raise ValueError("polynomial-basis word out of range")
        code, _ = self.reducer.represent(polynomial_word)
        if code is None:
            raise ArithmeticError("normal basis failed to span the field")
        return code

    def to_polynomial(self, normal_code: int) -> int:
        if not 0 <= normal_code <= FIELD_MASK:
            raise ValueError("normal-basis code out of range")
        word = 0
        for bit, value in enumerate(self.orbit):
            if normal_code & (1 << bit):
                word ^= value
        return word

    def seed_code(self, mask: int) -> int:
        if not 0 < mask < (1 << 24):
            raise ValueError("nonzero W24 seed mask required")
        code = 0
        for bit, column in enumerate(self.w24_to_normal_columns):
            if mask & (1 << bit):
                code ^= column
        return code

    def gate_counts(self) -> dict[str, int]:
        seed_map_xors = linear_xor_gates(self.w24_to_normal_columns)
        output_map_xors = linear_xor_gates(self.orbit)
        muxes = DEGREE * len(LAYERS)
        return {
            "per_leaf_seed_map_xor": seed_map_xors,
            "per_leaf_barrel_mux": muxes,
            "per_leaf_barrel_and_equivalent": muxes,
            "per_leaf_barrel_xor_equivalent": 2 * muxes,
            "per_leaf_output_map_xor": output_map_xors,
            "five_leaf_seed_map_xor": 5 * seed_map_xors,
            "five_leaf_barrel_mux": 5 * muxes,
            "five_leaf_barrel_and_equivalent": 5 * muxes,
            "five_leaf_barrel_xor_equivalent": 10 * muxes,
            "five_leaf_output_map_xor": 5 * output_map_xors,
        }
