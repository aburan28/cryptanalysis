"""Bounded, public-synthetic index-calculus relation research without point maps.

The fixed degree-131 profile tests relation arithmetic on synthetic sums only.
This module has no discrete-log extraction or imported-target workflow.
"""

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from itertools import combinations_with_replacement
import json
import math
from pathlib import Path
import platform
import random
import sys
import time


PROFILES = {
    "toy5": (5, 0x25, 11, 3),
    "toy7": (7, 0x83, 29, 6),
    "toy9": (9, 0x211, 127, 6),
    "ecc2k130": (131, (1 << 131) | (1 << 13) | 7,
                 0x200000000000000004D4FDD5703A3F269, 7),
}
FORMAT = "nonfrobenius-ic-relations-v1"
MAX_BASE = 128
MAX_ROWS = 512
MAX_ORACLE_TUPLES = 200000


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Ledger:
    def __init__(self):
        self.current = "unscoped"
        self.counts = defaultdict(Counter)
        self.seconds = defaultdict(float)

    def tick(self, name, count=1):
        self.counts[self.current][name] += count

    @contextmanager
    def phase(self, name):
        previous = self.current
        self.current = name
        start = time.perf_counter()
        try:
            yield
        finally:
            self.seconds[name] += time.perf_counter() - start
            self.current = previous

    def report(self):
        return {name: {"seconds": self.seconds[name],
                       "operations": dict(sorted(self.counts[name].items()))}
                for name in sorted(set(self.seconds) | set(self.counts))}


def polynomial_remainder(value, modulus):
    while value.bit_length() >= modulus.bit_length():
        value ^= modulus << (value.bit_length() - modulus.bit_length())
    return value


def polynomial_gcd(a, b):
    while b:
        a, b = b, polynomial_remainder(a, b)
    return a


class BinaryField:
    """Polynomial coordinates; square is ordinary field arithmetic, not a point map."""

    def __init__(self, degree, modulus, ledger):
        require(degree >= 3 and degree % 2 == 1, "expected odd field degree >= 3")
        require(modulus.bit_length() == degree + 1 and modulus & 1,
                "invalid modulus degree or constant term")
        self.degree, self.modulus, self.ledger = degree, modulus, ledger
        self.limit = 1 << degree

    def _multiply(self, a, b):
        result = 0
        while b:
            if b & 1:
                result ^= a
            b >>= 1
            a <<= 1
            if a & self.limit:
                a ^= self.modulus
        return result

    def mul(self, a, b):
        self.ledger.tick("field_multiplications")
        return self._multiply(a, b)

    def square(self, a):
        self.ledger.tick("field_squarings")
        return self._multiply(a, a)

    def inv(self, a):
        self.ledger.tick("field_inversions")
        if a == 0:
            raise ZeroDivisionError("zero has no inverse")
        u, v, left, right = a, self.modulus, 1, 0
        while u != 1:
            require(u != 0, "modulus is reducible or element is invalid")
            shift = u.bit_length() - v.bit_length()
            if shift < 0:
                u, v, left, right = v, u, right, left
                shift = -shift
            u ^= v << shift
            left ^= right << shift
        return polynomial_remainder(left, self.modulus)

    def irreducible(self):
        # Rabin's criterion, including each prime divisor of the field degree.
        remaining, prime_divisors, divisor = self.degree, set(), 2
        while divisor * divisor <= remaining:
            if remaining % divisor == 0:
                prime_divisors.add(divisor)
                while remaining % divisor == 0:
                    remaining //= divisor
            divisor += 1
        if remaining > 1:
            prime_divisors.add(remaining)
        checkpoints = {self.degree // p for p in prime_divisors}
        power = 2
        for step in range(1, self.degree + 1):
            power = self.square(power)
            if step in checkpoints and polynomial_gcd(power ^ 2, self.modulus) != 1:
                return False
        return power == 2


class BinaryCurve:
    """E: y^2 + xy = x^3 + 1. No curve endomorphism or orbit methods."""

    def __init__(self, field):
        self.f, self.ledger = field, field.ledger

    def on_curve(self, point):
        if point is None:
            return True
        x, y = point
        if not (0 <= x < self.f.limit and 0 <= y < self.f.limit):
            return False
        f = self.f
        return f.square(y) ^ f.mul(x, y) == f.mul(f.square(x), x) ^ 1

    def neg(self, point):
        self.ledger.tick("point_negations")
        return None if point is None else (point[0], point[0] ^ point[1])

    def add(self, first, second):
        self.ledger.tick("point_additions_including_special_cases")
        if first is None:
            return second
        if second is None:
            return first
        f = self.f
        x, y = first
        u, v = second
        if x == u:
            if y != v or x == 0:
                return None
            self.ledger.tick("point_doublings_subset")
            slope = x ^ f.mul(y, f.inv(x))
            out_x = f.square(slope) ^ slope
            out_y = f.square(x) ^ f.mul(slope ^ 1, out_x)
        else:
            slope = f.mul(y ^ v, f.inv(x ^ u))
            out_x = f.square(slope) ^ slope ^ x ^ u
            out_y = f.mul(slope, x ^ out_x) ^ out_x ^ y
        return out_x, out_y

    def mul(self, point, scalar):
        require(type(scalar) is int and scalar >= 0, "expected nonnegative scalar")
        self.ledger.tick("scalar_multiplications")
        result = None
        while scalar:
            if scalar & 1:
                result = self.add(result, point)
            scalar >>= 1
            if scalar:
                point = self.add(point, point)
        return result

    def lift(self, x):
        """Return both actual points above x, including the order-two exception."""
        require(type(x) is int and 0 <= x < self.f.limit, "x outside field")
        if x == 0:
            return [(0, 1)]
        f = self.f
        rhs = x ^ f.inv(f.square(x))
        term, half_trace = rhs, rhs
        for _ in range((f.degree - 1) // 2):
            term = f.square(f.square(term))
            half_trace ^= term
        if f.square(half_trace) ^ half_trace != rhs:
            return []
        y = f.mul(x, half_trace)
        return sorted([(x, y), (x, x ^ y)])


def setup(profile, ledger):
    require(profile in PROFILES, "unknown fixed profile")
    degree, modulus, order, _ = PROFILES[profile]
    field = BinaryField(degree, modulus, ledger)
    require(field.irreducible(), "profile polynomial is not irreducible")
    return BinaryCurve(field), order


def factor_base(curve, order, dimension):
    """F = {P != O : x(P) in span(1,z,...,z^(d-1)), [order]P = O}."""
    require(type(dimension) is int and 1 <= dimension <= min(curve.f.degree, 7),
            "subspace dimension must be between 1 and min(field degree, 7)")
    points = []
    for x in range(1 << dimension):
        curve.ledger.tick("factor_base_x_candidates")
        for point in curve.lift(x):
            require(curve.on_curve(point), "invalid lifted factor-base point")
            # Filter instead of clearing the cofactor: clearing changes x.
            curve.ledger.tick("subgroup_membership_checks")
            if curve.mul(point, order) is None:
                points.append(point)
    require(0 < len(points) <= MAX_BASE, "empty or oversized factor base")
    return tuple(sorted(points))


def point_sum(curve, base, indices):
    result = None
    for index in indices:
        result = curve.add(result, base[index])
    return result


def verify_witness(curve, base, query, witness, summands):
    if (not isinstance(witness, (tuple, list)) or len(witness) != summands
            or any(type(i) is not int or not 0 <= i < len(base) for i in witness)):
        return False
    return point_sum(curve, base, witness) == query


class PairTable:
    """Full (x,y) keys and all unordered pair witnesses, including repetitions."""

    def __init__(self, curve, base):
        self.curve, self.base = curve, base
        self.by_sum = defaultdict(list)
        self.pair_count = 0
        for first in range(len(base)):
            for second in range(first, len(base)):
                point = curve.add(base[first], base[second])
                self.by_sum[point].append((first, second))
                self.pair_count += 1
                curve.ledger.tick("pair_candidates")

    def decompose(self, query, summands, max_probes):
        require(summands in (2, 3, 4), "expected 2, 3, or 4 summands")
        require(type(max_probes) is int and max_probes >= 0, "invalid probe budget")
        require(self.curve.on_curve(query), "query is not on the curve")
        if summands == 2:
            choices = [(None, ())]
        elif summands == 3:
            choices = [(point, (i,)) for i, point in enumerate(self.base)]
        else:
            # Every sum key is searched; one left witness per sum is sufficient
            # for existence. The table retains all witnesses for relation rank.
            choices = [(point, witnesses[0]) for point, witnesses in self.by_sum.items()]
        probes = 0
        for left, indices in choices:
            if probes == max_probes:
                return {"status": "budget", "complete": False,
                        "probes": probes, "witness": None}
            residual = self.curve.add(query, self.curve.neg(left))
            probes += 1
            self.curve.ledger.tick("pair_lookup_probes")
            right = self.by_sum.get(residual)
            if right:
                witness = tuple(sorted(indices + right[0]))
                require(verify_witness(self.curve, self.base, query, witness, summands),
                        "decomposition failed exact group verification")
                return {"status": "found", "complete": True,
                        "probes": probes, "witness": list(witness)}
        return {"status": "no_decomposition", "complete": True,
                "probes": probes, "witness": None}


def relation_row(left, right=()):
    coefficients = Counter(left)
    coefficients.subtract(right)
    row = tuple((i, c) for i, c in sorted(coefficients.items()) if c)
    if row and row[0][1] < 0:
        row = tuple((i, -c) for i, c in row)
    return row


def verify_row(curve, base, row):
    result = None
    for index, coefficient in row:
        if type(index) is not int or not 0 <= index < len(base) or type(coefficient) is not int:
            return False
        point = base[index] if coefficient >= 0 else curve.neg(base[index])
        result = curve.add(result, curve.mul(point, abs(coefficient)))
    return result is None


def rank_mod(rows, columns, prime):
    """Rank only; no nullspace extraction, target coefficients, or log solving."""
    pivots = {}
    for row in rows:
        vector = [0] * columns
        for index, coefficient in row:
            vector[index] = (vector[index] + coefficient) % prime
        for column in range(columns):
            if not vector[column]:
                continue
            if column in pivots:
                factor = vector[column]
                vector = [(a - factor * b) % prime for a, b in zip(vector, pivots[column])]
            else:
                inverse = pow(vector[column], -1, prime)
                pivots[column] = [(x * inverse) % prime for x in vector]
                break
    return len(pivots)


def relation_audit(table, order):
    rows, seen, omitted = [], set(), 0
    for point, witnesses in table.by_sum.items():
        anchor = witnesses[0]
        for witness in witnesses if point is None else witnesses[1:]:
            row = relation_row(witness, () if point is None else anchor)
            if not row or row in seen:
                continue
            seen.add(row)
            if len(rows) == MAX_ROWS:
                omitted += 1
                continue
            require(verify_row(table.curve, table.base, row), "invalid homogeneous relation")
            table.curve.ledger.tick("verified_matrix_rows")
            rows.append(row)
    identities = [relation_row(pair) for pair in table.by_sum.get(None, [])]
    baseline_rank = rank_mod(identities, len(table.base), order)
    rank = rank_mod(rows, len(table.base), order)
    combined_rank = rank_mod(identities + rows, len(table.base), order)
    return {"columns": len(table.base), "column_encoding": "one_actual_point_per_column",
            "rows": rows, "verified_rows": len(rows), "omitted_rows": omitted,
            "complete_equal_pair_span": omitted == 0, "rank_mod_subgroup_order": rank,
            "negation_identity_rank": baseline_rank,
            "rank_added_beyond_negation_identities": combined_rank - baseline_rank,
            "maximum_homogeneous_rank": len(table.base) - 1}


def encode_point(point):
    return None if point is None else [hex(point[0]), hex(point[1])]


def exhaustive_control(curve, order, table):
    """Tiny fields only. Exhaustive tuples independently check lookup support."""
    require(curve.f.degree <= 9, "exhaustive controls are restricted to toy profiles")
    subgroup = [None]
    for x in range(curve.f.limit):
        for point in curve.lift(x):
            if curve.mul(point, order) is None:
                subgroup.append(point)
    require(len(subgroup) == order, "toy subgroup enumeration disagrees with profile")
    controls = []
    for summands in (2, 3, 4):
        tuple_count = math.comb(len(table.base) + summands - 1, summands)
        require(tuple_count <= MAX_ORACLE_TUPLES, "exhaustive tuple control exceeds fixed cap")
        support = set()
        for indices in combinations_with_replacement(range(len(table.base)), summands):
            support.add(point_sum(curve, table.base, indices))
        require(support <= set(subgroup), "tuple sum outside enumerated subgroup")
        found = 0
        for query in subgroup:
            result = table.decompose(query, summands, table.pair_count + len(table.base) + 1)
            expected = query in support
            require(result["complete"] and (result["status"] == "found") == expected,
                    "lookup support differs from exhaustive tuple oracle")
            found += expected
        controls.append({"summands": summands, "tuples_enumerated": tuple_count,
                         "subgroup_points_checked": len(subgroup), "supported_points": found,
                         "supported_nonidentity_points": len(support - {None}),
                         "identity_supported": None in support, "support_matches": True})
    return controls


def support_bound(base_size, order, summands):
    tuples = math.comb(base_size + summands - 1, summands)
    numerator = min(order - 1, tuples)
    return {"summands": summands, "unordered_tuples_with_repetition": str(tuples),
            "nonidentity_support_upper_bound": str(numerator),
            "nonidentity_subgroup_size": str(order - 1),
            "uniform_nonidentity_query_success_upper_bound": numerator / (order - 1),
            "status": "counting_bound_not_measured_yield"}


def run(profile, dimension=None, trials=8, seed=1, max_probes=10000):
    require(profile in PROFILES, "unknown fixed profile")
    require(type(trials) is int and 1 <= trials <= 64, "trials must be between 1 and 64")
    require(type(max_probes) is int and 0 <= max_probes <= 10000,
            "probe budget must be between 0 and 10000")
    degree, modulus, order, default_dimension = PROFILES[profile]
    dimension = default_dimension if dimension is None else dimension
    require(type(dimension) is int and 1 <= dimension <= min(degree, 7),
            "subspace dimension must be between 1 and min(field degree, 7)")
    ledger, started = Ledger(), time.perf_counter()
    with ledger.phase("parameter_validation"):
        curve, order = setup(profile, ledger)
    with ledger.phase("factor_base_construction_and_validation"):
        base = factor_base(curve, order, dimension)
    with ledger.phase("pair_table_construction"):
        table = PairTable(curve, base)
    queries = []
    rng = random.Random(seed)
    for summands in (2, 3, 4):
        for number in range(trials):
            with ledger.phase("planted_query_construction"):
                planted = [rng.randrange(len(base)) for _ in range(summands)]
                query = point_sum(curve, base, planted)
            with ledger.phase("planted_query_lookup_and_verification"):
                result = table.decompose(query, summands, max_probes)
            require(result["status"] != "no_decomposition", "planted witness was missed")
            queries.append({"summands": summands, "number": number,
                            "query": encode_point(query), "query_is_identity": query is None,
                            "planted_indices": planted, **result})
    with ledger.phase("homogeneous_relation_verification_and_rank"):
        matrix = relation_audit(table, order)
    controls = None
    if degree <= 9:
        with ledger.phase("exhaustive_natural_support_control"):
            controls = exhaustive_control(curve, order, table)
    with ledger.phase("counting_bounds"):
        bounds = [support_bound(len(base), order, r) for r in (2, 3, 4)]
    source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(Path(__file__).parent.glob("*.py"))}
    return {
        "format": FORMAT, "profile": profile,
        "curve": {"equation": "y^2 + x*y = x^3 + 1", "degree": degree,
                  "basis": "polynomial", "modulus": hex(modulus),
                  "subgroup_order": str(order), "cofactor": 4},
        "constraints": {"frobenius_endomorphism": False, "orbit_compression": False,
                        "negation_column_folding": False, "imported_targets": False,
                        "discrete_log_extraction": False},
        "factor_base": {"dimension": dimension, "recipe": "x_in_low_degree_subspace_and_nP_is_identity",
                        "x_candidates": 1 << dimension, "size": len(base),
                        "points": [encode_point(point) for point in base]},
        "pair_table": {"pairs": table.pair_count, "distinct_sums": len(table.by_sum),
                       "equal_sum_extra_witnesses": table.pair_count - len(table.by_sum),
                       "identity_witnesses": len(table.by_sum.get(None, [])),
                       "retains_all_witnesses": True},
        "planted_queries": queries,
        "planted_summary": dict(Counter(item["status"] for item in queries)),
        "homogeneous_matrix_audit": matrix,
        "natural_support": {"status": "exhaustive_toy_control" if controls else "not_measured",
                            "controls": controls},
        "support_bounds": bounds, "phases": ledger.report(),
        "research_run_seconds_before_serialization": time.perf_counter() - started,
        "complete_index_calculus_cost": None, "matched_rho_cost": None,
        "speedup_over_rho": None, "peak_memory_bytes": None,
        "claim": "bounded_relation_and_rank_controls_only",
        "provenance": {"utc": datetime.now(timezone.utc).isoformat(),
                       "python": platform.python_version(), "platform": platform.platform(),
                       "seed": seed, "trials_per_arity": trials, "max_probes": max_probes,
                       "source_sha256": source_hashes},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="toy7")
    parser.add_argument("--dimension", type=int)
    parser.add_argument("--trials", type=int, default=8, help="planted queries per arity (1..64)")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-probes", type=int, default=10000)
    parser.add_argument("--out", type=Path, help="new JSON receipt; existing files are refused")
    args = parser.parse_args()
    if args.out and args.out.exists():
        parser.error("output already exists; use a new receipt path")
    try:
        result = run(args.profile, args.dimension, args.trials, args.seed, args.max_probes)
    except ValueError as error:
        parser.error(str(error))
    result["provenance"]["argv"] = sys.argv
    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.out:
        with args.out.open("x") as stream:
            stream.write(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
