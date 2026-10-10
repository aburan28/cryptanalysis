#!/usr/bin/env python3
"""Bounded, subgroup-correct n83 four-summand chained-S3 SAT probe.

The public target is an ordinary target.  A separate planted target checks
the encoding, but is never used as a relation-yield observation.
"""

import hashlib
import json
import math
import platform
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))

import cnf
import curves
import decomp
import field
import indexcalc_e2e

PROPOSAL_ID = "Q1035"
WEIGHT = 4
POINTS = 4
MAX_SECONDS = 20
MAX_CONFLICTS = 100000
SOLVER = "cryptominisat5"
REFERENCE = HERE / "runs" / "n83_perf_prefix.json"
OUTPUT = HERE / "runs" / "n83_weight4_s3_stage.json"


def frozen(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def peak_rss():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if platform.system() == "Darwin" else rss * 1024


def point_digest(points):
    h = hashlib.sha256()
    for x, y in sorted(points):
        h.update(f"{x},{y}\n".encode())
    return h.hexdigest()


def solver_result(path, pvars, onb, curve, target, lookup):
    args = [SOLVER, "--threads=1", "--verb=1",
            f"--maxtime={MAX_SECONDS}", f"--maxconfl={MAX_CONFLICTS}",
            str(path)]
    started = time.perf_counter_ns()
    try:
        process = subprocess.run(args, text=True, capture_output=True,
                                 timeout=MAX_SECONDS + 10, check=False)
        outcome = process.stdout
        code = process.returncode
        if "s SATISFIABLE" in outcome:
            status = "sat"
        elif "s UNSATISFIABLE" in outcome:
            status = "unsat"
        else:
            status = "budget_or_unknown"
    except subprocess.TimeoutExpired as error:
        outcome = (error.stdout or b"").decode(errors="replace")
        code = None
        status = "external_timeout"
    elapsed = time.perf_counter_ns() - started
    row = {"status": status, "wall_ns": elapsed, "return_code": code,
           "stdout_sha256": hashlib.sha256(outcome.encode()).hexdigest(),
           "solver_output_tail": outcome.splitlines()[-25:],
           "solver_summary_lines": [line for line in outcome.splitlines()
                                    if line.startswith("s ") or
                                    "conflicts" in line.lower() or
                                    "total time (this thread)" in line.lower()][-20:],
           "threads": 1, "max_seconds": MAX_SECONDS,
           "max_conflicts": MAX_CONFLICTS,
           "verified_subgroup_relation": False}
    if status == "sat":
        assignment = {}
        for line in outcome.splitlines():
            if line.startswith("v "):
                for token in line[2:].split():
                    literal = int(token)
                    if literal:
                        assignment[abs(literal)] = literal > 0
        coords = []
        for vector in pvars:
            value = 0
            for i, literal in enumerate(vector):
                bit = assignment.get(abs(literal), False)
                if bit if literal > 0 else not bit:
                    value |= 1 << i
            coords.append(value)
        lifted = indexcalc_e2e.strictLift(onb, curve, coords, target, lookup)
        row["model_point_x_coordinates"] = coords
        row["verified_subgroup_relation"] = lifted is not None
        if lifted is not None:
            points, signs = lifted
            row["verified_points"] = [list(p) for p in points]
            row["signs"] = signs
    return row


def encode_and_solve(label, target, prog, roots, onb, curve, lookup, pinned=None):
    started = time.perf_counter_ns()
    formula = cnf.Cnf()
    encoded = decomp.encode(prog, roots, 83, POINTS, WEIGHT,
                            onb.toCoords(target[0]), formula,
                            returnInputs=pinned is not None)
    pvars, input_lits = encoded if pinned is not None else (encoded, None)
    for vector in pvars:
        formula.addClause(vector)  # x=0 is the 2-torsion point.
        formula.addXor(vector, False)  # Odd normal-x weight cannot be in the odd subgroup.
    if pinned is not None:
        for vector, point in zip(pvars, pinned):
            coordinate = onb.toCoords(point[0])
            for i, literal in enumerate(vector):
                formula.addClause([literal if coordinate >> i & 1 else -literal])
        intermediate = pinned[0]
        for j in range(POINTS - 2):
            intermediate = curve.add(intermediate, pinned[j + 1])
            assert intermediate is not None
            coordinate = onb.toCoords(intermediate[0])
            for i in range(83):
                literal = input_lits[(f"t{j}", i)]
                formula.addClause([literal if coordinate >> i & 1 else -literal])
    encode_ns = time.perf_counter_ns() - started
    stats = formula.stats()
    with tempfile.TemporaryDirectory(prefix="n83-w4-s3-") as directory:
        path = Path(directory) / "instance.cnf"
        started = time.perf_counter_ns()
        formula.writeDimacs(path)
        write_ns = time.perf_counter_ns() - started
        result = solver_result(path, pvars, onb, curve, target, lookup)
        result.update({"target": list(target), "encode_ns": encode_ns,
                       "input_pin_policy": "all four x coordinates and both chain intermediate x coordinates" if pinned is not None else "none",
                       "dimacs_write_ns": write_ns,
                       "dimacs_bytes": path.stat().st_size,
                       "dimacs_sha256": sha(path), "formula": stats})
    print(json.dumps({"instance": label, "status": result["status"],
                      "formula": stats, "encode_seconds": encode_ns / 1e9,
                      "solver_seconds": result["wall_ns"] / 1e9}), flush=True)
    return result


def run():
    reference = json.loads(REFERENCE.read_text())
    assert reference["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert reference["curve_identity_record"]["field"]["basis"] == "type_ii_optimal_normal"
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert reference["curve_identity_record"]["curve"]["cofactor"] == 4
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    eigen = curves.frobeniusEigenvalue(curve, generator, order)
    started = time.perf_counter_ns()
    reps, lookup = indexcalc_e2e.subgroupBase(onb, curve, order, eigen, WEIGHT)
    base_ns = time.perf_counter_ns() - started
    assert len(reps) == 5637 and len(lookup) == 935742
    base = {
        "construction": "nonzero ONB x of weight at most 4, rational lift, prime-subgroup test, signed-Frobenius closure",
        "enumerated_set_encoding": "sorted point (x,y) pairs as decimal x,y\\n lines",
        "nominal_normal_x_weight_bound": WEIGHT,
        "actual_usable_points_B_before_folding": len(lookup),
        "signed_frobenius_columns": len(reps),
        "enumerated_set_sha256": point_digest(lookup),
        "construction_ns": base_ns,
        "frobenius_eigenvalue_mod_r": str(eigen),
    }
    tuple_count = math.comb(len(lookup) + POINTS - 1, POINTS)
    base["uniform_query_hit_probability_upper"] = {
        "numerator": str(tuple_count), "denominator": str(order),
        "decimal": tuple_count / order,
        "assumptions": "uniform subgroup query; all unordered four-point multisets counted, including possible invalid cancellations",
        "expected_queries_per_verified_relation_lower": order / tuple_count,
        "expected_queries_for_at_least_columns_plus_target_hits_lower":
            (len(reps) + 1) * order / tuple_count,
    }
    print(json.dumps({"base_points": len(lookup), "columns": len(reps),
                      "base_seconds": base_ns / 1e9}), flush=True)
    chosen = [reps[i] for i in (0, 10, 100, 1000)]
    # decomp.encode orders low-index coordinate bits lexicographically.
    chosen.sort(key=lambda point: tuple(
        (onb.toCoords(point[0]) >> i) & 1 for i in range(83)))
    planted = None
    for point in chosen:
        planted = curve.add(planted, point)
    assert planted is not None and curve.mul(planted, order) is None
    assert planted != target
    started = time.perf_counter_ns()
    prog, roots = decomp.buildSystem(83, onb.n, POINTS, 12)
    circuit_ns = time.perf_counter_ns() - started
    gates = prog.bitOpCount(roots)
    print(json.dumps({"circuit_gates": gates,
                      "circuit_seconds": circuit_ns / 1e9}), flush=True)
    natural = encode_and_solve("ordinary_public_target", target,
                               prog, roots, onb, curve, lookup)
    planted_row = encode_and_solve("planted_control", planted,
                                   prog, roots, onb, curve, lookup)
    pinned_row = encode_and_solve("pinned_planted_encoding_control", planted,
                                  prog, roots, onb, curve, lookup, chosen)
    workload = {"curve_id": reference["curve_id"], "target": list(target),
                "target_count": 1,
                "input_law": "fixed public subgroup point from n83_perf_prefix.json",
                "ordinary_instances": 1,
                "solver_max_seconds": MAX_SECONDS,
                "solver_max_conflicts": MAX_CONFLICTS}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report = {
        "kind": "n83_subgroup_weight4_chained_s3_bounded_stage",
        "scope": "one ordinary public target and one separate planted correctness control; bounded SAT solver costs, no relation-yield estimate",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "workload_id": workload_id,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "factor_base": base,
        "point_decomposition": {"summands": POINTS,
                                "chain": "three S3 links with two intermediate x variables",
                                "solver": "CryptoMiniSat CLI with native XOR clauses",
                                "even_weight_filter": True,
                                "circuit_gates": gates,
                                "circuit_build_ns": circuit_ns},
        "ordinary_public_target": natural,
        "planted_correctness_control": planted_row,
        "pinned_planted_encoding_control": pinned_row,
        "planted_input_point_indices": [0, 10, 100, 1000],
        "planted_input_points_after_lex_order": [list(point) for point in chosen],
        "planted_target": list(planted),
        "verified_natural_relation": natural["verified_subgroup_relation"],
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "solver_version": subprocess.run([SOLVER, "--version"],
                                         capture_output=True, text=True).stdout.strip(),
        "runtime": {"python": sys.version, "platform": platform.platform(),
                    "machine": platform.machine()},
        "peak_parent_rss_bytes_excluding_solver_child": peak_rss(),
        "peak_solver_child_rss_bytes_across_instances": (
            resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            if platform.system() == "Darwin" else
            resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024),
        "source_sha256": sha(Path(__file__)),
        "reference_sha256": sha(REFERENCE),
        "dependency_sha256": {name: sha(CODEGEN / name) for name in
                              ("cnf.py", "curves.py", "decomp.py", "field.py",
                               "indexcalc.py", "indexcalc_e2e.py", "ir.py",
                               "build.py")},
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"receipt": str(OUTPUT),
                      "natural": natural["status"],
                      "planted": planted_row["status"],
                      "pinned": pinned_row["status"]}), flush=True)


if __name__ == "__main__":
    run()
