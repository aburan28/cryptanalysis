#!/usr/bin/env python3
"""Complete n=23 IC control for a two-color, four-summand pair claw.

The point-to-pair walk is memory-bounded by distinguished endpoints. A merge
between opposite colors gives an ordinary four-point relation. This small
instance validates relation collection, orbit-folded logs, and one target;
it does not project a measured n=83 cost or claim a speedup over rho.
"""

import hashlib
import json
import math
import platform
import random
import resource
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))

import curves
import field
import indexcalc

N = 23
WEIGHT = 2
COFACTOR = 4
DISTINGUISHED_BITS = 4
MAX_TRAIL = 512
MAX_WALK_EVALS = 100000
MAX_SETUP_QUERIES = 100
SETUP_ALPHA_SEED = 23092026
TARGET_SCALAR_FIXTURE = 987654
TARGET_WALK_SEED = 999999
GENERATOR_SEED = 23
POINT_HASH_BYTES = 48  # Encodes symmetric ONB elements through n=131.
PROPOSAL_ID = "Q1036"


class CountingCurve(curves.Curve):
    """Logical API calls; nested categories must not be added together."""

    def __init__(self, onb):
        self.calls = Counter()
        super().__init__(onb)

    def add(self, p, q):
        self.calls["add"] += 1
        return super().add(p, q)

    def dbl(self, p):
        self.calls["dbl"] += 1
        return super().dbl(p)

    def neg(self, p):
        self.calls["neg"] += 1
        return super().neg(p)

    def frob(self, p, j=1):
        self.calls["frob"] += 1
        return super().frob(p, j)

    def mul(self, p, k):
        self.calls["mul"] += 1
        return super().mul(p, k)

    def pointFromX(self, x):
        self.calls["pointFromX"] += 1
        return super().pointFromX(x)


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def point_digest(points):
    digest = hashlib.sha256()
    for x, y in sorted(points):
        digest.update(f"{x},{y}\n".encode())
    return digest.hexdigest()


def build_base(curve, onb, order):
    """All rational normal-x supports of size 1 or 2, projected by [4]."""
    points = set()
    rational_x = 0
    for support in indexcalc.combinationsUpTo(N, WEIGHT):
        if not support:
            continue
        coordinate = sum(1 << bit for bit in support)
        point = curve.pointFromX(onb.fromCoords(coordinate))
        if point is None:
            continue
        rational_x += 1
        projected = curve.mul(point, COFACTOR)
        if projected is None:
            continue
        assert curve.mul(projected, order) is None
        points.add(projected)
        points.add(curve.neg(projected))
    return sorted(points), rational_x


def orbit_labels(curve, generator, order, points):
    eigen = curves.frobeniusEigenvalue(curve, generator, order)
    assert curve.mul(generator, eigen) == curve.frob(generator)
    labels = {}
    representatives = []
    for point in points:
        if point in labels:
            continue
        column = len(representatives)
        representatives.append(point)
        value, coefficient = point, 1
        for _ in range(N):
            for signed, coeff in ((value, coefficient),
                                  (curve.neg(value), -coefficient % order)):
                existing = labels.get(signed)
                if existing is not None:
                    assert existing == (column, coeff)
                labels[signed] = (column, coeff)
            value = curve.frob(value)
            coefficient = coefficient * eigen % order
    assert len(labels) == len(points)
    return representatives, labels, eigen


def digest_state(point):
    if point is None:
        encoded = b"identity"
    else:
        encoded = (point[0].to_bytes(POINT_HASH_BYTES, "little") +
                   point[1].to_bytes(POINT_HASH_BYTES, "little"))
    return hashlib.blake2s(encoded, digest_size=16).digest()


def step(curve, base, target, state):
    digest = digest_state(state)
    color = digest[0] & 1
    left = int.from_bytes(digest[1:5], "little") % len(base)
    right = int.from_bytes(digest[5:9], "little") % len(base)
    pair = curve.add(base[left], base[right])
    output = pair if color == 0 else curve.add(target, curve.neg(pair))
    return output, (color, left, right)


def distinguished(point):
    return int.from_bytes(digest_state(point)[12:16], "little") & (
        (1 << DISTINGUISHED_BITS) - 1) == 0


def proper(curve, points):
    return all(points[i] != curve.neg(points[j])
               for i in range(len(points)) for j in range(i))


def replay_endpoint(curve, base, target, first, second):
    """Recover the two predecessors of the first trail merge."""
    first_seed, first_length = first
    second_seed, second_length = second
    first_states = []
    state = first_seed
    for _ in range(first_length + 1):
        first_states.append(state)
        state, _ = step(curve, base, target, state)
    first_position = {}
    for index, point in enumerate(first_states):
        first_position.setdefault(point, index)
    state, previous = second_seed, None
    for second_index in range(second_length + 1):
        first_index = first_position.get(state)
        if first_index is not None:
            if first_index == 0 or second_index == 0:
                return None
            first_predecessor = first_states[first_index - 1]
            second_predecessor = previous
            first_output, first_meta = step(curve, base, target,
                                            first_predecessor)
            second_output, second_meta = step(curve, base, target,
                                              second_predecessor)
            assert first_output == second_output == state
            if first_meta[0] == second_meta[0]:
                return None
            first_pair = [base[first_meta[1]], base[first_meta[2]]]
            second_pair = [base[second_meta[1]], base[second_meta[2]]]
            witness = first_pair + second_pair
            if not proper(curve, witness):
                return None
            total = None
            for point in witness:
                total = curve.add(total, point)
            assert total == target
            return {"points": [list(point) for point in witness],
                    "first_meta": list(first_meta),
                    "second_meta": list(second_meta),
                    "merge_depths": [first_index, second_index]}
        previous = state
        state, _ = step(curve, base, target, state)
    return None


def walk(curve, base, generator, order, target, seed):
    rng = random.Random(seed)
    endpoints = {}
    evaluations = 0
    trails = 0
    endpoint_replays = 0
    discarded = 0
    while evaluations < MAX_WALK_EVALS:
        start = curve.mul(generator, rng.randrange(1, order))
        state, length = start, 0
        while length < MAX_TRAIL and evaluations < MAX_WALK_EVALS:
            state, _ = step(curve, base, target, state)
            length += 1
            evaluations += 1
            if distinguished(state):
                break
        if not distinguished(state):
            discarded += 1
            continue
        trails += 1
        previous = endpoints.get(state)
        if previous is not None:
            endpoint_replays += 1
            witness = replay_endpoint(curve, base, target,
                                      previous, (start, length))
            if witness is not None:
                return {"status": "verified_four_point_relation",
                        "step_evaluations_excluding_replay": evaluations,
                        "trails": trails, "endpoint_rows": len(endpoints),
                        "endpoint_replays": endpoint_replays,
                        "discarded_no_endpoint": discarded,
                        "relation": witness}
        else:
            endpoints[state] = (start, length)
    return {"status": "budget", "step_evaluations_excluding_replay": evaluations,
            "trails": trails, "endpoint_rows": len(endpoints),
            "endpoint_replays": endpoint_replays,
            "discarded_no_endpoint": discarded, "relation": None}


def relation_row(labels, points, columns, order):
    row = [0] * columns
    for encoded in points:
        column, coefficient = labels[tuple(encoded)]
        row[column] = (row[column] + coefficient) % order
    return row


def rank(rows, columns, order):
    matrix = [row[:] for row in rows]
    pivot_row = 0
    for column in range(columns):
        pivot = next((i for i in range(pivot_row, len(matrix))
                      if matrix[i][column]), None)
        if pivot is None:
            continue
        matrix[pivot_row], matrix[pivot] = matrix[pivot], matrix[pivot_row]
        inverse = pow(matrix[pivot_row][column], -1, order)
        matrix[pivot_row] = [value * inverse % order
                             for value in matrix[pivot_row]]
        for i in range(pivot_row + 1, len(matrix)):
            coefficient = matrix[i][column]
            matrix[i] = [(left - coefficient * right) % order
                         for left, right in zip(matrix[i], matrix[pivot_row])]
        pivot_row += 1
        if pivot_row == len(matrix):
            break
    return pivot_row


def solve_rows(rows, rhs, order):
    columns = len(rows[0])
    assert len(rows) == len(rhs) == columns
    matrix = [row[:] + [value] for row, value in zip(rows, rhs)]
    for column in range(columns):
        pivot = next(i for i in range(column, columns)
                     if matrix[i][column])
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        inverse = pow(matrix[column][column], -1, order)
        matrix[column] = [value * inverse % order for value in matrix[column]]
        for i in range(columns):
            if i == column:
                continue
            coefficient = matrix[i][column]
            matrix[i] = [(left - coefficient * right) % order
                         for left, right in zip(matrix[i], matrix[column])]
    return [row[-1] for row in matrix]


def main():
    started = time.perf_counter_ns()
    onb = field.Onb(N)
    curve = CountingCurve(onb)
    order = curves.curveOrder(N) // COFACTOR
    assert curves.curveOrder(N) == COFACTOR * order
    assert curves.isPrimeBig(order)
    generator = curve.randomPointOfOrder(order, COFACTOR,
                                         random.Random(GENERATOR_SEED))
    assert curve.mul(generator, order) is None
    base, rational_x = build_base(curve, onb, order)
    representatives, labels, eigen = orbit_labels(curve, generator,
                                                   order, base)
    assert len(base) == 322 and len(representatives) == 7
    base_ready = time.perf_counter_ns()
    base_calls = curve.calls.copy()

    field_record = {
        "p": 2, "n": N, "basis": "type_ii_optimal_normal",
        "defining_modulus": "symmetric subalgebra of F2[z]/(z^47-1), modulo sum(z^i, i=0..46)",
        "basis_coordinates": "bit i-1 is coefficient of gamma_i=zeta^i+zeta^-i, i=1..n",
        "element_encoding": "nonnegative integer native ONB symmetric bit vector, normalized bit zero"}
    curve_record = {
        "model": "y^2 + x*y = x^3 + 1", "a1": 1, "a2": 0,
        "a3": 0, "a4": 0, "a6": 1,
        "order": curves.curveOrder(N), "subgroup_order": order,
        "cofactor": COFACTOR, "generator": list(generator),
        "target_group": "subgroup generated by generator"}
    identity = {"field": field_record, "curve": curve_record}
    curve_id = "EC1N23Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    source_hash = sha(Path(__file__))
    dependencies = {name: sha(CODEGEN / name)
                    for name in ("curves.py", "field.py", "indexcalc.py")}
    factor_base = {
        "construction": "all nonzero type-II ONB x supports of Hamming weight at most two; rational lift; [4] projection; both signs; full Frobenius closure",
        "nominal_normal_x_weight_bound": WEIGHT,
        "nominal_nonzero_x_coordinates": math.comb(N, 1) + math.comb(N, 2),
        "rational_x_coordinates": rational_x,
        "actual_usable_points_B_before_folding": len(base),
        "signed_frobenius_columns": len(representatives),
        "enumerated_set_encoding": "sorted point (x,y) pairs as decimal x,y\\n lines",
        "enumerated_set_sha256": point_digest(base),
        "frobenius_eigenvalue_mod_r": eigen,
    }
    candidate_record = {
        "schema_version": 1, "field": field_record,
        "curve": dict(curve_record, curve_id=curve_id),
        "isogeny": "none",
        "endomorphism": {"endomorphism_order_conductor": None,
                          "frobenius_order_conductor": None,
                          "volcano_levels": "not_applicable_for_degree_two_in_characteristic_two"},
        "factor_base": factor_base,
        "point_decomposition": {
            "m": 4, "summation_chain": "group-law pair sums; two-color claw",
            "solver_family": "distinguished_point_pair_claw",
            "stage_code": "PDP4claw", "hash": "BLAKE2s-128",
            "point_encoding_bytes_per_coordinate": POINT_HASH_BYTES,
            "hash_fields": "color=digest[0]&1; pair indices=LE32 digest[1:5],digest[5:9] mod B; distinguished=low four bits of LE32 digest[12:16]",
            "distinguished_bits": DISTINGUISHED_BITS,
            "max_trail_evaluations": MAX_TRAIL,
            "max_query_evaluations": MAX_WALK_EVALS,
            "same_color_collision_policy": "continue from a fresh deterministic seed",
            "proper_relation_policy": "reject any opposite-point cancellation",
            "implementation_sha256": source_hash},
        "relation_collection": {
            "query_law": "independent deterministic uniform nonzero alpha in Z_r; target alpha*G",
            "stage_code": "RCwalk", "rank_stop": len(representatives),
            "max_setup_queries": MAX_SETUP_QUERIES,
            "walk_seed_schedule": "100000 plus zero-based setup query index",
            "failed_query_policy": "retain and charge every budget miss",
            "duplicate_policy": "discard dependent rows",
            "implementation_sha256": source_hash},
        "relation_linear_algebra": {
            "modulus": order, "columns": len(representatives),
            "matrix_construction": "signed-Frobenius coefficient sum per verified relation",
            "rank_criterion": "full column rank",
            "solver": "modular_gauss", "stage_code": "LAgauss",
            "implementation_sha256": source_hash},
        "target_descent": {
            "policy": "direct four-point relation after reusable base logs are ready",
            "stage_code": "TDdirect", "implementation_sha256": source_hash},
        "implementation": {"source_sha256": source_hash,
                           "dependency_sha256": dependencies,
                           "python_implementation": platform.python_implementation()},
    }
    candidate_hash = hashlib.sha256(frozen(candidate_record)).hexdigest()
    candidate_id = (f"IC1N23Ckb1fb{len(base)}PDP4clawRCwalkLAgauss"
                    f"TDdirectISO0h{candidate_hash[:12]}")
    candidate = dict(candidate_record, candidate_id=candidate_id,
                     candidate_record_sha256=candidate_hash)

    setup_rng = random.Random(SETUP_ALPHA_SEED)
    rows, rhs, collection = [], [], []
    for query_number in range(1, MAX_SETUP_QUERIES + 1):
        alpha = setup_rng.randrange(1, order)
        query_target = curve.mul(generator, alpha)
        start = time.perf_counter_ns()
        outcome = walk(curve, base, generator, order, query_target,
                       100000 + query_number - 1)
        outcome["wall_ns"] = time.perf_counter_ns() - start
        outcome["query_number"] = query_number
        outcome["alpha"] = alpha
        outcome["target"] = list(query_target)
        if outcome["relation"] is not None:
            row = relation_row(labels, outcome["relation"]["points"],
                               len(representatives), order)
            outcome["relation_row"] = row
            novel = rank(rows + [row], len(representatives), order) > len(rows)
            outcome["novel_row"] = novel
            if novel:
                rows.append(row)
                rhs.append(alpha)
        else:
            outcome["novel_row"] = False
        collection.append(outcome)
        if len(rows) == len(representatives):
            break
    assert len(rows) == len(representatives), "rank gate not reached"
    logs = solve_rows(rows, rhs, order)
    assert all(curve.mul(generator, value) == point
               for point, value in zip(representatives, logs))
    precompute_ready = time.perf_counter_ns()
    precompute_calls = curve.calls.copy()

    # The scalar is a fixture only. The online method receives just target.
    target = curve.mul(generator, TARGET_SCALAR_FIXTURE)
    assert all(row["target"] != list(target) for row in collection)
    before_online_calls = curve.calls.copy()
    workload = {
        "curve_id": curve_id, "target": list(target),
        "target_count": 1, "input_law": "fixed public subgroup point from a seeded scalar fixture",
        "fixture_scalar_seed": TARGET_SCALAR_FIXTURE,
        "target_walk_seed": TARGET_WALK_SEED,
        "setup_alpha_seed": SETUP_ALPHA_SEED,
        "setup_query_cap": MAX_SETUP_QUERIES,
        "distinguished_bits": DISTINGUISHED_BITS,
        "max_trail_evaluations": MAX_TRAIL,
        "max_query_evaluations": MAX_WALK_EVALS,
    }
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    phase = {}
    start = time.perf_counter_ns()
    result = walk(curve, base, generator, order, target, TARGET_WALK_SEED)
    phase["target_pdp"] = time.perf_counter_ns() - start
    assert result["relation"] is not None
    start = time.perf_counter_ns()
    points = [tuple(point) for point in result["relation"]["points"]]
    assert proper(curve, points)
    assert all(point in labels for point in points)
    total = None
    for point in points:
        total = curve.add(total, point)
    assert total == target
    target_row = relation_row(labels, result["relation"]["points"],
                              len(representatives), order)
    phase["target_relation_check"] = time.perf_counter_ns() - start
    start = time.perf_counter_ns()
    recovered = sum(value * log for value, log in zip(target_row, logs)) % order
    assert curve.mul(generator, recovered) == target
    phase["target_recovery_check"] = time.perf_counter_ns() - start
    assert recovered == TARGET_SCALAR_FIXTURE  # independent fixture control
    after_online_calls = curve.calls.copy()
    phase["target_query"] = 0
    phase["target_descent"] = 0
    online_ns = sum(phase.values())

    report = {
        "kind": "n23_pair_claw_complete_one_target_ic_control",
        "scope": "complete toy pipeline and one previously unseen target; no n83 relation, DLP, or speedup claim",
        "proposal_id": PROPOSAL_ID,
        "candidate_id": candidate_id,
        "run_id": f"{candidate_id}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": curve_id, "curve_identity_record": identity,
        "isogeny": "none", "endomorphism_order_conductor": None,
        "factor_base": factor_base,
        "factor_base_ready_wall_ns": base_ready - started,
        "target_independent_precompute_wall_ns": precompute_ready - started,
        "factor_base_group_api_calls": dict(base_calls),
        "target_independent_group_api_calls": dict(precompute_calls),
        "relation_collection": collection,
        "verified_relation_count": sum(row["relation"] is not None for row in collection),
        "novel_rows": len(rows), "final_rank": rank(rows, len(representatives), order),
        "matrix_rows": rows, "matrix_rhs": rhs,
        "representatives": [list(point) for point in representatives],
        "representative_logs": logs,
        "target_result": result, "target_relation_row": target_row,
        "verified_single_target_dlp": True,
        "recovered_scalar": recovered,
        "fixture_scalar_validation_only": TARGET_SCALAR_FIXTURE,
        "online_phase_wall_ns": phase,
        "online_one_target_wall_ns": online_ns,
        "online_interval": "first target-dependent pair-claw walk through independent scalar replay; factor-base and base-log setup excluded",
        "rho_online_wall_ns": None, "online_speedup": None,
        "common_operation_total": None,
        "logical_walk_evaluations_online": result["step_evaluations_excluding_replay"],
        "logical_walk_evaluations_setup": sum(row[
            "step_evaluations_excluding_replay"] for row in collection),
        "online_group_api_calls_including_replay_and_scalar_check": dict(
            after_online_calls - before_online_calls),
        "operation_accounting": "group API categories are nested and must not be summed; step-evaluation counts exclude endpoint replay, while online group API calls include it and scalar verification",
        "peak_parent_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                  if platform.system() == "Darwin" else
                                  resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": source_hash, "dependency_sha256": dependencies,
        "candidate_record_sha256": candidate_hash,
    }
    candidate_path = HERE / "candidates" / f"{candidate_id}.json"
    receipt_path = HERE / "runs" / "n23_one_target.json"
    candidate_path.write_text(json.dumps(candidate, indent=2) + "\n")
    receipt_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": curve_id, "candidate_id": candidate_id,
                      "actual_B": len(base), "columns": len(representatives),
                      "rank": len(rows), "setup_queries": len(collection),
                      "online_steps": result["step_evaluations_excluding_replay"],
                      "online_wall_ns": online_ns, "recovered": recovered,
                      "receipt": str(receipt_path)}))


if __name__ == "__main__":
    main()
