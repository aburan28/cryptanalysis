#!/usr/bin/env python3
"""Complete toy N13 IC run with an exact four-sum selector SAT index and paired rho.

The reusable SAT index explicitly lists every four-point multiset. It is a
different, fully specified SAT encoding from the earlier S3-chain stage probe.
The target routine accepts only a public point; fixture scalars are used after
both solvers finish for independent audit.
"""

from __future__ import annotations

from collections import Counter
import hashlib
from itertools import combinations_with_replacement
import json
from pathlib import Path
import platform
import random
import resource
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CATALOG = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments/shifted-base-geometry"))
sys.path.insert(0, str(CATALOG))
import audit  # noqa: E402

E = audit.engine
R = 2003
BUDGET_NS = 50_000_000
PHASES = ("target_query", "target_pdp", "target_relation_check",
          "target_descent", "target_recovery_check")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point_code(point: tuple[int, int] | None) -> int:
    return 0 if point is None else (1 << 26) | point[0] << 13 | point[1]


def point_list(point: tuple[int, int] | None) -> list[int] | None:
    return None if point is None else list(point)


def group_sum(curve, points):
    result = None
    for point in points:
        result = curve.add(result, point)
    return result


def prepare():
    import pycryptosat

    ledger = E.Ledger()
    times = {}
    tick = time.perf_counter_ns()
    curve, prime, generator, eigen = E.setup(13, ledger)
    assert prime == R and curve.f.modulus == 0x201b
    times["curve_setup"] = time.perf_counter_ns() - tick
    tick = time.perf_counter_ns()
    normal = audit.normal_basis(curve.f, 87006)
    xs = audit.subspace([normal[4 * j] for j in range(3)])
    base = tuple(sorted(point for x in xs for point in curve.lift(x)
                        if point is not None and curve.mul(point, prime) is None))
    reps, encoding, _ = E.old.fold_base(curve, base, prime, eigen)
    known = E.public_rows(curve, reps, prime, generator, eigen)
    assert len(base) == 6 and len(reps) == 2
    anchor = json.loads((CATALOG / "toy_base_anchors.json").read_text())["bases"][0]
    assert [list(point) for point in base] == anchor["union_points"]
    profile = json.loads((CATALOG / "profiles.json").read_text())["profiles"][0]
    assert digest([list(point) for point in base]) == profile["base_digest"]
    times["factor_base"] = time.perf_counter_ns() - tick

    tick = time.perf_counter_ns()
    tuples = list(combinations_with_replacement(range(len(base)), 4))
    sums = [group_sum(curve, (base[i] for i in indices)) for indices in tuples]
    support = {point for point in sums if point is not None}
    assert len(tuples) == 126 and len(support) == 84
    times["exact_four_sum_enumeration"] = time.perf_counter_ns() - tick
    tick = time.perf_counter_ns()
    # Each selector implies the 27-bit encoded sum. Assumed target bits force
    # every nonmatching selector false; one selector must be true.
    solver = pycryptosat.Solver(threads=1, time_limit=BUDGET_NS / 1e9)
    solver.add_clause(list(range(1, len(tuples) + 1)))
    target_vars = tuple(range(len(tuples) + 1, len(tuples) + 28))
    for selector, point in enumerate(sums, 1):
        code = point_code(point)
        for bit, variable in enumerate(target_vars):
            solver.add_clause([-selector, variable if code >> bit & 1 else -variable])
    times["sat_cnf_build"] = time.perf_counter_ns() - tick
    return {"curve": curve, "r": prime, "generator": generator, "eigen": eigen,
            "base": base, "reps": reps, "encoding": encoding, "known": known,
            "tuples": tuples, "sums": sums, "support": support,
            "solver": solver, "target_vars": target_vars, "prep_wall_ns": times,
            "ledger": ledger}


def pdp(context, target):
    assert target is not None and context["curve"].on_curve(target)
    code = point_code(target)
    assumptions = [variable if code >> bit & 1 else -variable
                   for bit, variable in enumerate(context["target_vars"])]
    start = time.perf_counter_ns()
    sat, assignment = context["solver"].solve(assumptions=assumptions)
    elapsed = time.perf_counter_ns() - start
    if sat is None or elapsed > BUDGET_NS:
        return "timeout", None, elapsed
    if not sat:
        return "proved_unsat_exact_index", None, elapsed
    selected = next((i for i in range(1, len(context["tuples"]) + 1)
                     if assignment[i]), None)
    assert selected is not None
    return "verified", context["tuples"][selected - 1], elapsed


def checked_row(context, target, indices):
    curve, base, reps = context["curve"], context["base"], context["reps"]
    assert group_sum(curve, (base[i] for i in indices)) == target
    row = [0] * len(reps)
    for index in indices:
        column, coefficient = context["encoding"][index]
        row[column] = (row[column] + coefficient) % R
    assert group_sum(curve, (curve.mul(rep, coefficient)
                             for rep, coefficient in zip(reps, row))) == target
    return row


def gaussian(rows, columns):
    pivots = {}
    for coefficients, rhs in rows:
        vector = [value % R for value in coefficients] + [rhs % R]
        for pivot in sorted(pivots):
            coefficient = vector[pivot]
            if coefficient:
                vector = [(x - coefficient * y) % R
                          for x, y in zip(vector, pivots[pivot])]
        pivot = next((i for i in range(columns) if vector[i]), None)
        if pivot is None:
            assert vector[-1] == 0, "inconsistent factor-log relation"
            continue
        inverse = pow(vector[pivot], -1, R)
        pivots[pivot] = [value * inverse % R for value in vector]
    if len(pivots) < columns:
        return len(pivots), None
    solution = [0] * columns
    for pivot in sorted(pivots, reverse=True):
        row = pivots[pivot]
        solution[pivot] = (row[-1] - sum(row[j] * solution[j]
                                         for j in range(pivot + 1, columns))) % R
    assert all(sum(c * solution[i] for i, c in enumerate(coefficients)) % R == rhs % R
               for coefficients, rhs in rows)
    return len(pivots), solution


def collect_factor_logs(context):
    curve, generator = context["curve"], context["generator"]
    rows = [(item["row"], item["scalar_rhs"]) for item in context["known"]]
    rank, logs = gaussian(rows, len(context["reps"]))
    rng = random.Random(61013)
    records = []
    phase_ns = Counter()
    for _ in range(10000):
        if logs is not None:
            break
        start = time.perf_counter_ns()
        scalar = rng.randrange(1, R)
        target = curve.mul(generator, scalar)
        phase_ns["query_generation"] += time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        status, witness, native_solver_ns = pdp(context, target)
        full_pdp_ns = time.perf_counter_ns() - start
        phase_ns["pdp"] += full_pdp_ns
        old_rank = rank
        row = None
        if witness is not None:
            start = time.perf_counter_ns()
            row = checked_row(context, target, witness)
            phase_ns["relation_check"] += time.perf_counter_ns() - start
            start = time.perf_counter_ns()
            rows.append((row, scalar))
            rank, logs = gaussian(rows, len(context["reps"]))
            phase_ns["relation_la"] += time.perf_counter_ns() - start
        records.append({"target": point_list(target), "known_query_scalar": scalar,
                        "status": status, "witness": witness, "row": row,
                        "rank_gain": rank - old_rank, "pdp_wall_ns": full_pdp_ns,
                        "native_solver_wall_ns": native_solver_ns})
    assert logs is not None, "factor-log precomputation failed within query cap"
    start = time.perf_counter_ns()
    for representative, log in zip(context["reps"], logs):
        assert curve.mul(generator, log) == representative
        assert E.ref.scalar_mul(generator, log, 13, curve.f.modulus) == representative
    phase_ns["factor_log_certificates"] = time.perf_counter_ns() - start
    for record in records:
        assert (record["status"] == "verified") == (tuple(record["target"]) in context["support"])
    return logs, {"records": records, "known_rows": context["known"],
                  "rank": rank, "logs": logs, "phase_wall_ns": dict(phase_ns),
                  "status_counts": dict(Counter(item["status"] for item in records)),
                  "novel_rows": sum(item["rank_gain"] for item in records)}


class OnlineClock:
    def __init__(self):
        self.times = {phase: 0 for phase in PHASES}
        self.start = self.last = time.perf_counter_ns()
        self.phase = "target_query"

    def switch(self, phase):
        now = time.perf_counter_ns()
        self.times[self.phase] += now - self.last
        self.phase, self.last = phase, now

    def finish(self):
        now = time.perf_counter_ns()
        self.times[self.phase] += now - self.last
        assert sum(self.times.values()) == now - self.start
        return now - self.start


def ic_online(context, logs, public_target, seed):
    """Only the public point enters this target-dependent routine."""
    curve, generator = context["curve"], context["generator"]
    rng = random.Random(seed)
    clock = OnlineClock()
    cpu_start = time.process_time_ns()
    outcomes = Counter()
    attempts = 0
    trace = []
    while attempts < 10000:
        shift = rng.randrange(0, R)
        translated = curve.add(public_target, curve.mul(generator, shift))
        attempts += 1
        if translated is None:
            outcomes["identity_translation"] += 1
            trace.append({"translated": None, "status": "identity_translation", "pdp_wall_ns": 0})
            continue
        clock.switch("target_pdp")
        status, witness, solve_ns = pdp(context, translated)
        outcomes[status] += 1
        trace.append({"translated": point_list(translated), "status": status,
                      "pdp_wall_ns": solve_ns})
        clock.switch("target_relation_check")
        if witness is None:
            clock.switch("target_query")
            continue
        row = checked_row(context, translated, witness)
        clock.switch("target_descent")
        recovered = (sum(c * log for c, log in zip(row, logs)) - shift) % R
        clock.switch("target_recovery_check")
        replay = curve.mul(generator, recovered)
        independent_replay = E.ref.scalar_mul(generator, recovered, 13, curve.f.modulus)
        assert replay == independent_replay == public_target
        elapsed = clock.finish()
        cpu_ns = time.process_time_ns() - cpu_start
        return {"scalar": recovered, "wall_ns": elapsed,
                "cpu_ns": cpu_ns,
                "online_phase_wall_ns": clock.times, "attempts": attempts,
                "outcomes": dict(outcomes), "last_witness": witness,
                "last_row": row, "last_shift": shift, "last_pdp_wall_ns": solve_ns,
                "trace": trace}
    raise RuntimeError("target descent query cap reached")


def rho_online(curve, generator, public_target, seed):
    """Floyd Pollard rho on the same public subgroup point, with replay charged."""
    rng = random.Random(seed)
    start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()
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
        for _ in range(20000):
            if tortoise[0] == hare[0]:
                denominator = (hare[2] - tortoise[2]) % R
                if denominator:
                    scalar = (tortoise[1] - hare[1]) * pow(denominator, -1, R) % R
                    if (curve.mul(generator, scalar) == public_target
                            and E.ref.scalar_mul(generator, scalar, 13, curve.f.modulus) == public_target):
                        elapsed = time.perf_counter_ns() - start
                        return {"scalar": scalar, "wall_ns": elapsed,
                                "cpu_ns": time.process_time_ns() - cpu_start,
                                "additions": additions, "doublings": doublings,
                                "restarts": restarts}
                break
            tortoise, hare = step(tortoise), step(step(hare))
        restarts += 1
    raise RuntimeError("rho restart cap reached")


def manifest(context):
    import pycryptosat

    curve = context["curve"]
    field = {"p": 2, "n": 13, "basis": "polynomial", "defining_polynomial_int": curve.f.modulus,
             "element_encoding": "nonnegative polynomial coefficient bit mask"}
    curve_record = {"model": "y^2+x*y=x^3+1", "coefficients": {"a1": 1, "a2": 0,
                    "a3": 0, "a4": 0, "a6": 1}, "curve_order": 4 * R,
                    "trace": (1 << 13) + 1 - 4 * R, "r": R, "cofactor": 4,
                    "G": list(context["generator"]), "target_group": "prime_order_r_subgroup"}
    curve_id = f"EC1N13Ckb1h{digest({'field': field, 'curve': curve_record})[:12]}"
    curve_record["curve_id"] = curve_id
    source_paths = [Path(__file__), ROOT / "experiments/shifted-base-geometry/audit.py",
                    ROOT / "experiments/factor-base-yield-v2/engine.py",
                    E.V1 / "study.py", E.V1 / "toy_group.py", E.V1 / "verify.py",
                    E.V1 / "reference_group.py"]
    sources = {str(path.relative_to(ROOT)): file_sha(path) for path in source_paths}
    native_binary_sha = file_sha(Path(pycryptosat.__file__))
    point_set = [list(point) for point in context["base"]]
    record = {
        "schema_version": 1, "proposal_lineage": "Q1", "field": field, "curve": curve_record,
        "isogeny": "none",
        "endomorphism": {"endomorphism_order_conductor": None,
                         "frobenius_order_conductor": None, "volcano_levels": None,
                         "status": "unproved_not_used"},
        "factor_base": {"recipe": "seed87006_normal_basis_stride4_subspace_d3",
                        "subspace_x_values": sorted(audit.subspace([audit.normal_basis(curve.f, 87006)[4*j]
                                                                            for j in range(3)])),
                        "encoded_points": point_set, "point_set_sha256": digest(point_set),
                        "nominal_dimension": 3, "actual_usable_points": 6,
                        "sign_frobenius_quotient": "fold_base", "effective_columns": 2,
                        "seed": 87006},
        "point_decomposition": {"m": 4, "family": "sat", "variant": "exact_sumset_selector_cnf",
                                "sumset_multisets": 126, "target_encoding_bits": 27,
                                "cnf_rule": "at_least_one_selector; each selector_implies_27_target_bits",
                                "monomial_order": "none", "internal_matrix_kernel": "none",
                                "native_solver": "pycryptosat", "native_version": pycryptosat.__version__,
                                "native_binary_sha256": native_binary_sha,
                                "per_query_budget_ns": BUDGET_NS, "cache_policy": "reusable_index_and_solver"},
        "relation_collection": {"query_distribution": "uniform_nonzero_known_scalar_times_G",
                                "witness_policy": "first_verified_sat_model",
                                "rank_stop": "two_independent_columns", "query_cap": 10000,
                                "precompute_seed_policy": "run_record", "source_digest": sources[str(Path(__file__).relative_to(ROOT))]},
        "relation_linear_algebra": {"modulus": R, "columns": 2,
                                    "row_rule": "signed_frobenius_folded_coefficients",
                                    "solver": "gauss", "rank_criterion": 2,
                                    "implementation": "complete_n13_sat.py:gaussian",
                                    "source_digest": sources[str(Path(__file__).relative_to(ROOT))]},
        "target_descent": {"policy": "uniform_known_scalar_translates_until_sat_witness",
                           "query_cap": 10000, "recover": "sum(row_i*log_i)-shift mod r",
                           "source_digest": sources[str(Path(__file__).relative_to(ROOT))]},
        "implementation": {"source_sha256": sources,
                           "algorithm_flags": {"sat_threads": 1, "target_bits": 27,
                                               "per_query_budget_ns": BUDGET_NS}}
    }
    candidate_id = "IC1N13Ckb1fb6PDP4satRCsampleLAgaussTDdescentISO0h" + digest(record)[:12]
    return candidate_id, record


def make_run(context, candidate_id, source_sha, prep, target, ic, rho, workload,
             run_number, fixture_index):
    phase_names = ("setup", "isogeny", "factor_base", "precompute", "queries", "pdp",
                   "relation_check", "matrix_build", "relation_la", "target_descent", "recovery_check")
    outcomes = ic["outcomes"]
    attempts = ic["attempts"] - outcomes.get("identity_translation", 0)
    verified = outcomes.get("verified", 0)
    return {"schema_version": 2, "kind": "full_dlp", "status": "complete",
            "proposal_id": None, "candidate_id": candidate_id,
            "run_id": f"{candidate_id}{workload['workload_id']}R{run_number}",
            "workload_id": workload["workload_id"], "pair_block_id": workload["workload_id"],
            "source_curve_ref": "shifted-base-geometry/toy13/seed87006",
            "profile_id": "n13_same_d3_m4", "isogeny_route_ref": "none", "subgroup_order": str(R),
            "provenance": {"workload_fixture_sha256": workload["fixture_sha256"],
                           "source_sha256": source_sha, "host_id": platform.node(),
                           "resource_envelope_id": "one_process_one_native_sat_thread_same_python_curve",
                           "calibration_id": "paired_wall_ns_operations_unpriced",
                           "relation_precompute_seed": 61013,
                           "target_descent_seed": 73000 + fixture_index,
                           "rho_walk_seed": 92000 + fixture_index},
            "counts": {"ordinary_queries": attempts, "solved_queries": verified,
                       "verified_decompositions": verified, "verified_relations": verified,
                       "novel_rows": 0, "effective_columns": 2, "final_rank": prep["rank"],
                       "pdp_attempts": attempts, "pdp_verified": verified,
                       "pdp_proved_unsat": outcomes.get("proved_unsat_exact_index", 0),
                       "pdp_timeout": outcomes.get("timeout", 0), "pdp_budget": 0,
                       "pdp_error": 0, "pdp_lift_rejected": 0},
            "phase_operations": {name: None for name in phase_names},
            "phase_wall_ns": {name: None for name in phase_names},
            "online_phase_wall_ns": ic["online_phase_wall_ns"],
            "online_wall_ns": ic["wall_ns"], "rho_online_wall_ns": rho["wall_ns"],
            "rho_verified": True, "target_count": 1, "target_point_sha256": digest(point_list(target)),
            "precomputation_ready": True, "total_operations": None, "rho_operations": None,
            "verified_scalar": True, "scalar_certificate_ref": "complete_n13_sat_receipt.json#targets",
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "wall_ns": ic["wall_ns"]}


def main():
    import analyze

    out = HERE / "complete_n13_sat_receipt.json"
    runs_out = HERE / "complete_n13_sat_runs.jsonl"
    manifest_out = HERE / "complete_n13_sat_candidate.json"
    if any(path.exists() for path in (out, runs_out, manifest_out)):
        raise SystemExit("outputs already exist")
    cold_start = time.perf_counter_ns()
    context = prepare()
    candidate_id, candidate = manifest(context)
    logs, prep = collect_factor_logs(context)
    assert prep["rank"] == 2
    cold_total_wall_ns = time.perf_counter_ns() - cold_start
    fixture_rng = random.Random(20260925)
    fixture_scalars = []
    precomputed_points = {tuple(item["target"]) for item in prep["records"]}
    while len(fixture_scalars) < 20:
        value = fixture_rng.randrange(1, R)
        point = context["curve"].mul(context["generator"], value)
        if value not in fixture_scalars and point not in precomputed_points:
            fixture_scalars.append(value)
    receipts, run_rows = [], []
    source_sha = file_sha(Path(__file__))
    for number, hidden_scalar in enumerate(fixture_scalars, 1):
        target = context["curve"].mul(context["generator"], hidden_scalar)
        assert target is not None and context["curve"].on_curve(target)
        fixture = {"curve_id": candidate["curve"]["curve_id"],
                   "generator": candidate["curve"]["G"], "target": point_list(target),
                   "target_fixture_seed": 20260925, "target_fixture_index": number,
                   "target_generation_law": "uniform_nonzero_scalar_times_G",
                   "target_count": 1, "precomputation_state": "ready"}
        workload = {"fixture_sha256": digest(fixture), "workload_id": "W" + digest(fixture)[:12]}
        ic = ic_online(context, logs, target, seed=73000 + number)
        rho = rho_online(context["curve"], context["generator"], target, seed=92000 + number)
        assert ic["scalar"] == rho["scalar"] == hidden_scalar
        for attempt in ic["trace"]:
            assert (attempt["status"] == "verified") == (
                tuple(attempt["translated"]) in context["support"]
                if attempt["translated"] is not None else False)
        run = make_run(context, candidate_id, source_sha, prep, target, ic, rho,
                       workload, 1, number)
        analyze.validate_run(run)
        run_rows.append(run)
        receipts.append({"fixture": fixture, "workload": workload,
                         "audit_fixture_scalar": hidden_scalar, "ic": ic, "rho": rho,
                         "target_descent_seed": 73000 + number,
                         "rho_walk_seed": 92000 + number,
                         "online_speedup": rho["wall_ns"] / ic["wall_ns"],
                         "run_id": run["run_id"]})
    report = {"kind": "complete_single_target_ic_vs_rho_toy_n13",
              "scope": "twenty independent one-target public-synthetic toy DLP workloads; first is primary",
              "candidate_id": candidate_id, "curve_id": candidate["curve"]["curve_id"],
              "profile_id": "n13_same_d3_m4", "proposal_lineage": "Q1",
              "method_distinction": "exact_sumset_selector_cnf; earlier chained_S3_SAT_stage_receipts_do_not_apply",
              "cold_preparation": {"setup_wall_ns": context["prep_wall_ns"],
                                   "cold_total_wall_ns": cold_total_wall_ns,
                                   "relation_query_seed": 61013,
                                   "factor_log_collection": prep,
                                   "sumset_support_nonidentity": len(context["support"]),
                                   "sumset_tuple_count": len(context["tuples"])},
              "targets": receipts, "environment": {"platform": platform.platform(),
                         "python": platform.python_version(),
                         "pycryptosat": __import__("pycryptosat").__version__},
              "source_sha256": source_sha, "candidate_manifest_sha256": digest(candidate)}
    manifest_out.write_text(json.dumps({"candidate_id": candidate_id, "record": candidate}, indent=2, sort_keys=True) + "\n")
    runs_out.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in run_rows))
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"candidate_id": candidate_id,
                      "factor_log_queries": len(prep["records"]),
                      "targets": [{"ic_online_ns": item["ic"]["wall_ns"],
                                   "rho_online_ns": item["rho"]["wall_ns"],
                                   "speedup": item["online_speedup"],
                                   "target_queries": item["ic"]["attempts"]}
                                  for item in receipts]}, indent=2))


if __name__ == "__main__":
    main()
