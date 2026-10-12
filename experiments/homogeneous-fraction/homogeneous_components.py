#!/usr/bin/env python3
"""Explicit tri-homogeneous Macaulay components in the Boolean field quotient.

This bounded XL solver retains the three formal degrees of the homogenized
fraction equations. The 'split' arm eliminates one exact tri-degree at a time;
the 'flat' arm eliminates the identical tagged rows in one large sparse matrix.
Both dehomogenize the resulting consequences and call the same exact search.
This is an actual component-wise linear-algebra comparison, not an F4 claim.
"""

import argparse
import collections
import hashlib
import itertools
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

from block_fraction_solver import (
    MODULI, audit_consequences, block_profile, equations, independent_oracle,
    multiplied, search,
)
from math_model import GF2n


def tagged_rows(n, k, target, cap, field=None, include_denominators=True,
                max_multiplier_degree=None, validate_rows=True,
                equations_override=None):
    """Rows modulo x_j^2=x_j*h_i, tagged by their *exact* homogeneous degree.

    The coordinate equations lift to degree (4,4,4), and each denominator
    equation to degree k+1 in its own block. A squarefree multiplier m adds
    block_profile(m) to this degree. Reduction x_j^2=x_j*h_i leaves the
    x-support equal to the Boolean product's support, with h_i exponent
    D_i - popcount(x-support_i). Thus a (D, mask) pair is an unambiguous
    monomial of the graded field-equation quotient.
    """
    if field is None:
        field = GF2n(n, MODULI[n])
    width = 2 * (k + 1)
    nv = 3 * width
    eqs = equations_override if equations_override is not None else equations(field, k, target)
    row_eqs = eqs if include_denominators else eqs[:n]
    formal = [(4, 4, 4)] * n + ([
        tuple(k + 1 if b == i else 0 for i in range(3)) for b in range(3)
    ] if include_denominators else [])
    if any(any(block_profile(mon, width)[i] > degree[i]
                   for i in range(3)) for poly, degree in zip(row_eqs, formal)
           for mon in poly):
        raise AssertionError("input has no declared homogeneous lift")
    masks_by_limit = {
        limit: [mask for mask in range(1 << width) if mask.bit_count() <= limit]
        for limit in set(max(0, c - d) for base in formal for c, d in zip(cap, base))
    }
    groups = collections.defaultdict(set)
    for poly, base in zip(row_eqs, formal):
        if not poly:
            continue
        limits = tuple(c - d for c, d in zip(cap, base))
        if any(limit < 0 for limit in limits):
            continue
        choices = [masks_by_limit[limit] for limit in limits]
        for pieces in itertools.product(*choices):
            if (max_multiplier_degree is not None
                    and sum(piece.bit_count() for piece in pieces) > max_multiplier_degree):
                continue
            multiplier = sum(piece << (block * width)
                             for block, piece in enumerate(pieces))
            degree = tuple(d + piece.bit_count() for d, piece in zip(base, pieces))
            row = multiplied(poly, multiplier)
            if not row:
                continue
            # Every input monomial is checked against its declared base degree
            # above.  Since Boolean multiplication is mask union, its output
            # support cannot exceed base degree plus multiplier degree.  Keep
            # the full per-row assertion for the reference path; the bounded
            # experiment can skip this repeated scan over very large rows.
            if validate_rows and any(any(block_profile(mon, width)[i] > degree[i]
                                         for i in range(3)) for mon in row):
                raise AssertionError("field reduction broke the grading")
            groups[degree].add(row)
    return field, width, eqs, groups


def eliminate(groups, split, deduction_degree, canonical_row_order=True):
    """Eliminate identical rows and columns, changing only block partition."""
    begin = time.perf_counter()
    degrees = sorted(groups)
    columns = {
        d: sorted(set().union(*groups[d]), key=lambda mon: (mon.bit_count(), mon))
        for d in degrees
    }
    if canonical_row_order:
        row_order = {
            d: sorted(groups[d], key=lambda row:
                      (max(mon.bit_count() for mon in row), len(row), tuple(sorted(row))))
            for d in degrees
        }
    else:
        # The final reduced row space is canonical for a fixed column order.
        # Avoid sorting millions of monomial IDs just to choose a pivot order.
        row_order = {d: list(groups[d]) for d in degrees}
    assembly = time.perf_counter() - begin
    begin = time.perf_counter()
    if split:
        buckets = []
        for d in degrees:
            buckets.append(([(d, mon) for mon in columns[d]],
                            [(d, row) for row in row_order[d]]))
    else:
        buckets = [([pair for d in degrees for pair in
                     ((d, mon) for mon in columns[d])],
                    [(d, row) for d in degrees for row in row_order[d]])]
    deductions = set()
    rank = 0
    largest_matrix = 0
    largest_vector_bits = 0
    pivot_xors = 0
    for tagged_cols, tagged_rowset in buckets:
        pos = {pair: j for j, pair in enumerate(tagged_cols)}
        pivots = {}
        for d, row in tagged_rowset:
            bits = 0
            for mon in row:
                bits ^= 1 << pos[(d, mon)]
            while bits:
                lead = bits.bit_length() - 1
                prior = pivots.get(lead)
                if prior is None:
                    pivots[lead] = bits
                    break
                bits ^= prior
                pivot_xors += 1
        rank += len(pivots)
        largest_matrix = max(largest_matrix, len(tagged_rowset) * len(tagged_cols))
        largest_vector_bits = max(largest_vector_bits, len(tagged_cols))
        # Back reduction stays within the same degree because the columns are
        # disjoint across components, even in the flat arm.
        for lead in sorted(pivots):
            bits = pivots[lead]
            for high in pivots:
                if high > lead and pivots[high] & (1 << lead):
                    pivots[high] ^= bits
                    pivot_xors += 1
        for bits in pivots.values():
            poly = set()
            while bits:
                one = bits & -bits
                poly.add(tagged_cols[one.bit_length() - 1][1])
                bits ^= one
            if poly and max(mon.bit_count() for mon in poly) <= deduction_degree:
                deductions.add(frozenset(poly))
    elapsed = time.perf_counter() - begin
    canon = sorted((tuple(sorted(poly)) for poly in deductions))
    fingerprint = hashlib.sha256(json.dumps(canon).encode()).hexdigest()
    return [set(poly) for poly in canon], {
        "degree_components": len(degrees),
        "homogeneous_rows": sum(map(len, groups.values())),
        "tagged_columns": sum(map(len, columns.values())),
        "rank": rank,
        "largest_matrix_entries": largest_matrix,
        "largest_vector_bits": largest_vector_bits,
        "pivot_xors": pivot_xors,
        "derived_consequences": len(deductions),
        "derived_sha256": fingerprint,
        "assembly_seconds": assembly,
        "elimination_seconds": elapsed,
        "canonical_row_order": canonical_row_order,
    }


def run_worker(n, k, target, arm, cap, deduction_degree):
    begin = time.perf_counter()
    field, width, eqs, groups = tagged_rows(n, k, target, cap)
    setup_seconds = time.perf_counter() - begin
    deductions, matrix = eliminate(groups, arm == "split", deduction_degree)
    audit_start = time.perf_counter()
    raw_roots, verified_roots = audit_consequences(
        eqs, deductions, 3 * width, field, k, target)
    audit_seconds = time.perf_counter() - audit_start
    result = search(eqs, deductions, field, width, k, target)
    oracle_start = time.perf_counter()
    expected = independent_oracle(field, k, target)
    oracle_seconds = time.perf_counter() - oracle_start
    assert (result["status"] == "verified") == expected
    return {
        "n": n, "k": k, "target": target, "arm": arm, "cap": cap,
        "setup_seconds": setup_seconds, "matrix": matrix, "search": result,
        "raw_roots": raw_roots, "verified_roots": verified_roots,
        "oracle": expected,
        "total_solver_seconds": time.perf_counter() - begin
        - audit_seconds - oracle_seconds,
        "audit_seconds_excluded": audit_seconds,
        "oracle_seconds_excluded": oracle_seconds,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--worker", action="store_true")
    p.add_argument("--n", type=int, choices=(5, 7), default=5)
    p.add_argument("--k", type=int, choices=(0, 1), default=0)
    p.add_argument("--target", type=int, default=0)
    p.add_argument("--arm", choices=("split", "flat"), default="split")
    p.add_argument("--cap", nargs=3, type=int, default=(5, 5, 5))
    p.add_argument("--deduction-degree", type=int, default=2)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--output", type=Path, default=Path("homogeneous_component_results.json"))
    args = p.parse_args()
    if args.worker:
        print(json.dumps(run_worker(args.n, args.k, args.target, args.arm,
                                    tuple(args.cap), args.deduction_degree)), flush=True)
        return
    cases = [(5, 0, 0, (5, 5, 5)), (5, 0, 2, (5, 5, 5)),
             (7, 1, 1, (4, 4, 4)), (7, 1, 50, (4, 4, 4))]
    records = []
    for n, k, target, cap in cases:
        for repeat in range(args.repeats):
            for arm in (("split", "flat") if repeat % 2 == 0 else ("flat", "split")):
                cmd = [sys.executable, str(Path(__file__).resolve()), "--worker",
                       "--n", str(n), "--k", str(k), "--target", str(target),
                       "--cap", *map(str, cap), "--arm", arm,
                       "--deduction-degree", str(args.deduction_degree)]
                try:
                    proc = subprocess.run(cmd, text=True, capture_output=True,
                                          timeout=args.timeout, check=True)
                    record = json.loads(proc.stdout)
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as err:
                    raise RuntimeError(f"{n=}, {k=}, {target=}, {arm=}: {err}") from err
                record["repeat"] = repeat
                records.append(record)
                args.output.write_text(json.dumps({
                    "model": "graded Boolean-quotient Macaulay components",
                    "note": "identical tagged rows and columns, split vs flat elimination",
                    "runs": records,
                }, indent=2) + "\n")
                print(json.dumps({
                    "n": n, "k": k, "target": target, "arm": arm, "repeat": repeat,
                    "status": record["search"]["status"],
                    "degrees": record["matrix"]["degree_components"],
                    "rows": record["matrix"]["homogeneous_rows"],
                    "rank": record["matrix"]["rank"],
                    "solver_s": record["total_solver_seconds"],
                }), flush=True)
            first, second = records[-2:]
            for field in ("degree_components", "homogeneous_rows", "tagged_columns",
                          "rank", "derived_sha256"):
                if first["matrix"][field] != second["matrix"][field]:
                    raise AssertionError(f"split and flat differ on {field}")
            for field in ("raw_roots", "verified_roots", "oracle"):
                if first[field] != second[field]:
                    raise AssertionError(f"split and flat differ on {field}")


if __name__ == "__main__":
    main()
