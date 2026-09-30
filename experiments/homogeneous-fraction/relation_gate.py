#!/usr/bin/env python3
"""A subgroup-valid, fully charged relation-collection gate for fraction x's.

The n=13,k=2 original fraction point set contains four-torsion classes. Each
verified relation is projected by the cofactor four before sign-folded rank is
tested over the prime-order subgroup. This is an honest meet-in-middle control
for the homogeneous-block experiment, not a claimed IC speedup.
"""

import argparse
import collections
import hashlib
import json
import random
import resource
import subprocess
import sys
import time
from pathlib import Path

from block_fraction_solver import MODULI, fraction_pair
from math_model import GF2n

N = 13
K = 2
MODULUS = MODULI[N]
COFACTOR = 4
ORDER = 2003
SEED = 20260927


def mul(field, point, scalar):
    out = None
    while scalar:
        if scalar & 1:
            out = field.add(out, point)
        point = field.add(point, point)
        scalar >>= 1
    return out


def negative(point):
    return None if point is None else (point[0], point[1] ^ point[0])


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def prepare_base():
    start = time.perf_counter_ns()
    field = GF2n(N, MODULUS)
    all_points = field.all_points()
    assert len(all_points) + 1 == COFACTOR * ORDER
    lookup = collections.defaultdict(list)
    for point in all_points:
        lookup[point[0]].append(point)
    abscissae = set()
    for word in range(1 << (2 * (K + 1))):
        numerator, denominator = fraction_pair(word, K, field)
        if denominator:
            abscissae.add(field.mul(numerator, field.inv(denominator)))
    original = sorted(point for x in abscissae for point in lookup[x])
    projected = {point: mul(field, point, COFACTOR) for point in original}
    subgroup = sorted(set(projected.values()) - {None})
    assert all(mul(field, point, ORDER) is None for point in subgroup)
    assert len(original) == 35 and len(subgroup) == 16
    representatives = sorted({min(point, negative(point)) for point in subgroup})
    assert len(representatives) == 8
    column = {point: (j, 1 if point == rep else -1)
              for j, rep in enumerate(representatives)
              for point in (rep, negative(rep))}
    assert len(column) == len(subgroup)
    generator = subgroup[0]
    assert generator and mul(field, generator, ORDER) is None
    base = {
        "n": N, "k": K, "modulus": hex(MODULUS),
        "curve": "y^2+xy=x^3+1", "curve_order": COFACTOR * ORDER,
        "subgroup_order": ORDER, "cofactor": COFACTOR,
        "fraction_abscissae": sorted(abscissae), "original_points": original,
        "projected_points": subgroup, "signed_representatives": representatives,
        "generator": generator, "projection": "P -> [4]P",
        "rank_modulus": ORDER,
    }
    return (field, original, projected, column, generator, base,
            time.perf_counter_ns() - start)


class Rank:
    def __init__(self, columns):
        self.columns = columns
        self.pivots = {}
        self.seen = set()

    @property
    def value(self):
        return len(self.pivots)

    def add(self, coefficients):
        signature = tuple(x % ORDER for x in coefficients)
        repeated = signature in self.seen
        self.seen.add(signature)
        vector = list(signature)
        for lead in sorted(self.pivots):
            factor = vector[lead]
            if factor:
                pivot = self.pivots[lead]
                vector = [(x - factor * y) % ORDER for x, y in zip(vector, pivot)]
        lead = next((i for i, x in enumerate(vector) if x), None)
        if lead is None:
            return False, repeated
        inv = pow(vector[lead], ORDER - 2, ORDER)
        self.pivots[lead] = [x * inv % ORDER for x in vector]
        return True, repeated


def pair_table(field, original):
    start = time.perf_counter_ns()
    table = collections.defaultdict(list)
    for i, point in enumerate(original):
        for j in range(i, len(original)):
            table[field.add(point, original[j])].append((i, j))
    return table, time.perf_counter_ns() - start


def relation_vector(points, projected, column):
    vector = [0] * (len(column) // 2)
    for point in points:
        image = projected[point]
        if image is not None:
            j, sign = column[image]
            vector[j] += sign
    return tuple(vector)


def collect(field, original, projected, column, generator, table,
            scalar, rank, ordinal):
    started = time.perf_counter_ns()
    query_start = time.perf_counter_ns()
    target = mul(field, generator, scalar)
    query_ns = time.perf_counter_ns() - query_start
    assert target is not None and mul(field, target, ORDER) is None
    check_ns = rank_ns = 0
    candidates = duplicates = dependent = 0
    rank_before = rank.value
    status = "no_relation"
    relation = None
    for third in original:
        lookup_start = time.perf_counter_ns()
        needed = field.add(target, negative(third))
        pairs = table.get(needed, ())
        query_ns += time.perf_counter_ns() - lookup_start
        for i, j in pairs:
            points = (original[i], original[j], third)
            candidates += 1
            verify_start = time.perf_counter_ns()
            exact = field.add(field.add(points[0], points[1]), points[2])
            assert exact == target
            assert field.s4(*(p[0] for p in points), target[0]) == 0
            projected_sum = field.add(
                field.add(projected[points[0]], projected[points[1]]),
                projected[points[2]])
            assert projected_sum == mul(field, target, COFACTOR)
            row = relation_vector(points, projected, column)
            assert row and any(row)
            check_ns += time.perf_counter_ns() - verify_start
            rank_start = time.perf_counter_ns()
            novel, repeated = rank.add(row)
            rank_ns += time.perf_counter_ns() - rank_start
            duplicates += repeated
            dependent += not novel and not repeated
            if novel:
                status = "new_independent_relation"
                relation = {"points": points, "coefficients": row,
                            "projected_rhs_scalar": COFACTOR * scalar % ORDER}
                break
            status = "dependent_relation"
        if relation is not None:
            break
    wall_ns = time.perf_counter_ns() - started
    return {
        "index": ordinal, "target_scalar": scalar, "target_point": target,
        "status": status, "rank_before": rank_before, "rank_after": rank.value,
        "candidates_verified": candidates, "repeated_rows": duplicates,
        "other_dependent_rows": dependent, "relation": relation,
        "timings_ns": {"query": query_ns, "verification": check_ns,
                       "rank": rank_ns, "unattributed": wall_ns-query_ns-check_ns-rank_ns,
                       "total": wall_ns},
    }


def worker(attempts, seed, target_rank):
    total_start = time.perf_counter_ns()
    field, original, projected, column, generator, base, build_ns = prepare_base()
    table, table_ns = pair_table(field, original)
    assert sum(map(len, table.values())) == len(original) * (len(original) + 1) // 2
    rng = random.Random(seed)
    rank = Rank(len(column) // 2)
    targets = [rng.randrange(1, ORDER) for _ in range(attempts)]
    records = []
    for i, scalar in enumerate(targets):
        records.append(collect(field, original, projected, column, generator,
                               table, scalar, rank, i))
        if target_rank and rank.value >= target_rank:
            break
    all_ns = time.perf_counter_ns() - total_start
    assert rank.value == sum(r["status"] == "new_independent_relation" for r in records)
    expected = sum((r["timings_ns"]["total"] for r in records), 0) + build_ns + table_ns
    assert all_ns >= expected
    return {
        "schema": "homogeneous-fraction-relation-gate.v1",
        "scope": "relation_collection_only; no final LA or DLP",
        "candidate_id": None, "solver": "complete direct point-pair table",
        "target_rank": target_rank,
        "status": "rank_reached" if target_rank and rank.value >= target_rank
                  else "fixed_attempts_complete" if not target_rank else "budget_exhausted",
        "seed": seed, "targets": targets, "workload_sha256": digest(targets),
        "base": base, "base_sha256": digest(base),
        "counts": {
            "attempt_budget": attempts, "ordinary_attempts": len(records),
            "verified_relations": sum(
                r["candidates_verified"] > 0 for r in records),
            "novel_rows": rank.value,
            "failed_targets": sum(r["status"] == "no_relation" for r in records),
            "dependent_targets": sum(r["status"] == "dependent_relation" for r in records),
            "repeated_rows": sum(r["repeated_rows"] for r in records),
            "rank": rank.value, "effective_columns": rank.columns,
            "original_fraction_points": len(original),
            "projected_base_points": len(column),
            "pair_entries": sum(map(len, table.values())),
            "distinct_pair_sums": len(table),
        },
        "timings_ns": {
            "base_construction": build_ns, "pair_index_construction": table_ns,
            "query_generation_and_lookup": sum(r["timings_ns"]["query"] for r in records),
            "point_and_equation_verification": sum(
                r["timings_ns"]["verification"] for r in records),
            "rank_filter": sum(r["timings_ns"]["rank"] for r in records),
            "unattributed": all_ns - expected
                            + sum(r["timings_ns"]["unattributed"] for r in records),
            "charged_total": all_ns,
        },
        "charged_seconds_per_new_row": all_ns / 1e9 / rank.value if rank.value else None,
        "attempts": records, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--worker", action="store_true")
    p.add_argument("--attempts", type=int, default=128)
    p.add_argument("--target-rank", type=int, default=8,
                   help="stop at this independent rank; use 0 for a fixed-length yield audit")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--seeds", nargs="+", type=int,
                   help="freeze several ordinary-target workloads")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--out", type=Path, default=Path("relation_gate_results.json"))
    args = p.parse_args()
    if not 0 <= args.target_rank <= 8:
        p.error("target rank must be between 0 and eight signed columns")
    if args.worker:
        print(json.dumps(worker(args.attempts, args.seed, args.target_rank)), flush=True)
        return
    runs = []
    for seed in args.seeds or [args.seed]:
        for repeat in range(args.repeats):
            started = time.perf_counter_ns()
            proc = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker",
                 "--attempts", str(args.attempts), "--seed", str(seed),
                 "--target-rank", str(args.target_rank)],
                text=True, capture_output=True, check=True, timeout=120)
            wall_ns = time.perf_counter_ns() - started
            result = json.loads(proc.stdout)
            result["repeat"] = repeat
            result["driver_wall_ns_including_startup"] = wall_ns
            result["driver_seconds_per_new_row"] = (
                wall_ns / 1e9 / result["counts"]["novel_rows"]
                if result["counts"]["novel_rows"] else None)
            runs.append(result)
            args.out.write_text(json.dumps({"runs": runs}, separators=(",", ":")) + "\n")
            print(json.dumps({"seed": seed, "repeat": repeat,
                              "attempts": result["counts"]["ordinary_attempts"],
                              "attempt_budget": args.attempts, "target_rank": args.target_rank,
                              "verified": result["counts"]["verified_relations"],
                              "rank": result["counts"]["rank"],
                              "failed": result["counts"]["failed_targets"],
                              "dependent": result["counts"]["dependent_targets"],
                              "charged_seconds_per_row": result["driver_seconds_per_new_row"]}),
                  flush=True)


if __name__ == "__main__":
    main()
