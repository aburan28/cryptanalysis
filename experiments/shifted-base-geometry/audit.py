"""Bounded forward sumset audit on fixed toy curves; no target or DLP solver.

Tests the disjoint-base construction in Galbraith et al., SAC 2020, section
3.1. Coverage is computed exactly, not inferred from planted decompositions.
This is a geometry diagnostic, not an implementation of their index calculus.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
from itertools import combinations_with_replacement, product
import json
from math import comb, factorial
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parent
ENGINE_PATH = ROOT.parent / "factor-base-yield-v2/engine.py"
spec = importlib.util.spec_from_file_location("shift_geometry_engine", ENGINE_PATH)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
SEEDS = tuple(range(87001, 87009))
CASES = ((13, 3, 4), (19, 3, 5), (19, 3, 6))
MAX_LEAVES = 100_000


def binary_rank(vectors):
    pivots = {}
    for value in vectors:
        while value:
            lead = value.bit_length() - 1
            if lead in pivots:
                value ^= pivots[lead]
            else:
                pivots[lead] = value
                break
    return len(pivots)


def normal_basis(field, seed):
    rng = random.Random(seed)
    for _ in range(1000):
        basis = [rng.randrange(1, field.limit)]
        for _ in range(field.degree - 1):
            basis.append(field.square(basis[-1]))
        if binary_rank(basis) == field.degree:
            assert field.square(basis[-1]) == basis[0]
            return basis
    raise ValueError("normal basis search cap")


def subspace(basis):
    result = [0]
    for vector in basis:
        result += [value ^ vector for value in result]
    return result


def histogram(curve, bases, homogeneous):
    """Forward enumeration, retaining multiplicities but no inverse lookup."""
    size, arity = len(bases[0]), len(bases)
    leaves = comb(size + arity - 1, arity) if homogeneous and size else size ** arity
    if leaves > MAX_LEAVES:
        raise ValueError("toy tuple cap")
    counts = Counter()

    def visit(depth, point, first):
        if depth == arity:
            counts[point] += 1
            return
        for i in range(first if homogeneous else 0, size):
            visit(depth + 1, curve.add(point, bases[depth][i]), i)

    visit(0, None, 0)
    assert sum(counts.values()) == leaves
    return counts


def independent_histogram(bases, homogeneous, degree, modulus):
    """Separate arithmetic and flat tuple enumeration, without prefix reuse."""
    choices = (combinations_with_replacement(range(len(bases[0])), len(bases))
               if homogeneous else product(range(len(bases[0])), repeat=len(bases)))
    result = Counter()
    # Cache only arithmetic pairs; the flat tuple enumeration is exhaustive.
    cache = {}
    for indices in choices:
        point = None
        for j, index in enumerate(indices):
            pair = point, bases[j][index]
            if pair not in cache:
                cache[pair] = engine.ref.add(*pair, degree, modulus)
            point = cache[pair]
        result[point] += 1
    return result


def describe(counts, prime):
    nonzero = {point: count for point, count in counts.items() if point is not None}
    canonical = sorted((list(point) if point is not None else [], count)
                       for point, count in counts.items())
    return {"tuple_leaves": sum(counts.values()), "nonzero_support": len(nonzero),
            "coverage": len(nonzero) / (prime - 1),
            "identity_multiplicity": counts.get(None, 0),
            "nonzero_energy": sum(count * count for count in nonzero.values()),
            "histogram_sha256": hashlib.sha256(json.dumps(canonical).encode()).hexdigest()}


def cell(degree, dimension, arity, seed, independent=False):
    if (degree, dimension, arity) not in CASES or seed not in SEEDS:
        raise ValueError("only the fixed toy panel is supported")
    assert dimension * arity <= degree
    ledger = engine.Ledger()
    with ledger.phase("construction"):
        curve, prime, generator, lam = engine.setup(degree, ledger)
        basis = normal_basis(curve.f, seed)
        spaces = [set(subspace([basis[arity * j + i] for j in range(dimension)]))
                  for i in range(arity)]
        assert all(spaces[i] & spaces[j] == {0}
                   for i in range(arity) for j in range(i))
        base = sorted(point for x in spaces[0] for point in curve.lift(x)
                      if point is not None and curve.mul(point, prime) is None)
        shifted = [base]
        for i in range(1, arity):
            shifted.append([engine.old.phi(curve, point) for point in shifted[-1]])
        for i, points in enumerate(shifted):
            assert all(p[0] in spaces[i] and curve.on_curve(p) for p in points)
            assert all(curve.mul(p, pow(lam, i, prime)) == q
                       for p, q in zip(base, points))
        assert all(set(shifted[i]).isdisjoint(shifted[j])
                   for i in range(arity) for j in range(i))
        representatives, _, _ = engine.old.fold_base(curve, base, prime, lam)
        union_representatives, _, _ = engine.old.fold_base(
            curve, sorted(set().union(*map(set, shifted))), prime, lam)
        assert representatives == union_representatives
        known = engine.public_rows(curve, representatives, prime, generator, lam)

    data = {"degree": degree, "dimension": dimension, "arity": arity, "seed": seed,
            "normal_element": basis[0], "prime": prime, "base_points": len(base),
            "folded_columns": len(representatives), "initially_known_columns": len(known),
            "union_folded_columns": len(union_representatives),
            "asymptotic_tuple_factor": factorial(arity), "independent_replay": independent}
    for name, bases, homogeneous in (("same_base", [base] * arity, True),
                                     ("shifted_bases", shifted, False)):
        with ledger.phase(name):
            counts = histogram(curve, bases, homogeneous)
        if independent:
            with ledger.phase(name + "_independent_replay"):
                replay = independent_histogram(bases, homogeneous, degree, curve.f.modulus)
                assert replay == counts, "independent histogram disagreement"
        data[name] = describe(counts, prime)
    ordinary = data["same_base"]["nonzero_support"]
    changed = data["shifted_bases"]["nonzero_support"]
    data["coverage_ratio"] = changed / ordinary if ordinary else None
    data["status"] = "complete" if base else "empty_base"
    data["phases"] = ledger.report()
    return data


def source_hashes():
    sources = [Path(__file__), ENGINE_PATH]
    sources += [engine.V1 / name for name in ("study.py", "toy_group.py", "verify.py", "reference_group.py")]
    return {str(path.relative_to(ROOT.parent.parent)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--independent-replay", action="store_true")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists")
    started = time.perf_counter()
    rows = []
    for degree, dimension, arity in CASES:
        for seed in SEEDS:
            row = cell(degree, dimension, arity, seed, args.independent_replay)
            rows.append(row)
            print(json.dumps({k: row[k] for k in ("degree", "arity", "seed", "base_points", "coverage_ratio")}),
                  file=sys.stderr, flush=True)
    report = {"kind": "exact_toy_forward_sumset_geometry", "sources": source_hashes(),
              "scope": "Fixed degrees 13 and 19 only; no target input, relation solver, or logarithm extraction",
              "pilot_disclosure": "Seeds 87001..87008 at degree 19 were inspected for base size before the full panel; no cases were removed",
              "cost_claim": None, "degree131_speedup": None, "rank_yield": None,
              "rows": rows, "elapsed_seconds": time.perf_counter() - started}
    with args.out.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
