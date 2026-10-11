#!/usr/bin/env python3
"""Bounded Boolean Macaulay comparison for three fraction blocks.

The block arm constrains the *actual columns and multiples* by their three
block degrees. This is a filtered XL/Macaulay solver, not a full F4 or F5.
Both arms use identical field and denominator equations and the same exact
branch/search and independent elliptic-curve verification.
"""

import argparse
import collections
import itertools
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

from math_model import GF2n, symbolic_anf

MODULI = {5: 0x25, 7: 0x83, 11: 0x805, 13: 0x2027}


def fraction_pair(word, k, field):
    length = k + 1
    num = den = 0
    for j in range(length):
        if word & (1 << j):
            num ^= field.power(2, j)
        if word & (1 << (length + j)):
            den ^= field.power(2, j)
    return num, den


def denominator_equations(k):
    """prod_j (1 + d_ij) = 0 iff a denominator coefficient is nonzero."""
    w = 2 * (k + 1)
    return [set(sum((1 << (block * w + k + 1 + j) for j in subset), 0)
                for size in range(k + 2)
                for subset in itertools.combinations(range(k + 1), size))
            for block in range(3)]


def equations(field, k, target):
    anf = symbolic_anf(field, 2, k, target)
    return [{mon for mon, coeff in anf.items() if coeff & (1 << i)}
            for i in range(field.n)] + denominator_equations(k)


def block_profile(mask, width):
    piece = (1 << width) - 1
    return tuple(((mask >> (i * width)) & piece).bit_count() for i in range(3))


def allowed(mask, width, arm, budget):
    degrees = block_profile(mask, width)
    if arm == "block":
        return all(degree <= cap for degree, cap in zip(degrees, budget))
    return sum(degrees) <= sum(budget)


def multiplied(poly, multiplier):
    row = set()
    for monomial in poly:
        term = monomial | multiplier  # reduction modulo x_i^2 + x_i
        if term in row:
            row.remove(term)
        else:
            row.add(term)
    return frozenset(row)


def matrix(eqs, width, arm, budget, deduction_degree=3):
    """Generate polynomial multiples inside the selected monomial filtration."""
    start = time.perf_counter()
    nv = 3 * width
    # The same candidate multipliers and equations are used in both arms.
    multipliers = [mon for mon in range(1 << nv)
                   if allowed(mon, width, arm, budget)]
    if any(not all(allowed(term, width, arm, budget) for term in poly)
           for poly in eqs):
        raise ValueError("filtration excludes an input equation")
    rows = set()
    cols = set()
    attempted = 0
    for poly in eqs:
        if not poly:
            continue
        for multiplier in multipliers:
            attempted += 1
            row = multiplied(poly, multiplier)
            if row and all(allowed(mon, width, arm, budget) for mon in row):
                rows.add(row)
                cols.update(row)
    assembly_s = time.perf_counter() - start
    # Identical graded order in both arms: comparisons reflect the filtration.
    col_order = sorted(cols, key=lambda x: (x.bit_count(), x))
    pos = {mon: j for j, mon in enumerate(col_order)}
    pivots = {}
    zero_rows = 0
    max_pivot_degree = 0
    start = time.perf_counter()
    for row in sorted(rows, key=lambda r: (max(x.bit_count() for x in r), len(r), tuple(sorted(r)))):
        bits = 0
        for mon in row:
            bits ^= 1 << pos[mon]
        while bits:
            lead = bits.bit_length() - 1
            previous = pivots.get(lead)
            if previous is None:
                pivots[lead] = bits
                max_pivot_degree = max(max_pivot_degree, col_order[lead].bit_count())
                break
            bits ^= previous
        if not bits:
            zero_rows += 1
    # Back elimination extracts low-degree consequences without assuming a
    # homogeneous ideal or claiming that an XL matrix is a Groebner basis.
    for lead in sorted(pivots):
        p = pivots[lead]
        for high in pivots:
            if high > lead and pivots[high] & (1 << lead):
                pivots[high] ^= p
    low = []
    for lead, bits in pivots.items():
        if col_order[lead].bit_count() > deduction_degree:
            continue
        poly = set()
        while bits:
            bit = bits & -bits
            poly.add(col_order[bit.bit_length() - 1])
            bits ^= bit
        low.append(poly)
    elimination_s = time.perf_counter() - start
    return low, {
        "budget": list(budget), "arm": arm,
        "candidate_multipliers": len(multipliers), "attempted_rows": attempted,
        "unique_rows": len(rows), "columns": len(cols), "rank": len(pivots),
        "zero_rows": zero_rows, "max_pivot_degree": max_pivot_degree,
        "derived_linear": sum(max(map(int.bit_count, p)) <= 1 for p in low),
        "derived_quadratic": sum(max(map(int.bit_count, p)) == 2 for p in low),
        "derived_cubic": sum(max(map(int.bit_count, p)) == 3 for p in low),
        "derived_quartic": sum(max(map(int.bit_count, p)) == 4 for p in low),
        "assembly_seconds": assembly_s, "elimination_seconds": elimination_s,
        "column_block_profiles": dict(sorted(collections.Counter(
            ','.join(map(str, block_profile(c, width))) for c in cols).items())),
    }


def curve_lookup(field):
    lookup = {}
    for point in field.all_points():
        lookup.setdefault(point[0], []).append(point)
    return lookup


def verify_root(bits, field, width, k, target, lookup):
    xs = []
    words = []
    for block in range(3):
        word = bits >> (width * block) & ((1 << width) - 1)
        num, den = fraction_pair(word, k, field)
        if not den:
            raise AssertionError("invalid denominator escaped equations")
        words.append(word)
        xs.append(field.mul(num, field.inv(den)))
    if field.s4(*xs, target) != 0:
        raise AssertionError("cleared equation failed S4 check")
    for pts in itertools.product(*(lookup.get(x, ()) for x in xs)):
        total = field.add(field.add(pts[0], pts[1]), pts[2])
        if total is not None and total[0] == target:
            return {"words": words, "abscissas": xs, "points": pts}
    return None


def simplify(poly, known, ones):
    result = set()
    for monomial in poly:
        if monomial & known & ~ones:
            continue
        remaining = monomial & ~known
        if remaining in result:
            result.remove(remaining)
        else:
            result.add(remaining)
    return result


def search(eqs, deductions, field, width, k, target):
    """Exact Boolean DFS with polynomial propagation; no enumerated witness."""
    lookup = curve_lookup(field)
    nv = 3 * width
    nodes = 0
    candidates = 0
    invalid_candidates = 0

    def recurse(known, ones):
        nonlocal nodes, candidates, invalid_candidates
        nodes += 1
        # Consequences from the Macaulay matrix are logically implied by eqs.
        # Always evaluate the original equations again at candidate leaves.
        reduced = []
        for poly in itertools.chain(eqs, deductions):
            p = simplify(poly, known, ones)
            if p == {0}:
                return None
            if p:
                reduced.append(p)
        for poly in reduced:
            nonconstant = poly - {0}
            if len(nonconstant) == 1:
                term = next(iter(nonconstant))
                if term.bit_count() == 1 and not known & term:
                    return recurse(known | term, ones | (term if 0 in poly else 0))
        if known == (1 << nv) - 1:
            candidates += 1
            if any(simplify(p, known, ones) for p in eqs):
                raise AssertionError("derived equation changed the solution set")
            witness = verify_root(ones, field, width, k, target, lookup)
            if witness is not None:
                return witness
            invalid_candidates += 1
            return None
        score = collections.Counter(j for p in reduced for m in p
                                    for j in range(nv) if m & 1 << j and not known & 1 << j)
        bit = 1 << (score.most_common(1)[0][0] if score else
                    next(j for j in range(nv) if not known & 1 << j))
        for value in (0, bit):
            witness = recurse(known | bit, ones | value)
            if witness is not None:
                return witness
        return None

    start = time.perf_counter()
    witness = recurse(0, 0)
    return {"status": "verified" if witness else "no_verified_relation",
            "witness": witness, "nodes": nodes, "candidate_roots": candidates,
            "invalid_candidate_roots": invalid_candidates,
            "search_seconds": time.perf_counter() - start}


def independent_oracle(field, k, target):
    lookup = curve_lookup(field)
    xs = set()
    for word in range(1 << (2 * (k + 1))):
        num, den = fraction_pair(word, k, field)
        if den:
            xs.add(field.mul(num, field.inv(den)))
    base = [p for x in xs for p in lookup.get(x, ())]
    for pts in itertools.product(base, repeat=3):
        total = field.add(field.add(pts[0], pts[1]), pts[2])
        if total is not None and total[0] == target:
            return True
    return False


def audit_consequences(eqs, deductions, nv, field, k, target):
    """Check every input root and count true curve relations independently."""
    root_count = 0
    verified_count = 0
    lookup = curve_lookup(field)
    width = 2 * (k + 1)
    for bits in range(1 << nv):
        if all(not sum((m & bits) == m for m in poly) & 1 for poly in eqs):
            root_count += 1
            assert all(not sum((m & bits) == m for m in poly) & 1
                       for poly in deductions)
            verified_count += verify_root(bits, field, width, k, target, lookup) is not None
    return root_count, verified_count


def run_worker(n, k, target, arm, budget, deduction_degree):
    start = time.perf_counter()
    field = GF2n(n, MODULI[n])
    width = 2 * (k + 1)
    eqs = equations(field, k, target)
    built = time.perf_counter() - start
    if arm == "direct":
        low, mat = [], {"arm": "direct", "budget": list(budget),
                        "unique_rows": 0, "columns": 0, "rank": 0}
    else:
        low, mat = matrix(eqs, width, arm, budget, deduction_degree)
    audit_start = time.perf_counter()
    raw_roots, verified_roots = audit_consequences(
        eqs, low, 3 * width, field, k, target)
    audit_s = time.perf_counter() - audit_start
    outcome = search(eqs, low, field, width, k, target)
    oracle_start = time.perf_counter()
    expected = independent_oracle(field, k, target)
    oracle_s = time.perf_counter() - oracle_start
    assert (outcome["status"] == "verified") == expected
    return {"n": n, "k": k, "target": target, "arm": arm,
            "equation_count": len(eqs), "compile_seconds": built,
            "raw_boolean_roots": raw_roots,
            "verified_boolean_roots": verified_roots,
            "invalid_boolean_roots": raw_roots - verified_roots,
            "matrix": mat,
            "search": outcome, "oracle_result": expected,
            "audit_seconds_excluded": audit_s, "oracle_seconds_excluded": oracle_s,
            "total_solver_seconds": time.perf_counter() - start - oracle_s - audit_s,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--n", type=int, choices=MODULI)
    parser.add_argument("--k", type=int, choices=(0, 1, 2))
    parser.add_argument("--target", type=int)
    parser.add_argument("--arm", choices=("block", "total", "direct"))
    parser.add_argument("--budget", type=int, nargs=3, default=(3, 3, 3))
    parser.add_argument("--deduction-degree", type=int, choices=(2, 3, 4), default=3)
    parser.add_argument("--output", type=Path, default=Path("block_fraction_results.json"))
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(run_worker(args.n, args.k, args.target,
                                    args.arm, args.budget, args.deduction_degree)), flush=True)
        return
    # Targets copied from the prior paired F4 audit: planted and negative.
    cases = [(7, 1, 1), (7, 1, 50), (11, 1, 679), (11, 1, 702)]
    results = []
    for n, k, target in cases:
        for repeat in range(args.repeats):
            for arm in (("block", "total", "direct") if repeat % 2 == 0
                        else ("direct", "total", "block")):
                command = [sys.executable, str(Path(__file__).resolve()), "--worker",
                           "--n", str(n), "--k", str(k), "--target", str(target),
                           "--arm", arm, "--budget", *map(str, args.budget),
                           "--deduction-degree", str(args.deduction_degree)]
                try:
                    run = subprocess.run(command, capture_output=True, text=True,
                                         timeout=args.timeout, check=True)
                    result = json.loads(run.stdout)
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
                    result = {"n": n, "k": k, "target": target, "arm": arm,
                              "error": str(exc), "stderr": getattr(exc, "stderr", "")}
                result["repeat"] = repeat
                results.append(result)
                args.output.write_text(json.dumps({"model": "filtered Boolean Macaulay/XL",
                                                   "budget": args.budget,
                                                   "deduction_degree": args.deduction_degree,
                                                   "runs": results}, indent=2) + "\n")
                print(json.dumps({"n": n, "k": k, "target": target, "arm": arm,
                                  "repeat": repeat,
                                  "status": result.get("search", {}).get("status", result.get("error")),
                                  "matrix": {key: result.get("matrix", {}).get(key) for key in
                                             ("unique_rows", "columns", "rank")},
                                  "solver_s": result.get("total_solver_seconds")}), flush=True)


if __name__ == "__main__":
    main()
