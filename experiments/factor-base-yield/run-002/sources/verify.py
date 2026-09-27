"""Independent reference-group, multiplicity, bounded-solver and rank replay.

This verifier does not import the measured collector or its rank implementation.
The complete toy group is independently enumerated for audit only. Its scalar
labels never enter the collector, and no unknown logarithm is extracted.
"""
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
from itertools import combinations_with_replacement
import json
from math import comb
from pathlib import Path
import random
import time

import reference_group as ref

PROFILES = {5: (0x25, 11), 7: (0x83, 29), 9: (0x211, 127), 13: (0x201b, 2003)}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def fraction(a, b):
    if not b:
        return None
    f = Fraction(a, b)
    return {"numerator": f.numerator, "denominator": f.denominator, "value": float(f)}


def neg(p):
    return p[0], p[0] ^ p[1]


def frobenius(p, modulus):
    return ref.mul(p[0], p[0], modulus), ref.mul(p[1], p[1], modulus)


def lift(x, n, modulus):
    if x == 0:
        return [(0, 1)]
    beta = x ^ ref.inv(ref.mul(x, x, modulus), n, modulus)
    z, term = 0, beta
    for _ in range((n + 1) // 2):
        z ^= term
        term = ref.mul(term, term, modulus)
        term = ref.mul(term, term, modulus)
    if ref.mul(z, z, modulus) ^ z != beta:
        return []
    y = ref.mul(x, z, modulus)
    return sorted(((x, y), (x, x ^ y)))


def orbit(p, n, modulus):
    result = []
    for _ in range(n):
        result.extend((p, neg(p)))
        p = frobenius(p, modulus)
    return sorted(set(result))


def context(degree):
    check(degree in PROFILES, "unsupported toy degree")
    modulus, prime = PROFILES[degree]
    generator = None
    for x in range(1 << degree):
        points = lift(x, degree, modulus)
        if points:
            generator = ref.scalar_mul(points[0], 4, degree, modulus)
            if generator is not None:
                break
    check(generator is not None, "no generator")
    labels, points, p = {None: 0}, [None], None
    for scalar in range(1, prime):
        p = ref.add(p, generator, degree, modulus)
        check(p is not None and p not in labels, "group cycle too short")
        check(ref.on_curve(p, degree, modulus), "reference point off curve")
        labels[p] = scalar
        points.append(p)
    check(ref.add(p, generator, degree, modulus) is None, "wrong subgroup order")
    eigenvalue = labels[frobenius(generator, modulus)]
    check((eigenvalue * eigenvalue + eigenvalue + 2) % prime == 0, "wrong endomorphism equation")
    catalog = sorted({min(orbit(p, degree, modulus)) for p in points[1:]})
    return {"degree": degree, "modulus": modulus, "prime": prime, "generator": generator,
            "eigenvalue": eigenvalue, "labels": labels, "points": points, "catalog": catalog}


def expected_base(ctx, dimension, control_seed):
    n, modulus, prime = ctx["degree"], ctx["modulus"], ctx["prime"]
    check(1 <= dimension <= min(n, 7), "invalid dimension")
    seed_base = sorted(p for x in range(1 << dimension) for p in lift(x, n, modulus)
                       if ref.scalar_mul(p, prime, n, modulus) is None)
    if control_seed is None or not seed_base:
        return seed_base
    counts = Counter(min(orbit(p, n, modulus)) for p in seed_base)
    generator_rep = min(orbit(ctx["generator"], n, modulus))
    known_count = counts.get(generator_rep, 0)
    occupancy = sorted(count for representative, count in counts.items() if representative != generator_rep)
    rng = random.Random(control_seed)
    representatives = rng.sample([p for p in ctx["catalog"] if p != generator_rep], len(occupancy))
    if known_count:
        representatives.append(generator_rep)
        occupancy.append(known_count)
    base = []
    for representative, count in zip(representatives, occupancy):
        pairs = sorted({min(p, neg(p)) for p in orbit(representative, n, modulus)})
        for p in rng.sample(pairs, count // 2):
            base.extend((p, neg(p)))
    return sorted(base)


def encoding(ctx, base):
    n, modulus, prime, lam = ctx["degree"], ctx["modulus"], ctx["prime"], ctx["eigenvalue"]
    reps = sorted({min(orbit(p, n, modulus)) for p in base})
    coefficients = {}
    for column, representative in enumerate(reps):
        p, coefficient = representative, 1
        for _ in range(n):
            for q, c in ((p, coefficient), (neg(p), -coefficient % prime)):
                check(ctx["labels"][q] == c * ctx["labels"][representative] % prime, "incorrect reference orbit transport")
                coefficients[q] = [column, c]
            p, coefficient = frobenius(p, modulus), coefficient * lam % prime
    result = [coefficients[p] for p in base]
    return reps, result, sorted(Counter(c for c, _ in result).values())


def rank_and_annihilator(rows, columns, prime):
    """Batch Gauss-Jordan plus nullspace: distinct membership test from collector."""
    matrix, pivot_columns, current = [list(row) for row in rows], [], 0
    for column in range(columns):
        pivot = next((i for i in range(current, len(matrix)) if matrix[i][column] % prime), None)
        if pivot is None:
            continue
        matrix[current], matrix[pivot] = matrix[pivot], matrix[current]
        inv = pow(matrix[current][column] % prime, -1, prime)
        matrix[current] = [x * inv % prime for x in matrix[current]]
        for i in range(len(matrix)):
            if i != current and matrix[i][column] % prime:
                value = matrix[i][column] % prime
                matrix[i] = [(a - value * b) % prime for a, b in zip(matrix[i], matrix[current])]
        pivot_columns.append(column)
        current += 1
        if current == len(matrix):
            break
    kernel = []
    for free in sorted(set(range(columns)) - set(pivot_columns)):
        vector = [0] * columns
        vector[free] = 1
        for i, pivot in enumerate(pivot_columns):
            vector[pivot] = -matrix[i][free] % prime
        kernel.append(vector)
    return current, kernel


def is_novel(row, kernel, prime):
    return any(sum(a * b for a, b in zip(row, vector)) % prime for vector in kernel)


def audit_geometry(case, diagnostic, ctx):
    prime, labels = ctx["prime"], ctx["labels"]
    check(case["modulus"] == ctx["modulus"] and case["prime"] == prime, "wrong fixed profile")
    check(tuple(case["generator"]) == ctx["generator"] and case["eigenvalue"] == ctx["eigenvalue"], "wrong generator or eigenvalue")
    base = expected_base(ctx, case["dimension"], case["control_seed"])
    check(case["base"] == [list(p) for p in base], "base recipe mismatch")
    reps, enc, occupancy = encoding(ctx, base)
    check(case["representatives"] == [list(p) for p in reps], "representative mismatch")
    check([list(x) for x in case["encoding"]] == enc and case["occupancy"] == occupancy, "folding mismatch")
    check(case["base_points"] == len(base) and case["columns"] == len(reps), "wrong base dimensions")
    generator_orbit = orbit(ctx["generator"], ctx["degree"], ctx["modulus"])
    known_rows = []
    for i, representative in enumerate(reps):
        if representative in generator_orbit:
            row = [0] * len(reps)
            row[i] = 1
            known_rows.append({"row": row, "scalar_rhs": labels[representative]})
    check(case["known_rows"] == known_rows and case["initial_known_rank"] == len(known_rows), "known generator information mismatch")
    check(case["unknown_columns"] == len(reps) - len(known_rows), "wrong number of unknown columns")
    scalars = [labels[p] for p in base]
    multiplicity = Counter(sum(scalars[i] for i in witness) % prime
                           for witness in combinations_with_replacement(range(len(base)), 3))
    nonzero = {a: n for a, n in multiplicity.items() if a}
    support, mass, energy = len(nonzero), sum(nonzero.values()), sum(n * n for n in nonzero.values())
    expected = {"support": support, "nonzero_multisets": mass, "zero_multisets": multiplicity.get(0, 0),
                "energy": energy, "multiplicities": [[a, nonzero[a]] for a in sorted(nonzero)],
                "coverage": fraction(support, prime - 1),
                "energy_coverage_lower_bound": fraction(mass * mass, (prime - 1) * energy),
                "counting_coverage_upper_bound": fraction(min(prime - 1, comb(len(base) + 2, 3)), prime - 1)}
    for key, value in expected.items():
        check(diagnostic[key] == value, "support/energy mismatch: " + key)
    check(mass * mass <= support * energy, "invalid energy lower bound")
    table = {}
    for i, j in combinations_with_replacement(range(len(base)), 2):
        table.setdefault((scalars[i] + scalars[j]) % prime, (i, j))
    check(case["pair_entries"] == len(table), "pair count mismatch")
    budget = len(base) if case["budget_label"] == "complete" else case["budget_label"]
    check(budget == case["probe_budget"] and case["budget_label"] in (1, "complete"), "invalid query budget")
    expected_queries = []
    for scalar in range(1, prime):
        witness, probes = None, 0
        for i in range(min(budget, len(base))):
            probes += 1
            pair = table.get((scalar - scalars[i]) % prime)
            if pair is not None:
                witness = sorted((i, *pair))
                break
        row = None
        if witness is not None:
            row = [0] * len(reps)
            for i in witness:
                col, coefficient = enc[i]
                row[col] = (row[col] + coefficient) % prime
            check(sum(a * labels[p] for a, p in zip(row, reps)) % prime == scalar, "folded RHS fails reference group")
        status = "found" if witness is not None else "no_decomposition" if budget >= len(base) else "budget"
        expected_queries.append({"scalar_rhs": scalar, "status": status, "probes": probes, "witness": witness, "row": row})
    check(diagnostic["ordinary_queries"] == expected_queries, "exhaustive bounded-query mismatch")
    rows = [q["row"] for q in expected_queries if q["row"] is not None]
    check(diagnostic["found"] == len(rows), "found count mismatch")
    check(diagnostic["solver_yield"] == fraction(len(rows), prime - 1), "solver yield mismatch")
    check(diagnostic["conditional_solver_success"] == fraction(len(rows), support), "conditional solver success mismatch")
    rank, _ = rank_and_annihilator([k["row"] for k in known_rows] + rows, len(reps), prime)
    check(rank - len(known_rows) == diagnostic["selected_row_span_rank"], "selected row rank mismatch")
    if case["budget_label"] == "complete":
        check(len(rows) == support, "complete lookup misses support")
    return expected_queries


def audit_stream(case, diagnostic, ctx, expected_queries):
    prime, columns = ctx["prime"], case["columns"]
    rng = random.Random(case["query_seed"])
    rows = [known["row"] for known in case["known_rows"]]
    initial_rank = case["initial_known_rank"]
    rank, kernel = rank_and_annihilator(rows, columns, prime)
    total_probes = sum(q["probes"] for q in expected_queries)
    frontiers, successes = [], 0
    def frontier(prefix):
        novel = sum(is_novel(q["row"], kernel, prime) for q in expected_queries if q["row"] is not None)
        frontiers.append({"after_queries": prefix, "rank": rank - initial_rank,
                          "matrix_rank": rank, "novel_inputs": novel,
                          "independent_yield": fraction(novel, prime - 1),
                          "conditional_novelty": fraction(novel, diagnostic["found"]),
                          "expected_lookup_probes_to_next_rank": fraction(total_probes, novel),
                          "next_rank_reachable": bool(novel)})
    frontier(0)
    for i, query in enumerate(case["queries"], 1):
        scalar = rng.randrange(1, prime)
        check(query["scalar_rhs"] == scalar, "ordinary scalar stream mismatch")
        check(tuple(query["target"]) == ctx["points"][scalar], "ordinary query point mismatch")
        for key, value in expected_queries[scalar - 1].items():
            check(query[key] == value, "sampled query mismatch: " + key)
        novel = query["row"] is not None and is_novel(query["row"], kernel, prime)
        check(query["independent"] == novel, "incorrect rank increment")
        if query["row"] is not None:
            successes += 1
        if novel:
            rows.append(query["row"])
            rank, kernel = rank_and_annihilator(rows, columns, prime)
            frontier(i)
        check(query["rank"] == rank - initial_rank and query["matrix_rank"] == rank, "rank path mismatch")
        check(rank != columns or i == len(case["queries"]), "continued beyond full rank")
    check(case["rank_frontiers"] == frontiers, "exact rank frontier mismatch")
    status = "empty_base" if not case["base"] else "already_known" if initial_rank == columns else "full_rank" if rank == columns else "censored"
    check(case["status"] == status and case["rank"] == rank - initial_rank and case["matrix_rank"] == rank, "wrong terminal status")
    check(len(case["queries"]) <= 256 and (status != "censored" or len(case["queries"]) == 256), "invalid stopping rule")
    check(status not in ("empty_base", "already_known") or not case["queries"], "queries when there are no unknown columns")
    phases = case["phases"]
    counts = Counter()
    for phase in phases.values():
        check(phase["seconds"] >= 0 and all(v >= 0 for v in phase["operations"].values()), "negative phase cost")
        counts.update(phase["operations"])
    check(counts["pair_candidates"] == comb(case["base_points"] + 1, 2), "uncharged pair construction")
    check(counts["pair_lookup_probes"] == sum(q["probes"] for q in case["queries"]), "uncharged lookup")
    check(counts["verified_rows"] == successes, "uncharged verification")
    check(counts["rank_modular_inversions"] == rank, "rank operation count mismatch")
    check(case["cold_collection_ns"] >= sum(p["seconds"] for p in phases.values()) * 1e9, "overlapping phase accounting")
    expected_cost = case["cold_collection_ns"] / (rank - initial_rank) if rank > initial_rank else None
    check(case["cold_ns_per_independent_row"] == expected_cost, "wrong cost denominator")
    return len(case["queries"]), successes, rank - initial_rank


def replay(directory):
    start = time.perf_counter_ns()
    manifest = json.loads((directory / "manifest.json").read_text())
    for name, expected in manifest["sha256"].items():
        path = (directory / name).resolve()
        check(path.is_relative_to(directory.resolve()), "manifest path outside receipt")
        check(hashlib.sha256(path.read_bytes()).hexdigest() == expected, "artifact hash mismatch: " + name)
    summary = json.loads((directory / "summary.json").read_text())
    contract = json.loads((directory / "contract.json").read_text())
    check(summary["contract_sha256"] == hashlib.sha256((directory / "contract.json").read_bytes()).hexdigest(), "contract hash mismatch")
    for name, expected in summary["source_sha256"].items():
        check(hashlib.sha256((directory / "sources" / name).read_bytes()).hexdigest() == expected, "source hash mismatch")
    contexts, seen, queries, rows, increments, oracle_inputs = {}, set(), 0, 0, 0, 0
    expected_cells = {(p["degree"], d, c, b) for p in contract["profiles"] for d in p["dimensions"]
                      for c in [None, *contract["control_seeds"]] for b in contract["probe_budgets"]}
    for entry in summary["cells"]:
        cell = json.loads((directory / entry["file"]).read_text())
        first, diagnostic = cell["cases"][0], cell["oracle"]
        key = tuple(first[k] for k in ("degree", "dimension", "control_seed", "budget_label"))
        check(key not in seen and key in expected_cells, "unexpected or repeated cell")
        seen.add(key)
        if first["degree"] not in contexts:
            contexts[first["degree"]] = context(first["degree"])
        ctx = contexts[first["degree"]]
        expected_queries = audit_geometry(first, diagnostic, ctx)
        oracle_inputs += len(expected_queries)
        check([c["query_seed"] for c in cell["cases"]] == contract["query_seeds"], "missing query stream")
        for case in cell["cases"]:
            for key_name in ("degree", "dimension", "control_seed", "budget_label", "base", "representatives", "encoding", "occupancy", "columns", "base_points", "probe_budget", "known_rows", "initial_known_rank", "unknown_columns"):
                check(case[key_name] == first[key_name], "fixture drift between streams")
            q, v, rank = audit_stream(case, diagnostic, ctx, expected_queries)
            queries, rows, increments = queries + q, rows + v, increments + rank
        for name in ("degree", "dimension", "control_seed", "budget_label", "base_points", "columns", "unknown_columns", "initial_known_rank", "occupancy"):
            check(entry[name] == first[name], "summary fixture mismatch")
        for name in ("support", "coverage", "energy", "energy_coverage_lower_bound", "found", "solver_yield", "selected_row_span_rank"):
            check(entry[name] == diagnostic[name], "summary diagnostic mismatch")
        for name, source in (("statuses", "status"), ("ranks", "rank"), ("cold_collection_ns", "cold_collection_ns"), ("cold_ns_per_independent_row", "cold_ns_per_independent_row")):
            check(entry[name] == [c[source] for c in cell["cases"]], "summary stream mismatch")
        check(entry["attempts"] == [len(c["queries"]) for c in cell["cases"]], "summary attempt mismatch")
    check(seen == expected_cells, "missing frozen cells")
    return {"verified": True, "cells": len(seen), "streams": 3 * len(seen),
            "ordinary_query_records": queries, "verified_row_records": rows,
            "rank_increments": increments, "exhaustive_budgeted_inputs": oracle_inputs,
            "manifest_files": len(manifest["sha256"]), "replay_ns": time.perf_counter_ns() - start,
            "timings_independently_reproduced": False, "all_primitive_counters_independently_reproduced": False,
            "scope": "Independent implementation within this project; not unaffiliated reproduction"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = replay(args.directory)
    if args.out:
        with args.out.open("x") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))
