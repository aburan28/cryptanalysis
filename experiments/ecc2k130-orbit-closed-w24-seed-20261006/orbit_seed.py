"""Implicit W24 Frobenius-closure membership over polynomial GF(2^131)."""

from __future__ import annotations

from dataclasses import dataclass

DEGREE = 131
FIELD_MASK = (1 << DEGREE) - 1
MODULUS = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
SQUARE_BYTE = tuple(sum(((byte >> bit) & 1) << (2 * bit) for bit in range(8))
                    for byte in range(256))


def square(word: int) -> int:
    """Square a polynomial-basis field word; reject noncanonical encodings."""
    if not 0 <= word <= FIELD_MASK:
        raise ValueError("field word outside GF(2^131)")
    doubled = 0
    for byte_index in range(17):
        doubled |= SQUARE_BYTE[(word >> (8 * byte_index)) & 255] << (16 * byte_index)
    while doubled.bit_length() > DEGREE:
        doubled ^= MODULUS << (doubled.bit_length() - DEGREE - 1)
    return doubled


def frobenius(word: int, exponent: int) -> int:
    if not 0 <= exponent < DEGREE:
        raise ValueError("Frobenius exponent outside 0..130")
    for _ in range(exponent):
        word = square(word)
    return word


def trace(word: int) -> int:
    total = 0
    value = word
    for _ in range(DEGREE):
        total ^= value
        value = square(value)
    if value != word or total not in (0, 1):
        raise ArithmeticError("GF(2^131) trace/fixed-field check failed")
    return total


def w24_basis() -> tuple[int, ...]:
    basis = tuple((1 << j) ^ trace(1 << j) for j in range(1, 25))
    if len(set(basis)) != 24 or any(trace(value) for value in basis):
        raise ArithmeticError("W24 basis failed trace-zero check")
    return basis


def seed_from_mask(mask: int, basis: tuple[int, ...]) -> int:
    if not 0 < mask < (1 << len(basis)):
        raise ValueError("W24 seed mask must be nonzero and in range")
    word = 0
    for bit, value in enumerate(basis):
        if mask & (1 << bit):
            word ^= value
    return word


@dataclass(frozen=True)
class Span:
    # Each pivot carries its original W24 coefficient mask as well as its word.
    pivots: dict[int, tuple[int, int]]

    @classmethod
    def from_vectors(cls, vectors: tuple[int, ...]) -> "Span":
        pivots: dict[int, tuple[int, int]] = {}
        for bit, vector in enumerate(vectors):
            word, mask = vector, 1 << bit
            while word:
                lead = word.bit_length() - 1
                old = pivots.get(lead)
                if old is None:
                    pivots[lead] = (word, mask)
                    break
                word ^= old[0]
                mask ^= old[1]
            else:
                raise ArithmeticError("conjugate W24 vectors are dependent")
        return cls(pivots)

    def represent(self, word: int) -> tuple[int | None, int]:
        mask = 0
        reductions = 0
        while word:
            old = self.pivots.get(word.bit_length() - 1)
            if old is None:
                return None, reductions
            word ^= old[0]
            mask ^= old[1]
            reductions += 1
        return mask, reductions


class OrbitClosedW24:
    def __init__(self) -> None:
        self.basis = w24_basis()
        vectors = self.basis
        spaces = []
        for _ in range(DEGREE):
            spaces.append(Span.from_vectors(vectors))
            vectors = tuple(square(value) for value in vectors)
        if vectors != self.basis:
            raise ArithmeticError("Frobenius did not return after 131 steps")
        self.spaces = tuple(spaces)

    def witnesses(self, word: int) -> tuple[list[dict[str, int]], int]:
        if not 0 <= word <= FIELD_MASK:
            raise ValueError("field word outside GF(2^131)")
        if word == 0:
            return [], 0  # The factor base deliberately excludes zero seeds.
        found: list[dict[str, int]] = []
        reductions = 0
        for exponent, space in enumerate(self.spaces):
            mask, count = space.represent(word)
            reductions += count
            if mask is not None:
                if mask == 0 or frobenius(seed_from_mask(mask, self.basis), exponent) != word:
                    raise ArithmeticError("subspace witness failed reconstruction")
                found.append({"exponent": exponent, "mask": mask})
        return found, reductions
