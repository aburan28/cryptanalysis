#!/usr/bin/env python3
"""Exact low-degree algebraic gate for the N23 cyclotomic weight-2/3 family.

The binary evaluation matrix at degree four tests whether any nonzero
quartic Boolean polynomial vanishes on every proposed x coordinate. Full
column rank would exclude every such x-only equation, not just the two
root-power equations previously tested. The exact membership indicator ANF
and a compact 6-bit root-index lookup are measured separately.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import random
import time
from pathlib import Path

import numpy as np
from sage.all import GF, matrix

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-20261007/results/a2_final.json"


def multiply(a, b, modulus, degree):
    out = 0
    while b:
        if b & 1:
            out ^= a
        b >>= 1
        a <<= 1
        if a >> degree:
            a ^= modulus
    return out


def family(gamma, modulus):
    powers = [1]
    for _ in range(46):
        powers.append(multiply(powers[-1], gamma, modulus, 23))
    assert multiply(powers[-1], gamma, modulus, 23) == 1
    two = {a ^ b for a, b in itertools.combinations(powers, 2)}
    three = {a ^ b ^ c for a, b, c in itertools.combinations(powers, 3)}
    assert len(two) == 1081 and len(three) == 16215
    assert len(two | three) == 17296
    return powers, sorted(two | three)


def transform(values):
    data = values.copy()
    for bit in range(23):
        stride = 1 << bit
        blocks = data.reshape((-1, 2 * stride))
        blocks[:, stride:] ^= blocks[:, :stride]
    return data


def membership_anf(values):
    truth = np.zeros(1 << 23, dtype=np.uint8)
    truth[values] = 1
    original_digest = hashlib.sha256(truth.tobytes()).hexdigest()
    transformed = transform(truth)
    indices = np.flatnonzero(transformed).astype(np.uint32)
    degrees = np.bitwise_count(indices)
    counts = np.bincount(degrees, minlength=24).tolist()
    assert sum(counts) == len(indices)
    assert hashlib.sha256(transform(transformed).tobytes()).hexdigest() == original_digest
    return {"membership_count": len(values), "truth_table_sha256": original_digest,
            "anf_term_count": len(indices), "anf_terms_by_degree": counts,
            "algebraic_degree": max(i for i, count in enumerate(counts) if count)}


def lookup_anf(powers):
    # Index 47 is the zero sentinel for weight two. Other invalid codes have
    # zero output but are excluded by the leaf-index range constraint.
    table = powers + [0] * (64 - len(powers))
    rows = []
    for coordinate in range(23):
        values = np.fromiter(((value >> coordinate) & 1 for value in table),
                             dtype=np.uint8, count=64)
        for bit in range(6):
            stride = 1 << bit
            blocks = values.reshape((-1, 2 * stride))
            blocks[:, stride:] ^= blocks[:, :stride]
        terms = np.flatnonzero(values)
        rows.append({"coordinate": coordinate, "terms": len(terms),
                     "degree": max((int(i).bit_count() for i in terms), default=-1)})
    return {"index_bits_per_root": 6, "indices_per_leaf": 3,
            "index_bits_per_leaf": 18, "invalid_code_rule": "0 <= i < j < k <= 47; k=47 encodes weight two",
            "coordinate_anf": rows,
            "maximum_coordinate_degree": max(row["degree"] for row in rows),
            "total_coordinate_terms": sum(row["terms"] for row in rows)}


def quartic_rank(values):
    columns = [sum(1 << i for i in index)
               for degree in range(5)
               for index in itertools.combinations(range(23), degree)]
    position = {mask: j for j, mask in enumerate(columns)}
    # A deterministic row permutation avoids a fortuitous ordering of the
    # exponent triples. Full column rank of any subset certifies all rows.
    selected = list(values)
    random.Random(20261008).shuffle(selected)
    M = matrix(GF(2), len(selected), len(columns))
    set_bits = 0
    for row_index, value in enumerate(selected):
        support = [i for i in range(23) if value >> i & 1]
        for degree in range(5):
            for subset in itertools.combinations(support, degree):
                M[row_index, position[sum(1 << i for i in subset)]] = 1
                set_bits += 1
    started = time.perf_counter_ns()
    rank = M.rank()
    return {"degree_bound": 4, "rows": len(selected),
            "columns": len(columns), "nonzeros": set_bits,
            "rank": rank, "nullity": len(columns) - rank,
            "full_column_rank": rank == len(columns),
            "rank_wall_ns_exploratory": time.perf_counter_ns() - started,
            "row_shuffle_seed": 20261008}


def main():
    out = HERE / "a2_membership_degree.json"
    if out.exists():
        raise FileExistsError(out)
    prior = json.loads(PRIOR.read_text())
    gamma, modulus = prior["gamma_bits"], prior["field_modulus_bits"]
    powers, values = family(gamma, modulus)
    answer = {"schema_version": 1, "proposal_id": "A2",
              "candidate_id": None, "run_id": None,
              "field_degree": 23, "gamma_bits": gamma,
              "field_modulus_bits": modulus,
              "prior_receipt_sha256": hashlib.sha256(PRIOR.read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "membership_indicator": membership_anf(values),
              "compact_root_index": lookup_anf(powers),
              "quartic_vanishing_space": quartic_rank(values)}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"degree": answer["membership_indicator"]["algebraic_degree"],
                      "quartic_rank": answer["quartic_vanishing_space"]["rank"],
                      "quartic_columns": answer["quartic_vanishing_space"]["columns"]}))


if __name__ == "__main__":
    main()
