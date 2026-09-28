"""Fixed toy witness-fiber engine. No target import or logarithm extraction."""
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import importlib.util
from itertools import combinations_with_replacement
import json
from math import comb, isqrt
from pathlib import Path
import random
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parent
V1 = ROOT / "v1" if (ROOT / "v1").exists() else ROOT.parent / "factor-base-yield/run-002/sources"
sys.path.insert(0, str(V1))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, V1 / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("ordinary_v1_study", "study.py")
audit = load("ordinary_v1_audit", "verify.py")
ref = audit.ref
Ledger, Curve, Span = old.Ledger, old.BinaryCurve, old.Span
require = old.require
PROFILES = {
    9: (0x211, 127, 4), 13: (0x201b, 2003, 4),
    17: (0x20009, 239, 548), 19: (0x80027, 130873, 4),
    23: (0x800021, 2095853, 4),
}


class Field(old.BinaryField):
    def __init__(self, degree, ledger):
        require(degree in PROFILES, "only fixed toy fields through degree 23 are supported")
        self.degree, self.modulus, self.ledger = degree, PROFILES[degree][0], ledger
        self.limit = 1 << degree


def sqrt_mod(a, prime):
    """Tonelli-Shanks for the public Frobenius characteristic polynomial."""
    a %= prime
    require(pow(a, (prime - 1) // 2, prime) == 1, "nonsquare discriminant")
    if prime % 4 == 3:
        return pow(a, (prime + 1) // 4, prime)
    q, s = prime - 1, 0
    while q % 2 == 0:
        q //= 2
        s += 1
    z = 2
    while pow(z, (prime - 1) // 2, prime) != prime - 1:
        z += 1
    c, x, t, m = pow(z, q, prime), pow(a, (q + 1) // 2, prime), pow(a, q, prime), s
    while t != 1:
        i, power = 1, t * t % prime
        while power != 1:
            power = power * power % prime
            i += 1
        b = pow(c, 1 << (m - i - 1), prime)
        x, t, c, m = x * b % prime, t * b * b % prime, b * b % prime, i
    return x


def setup(degree, ledger):
    field = Field(degree, ledger)
    _, prime, cofactor = PROFILES[degree]
    require(all(prime % d for d in range(2, isqrt(prime) + 1)), "nonprime subgroup")
    require(field.irreducible(), "reducible fixed polynomial")
    curve = Curve(field)
    generator = None
    generator_seed = None
    generator_trace = []
    for x in range(field.limit):
        ledger.tick("generator_lift_candidates")
        points = curve.lift(x)
        if points:
            # Retain the actual cofactor-construction trace with integer
            # coefficients. Prime-subgroup points already produced here carry
            # known scalar RHS and cannot later be counted as new information.
            seed = points[0]
            generator, partial, doubled, coefficient = None, 0, seed, 1
            trace = [(seed, 1)]
            scalar = cofactor
            ledger.tick("scalar_multiplications")
            while scalar:
                if scalar & 1:
                    generator = curve.add(generator, doubled)
                    partial += coefficient
                    trace.append((generator, partial))
                scalar >>= 1
                if scalar:
                    doubled = curve.add(doubled, doubled)
                    coefficient *= 2
                    trace.append((doubled, coefficient))
            if generator is not None:
                generator_seed = points[0]
                generator_trace = trace
                break
    require(generator is not None and curve.mul(generator, prime) is None, "wrong generator order")
    root = sqrt_mod(-7, prime)
    eigenvalues = [(-1 + sign * root) * pow(2, -1, prime) % prime for sign in (1, -1)]
    lam = [v for v in eigenvalues if curve.mul(generator, v) == old.phi(curve, generator)]
    require(len(lam) == 1 and pow(lam[0], degree, prime) == 1, "invalid eigenvalue")
    curve.generator_seed = generator_seed
    curve.generator_seed_in_subgroup = curve.mul(generator_seed, prime) is None
    curve.known_public_points = [(generator, 1)]
    curve.generator_trace = generator_trace
    seen = {generator}
    for point, coefficient in generator_trace:
        if point is not None and point not in seen and curve.mul(point, prime) is None:
            point_scalar = coefficient * pow(cofactor, -1, prime) % prime
            require(curve.mul(generator, point_scalar) == point, "generator trace information mismatch")
            curve.known_public_points.append((point, point_scalar))
            seen.add(point)
    return curve, prime, generator, lam[0]


def public_orbits(curve, prime, lam):
    coefficients = {}
    for point, scalar in curve.known_public_points:
        for p, c in old.orbit(curve, point, prime, lam).items():
            value = c * scalar % prime
            require(p not in coefficients or coefficients[p] == value, "conflicting public orbit information")
            coefficients[p] = value
    return coefficients


def public_rows(curve, reps, prime, generator, lam):
    coefficients = public_orbits(curve, prime, lam)
    rows = []
    for i, p in enumerate(reps):
        if p in coefficients:
            row = [0] * len(reps)
            row[i] = 1
            require(curve.mul(generator, coefficients[p]) == p, "known public row failed group check")
            rows.append({"row": row, "scalar_rhs": coefficients[p]})
    return rows


def raw_base(curve, prime, dimension):
    require(1 <= dimension <= 8, "subspace dimension cap")
    base = []
    for x in range(1 << dimension):
        curve.ledger.tick("factor_base_x_candidates")
        for p in curve.lift(x):
            curve.ledger.tick("subgroup_checks")
            if p is not None and curve.mul(p, prime) is None:
                require(curve.on_curve(p), "invalid factor point")
                base.append(p)
    require(len(base) <= 128, "base point cap")
    return tuple(sorted(base))


def control(curve, base, prime, generator, lam, seed):
    reps, enc, _ = old.fold_base(curve, base, prime, lam)
    counts = Counter(col for col, _ in enc)
    known_reps = {min(old.orbit(curve, p, prime, lam)) for p, _ in curve.known_public_points}
    unknown_counts = sorted(counts[i] for i, p in enumerate(reps) if p not in known_reps)
    known_counts = sorted((p, counts[i]) for i, p in enumerate(reps) if p in known_reps)
    rng, selected, seen = random.Random(seed), [], set(known_reps)
    for _ in range(100000):
        if len(selected) == len(unknown_counts):
            break
        curve.ledger.tick("control_point_candidates")
        lifts = curve.lift(rng.randrange(curve.f.limit))
        if not lifts:
            continue
        p = lifts[rng.randrange(len(lifts))]
        if p is None or curve.mul(p, prime) is not None:
            continue
        representative = min(old.orbit(curve, p, prime, lam))
        if representative not in seen:
            seen.add(representative)
            selected.append(representative)
    require(len(selected) == len(unknown_counts), "control rejection cap reached")
    for rep, known_count in known_counts:
        selected.append(rep)
        unknown_counts.append(known_count)
    result = []
    for representative, count in zip(selected, unknown_counts):
        members = old.orbit(curve, representative, prime, lam)
        pairs = sorted({min(p, curve.neg(p)) for p in members})
        for p in rng.sample(pairs, count // 2):
            result.extend((p, curve.neg(p)))
    return tuple(sorted(result))


def fixture(spec, ledger):
    curve, prime, generator, lam = setup(spec["degree"], ledger)
    base = raw_base(curve, prime, spec["dimension"])
    if spec.get("parent_cell") is not None:
        if spec["control_seed"] is not None and base:
            base = old.matched_control(curve, base, prime, generator, lam, spec["control_seed"])
    elif spec["control_seed"] is not None and base:
        base = control(curve, base, prime, generator, lam, spec["control_seed"])
    reps, enc, occupancy = old.fold_base(curve, base, prime, lam)
    known = public_rows(curve, reps, prime, generator, lam)
    data = {**spec, "prime": prime, "cofactor": PROFILES[spec["degree"]][2],
            "modulus": curve.f.modulus, "generator": list(generator), "eigenvalue": lam,
            "generator_seed": list(curve.generator_seed), "generator_seed_in_subgroup": curve.generator_seed_in_subgroup,
            "known_public_points": [{"point": list(p), "scalar_rhs": scalar} for p, scalar in curve.known_public_points],
            "generator_trace": [{"point": list(p) if p is not None else None, "coefficient": coefficient} for p, coefficient in curve.generator_trace],
            "base": list(map(list, base)), "representatives": list(map(list, reps)),
            "encoding": list(map(list, enc)), "occupancy": occupancy, "known_rows": known,
            "M": len(base), "columns": len(reps), "K": len(reps) - len(known),
            "multiset_count": comb(len(base) + spec["arity"] - 1, spec["arity"]) if base else 0,
            "comparable_order": spec["degree"] != 17}
    return curve, data


def pkey(p):
    return "identity" if p is None else f"{p[0]}:{p[1]}"


def unkey(s):
    return None if s == "identity" else tuple(map(int, s.split(":")))


def hash_fibers(fibers):
    return hashlib.sha256(json.dumps({pkey(p): w for p, w in sorted(fibers.items(), key=lambda v:pkey(v[0]))}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ConstructionCap(Exception):
    pass


def fibers(curve, data, limits):
    require(3 <= data["arity"] <= 6, "arity must be 3 through 6")
    if data["multiset_count"] > limits["maximum_multisets"]:
        raise ConstructionCap("multiset_count_cap")
    table = defaultdict(list)
    base = tuple(map(tuple, data["base"]))
    begin = time.perf_counter()
    leaves = 0
    def visit(prefix, total, first):
        nonlocal leaves
        if len(prefix) == data["arity"]:
            table[total].append(prefix)
            leaves += 1
            curve.ledger.tick("witnesses_materialized")
            if leaves % 1024 == 0:
                if time.perf_counter() - begin > limits["maximum_construction_seconds"]:
                    raise ConstructionCap("construction_time_cap")
                if tracemalloc.is_tracing() and tracemalloc.get_traced_memory()[1] > limits["maximum_python_peak_bytes"]:
                    raise ConstructionCap("python_memory_cap")
            return
        for i in range(first, len(base)):
            curve.ledger.tick("fiber_prefix_additions")
            visit(prefix + (i,), curve.add(total, base[i]), i)
    visit((), None, 0)
    require(leaves == data["multiset_count"], "incomplete witness enumeration")
    return dict(table)


def row_for(witness, data):
    return old.folded_row(witness, data["encoding"], data["columns"], data["prime"])


def span_for(data, ledger=None):
    span = Span(data["columns"], data["prime"], ledger)
    for entry in data["known_rows"]:
        span.add(entry["row"])
    return span


def audit_state(data, table, basis, original_selected=None, scan_cap=64):
    span = Span(data["columns"], data["prime"])
    for row in basis:
        span.add(row)
    selected, available, rank_scan, uniform = 0, 0, 0, Fraction()
    witness_novel, total_witnesses = 0, 0
    for p, witnesses in table.items():
        if p is None:
            continue
        flags = [bool(any(span.reduce(row_for(w, data)))) for w in witnesses]
        count = sum(flags)
        witness_novel += count
        total_witnesses += len(flags)
        available += bool(count)
        uniform += Fraction(count, len(flags))
        if original_selected is not None:
            old_row = original_selected[p]
            selected += bool(any(span.reduce(old_row)))
        else:
            selected += flags[0]
        rank_scan += any(flags[:scan_cap])
    denominator = data["prime"] - 1
    uniform /= denominator
    return {"matrix_rank": span.rank, "useful_rank": span.rank - len(data["known_rows"]),
            "available_inputs": available, "first_inputs": selected, "rank_scan_inputs": rank_scan,
            "p_available": old.ratio(available, denominator), "p_first": old.ratio(selected, denominator),
            "p_rank_scan": old.ratio(rank_scan, denominator),
            "p_uniform_fiber": old.ratio(uniform.numerator, uniform.denominator),
            "first_efficiency": old.ratio(selected, available),
            "rank_scan_efficiency": old.ratio(rank_scan, available),
            "novel_witnesses": witness_novel, "all_nonzero_witnesses": total_witnesses}


def scan_pair_witnesses(curve, base, pairs, target, span, data, cap):
    seen, first, inspected = set(), None, 0
    for i, point in enumerate(base):
        residual = curve.add(target, curve.neg(point))
        curve.ledger.tick("pair_lookup_probes")
        for pair in pairs.get(residual, []):
            curve.ledger.tick("pair_witness_candidates")
            witness = tuple(sorted((i, *pair)))
            if witness in seen:
                curve.ledger.tick("duplicate_witnesses_skipped")
                continue
            seen.add(witness)
            if first is None:
                first = witness
            inspected += 1
            if any(span.reduce(row_for(witness, data))):
                return witness, inspected
            if inspected == cap:
                return first, inspected
    return first, inspected


def collect(spec, policy, seed, limits):
    require(policy in ("pair_first", "pair_rank_scan", "first", "uniform_fiber", "rank_scan"), "unsupported policy")
    pair_policy = policy in ("pair_first", "pair_rank_scan")
    require(not pair_policy or spec["arity"] == 3, "pair comparators are m=3 only")
    ledger = Ledger()
    tracemalloc.start()
    start, cpu_start = time.perf_counter_ns(), time.process_time_ns()
    with ledger.phase("parameters_and_base"):
        curve, data = fixture(spec, ledger)
    table, pair_table = None, None
    try:
        if pair_policy:
            with ledger.phase("pair_table_construction"):
                base = tuple(map(tuple, data["base"]))
                if policy == "pair_first":
                    pair_table = old.make_pairs(curve, base)
                else:
                    pair_table = defaultdict(list)
                    for i, j in combinations_with_replacement(range(len(base)), 2):
                        pair_table[curve.add(base[i], base[j])].append((i, j))
                        ledger.tick("pair_candidates")
                table = {}
        else:
            with ledger.phase("full_fiber_construction"):
                table = fibers(curve, data, limits)
    except ConstructionCap as exc:
        status = str(exc)
    records, states = [], []
    if table is not None:
        with ledger.phase("initial_known_information"):
            span = span_for(data, ledger)
        initial = len(data["known_rows"])
        states.append({"after_queries": 0, "basis": list(span.pivots.values())})
        rng, witness_rng = random.Random(seed), random.Random(seed ^ 0x64F1B3)
        base, reps = tuple(map(tuple, data["base"])), tuple(map(tuple, data["representatives"]))
        for attempt in range(limits["maximum_queries"] if data["K"] else 0):
            with ledger.phase("ordinary_input_generation"):
                scalar = rng.randrange(1, data["prime"])
                target = curve.mul(tuple(data["generator"]), scalar)
            selected, inspected, row = None, 0, None
            with ledger.phase("witness_selection"):
                if policy == "pair_first":
                    found = old.query(curve, base, pair_table, target, len(base))
                    choices = [tuple(found["witness"])] if found["witness"] is not None else []
                elif policy == "pair_rank_scan":
                    selected, inspected = scan_pair_witnesses(curve, base, pair_table, target, span, data, limits["rank_scan_witness_budget"])
                    choices = []
                else:
                    ledger.tick("fiber_lookups")
                    choices = table.get(target, [])
                if choices:
                    if policy == "uniform_fiber":
                        selected, inspected = choices[witness_rng.randrange(len(choices))], 1
                    elif policy in ("first", "pair_first"):
                        selected, inspected = choices[0], 1
                    else:
                        for candidate in choices[:limits["rank_scan_witness_budget"]]:
                            inspected += 1
                            trial = row_for(candidate, data)
                            if any(span.reduce(trial)):
                                selected = candidate
                                break
                        if selected is None:
                            selected = choices[0]
                if selected is not None:
                    ledger.tick("witnesses_inspected", inspected)
                    row = row_for(selected, data)
            independent = False
            if selected is not None:
                with ledger.phase("exact_witness_and_row_verification"):
                    total = None
                    for i in selected:
                        total = curve.add(total, base[i])
                    require(total == target, "witness mismatch")
                    total = None
                    for p, coefficient in zip(reps, row):
                        if coefficient:
                            total = curve.add(total, curve.mul(p, coefficient))
                    require(total == target, "folded known RHS mismatch")
                    ledger.tick("verified_rows")
                with ledger.phase("incremental_rank"):
                    independent = span.add(row)
            records.append({"scalar_rhs": scalar, "target": list(target), "witness": selected,
                            "row": row, "witnesses_inspected": inspected, "independent": independent,
                            "useful_rank": span.rank - initial})
            if independent and span.rank - initial in {data["K"] // 2, data["K"] - 1, data["K"]}:
                states.append({"after_queries": attempt + 1, "basis": list(span.pivots.values())})
            if span.rank == data["columns"]:
                break
        if not states or states[-1]["after_queries"] != len(records):
            states.append({"after_queries": len(records), "basis": list(span.pivots.values())})
        status = "empty_base" if not data["M"] else "already_known" if not data["K"] else "full_rank" if span.rank == data["columns"] else "query_cap"
        gain = span.rank - initial
    else:
        gain = 0
    elapsed, cpu = time.perf_counter_ns() - start, time.process_time_ns() - cpu_start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    outcome = {"policy": policy, "seed": seed, "status": status, "rank_gain": gain,
               "cold_ns": elapsed, "cpu_ns": cpu, "cold_ns_per_rank": elapsed / gain if gain else None,
               "python_peak_bytes": peak, "python_retained_bytes_at_stop": current,
               "queries": records, "states": states, "phases": ledger.report()}
    return data, table if not pair_policy else None, outcome


def geometry(data, table):
    counts = [len(w) for p, w in table.items() if p is not None]
    support, W, E = len(counts), sum(counts), sum(c*c for c in counts)
    available_span, first_span = span_for(data), span_for(data)
    for p, witnesses in table.items():
        if p is None:
            continue
        first_span.add(row_for(witnesses[0], data))
        if available_span.rank < data["columns"]:
            for witness in witnesses:
                available_span.add(row_for(witness, data))
                if available_span.rank == data["columns"]:
                    break
    return {"support": support, "W": W, "E": E, "zero_multisets": len(table.get(None, [])),
            "coverage": old.ratio(support, data["prime"] - 1),
            "coverage_lower": old.ratio(W*W, (data["prime"] - 1)*E),
            "coverage_upper": old.ratio(min(data["prime"] - 1, data["multiset_count"]), data["prime"] - 1),
            "normalized_energy": old.ratio((data["prime"] - 1)*E, W*W),
            "maximum_fiber": max(counts, default=0), "fiber_sha256": hash_fibers(table),
            "all_witness_useful_span": available_span.rank - len(data["known_rows"]),
            "first_witness_useful_span": first_span.rank - len(data["known_rows"])}
