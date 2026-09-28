#!/usr/bin/env python3
"""Compact one-step multihomogeneous Macaulay reduction over GF(2).

Rows are packed as Python integer bitsets indexed by the 24-bit Boolean
monomial mask.  Multiplication by one coefficient variable is a pairwise
bit-lane transform implementing x_j^2 = x_j after dehomogenization.  The
base and its three neighboring block-degree components are reduced apart.
Only reduced rows supported entirely on the requested low-degree monomials
are returned as search consequences; this is a conservative extraction.
"""

from __future__ import annotations

import itertools
import ctypes
import subprocess
import tempfile
import time
from functools import lru_cache
from pathlib import Path


def sparse_to_bits(poly: set[int], nvars: int) -> int:
    """Pack a squarefree-monomial support into a bit indexed by monomial mask."""
    nmonomials = 1 << nvars
    packed = bytearray((nmonomials + 7) // 8)
    for monomial in poly:
        packed[monomial >> 3] ^= 1 << (monomial & 7)
    return int.from_bytes(packed, "little")


def bits_to_sparse(packed: int,
                   degree_order: MonomialDegreeOrder | None = None) -> set[int]:
    """Unpack a coefficient bitset into squarefree monomial masks."""
    result = set()
    while packed:
        one = packed & -packed
        position = one.bit_length() - 1
        result.add(degree_order.monomial(position) if degree_order else position)
        packed ^= one
    return result


class MonomialDegreeOrder:
    """C-assisted permutation from monomial masks to degree-then-mask order."""

    def __init__(self, nvars: int, source: Path):
        if not 1 <= nvars <= 24:
            raise ValueError("degree order supports between 1 and 24 variables")
        self.nvars = nvars
        self.nmonomials = 1 << nvars
        self.nbytes = self.nmonomials // 8
        self._temporary = tempfile.TemporaryDirectory(prefix="ic-monomial-order-")
        library_path = Path(self._temporary.name) / "libmonomial_degree_order.so"
        started = time.perf_counter()
        subprocess.run(["cc", "-O3", "-std=c11", "-shared", "-fPIC",
                        str(source), "-o", str(library_path)],
                       check=True, capture_output=True, text=True)
        self.compile_seconds = time.perf_counter() - started
        self._library = ctypes.CDLL(str(library_path))
        self._library.degree_order_init.argtypes = [ctypes.c_int]
        self._library.degree_order_init.restype = ctypes.c_int
        self._library.degree_order_rank_map.restype = ctypes.POINTER(ctypes.c_uint32)
        self._library.degree_order_inverse_map.restype = ctypes.POINTER(ctypes.c_uint32)
        self._library.degree_order_reorder_bits.argtypes = [
            ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint8)]
        self._library.degree_order_reorder_bits.restype = ctypes.c_int
        started = time.perf_counter()
        if self._library.degree_order_init(nvars) != 0:
            raise RuntimeError("failed to initialize monomial degree permutation")
        self._rank_map = self._library.degree_order_rank_map()
        self._inverse_map = self._library.degree_order_inverse_map()
        self.initialize_seconds = time.perf_counter() - started

    def rank(self, monomial: int) -> int:
        return int(self._rank_map[monomial])

    def monomial(self, rank: int) -> int:
        return int(self._inverse_map[rank])

    def reorder(self, packed: int) -> int:
        source_bytes = packed.to_bytes(self.nbytes, "little")
        source = (ctypes.c_uint8 * self.nbytes).from_buffer_copy(source_bytes)
        output = (ctypes.c_uint8 * self.nbytes)()
        if self._library.degree_order_reorder_bits(source, output) != 0:
            raise RuntimeError("failed to reorder monomial bitset")
        return int.from_bytes(bytes(output), "little")


def multiply_variable(packed: int, variable: int, nvars: int) -> int:
    """Multiply by x_variable in the Boolean quotient x_i^2=x_i."""
    step, low_lanes, high_lanes = _variable_lanes(variable, nvars)
    return (packed & high_lanes) ^ ((packed & low_lanes) << step)


@lru_cache(maxsize=None)
def _variable_lanes(variable: int, nvars: int) -> tuple[int, int, int]:
    step = 1 << variable
    nmonomials = 1 << nvars
    all_positions = (1 << nmonomials) - 1
    low_lanes = (all_positions // ((1 << (2 * step)) - 1)) * ((1 << step) - 1)
    return step, low_lanes, all_positions ^ low_lanes


def low_degree_mask(nvars: int, degree: int,
                    degree_order: MonomialDegreeOrder | None = None) -> int:
    """Return monomial-position bits for all masks of weight <= degree."""
    degree = min(max(degree, 0), nvars)
    nmonomials = 1 << nvars
    packed = bytearray((nmonomials + 7) // 8)
    for weight in range(degree + 1):
        for support in itertools.combinations(range(nvars), weight):
            monomial = sum(1 << variable for variable in support)
            position = degree_order.rank(monomial) if degree_order else monomial
            packed[position >> 3] |= 1 << (position & 7)
    return int.from_bytes(packed, "little")


def _reduce_component(rows: list[int], low_support: int,
                      degree_order: MonomialDegreeOrder | None = None
                      ) -> tuple[list[set[int]], dict]:
    begin = time.perf_counter()
    pivots: dict[int, int] = {}
    pivot_xors = 0
    columns = 0
    for row in rows:
        columns |= row
        while row:
            lead = row.bit_length() - 1
            prior = pivots.get(lead)
            if prior is None:
                pivots[lead] = row
                break
            row ^= prior
            pivot_xors += 1

    leads = sorted(pivots)
    for lead in leads:
        row = pivots[lead]
        lead_bit = 1 << lead
        for high in leads:
            if high > lead and pivots[high] & lead_bit:
                pivots[high] ^= row
                pivot_xors += 1

    deductions = []
    for row in pivots.values():
        if row and not (row & ~low_support):
            deductions.append(bits_to_sparse(row, degree_order))
    deductions.sort(key=lambda poly: (len(poly), tuple(sorted(poly))))
    return deductions, {
        "rows": len(rows),
        "columns": columns.bit_count(),
        "rank": len(pivots),
        "pivot_xors": pivot_xors,
        "derived_consequences": len(deductions),
        "elimination_seconds": time.perf_counter() - begin,
    }


def degree_one_layer(equations: list[set[int]], width: int,
                     base_degree: tuple[int, int, int],
                     deduction_degree: int = 4,
                     degree_order: MonomialDegreeOrder | None = None
                     ) -> tuple[list[set[int]], dict]:
    """Build and reduce the constant and all one-variable homogeneous rows.

    The input equations are Boolean-reduced S4 coordinate polynomials.  Their
    homogeneous lift has `base_degree`; a multiplier of one variable in block
    i belongs to `base_degree + e_i`.  Reduction is performed separately in
    those four exact tri-degrees.  Denominator equations are intentionally not
    included here and must remain in the exact search and final replay.
    """
    if len(base_degree) != 3:
        raise ValueError("expected three block degrees")
    nvars = 3 * width
    low_support = low_degree_mask(nvars, deduction_degree, degree_order)
    begin = time.perf_counter()
    natural_equations = [sparse_to_bits(poly, nvars) for poly in equations]
    packed_equations = ([degree_order.reorder(poly) for poly in natural_equations]
                        if degree_order else natural_equations)
    pack_seconds = time.perf_counter() - begin

    begin = time.perf_counter()
    profiles = []
    for block in range(3):
        profile = tuple(d + (i == block) for i, d in enumerate(base_degree))
        # Multipliers in each block produce one neighboring component.  The
        # base component itself is added once, before the three block passes.
        neighbor_rows = [
            (degree_order.reorder(
                multiply_variable(poly, block * width + offset, nvars))
             if degree_order else multiply_variable(poly, block * width + offset, nvars))
            for poly in natural_equations
            for offset in range(width)
        ]
        profiles.append((profile, neighbor_rows))

    component_rows = [(base_degree, packed_equations)] + profiles
    row_generation_seconds = time.perf_counter() - begin
    all_deductions: dict[frozenset[int], set[int]] = {}
    matrices = []
    begin = time.perf_counter()
    for profile, rows in component_rows:
        consequences, matrix = _reduce_component(rows, low_support, degree_order)
        matrix["degree"] = list(profile)
        matrices.append(matrix)
        for consequence in consequences:
            all_deductions[frozenset(consequence)] = consequence
    elimination_seconds = time.perf_counter() - begin

    deductions = sorted(all_deductions.values(),
                        key=lambda poly: (len(poly), tuple(sorted(poly))))
    return deductions, {
        "degree_components": len(matrices),
        "rows": sum(matrix["rows"] for matrix in matrices),
        "tagged_columns": sum(matrix["columns"] for matrix in matrices),
        "rank": sum(matrix["rank"] for matrix in matrices),
        "pivot_xors": sum(matrix["pivot_xors"] for matrix in matrices),
        "derived_consequences": len(deductions),
        "deduction_degree": deduction_degree,
        "multiplier_layer": "constant plus every one-variable multiplier",
        "monomial_order": ("total degree then numeric mask" if degree_order else
                           "numeric monomial mask within each exact block degree"),
        "component_matrices": matrices,
        "pack_seconds": pack_seconds,
        "row_generation_seconds": row_generation_seconds,
        "elimination_seconds": elimination_seconds,
    }
