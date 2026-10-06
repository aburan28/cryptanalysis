#!/usr/bin/env python3
"""One-target N9 IC using FC-Hamming in every S3 PDP query.

The query routine receives a public point, never its fixture scalar.  The
factor-log phase and reusable SAT formula are complete before its online clock.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
from functools import reduce
from operator import xor
from pathlib import Path
import platform
import random
import resource
import sys
import time

import pycryptosat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments/shifted-base-geometry"))
import audit  # noqa: E402
from circuit import Circuit, s3  # noqa: E402
from fc_hamming import require_exact_weight as require_fc_weight  # noqa: E402
from unary_hamming import require_exact_weight as require_unary_weight  # noqa: E402

E = audit.engine
N, MODULUS, R, COFACTOR, M, WEIGHT = 9, 0x211, 127, 4, 5, 2
PDP_SECONDS, PDP_CONFLICTS = 3.0, 100_000
PRECOMPUTE_QUERY_CAP, ONLINE_QUERY_CAP = 100, 100
PHASES = ("target_query", "target_pdp", "target_relation_check",
          "target_descent", "target_recovery_check")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point_list(point):
    return None if point is None else list(point)


def normal_basis(field):
    for alpha in range(2, field.limit):
        conjugates = [alpha]
        for _ in range(1, N):
            conjugates.append(field.square(conjugates[-1]))
        if field.square(conjugates[-1]) != alpha:
            continue
        pivots = {}
        for value in conjugates:
            while value:
                bit = value.bit_length() - 1
                if bit not in pivots:
                    pivots[bit] = value
                    break
                value ^= pivots[bit]
        if len(pivots) == N:
            return alpha, conjugates
    raise AssertionError("normal basis not found")


def frobenius(field, point):
    return field.square(point[0]), field.square(point[1])


def orbit_encoding(curve, points, eigen):
    """Return signed Frobenius representatives and exact coefficients."""
    field = curve.f
    orbits = {}
    for point in points:
        orbit = []
        current = point
        for _ in range(N):
            orbit.extend((current, curve.neg(current)))
            current = frobenius(field, current)
        assert current == point
        orbits[point] = min(orbit)
    reps = tuple(sorted(set(orbits.values())))
    encoded = {}
    for point in points:
        rep = orbits[point]
        column = reps.index(rep)
        current = rep
        for exponent in range(N):
            if point == current:
                coefficient = pow(eigen, exponent, R)
                break
            if point == curve.neg(current):
                coefficient = -pow(eigen, exponent, R) % R
                break
            current = frobenius(field, current)
        else:
            raise AssertionError("unencoded base point")
        assert curve.mul(reps[column], coefficient) == point
        encoded[point] = (column, coefficient)
    return reps, encoded


def build_factor_base(curve, conjugates, eigen):
    raw = {}
    inadmissible = []
    for i, j in itertools.combinations(range(N), 2):
        x = conjugates[i] ^ conjugates[j]
        lifted = curve.lift(x)
        if not lifted:
            inadmissible.append((i, j))
        for point in lifted:
            projected = curve.mul(point, COFACTOR)
            if projected is None:
                continue
            assert curve.mul(projected, R) is None
            raw[point] = projected
    projected = tuple(sorted(set(raw.values())))
    reps, encoding = orbit_encoding(curve, projected, eigen)
    assert len(raw) == len(projected) == 36 and len(reps) == 2
    return {"raw_to_projected": raw, "points": projected,
            "representatives": reps, "encoding": encoding,
            "inadmissible_pairs": inadmissible}


def build_sat(conjugates, base, encoding):
    circuit = Circuit(N, [0, 4])
    x_rows = [[circuit.variable() for _ in range(N)] for _ in range(M)]
    middle_rows = [[circuit.variable() for _ in range(N)] for _ in range(M - 2)]
    target_bits = [circuit.variable() for _ in range(N)]
    hamming = []
    for row in x_rows:
        if encoding == "fc":
            hamming.append(require_fc_weight(circuit, row, WEIGHT))
        else:
            hamming.append(require_unary_weight(circuit, row, WEIGHT))
        for i, j in base["inadmissible_pairs"]:
            circuit.clauses.append(f"-{row[i]} -{row[j]} 0")
    for row in middle_rows:
        circuit.clauses.append(" ".join(map(str, row)) + " 0")
    xs = [circuit.linear_element(row, conjugates) for row in x_rows]
    middle = [circuit.linear_element(row, [1 << j for j in range(N)])
              for row in middle_rows]
    for a, b, c in ((xs[0], xs[1], middle[0]),
                    (middle[0], xs[2], middle[1]),
                    (middle[1], xs[3], middle[2]),
                    (middle[2], xs[4], target_bits)):
        s3(circuit, a, b, c)
    solver = pycryptosat.Solver(threads=1, time_limit=PDP_SECONDS,
                               confl_limit=PDP_CONFLICTS)
    for clause in circuit.clauses:
        terms = [int(v) for v in clause.split()[:-1]]
        solver.add_clause(terms)
    for row in circuit.xors:
        terms = [int(v) for v in row.split()[1:-1]]
        parity = 1 ^ (sum(v < 0 for v in terms) & 1)
        solver.add_xor_clause([abs(v) for v in terms], bool(parity))
    meta = {"x_rows": x_rows, "target_bits": target_bits,
            "variables": circuit.next_var - 1,
            "cnf_clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
            "and_gates": circuit.and_count,
            "hamming_tree_nodes": sum(h.get("tree_internal_nodes", 0) for h in hamming),
            "weight_encoding": encoding}
    return solver, meta


def group_sum(curve, points):
    result = None
    for point in points:
        result = curve.add(result, point)
    return result


def lift(curve, base, conjugates, meta, assignment, target):
    xs = [reduce(xor, (conjugates[i] for i, var in enumerate(row)
                       if assignment[var]), 0)
          for row in meta["x_rows"]]
    options = [curve.lift(x) for x in xs]
    if any(len(row) != 2 for row in options):
        return None
    torsion = (0, 1)
    allowed = {}
    for sign, point in ((1, target), (-1, curve.neg(target))):
        allowed[point] = sign
        allowed[curve.add(point, torsion)] = sign
    for points in itertools.product(*options):
        total = group_sum(curve, points)
        if total not in allowed:
            continue
        sign = allowed[total]
        projected = [base["raw_to_projected"][point] for point in points]
        assert group_sum(curve, projected) == curve.mul(
            target if sign == 1 else curve.neg(target), COFACTOR)
        row = [0] * len(base["representatives"])
        for point in projected:
            column, coefficient = base["encoding"][point]
            row[column] = (row[column] + coefficient) % R
        assert group_sum(curve, (curve.mul(rep, coefficient)
                                 for rep, coefficient in
                                 zip(base["representatives"], row))) == group_sum(curve, projected)
        return {"x": xs, "raw_points": [point_list(p) for p in points],
                "projected_points": [point_list(p) for p in projected],
                "row": row, "target_sign": sign,
                "through_two_torsion": total != (target if sign == 1 else curve.neg(target))}
    return None


def pdp(context, target):
    solver, meta = context["solver"], context["sat_meta"]
    assumptions = [var if target[0] >> bit & 1 else -var
                   for bit, var in enumerate(meta["target_bits"])]
    start = time.perf_counter_ns()
    sat, assignment = solver.solve(assumptions=assumptions)
    solver_ns = time.perf_counter_ns() - start
    if sat is None or solver_ns > int(PDP_SECONDS * 1e9):
        return "timeout", None, solver_ns
    if not sat:
        return "proved_unsat", None, solver_ns
    witness = lift(context["curve"], context["base"], context["conjugates"],
                   meta, assignment, target)
    return ("verified", witness, solver_ns) if witness else ("lift_rejected", None, solver_ns)


def gaussian(rows, columns):
    pivots = {}
    for coefficients, rhs in rows:
        vector = [v % R for v in coefficients] + [rhs % R]
        for pivot in sorted(pivots):
            factor = vector[pivot]
            if factor:
                vector = [(a - factor * b) % R for a, b in zip(vector, pivots[pivot])]
        pivot = next((i for i in range(columns) if vector[i]), None)
        if pivot is None:
            assert vector[-1] == 0, "inconsistent verified relation"
            continue
        inverse = pow(vector[pivot], -1, R)
        pivots[pivot] = [v * inverse % R for v in vector]
    if len(pivots) != columns:
        return len(pivots), None
    solution = [0] * columns
    for pivot in sorted(pivots, reverse=True):
        vector = pivots[pivot]
        solution[pivot] = (vector[-1] - sum(vector[j] * solution[j]
                                           for j in range(pivot + 1, columns))) % R
    assert all(sum(a * b for a, b in zip(row, solution)) % R == rhs % R
               for row, rhs in rows)
    return columns, solution


def collect_logs(context):
    curve, generator = context["curve"], context["generator"]
    rng = random.Random(61009)
    rows, records = [], []
    rank, logs = 0, None
    phase = Counter()
    for _ in range(PRECOMPUTE_QUERY_CAP):
        if logs is not None:
            break
        tick = time.perf_counter_ns()
        scalar = rng.randrange(1, R)
        target = curve.mul(generator, scalar)
        phase["query_generation"] += time.perf_counter_ns() - tick
        tick = time.perf_counter_ns()
        status, witness, solver_ns = pdp(context, target)
        phase["pdp_and_lift"] += time.perf_counter_ns() - tick
        old_rank = rank
        if witness:
            rhs = witness["target_sign"] * COFACTOR * scalar % R
            rows.append((witness["row"], rhs))
            tick = time.perf_counter_ns()
            rank, logs = gaussian(rows, len(context["base"]["representatives"]))
            phase["relation_la"] += time.perf_counter_ns() - tick
        records.append({"query_scalar": scalar, "target": point_list(target),
                        "status": status, "solver_wall_ns": solver_ns,
                        "witness": witness, "rank_gain": rank - old_rank})
    if logs is None:
        return None, {"records": records, "phase_wall_ns": dict(phase),
                      "rank": rank, "status": "insufficient_relations"}
    tick = time.perf_counter_ns()
    for rep, value in zip(context["base"]["representatives"], logs):
        assert curve.mul(generator, value) == rep
        assert E.ref.scalar_mul(generator, value, N, MODULUS) == rep
    phase["factor_log_replay"] += time.perf_counter_ns() - tick
    return logs, {"records": records, "phase_wall_ns": dict(phase),
                  "rank": rank, "status": "complete",
                  "status_counts": dict(Counter(row["status"] for row in records)),
                  "verified_relations": len(rows), "novel_rows": rank,
                  "logs": logs, "matrix_rows": rows}


class OnlineClock:
    def __init__(self):
        self.start = self.last = time.perf_counter_ns()
        self.phase = "target_query"
        self.times = {name: 0 for name in PHASES}

    def switch(self, phase):
        now = time.perf_counter_ns()
        self.times[self.phase] += now - self.last
        self.phase, self.last = phase, now

    def finish(self):
        now = time.perf_counter_ns()
        self.times[self.phase] += now - self.last
        assert sum(self.times.values()) == now - self.start
        return now - self.start


def ic_online(context, logs, public_target):
    curve, generator = context["curve"], context["generator"]
    rng = random.Random(73009)
    clock = OnlineClock()
    outcomes = Counter()
    trace = []
    for _ in range(ONLINE_QUERY_CAP):
        shift = rng.randrange(R)
        translated = curve.add(public_target, curve.mul(generator, shift))
        if translated is None or translated[0] == 0:
            outcomes["degenerate_query"] += 1
            continue
        clock.switch("target_pdp")
        status, witness, solver_ns = pdp(context, translated)
        clock.switch("target_relation_check")
        outcomes[status] += 1
        trace.append({"shift": shift, "translated": point_list(translated),
                      "status": status, "solver_wall_ns": solver_ns,
                      "witness": witness})
        if witness is None:
            clock.switch("target_query")
            continue
        assert group_sum(curve, (tuple(p) for p in witness["projected_points"])) == curve.mul(
            translated if witness["target_sign"] == 1 else curve.neg(translated), COFACTOR)
        clock.switch("target_descent")
        dot = sum(a * b for a, b in zip(witness["row"], logs)) % R
        scalar = (witness["target_sign"] * pow(COFACTOR, -1, R) * dot - shift) % R
        clock.switch("target_recovery_check")
        assert curve.mul(generator, scalar) == public_target
        assert E.ref.scalar_mul(generator, scalar, N, MODULUS) == public_target
        online_ns = clock.finish()
        return {"status": "complete", "scalar": scalar, "online_wall_ns": online_ns,
                "online_phase_wall_ns": clock.times, "attempts": sum(outcomes.values()),
                "status_counts": dict(outcomes), "trace": trace}
    online_ns = clock.finish()
    return {"status": "query_cap", "scalar": None, "online_wall_ns": online_ns,
            "online_phase_wall_ns": clock.times, "attempts": sum(outcomes.values()),
            "status_counts": dict(outcomes), "trace": trace}


def rho_online(curve, generator, public_target):
    rng = random.Random(92009)
    start = time.perf_counter_ns()
    additions = doublings = restarts = 0

    def step(state):
        nonlocal additions, doublings
        point, a, b = state
        bucket = 0 if point is None else point[0] % 3
        if bucket == 0:
            additions += 1
            return curve.add(point, generator), (a + 1) % R, b
        if bucket == 1:
            doublings += 1
            return curve.add(point, point), (2 * a) % R, (2 * b) % R
        additions += 1
        return curve.add(point, public_target), a, (b + 1) % R

    for _ in range(100):
        a, b = rng.randrange(R), rng.randrange(R)
        initial = (curve.add(curve.mul(generator, a), curve.mul(public_target, b)), a, b)
        tortoise, hare = step(initial), step(step(initial))
        for _ in range(1000):
            if tortoise[0] == hare[0]:
                denominator = (hare[2] - tortoise[2]) % R
                if denominator:
                    scalar = (tortoise[1] - hare[1]) * pow(denominator, -1, R) % R
                    if (curve.mul(generator, scalar) == public_target
                            and E.ref.scalar_mul(generator, scalar, N, MODULUS) == public_target):
                        return {"status": "complete", "scalar": scalar,
                                "online_wall_ns": time.perf_counter_ns() - start,
                                "additions": additions, "doublings": doublings,
                                "restarts": restarts, "workers": 1,
                                "distinguished_point_memory_bytes": 0,
                                "walk_policy": "three_bucket_floyd"}
                break
            tortoise, hare = step(tortoise), step(step(hare))
        restarts += 1
    return {"status": "restart_cap", "scalar": None,
            "online_wall_ns": time.perf_counter_ns() - start,
            "additions": additions, "doublings": doublings, "restarts": restarts,
            "workers": 1, "distinguished_point_memory_bytes": 0,
            "walk_policy": "three_bucket_floyd"}


def candidate_manifest(context):
    field = {"p": 2, "n": N, "basis": "polynomial",
             "defining_polynomial_int": MODULUS,
             "element_encoding": "nonnegative polynomial coefficient bit mask"}
    curve = {"model": "y^2+x*y=x^3+1",
             "coefficients": {"a1": 1, "a2": 0, "a3": 0, "a4": 0, "a6": 1},
             "curve_order": COFACTOR * R, "trace": (1 << N) + 1 - COFACTOR * R,
             "r": R, "cofactor": COFACTOR, "G": point_list(context["generator"]),
             "target_group": "prime_order_r_subgroup"}
    curve["curve_id"] = "EC1N9Ckb1h" + digest({"field": field, "curve": curve})[:12]
    paths = [Path(__file__), HERE / "circuit.py", HERE / "fc_hamming.py",
             HERE / "unary_hamming.py",
             ROOT / "experiments/shifted-base-geometry/audit.py",
             ROOT / "experiments/factor-base-yield-v2/engine.py",
             E.V1 / "study.py", E.V1 / "toy_group.py", E.V1 / "verify.py",
             E.V1 / "reference_group.py"]
    sources = {str(p.relative_to(ROOT)): file_hash(p) for p in paths}
    base = context["base"]
    point_set = [point_list(p) for p in base["points"]]
    record = {
        "schema_version": 1, "field": field, "curve": curve,
        "isogeny": "none",
        "endomorphism": {"endomorphism_order_conductor": None,
                         "frobenius_order_conductor": None,
                         "volcano_levels": None, "status": "unproved_not_used"},
        "factor_base": {
            "recipe": "deterministic_first_normal_element_weight2_rational_lifts_cofactor4",
            "normal_element": context["normal_element"],
            "normal_conjugates": context["conjugates"],
            "nominal_weight": WEIGHT, "nominal_mask_count": 36,
            "geometric_point_count": len(base["raw_to_projected"]),
            "actual_usable_points": len(base["points"]),
            "encoded_points": point_set, "point_set_sha256": digest(point_set),
            "sign_frobenius_quotient": "canonical_lexicographic_signed_frobenius_orbit",
            "effective_columns": len(base["representatives"]),
            "representatives": [point_list(p) for p in base["representatives"]],
            "eigenvalue": context["eigen"]},
        "point_decomposition": {
            "m": M, "family": "sat", "variant": context["encoding"] + "_weight2_s3_chain",
            "equations": "four_S3_e2_squared_plus_e3_plus_1",
            "encoding": "polynomial_basis_x_rows_from_normal_conjugates_with_rationality_clauses",
            "equation_order": "left_associative_S3_chain",
            "monomial_order": "none", "internal_matrix_kernel": "none",
            "native_solver": "pycryptosat", "native_version": pycryptosat.__version__,
            "native_binary_sha256": file_hash(Path(pycryptosat.__file__)),
            "per_query_seconds": "3.0", "per_query_conflicts": PDP_CONFLICTS,
            "cache_policy": "reusable_formula_and_incremental_solver_with_target_x_assumptions"},
        "relation_collection": {
            "target_query_distribution": "uniform_nonzero_known_scalar_times_G",
            "query_seed": 61009, "witness_policy": "first_sat_model_then_independent_group_lift",
            "filtering": "verified_raw_sum_to_plus_or_minus_query_mod_two_torsion",
            "duplicate_policy": "retain_all_verified_rows",
            "stop": "rank_two_or_100_queries",
            "source_digest": sources[str(Path(__file__).relative_to(ROOT))]},
        "relation_linear_algebra": {
            "modulus": R, "columns": len(base["representatives"]),
            "row_rule": "cofactor_project_raw_points_then_signed_frobenius_fold",
            "rank_criterion": len(base["representatives"]), "solver": "gauss",
            "implementation": "run_e2e_n9.py:gaussian",
            "source_digest": sources[str(Path(__file__).relative_to(ROOT))]},
        "target_descent": {
            "policy": "uniform_known_scalar_translates_until_verified_S3_lift",
            "query_seed": 73009, "query_cap": ONLINE_QUERY_CAP,
            "recover": "sign*inverse4*row_dot_logs-shift mod r",
            "source_digest": sources[str(Path(__file__).relative_to(ROOT))]},
        "implementation": {"source_sha256": sources,
                           "algorithm_flags": {"sat_threads": 1,
                                               "weight_encoding": context["encoding"],
                                               "pdp_seconds": "3.0",
                                               "pdp_conflicts": PDP_CONFLICTS,
                                               "precompute_query_cap": PRECOMPUTE_QUERY_CAP,
                                               "online_query_cap": ONLINE_QUERY_CAP}}}
    candidate_id = (f"IC1N9Ckb1fb{len(base['points'])}PDP5satRCsample"
                    f"LAgaussTDdescentISO0h{digest(record)[:12]}")
    return candidate_id, record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--encoding", choices=("fc", "unary"), default="fc")
    parser.add_argument("--run-number", type=int, default=1)
    args = parser.parse_args()
    if args.run_number < 1:
        raise ValueError("run number must be positive")
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("run output is immutable")
    out.mkdir(parents=True)
    prep_phase = {}
    tick = time.perf_counter_ns()
    curve, order, generator, eigen = E.setup(N, E.Ledger())
    assert order == R and curve.f.modulus == MODULUS
    assert frobenius(curve.f, generator) == curve.mul(generator, eigen)
    normal_element, conjugates = normal_basis(curve.f)
    prep_phase["setup_and_normal_basis_ns"] = time.perf_counter_ns() - tick
    tick = time.perf_counter_ns()
    base = build_factor_base(curve, conjugates, eigen)
    prep_phase["factor_base_ns"] = time.perf_counter_ns() - tick
    tick = time.perf_counter_ns()
    solver, sat_meta = build_sat(conjugates, base, args.encoding)
    prep_phase["reusable_sat_build_ns"] = time.perf_counter_ns() - tick
    context = {"curve": curve, "generator": generator, "eigen": eigen,
               "normal_element": normal_element, "conjugates": conjugates,
               "base": base, "solver": solver, "sat_meta": sat_meta,
               "encoding": args.encoding}
    candidate_id, candidate = candidate_manifest(context)
    tick = time.perf_counter_ns()
    logs, precompute = collect_logs(context)
    prep_phase["relation_precompute_ns"] = time.perf_counter_ns() - tick
    if logs is None:
        report = {"status": "insufficient_relations", "candidate_id": candidate_id,
                  "curve_id": candidate["curve"]["curve_id"], "precompute": precompute,
                  "prep_phase_wall_ns": prep_phase, "sat_formula": sat_meta}
        (out / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        (out / "candidate.json").write_text(json.dumps({"candidate_id": candidate_id,
            "record": candidate}, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": report["status"], "rank": precompute["rank"]}))
        return
    # Fixture scalar is kept outside the online routines and their clocks.
    precomputed_points = {tuple(row["target"]) for row in precompute["records"]}
    fixture_scalar = 49
    target = curve.mul(generator, fixture_scalar)
    assert target not in precomputed_points, "frozen target entered precomputation"
    fixture = {"curve_id": candidate["curve"]["curve_id"],
               "generator": point_list(generator), "target": point_list(target),
               "target_generation_law": "uniform_nonzero_scalar_times_G",
               "target_fixture_seed": 20260929, "target_count": 1,
               "precomputation_state": "ready", "cold_or_warm": "warm_one_target"}
    workload_id = "W" + digest(fixture)[:12]
    ic = ic_online(context, logs, target)
    rho = rho_online(curve, generator, target)
    verified = ic["status"] == rho["status"] == "complete" and (
        ic["scalar"] == rho["scalar"] == fixture_scalar)
    run_id = f"{candidate_id}{workload_id}R{args.run_number}"
    report = {
        "schema_version": 1, "kind": "single_unseen_target_full_ic_vs_rho",
        "status": "complete" if verified else "error",
        "weight_encoding": args.encoding,
        "candidate_id": candidate_id, "curve_id": candidate["curve"]["curve_id"],
        "workload_id": workload_id, "run_id": run_id,
        "fixture": fixture, "audit_fixture_scalar": fixture_scalar,
        "preparation": {"phase_wall_ns": prep_phase,
                        "factor_base_actual_points": len(base["points"]),
                        "factor_base_geometric_points": len(base["raw_to_projected"]),
                        "factor_base_effective_columns": len(base["representatives"]),
                        "factor_base_point_set_sha256": candidate["factor_base"]["point_set_sha256"],
                        "sat_formula": sat_meta, "factor_logs": precompute},
        "ic": ic, "rho": rho,
        "online_speedup": rho["online_wall_ns"] / ic["online_wall_ns"] if verified else None,
        "correctness": {"ic_scalar_replayed": ic["status"] == "complete",
                        "rho_scalar_replayed": rho["status"] == "complete",
                        "both_equal_fixture_scalar": verified},
        "host": {"platform": platform.platform(), "machine": platform.machine(),
                 "python": platform.python_version(),
                 "pycryptosat": pycryptosat.__version__, "workers": 1,
                 "same_resource_envelope": True},
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "unit": "wall_nanoseconds",
        "scope": "toy N9 result only; no ECC2K-130 performance inference"}
    phase_names = ("setup", "isogeny", "factor_base", "precompute", "queries",
                   "pdp", "relation_check", "matrix_build", "relation_la",
                   "target_descent", "recovery_check")
    online_statuses = ic["status_counts"]
    pdp_attempts = sum(online_statuses.get(name, 0) for name in
                       ("verified", "proved_unsat", "timeout", "lift_rejected"))
    row = {
        "schema_version": 2, "kind": "full_dlp", "status": report["status"],
        "candidate_id": candidate_id, "proposal_id": None,
        "workload_id": workload_id, "run_id": run_id,
        "pair_block_id": f"{workload_id}R{args.run_number}",
        "source_curve_ref": candidate["curve"]["curve_id"],
        "profile_id": "n9_weight2_m5", "isogeny_route_ref": "none",
        "subgroup_order": str(R), "target_count": 1,
        "target_point_sha256": digest(point_list(target)),
        "precomputation_ready": True, "rho_verified": rho["status"] == "complete",
        "verified_scalar": verified, "scalar_certificate_ref": "result.json#correctness",
        "provenance": {
            "workload_fixture_sha256": digest(fixture),
            "source_sha256": file_hash(Path(__file__)),
            "host_id": "sha256:" + hashlib.sha256(platform.node().encode()).hexdigest()[:12],
            "resource_envelope_id": "one_process_one_sat_thread_same_python_curve",
            "calibration_id": "paired_online_wall_ns_operations_unpriced"},
        "counts": {
            "ordinary_queries": pdp_attempts,
            "solved_queries": online_statuses.get("verified", 0),
            "verified_decompositions": online_statuses.get("verified", 0),
            "verified_relations": online_statuses.get("verified", 0),
            "novel_rows": 0,
            "effective_columns": len(base["representatives"]),
            "final_rank": precompute["rank"],
            "pdp_attempts": pdp_attempts,
            "pdp_verified": online_statuses.get("verified", 0),
            "pdp_proved_unsat": online_statuses.get("proved_unsat", 0),
            "pdp_timeout": online_statuses.get("timeout", 0),
            "pdp_budget": 0, "pdp_error": 0,
            "pdp_lift_rejected": online_statuses.get("lift_rejected", 0)},
        "phase_operations": {name: None for name in phase_names},
        "phase_wall_ns": {name: None for name in phase_names},
        "online_phase_wall_ns": ic["online_phase_wall_ns"],
        "online_wall_ns": ic["online_wall_ns"],
        "rho_online_wall_ns": rho["online_wall_ns"],
        "total_operations": None, "rho_operations": None,
        "peak_rss_bytes": report["peak_rss_bytes"],
        "wall_ns": ic["online_wall_ns"]}
    sys.path.insert(0, str(ROOT / "experiments/ic-candidate-catalog"))
    import analyze_v2  # noqa: E402
    analyze_v2.validate_run(row)
    (out / "candidate.json").write_text(json.dumps({"candidate_id": candidate_id,
        "record": candidate}, indent=2, sort_keys=True) + "\n")
    (out / "workload.json").write_text(json.dumps({"workload_id": workload_id,
        "record": fixture}, indent=2, sort_keys=True) + "\n")
    (out / "result.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (out / "run.jsonl").write_text(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "candidate_id": candidate_id,
                      "run_id": run_id, "precompute_queries": len(precompute["records"]),
                      "rank": precompute["rank"], "ic_online_ns": ic["online_wall_ns"],
                      "rho_online_ns": rho["online_wall_ns"],
                      "online_speedup": report["online_speedup"]}, indent=2))


if __name__ == "__main__":
    main()
