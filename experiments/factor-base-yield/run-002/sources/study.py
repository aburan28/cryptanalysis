"""Exhaustive ordinary-input and rank-yield study on four fixed toy groups."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
from itertools import combinations_with_replacement
import json
from pathlib import Path
import platform
import random
import time

from toy_group import BinaryCurve, BinaryField, Ledger, PROFILES, require

ROOT = Path(__file__).resolve().parent
FORMAT = "ordinary-rank-yield-v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def ratio(a, b):
    if not b:
        return None
    f = Fraction(a, b)
    return {"numerator": f.numerator, "denominator": f.denominator, "value": float(f)}


def point(p):
    return None if p is None else list(p)


def phi(curve, p):
    return curve.f.square(p[0]), curve.f.square(p[1])


def orbit(curve, p, prime, eigenvalue):
    result = {}
    coefficient = 1
    for _ in range(curve.f.degree):
        for q, c in ((p, coefficient), (curve.neg(p), -coefficient % prime)):
            if q in result:
                require(result[q] == c, "inconsistent orbit stabilizer")
            result[q] = c
        p, coefficient = phi(curve, p), coefficient * eigenvalue % prime
    return result


def setup(degree, ledger):
    require(degree in PROFILES, "unsupported toy degree")
    modulus, prime = PROFILES[degree]
    require(prime <= 2003 and all(prime % i for i in range(2, int(prime ** .5) + 1)), "nonprime toy subgroup")
    curve = BinaryCurve(BinaryField(degree, modulus, ledger))
    require(curve.f.irreducible(), "reducible polynomial")
    generator = None
    for x in range(1 << degree):
        ledger.tick("generator_x_candidates")
        lifts = curve.lift(x)
        if lifts:
            candidate = curve.mul(lifts[0], 4)
            if candidate is not None:
                generator = candidate
                break
    require(generator is not None and curve.mul(generator, prime) is None, "invalid toy generator")
    image = phi(curve, generator)
    roots = []
    for value in range(prime):
        ledger.tick("endomorphism_polynomial_candidates")
        if (value * value + value + 2) % prime == 0:
            roots.append(value)
    eigenvalues = [value for value in roots if curve.mul(generator, value) == image]
    require(len(eigenvalues) == 1, "endomorphism eigenvalue is not unique")
    return curve, prime, generator, eigenvalues[0]


def subspace_base(curve, prime, dimension):
    require(1 <= dimension <= min(7, curve.f.degree), "invalid toy subspace dimension")
    result = []
    for x in range(1 << dimension):
        curve.ledger.tick("factor_base_x_candidates")
        for p in curve.lift(x):
            require(curve.on_curve(p), "invalid lift")
            curve.ledger.tick("subgroup_checks")
            if curve.mul(p, prime) is None:
                result.append(p)
    require(len(result) <= 64, "toy base exceeds fixed cap")
    return tuple(sorted(result))


def fold_base(curve, base, prime, eigenvalue):
    ambient = {}
    for p in base:
        if p not in ambient:
            representative = min(orbit(curve, p, prime, eigenvalue))
            for q, coefficient in orbit(curve, representative, prime, eigenvalue).items():
                ambient[q] = representative, coefficient
    representatives = sorted({ambient[p][0] for p in base})
    columns = {p: i for i, p in enumerate(representatives)}
    encoding = [(columns[ambient[p][0]], ambient[p][1]) for p in base]
    occupancy = sorted(Counter(column for column, _ in encoding).values())
    return representatives, encoding, occupancy


def matched_control(curve, base, prime, generator, eigenvalue, seed):
    representatives, encoding, _ = fold_base(curve, base, prime, eigenvalue)
    counts = Counter(column for column, _ in encoding)
    generator_rep = min(orbit(curve, generator, prime, eigenvalue))
    known_count = next((counts[i] for i, p in enumerate(representatives) if p == generator_rep), 0)
    occupancy = sorted(counts[i] for i, p in enumerate(representatives) if p != generator_rep)
    catalog, seen = [], set()
    p = None
    for _ in range(1, prime):
        p = curve.add(p, generator)
        curve.ledger.tick("control_catalog_points")
        if p not in seen:
            members = orbit(curve, p, prime, eigenvalue)
            representative = min(members)
            catalog.append(representative)
            seen.update(members)
    require(len(seen) == prime - 1, "incomplete toy orbit catalog")
    rng = random.Random(seed)
    chosen = rng.sample(sorted(p for p in catalog if p != generator_rep), len(occupancy))
    if known_count:
        chosen.append(generator_rep)
        occupancy.append(known_count)
    result = []
    for representative, count in zip(chosen, occupancy):
        members = orbit(curve, representative, prime, eigenvalue)
        pairs = sorted({min(q, curve.neg(q)) for q in members})
        require(count % 2 == 0 and count // 2 <= len(pairs), "unmatchable occupancy")
        for q in rng.sample(pairs, count // 2):
            result.extend((q, curve.neg(q)))
    return tuple(sorted(result))


class Span:
    """Coefficient rank only. Right-hand sides are never solved for logs."""
    def __init__(self, columns, prime, ledger=None):
        self.columns, self.prime, self.ledger = columns, prime, ledger
        self.pivots = {}

    def reduce(self, row):
        vector = list(row)
        for col, pivot in sorted(self.pivots.items()):
            factor = vector[col]
            if factor:
                for j in range(col, self.columns):
                    vector[j] = (vector[j] - factor * pivot[j]) % self.prime
                    if self.ledger:
                        self.ledger.tick("rank_modular_multiply_subtracts")
        return vector

    def add(self, row):
        vector = self.reduce(row)
        for col, value in enumerate(vector):
            if value:
                inverse = pow(value, -1, self.prime)
                if self.ledger:
                    self.ledger.tick("rank_modular_inversions")
                    self.ledger.tick("rank_modular_multiplications", self.columns - col)
                self.pivots[col] = [x * inverse % self.prime for x in vector]
                return True
        return False

    @property
    def rank(self):
        return len(self.pivots)


def folded_row(witness, encoding, columns, prime):
    row = [0] * columns
    for i in witness:
        col, coefficient = encoding[i]
        row[col] = (row[col] + coefficient) % prime
    return row


def known_generator_rows(curve, representatives, generator, prime, eigenvalue):
    members = orbit(curve, generator, prime, eigenvalue)
    rows = []
    for i, p in enumerate(representatives):
        if p in members:
            row = [0] * len(representatives)
            row[i] = 1
            coefficient = members[p]
            require(curve.mul(generator, coefficient) == p, "invalid known generator-orbit column")
            rows.append({"row": row, "scalar_rhs": coefficient})
    return rows


def make_pairs(curve, base):
    table = {}
    for i, j in combinations_with_replacement(range(len(base)), 2):
        q = curve.add(base[i], base[j])
        curve.ledger.tick("pair_candidates")
        table.setdefault(q, (i, j))
    return table


def query(curve, base, table, target, budget):
    for i in range(min(budget, len(base))):
        residual = curve.add(target, curve.neg(base[i]))
        curve.ledger.tick("pair_lookup_probes")
        pair = table.get(residual)
        if pair is not None:
            return {"status": "found", "probes": i + 1, "witness": sorted((i, *pair))}
    return {"status": "no_decomposition" if budget >= len(base) else "budget",
            "probes": min(budget, len(base)), "witness": None}


def collect(degree, dimension, control_seed, query_seed, budget_label, maximum_queries):
    require(type(maximum_queries) is int and 0 <= maximum_queries <= 256, "toy stream exceeds 256-query cap")
    ledger = Ledger()
    start = time.perf_counter_ns()
    with ledger.phase("parameter_generator_endomorphism_validation"):
        curve, prime, generator, eigenvalue = setup(degree, ledger)
    with ledger.phase("factor_base_construction"):
        base = subspace_base(curve, prime, dimension)
        if control_seed is not None and base:
            base = matched_control(curve, base, prime, generator, eigenvalue, control_seed)
        reps, encoding, occupancy = fold_base(curve, base, prime, eigenvalue)
    with ledger.phase("pair_table_construction"):
        table = make_pairs(curve, base)
    span = Span(len(reps), prime, ledger)
    with ledger.phase("initial_known_information"):
        known_rows = known_generator_rows(curve, reps, generator, prime, eigenvalue)
        for known in known_rows:
            span.add(known["row"])
    initial_rank = span.rank
    rng, records = random.Random(query_seed), []
    budget = len(base) if budget_label == "complete" else budget_label
    for _ in range(maximum_queries if span.rank < len(reps) else 0):
        with ledger.phase("ordinary_input_generation"):
            scalar = rng.randrange(1, prime)
            target = curve.mul(generator, scalar)
        with ledger.phase("bounded_decomposition"):
            result = query(curve, base, table, target, budget)
        row, independent = None, False
        if result["status"] == "found":
            with ledger.phase("witness_and_folded_row_verification"):
                total = None
                for i in result["witness"]:
                    total = curve.add(total, base[i])
                require(total == target, "invalid point witness")
                row = folded_row(result["witness"], encoding, len(reps), prime)
                check = None
                for p, coefficient in zip(reps, row):
                    if coefficient:
                        check = curve.add(check, curve.mul(p, coefficient))
                require(check == target, "folded row does not match known scalar RHS")
                ledger.tick("verified_rows")
            with ledger.phase("incremental_rank"):
                independent = span.add(row)
        records.append({"scalar_rhs": scalar, "target": point(target), **result,
                        "row": row, "independent": independent,
                        "rank": span.rank - initial_rank, "matrix_rank": span.rank})
        if span.rank == len(reps):
            break
    elapsed = time.perf_counter_ns() - start
    phases = ledger.report()
    return {
        "degree": degree, "dimension": dimension, "prime": prime,
        "modulus": curve.f.modulus, "generator": point(generator), "eigenvalue": eigenvalue,
        "control_seed": control_seed, "query_seed": query_seed, "probe_budget": budget,
        "budget_label": budget_label, "base": list(map(point, base)),
        "representatives": list(map(point, reps)), "encoding": encoding,
        "occupancy": occupancy, "base_points": len(base), "columns": len(reps),
        "pair_entries": len(table), "queries": records, "rank": span.rank - initial_rank,
        "matrix_rank": span.rank, "initial_known_rank": initial_rank, "known_rows": known_rows,
        "unknown_columns": len(reps) - initial_rank,
        "status": "empty_base" if not base else "already_known" if initial_rank == len(reps) else "full_rank" if span.rank == len(reps) else "censored",
        "cold_collection_ns": elapsed,
        "cold_ns_per_independent_row": elapsed / (span.rank - initial_rank) if span.rank > initial_rank else None,
        "phases": phases,
        "unattributed_bookkeeping_ns": max(0, elapsed - round(sum(p["seconds"] for p in phases.values()) * 1e9)),
    }


def oracle(case):
    """Exhaustive diagnostic, called only after measured collection has finished."""
    ledger = Ledger()
    with ledger.phase("exhaustive_support_and_query_diagnostic"):
        curve, prime, generator, eigenvalue = setup(case["degree"], ledger)
        base = tuple(map(tuple, case["base"]))
        require(len(base) <= 64, "oracle base cap")
        from math import comb
        require(comb(len(base) + 2, 3) <= 50000, "oracle multiset cap")
        targets, labels = [], {}
        p = None
        for scalar in range(1, prime):
            p = curve.add(p, generator)
            targets.append(p)
            labels[p] = scalar
        require(len(labels) == prime - 1 and curve.add(p, generator) is None, "toy subgroup enumeration failed")
        counts = Counter()
        for witness in combinations_with_replacement(range(len(base)), 3):
            p = None
            for i in witness:
                p = curve.add(p, base[i])
            counts[labels.get(p, 0)] += 1
        require(sum(counts.values()) == comb(len(base) + 2, 3), "multiset total mismatch")
        weights = {a: n for a, n in counts.items() if a}
        w, energy = sum(weights.values()), sum(n * n for n in weights.values())
        support = len(weights)
        require(not energy or w * w <= support * energy, "energy inequality failed")
        table = make_pairs(curve, base)
        results, all_rows = [], Span(case["columns"], prime)
        for known in case["known_rows"]:
            all_rows.add(known["row"])
        for scalar, target in enumerate(targets, 1):
            result = query(curve, base, table, target, case["probe_budget"])
            row = None
            if result["status"] == "found":
                require(scalar in weights, "solver returned out-of-support point")
                row = folded_row(result["witness"], case["encoding"], case["columns"], prime)
                all_rows.add(row)
            if case["budget_label"] == "complete":
                require((result["status"] == "found") == (scalar in weights), "complete solver missed support")
            results.append({"scalar_rhs": scalar, **result, "row": row})
        found = sum(q["status"] == "found" for q in results)
    return {"support": support, "nonzero_multisets": w, "zero_multisets": counts.get(0, 0),
            "energy": energy, "coverage": ratio(support, prime - 1),
            "energy_coverage_lower_bound": ratio(w * w, (prime - 1) * energy),
            "counting_coverage_upper_bound": ratio(min(prime - 1, comb(len(base) + 2, 3)), prime - 1),
            "found": found, "solver_yield": ratio(found, prime - 1),
            "conditional_solver_success": ratio(found, support),
            "selected_row_span_rank": all_rows.rank - case["initial_known_rank"],
            "multiplicities": [[a, weights[a]] for a in sorted(weights)],
            "ordinary_queries": results, "phases": ledger.report()}


def frontiers(case, diagnostic):
    span, states = Span(case["columns"], case["prime"]), []
    for known in case["known_rows"]:
        span.add(known["row"])
    total_probes = sum(q["probes"] for q in diagnostic["ordinary_queries"])
    def record(prefix):
        novel = sum(any(span.reduce(q["row"])) for q in diagnostic["ordinary_queries"] if q["row"] is not None)
        states.append({"after_queries": prefix, "rank": span.rank - case["initial_known_rank"],
                       "matrix_rank": span.rank,
                       "novel_inputs": novel, "independent_yield": ratio(novel, case["prime"] - 1),
                       "conditional_novelty": ratio(novel, diagnostic["found"]),
                       "expected_lookup_probes_to_next_rank": ratio(total_probes, novel),
                       "next_rank_reachable": bool(novel)})
    record(0)
    for i, q in enumerate(case["queries"], 1):
        if q["row"] is not None and span.add(q["row"]):
            record(i)
    return states


def write_json(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write("\n")


def run(out):
    require(not out.exists(), "output directory must be new")
    contract = json.loads((ROOT / "contract.json").read_text())
    out.mkdir(parents=True)
    with (out / "contract.json").open("xb") as stream:
        stream.write((ROOT / "contract.json").read_bytes())
    source_names = ["study.py", "toy_group.py", "reference_group.py", "verify.py", "test_study.py", "contract.json"]
    (out / "sources").mkdir()
    source_hashes = {}
    for name in source_names:
        data = (ROOT / name).read_bytes()
        (out / "sources" / name).write_bytes(data)
        source_hashes[name] = hashlib.sha256(data).hexdigest()
    summaries, number = [], 0
    overall_start = time.perf_counter_ns()
    for profile in contract["profiles"]:
        degree = profile["degree"]
        for dimension in profile["dimensions"]:
            for control_seed in [None, *contract["control_seeds"]]:
                # Alternate budget order between controls; no winner selection.
                budgets = list(contract["probe_budgets"])
                if control_seed is not None and control_seed % 2:
                    budgets.reverse()
                for budget_label in budgets:
                    cases = [collect(degree, dimension, control_seed, seed, budget_label,
                                     contract["maximum_queries_per_stream"])
                             for seed in contract["query_seeds"]]
                    diagnostic = oracle(cases[0])
                    for case in cases:
                        require(case["base"] == cases[0]["base"], "base changed across streams")
                        case["rank_frontiers"] = frontiers(case, diagnostic)
                    number += 1
                    filename = f"cell-{number:03d}.json"
                    write_json(out / filename, {"format": FORMAT, "cases": cases, "oracle": diagnostic})
                    summary = {k: cases[0][k] for k in ("degree", "dimension", "control_seed", "budget_label", "base_points", "columns", "unknown_columns", "initial_known_rank", "occupancy")}
                    summary.update({k: diagnostic[k] for k in ("support", "coverage", "energy", "energy_coverage_lower_bound", "found", "solver_yield", "selected_row_span_rank")})
                    summary.update({"file": filename, "statuses": [c["status"] for c in cases],
                                    "ranks": [c["rank"] for c in cases], "attempts": [len(c["queries"]) for c in cases],
                                    "cold_collection_ns": [c["cold_collection_ns"] for c in cases],
                                    "cold_ns_per_independent_row": [c["cold_ns_per_independent_row"] for c in cases]})
                    summaries.append(summary)
                    print(json.dumps({"cell": number, **{k: summary[k] for k in ("degree", "dimension", "control_seed", "budget_label", "base_points", "columns", "support", "ranks", "statuses")}}), flush=True)
    write_json(out / "summary.json", {"format": FORMAT, "python": platform.python_version(),
               "platform": platform.platform(), "contract_sha256": source_hashes["contract.json"],
               "source_sha256": source_hashes, "cells": summaries,
               "research_wall_ns_before_final_serialization": time.perf_counter_ns() - overall_start,
               "claims": {"exact_finite_support": True, "ordinary_known_rhs_queries": True,
                          "orbit_copies_count_as_new_rank": False, "degree131_execution": False,
                          "scaling_law_established": False, "full_dlp_cost": None, "rho_ratio": None}})
    artifacts = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(out.rglob("*")) if p.is_file()}
    write_json(out / "manifest.json", {"format": FORMAT, "sha256": artifacts})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    run(args.out)
