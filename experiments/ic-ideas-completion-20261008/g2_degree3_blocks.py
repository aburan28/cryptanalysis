#!/usr/bin/env python3
"""Degree-three cyclic Macaulay rank decomposition for the S3 barrel system.

This is a rank experiment, not a Groebner basis or a timed F4 solve.  It uses
one representative of each cyclic source orbit, then checks the full binary
rank against character-block ranks over the smallest extension field.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
import time
from pathlib import Path

from sage.all import GF, matrix

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-20261007"
sys.path.insert(0, str(PRIOR))
from boolean_core import ANFField  # noqa: E402
from sage_probes import bits, field, normal_basis  # noqa: E402


def shift(mask: int, n: int) -> int:
    out = 0
    while mask:
        bit = mask & -mask
        i = bit.bit_length() - 1
        out |= 1 << ((i // n) * n + (i + 1) % n)
        mask ^= bit
    return out


def product(poly: set[int], monomial: int) -> frozenset[int]:
    out: set[int] = set()
    for term in poly:
        value = term | monomial
        if value in out:
            out.remove(value)
        else:
            out.add(value)
    return frozenset(out)


def masks(nvars: int, max_degree: int):
    for degree in range(max_degree + 1):
        for indices in itertools.combinations(range(nvars), degree):
            yield sum(1 << i for i in indices)


def echelon_rank(rows):
    pivots: dict[int, int] = {}
    for row in rows:
        while row:
            key = row.bit_length() - 1
            prior = pivots.get(key)
            if prior is None:
                pivots[key] = row
                break
            row ^= prior
    return len(pivots)


def equations(n: int):
    K, modulus = field(n)
    normal = normal_basis(K)
    inverse = matrix(GF(2), n, n,
                     lambda i, j: (bits(normal[j]) >> i) & 1).inverse()
    anf = ANFField(n, modulus)
    inputs = [anf.linear(list(range(block*n, (block+1)*n)),
                         [bits(value) for value in normal]) for block in range(3)]
    raw = anf.s3(*inputs)
    s3 = []
    for j in range(n):
        row = set()
        for i in range(n):
            if inverse[j, i]:
                row.symmetric_difference_update(raw[i])
        s3.append(row)
    assert all({shift(t, n) for t in s3[j]} == s3[(j+1) % n]
               for j in range(n)) or all(
                   {shift(t, n) for t in s3[j]} == s3[(j-1) % n]
                   for j in range(n))
    linear = {0} | {1 << (2*n+i) for i in range(n)}
    pair_reps = {}
    for i, j in itertools.combinations(range(n), 2):
        pair = (1 << (2*n+i)) | (1 << (2*n+j))
        orbit = [pair]
        for _ in range(n-1):
            orbit.append(shift(orbit[-1], n))
        pair_reps[min(orbit)] = {min(orbit)}
    assert len(pair_reps) == (n-1)//2
    return modulus, s3[0], linear, list(pair_reps.values())


def monomial_orbits(n: int, degree: int):
    nvars = 3*n
    mapping = {}
    representatives = []
    sizes = []
    for mask in masks(nvars, degree):
        if mask in mapping:
            continue
        orbit = [mask]
        while True:
            next_mask = shift(orbit[-1], n)
            if next_mask == mask:
                break
            orbit.append(next_mask)
        canonical = min(orbit)
        index = len(representatives)
        representatives.append(canonical)
        sizes.append(len(orbit))
        current = canonical
        for power in range(len(orbit)):
            mapping[current] = (index, power)
            current = shift(current, n)
    return mapping, representatives, sizes


def source_rows(n: int, s3, linear, pairs, degree=3):
    # One seed per orbit of multiplier sources for invariant linear constraint.
    multiplier_orbits = {}
    for term in masks(3*n, degree-1):
        orbit = [term]
        for _ in range(n-1):
            orbit.append(shift(orbit[-1], n))
        multiplier_orbits[min(orbit)] = min(orbit)
    rows = [("s3", product(s3, 0))]
    rows.extend(("onehot_linear", product(linear, term))
                for term in multiplier_orbits)
    rows.extend(("onehot_pair", product(pair, term))
                for pair in pairs for term in masks(3*n, degree-2))
    return rows


def block_rank(rows, column_count: int, omega, k: int, mapping, sizes):
    zero = omega.parent()(0)
    one = omega.parent()(1)
    powers = [omega**(k*j) for j in range(omega.multiplicative_order())]
    pivots = {}
    for _, row in rows:
        v = {}
        for term in row:
            col, power = mapping[term]
            if sizes[col] == 1 and k:
                continue
            v[col] = v.get(col, zero) + (powers[power] if k else one)
        v = {c: x for c, x in v.items() if x}
        while v:
            lead = max(v)
            prior = pivots.get(lead)
            if prior is None:
                scale = v[lead]**(-1)
                pivots[lead] = {c: x*scale for c, x in v.items()}
                break
            scale = v[lead]
            for col, value in prior.items():
                result = v.get(col, zero) + scale*value
                if result:
                    v[col] = result
                else:
                    v.pop(col, None)
    return len(pivots)


def run(n: int):
    started = time.perf_counter_ns()
    modulus, s3, linear, pairs = equations(n)
    degree = 3
    mapping, representatives, sizes = monomial_orbits(n, degree)
    rows = source_rows(n, s3, linear, pairs, degree)
    binary = []
    for _, seed in rows:
        current = seed
        for _ in range(n):
            binary.append(sum(1 << mapping[term][0]*n + mapping[term][1]
                              for term in current))
            current = frozenset(shift(term, n) for term in current)
    # The orbit-packed bit layout is injective even for the fixed constant.
    binary_rank = echelon_rank(binary)
    extension_degree = 1
    while pow(2, extension_degree, n) != 1:
        extension_degree += 1
    L = GF(2**extension_degree, f"u{n}")
    omega = L.multiplicative_generator()**((2**extension_degree-1)//n)
    assert omega.multiplicative_order() == n
    seen = set()
    characters = []
    for k in range(n):
        if k in seen:
            continue
        orbit = sorted({(k*pow(2, j, n)) % n for j in range(extension_degree)})
        seen.update(orbit)
        rank = block_rank(rows, len(representatives), omega, k, mapping, sizes)
        characters.append({"representative": k, "galois_orbit": orbit,
                           "orbit_size": len(orbit), "rank": rank})
    reconstructed = sum(item["rank"]*item["orbit_size"] for item in characters)
    assert reconstructed == binary_rank, (n, reconstructed, binary_rank)
    return {"field_degree": n, "field_modulus_bits": modulus,
            "boolean_variables": 3*n, "macaulay_degree": degree,
            "s3_degree": max(t.bit_count() for t in s3),
            "source_seed_rows": len(rows), "binary_rows_with_shifts": len(binary),
            "ambient_binary_columns": sum(math.comb(3*n, j) for j in range(degree+1)),
            "monomial_orbit_columns": len(representatives),
            "fixed_monomial_orbits": sum(size == 1 for size in sizes),
            "binary_rank": binary_rank, "character_blocks": characters,
            "reconstructed_binary_rank": reconstructed,
            "rank_agrees": reconstructed == binary_rank,
            "wall_ns_exploratory": time.perf_counter_ns()-started}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--degrees", type=int, nargs="+", default=[19, 23])
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    cells = [run(n) for n in args.degrees]
    result = {"schema_version": 1, "proposal_id": "G2", "candidate_id": None,
              "run_id": None, "cells": cells,
              "scope": "degree-three Macaulay row-space character decomposition; no F4 basis or isolated timing",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "prior_sources_sha256": {
                  name: hashlib.sha256((PRIOR / name).read_bytes()).hexdigest()
                  for name in ("boolean_core.py", "sage_probes.py")}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"cells": [{"n": c["field_degree"],
                                  "rank": c["binary_rank"],
                                  "blocks": c["character_blocks"]} for c in cells]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
