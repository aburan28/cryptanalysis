#!/usr/bin/env python3
"""Bounded paired N53 ordinary-target PDP probe; no complete IC claim."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import platform
import resource
import subprocess
import time

import psutil

from circuit import Circuit, s3
from fc_hamming import require_exact_weight as require_fc_weight
from n53_group import (COFACTOR, GENERATOR, LOW_TERMS, MODULUS, N, R,
                       TARGET, Curve, Field, normal_basis)
from unary_hamming import require_exact_weight as require_unary_weight

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CMS = Path("/opt/homebrew/bin/cryptominisat5")
M, WEIGHT = 5, 2
DEFAULT_SECONDS, DEFAULT_CONFLICTS = 30, 200_000
MAX_RSS_BYTES = 2 * 1024**3


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def group_sum(curve, points):
    value = None
    for point in points:
        value = curve.add(value, point)
    return value


def signed_frobenius_key(field, curve, point):
    candidates = []
    current = point
    for _ in range(N):
        candidates.extend((current, curve.neg(current)))
        current = (field.square(current[0]), field.square(current[1]))
    assert current == point
    return min(candidates)


def geometry(field, curve, conjugates):
    """Enumerate the exact raw and subgroup-usable weight-two base."""
    raw = {}
    rejected = []
    columns = set()
    # Each unordered weight-two pair has one gap in 1..(N-1)/2 and one
    # Frobenius rotation. Project one point per orbit and rotate its image.
    for gap in range(1, (N + 1) // 2):
        x = conjugates[0] ^ conjugates[gap]
        points = curve.lift(x)
        if not points:
            rejected.extend(tuple(sorted((shift, (shift + gap) % N)))
                            for shift in range(N))
        for point in points:
            projected = curve.mul(point, COFACTOR)
            if projected is None:
                continue
            assert curve.mul(projected, R) is None
            columns.add(signed_frobenius_key(field, curve, projected))
            current_raw, current_projected = point, projected
            for shift in range(N):
                assert current_raw[0] == (conjugates[shift] ^ conjugates[(shift + gap) % N])
                raw[current_raw] = current_projected
                current_raw = (field.square(current_raw[0]), field.square(current_raw[1]))
                current_projected = (field.square(current_projected[0]),
                                     field.square(current_projected[1]))
            assert current_raw == point and current_projected == projected
    base = set(raw.values())
    assert len(rejected) == 530
    assert len(raw) == len(base) == 1696 and len(columns) == 16
    return {"raw_to_projected": raw, "rejected_pairs": rejected,
            "raw_points": len(raw), "usable_projected_points": len(base),
            "signed_frobenius_columns": len(columns),
            "projected_set_sha256": digest([list(p) for p in sorted(base)]),
            "column_set_sha256": digest([list(p) for p in sorted(columns)])}


def build(circuit, conjugates, rejected_pairs, encoding):
    x_rows = [[circuit.variable() for _ in range(N)] for _ in range(M)]
    middle_rows = [[circuit.variable() for _ in range(N)] for _ in range(M - 2)]
    for row in x_rows:
        if encoding == "fc":
            require_fc_weight(circuit, row, WEIGHT)
        else:
            require_unary_weight(circuit, row, WEIGHT)
        for i, j in rejected_pairs:
            circuit.clauses.append(f"-{row[i]} -{row[j]} 0")
    for row in middle_rows:
        circuit.clauses.append(" ".join(map(str, row)) + " 0")
    xs = [circuit.linear_element(row, conjugates) for row in x_rows]
    middle = [circuit.linear_element(row, [1 << j for j in range(N)])
              for row in middle_rows]
    for a, b, c in ((xs[0], xs[1], middle[0]),
                    (middle[0], xs[2], middle[1]),
                    (middle[1], xs[3], middle[2]),
                    (middle[2], xs[4], circuit.constant(TARGET[0]))):
        s3(circuit, a, b, c)
    return {"x_rows": x_rows, "middle_rows": middle_rows,
            "variables": circuit.next_var - 1, "and_gates": circuit.and_count,
            "cnf_clauses": len(circuit.clauses), "xor_rows": len(circuit.xors)}


def parse_model(stdout):
    if "s SATISFIABLE" not in stdout:
        return None
    assignments = {}
    for line in stdout.splitlines():
        if line.startswith("v "):
            for word in line[2:].split():
                literal = int(word)
                if literal:
                    assignments[abs(literal)] = literal > 0
    return assignments


def verify_model(circuit, assignments):
    def lit(value):
        bit = assignments.get(abs(value))
        if bit is None:
            return None
        return bit if value > 0 else not bit

    for clause in circuit.clauses:
        values = [lit(int(word)) for word in clause.split()[:-1]]
        if not any(value is True for value in values):
            return False
    for row in circuit.xors:
        values = [lit(int(word)) for word in row.split()[1:-1]]
        if None in values or sum(values) % 2 != 1:
            return False
    return True


def lift_model(curve, raw_to_projected, conjugates, meta, assignment):
    xs = []
    for row in meta["x_rows"]:
        x = 0
        for i, var in enumerate(row):
            if assignment.get(var):
                x ^= conjugates[i]
        xs.append(x)
    choices = [curve.lift(x) for x in xs]
    if any(len(item) != 2 for item in choices):
        return {"verified": False, "reason": "nonrational_x", "x": xs}
    allowed = {}
    torsion = (0, 1)
    for sign, point in ((1, TARGET), (-1, curve.neg(TARGET))):
        allowed[point] = sign
        allowed[curve.add(point, torsion)] = sign
    for points in itertools.product(*choices):
        total = group_sum(curve, points)
        if total in allowed:
            projected = [raw_to_projected[point] for point in points]
            sign = allowed[total]
            expected = curve.mul(TARGET if sign == 1 else curve.neg(TARGET), COFACTOR)
            assert group_sum(curve, projected) == expected
            return {"verified": True, "x": xs,
                    "raw_points": [list(p) for p in points],
                    "projected_points": [list(p) for p in projected],
                    "target_sign": sign,
                    "through_two_torsion": total != (TARGET if sign == 1 else curve.neg(TARGET))}
    return {"verified": False, "reason": "no_group_lift", "x": xs}


def solve(path, output, seconds, conflicts):
    stdout_path = output / "solver.stdout.txt"
    stderr_path = output / "solver.stderr.txt"
    command = [str(CMS), "--verb=0", "--threads=1",
               f"--maxtime={seconds}", f"--maxconfl={conflicts}", str(path)]
    start = time.perf_counter_ns()
    peak = 0
    guard = None
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        proc = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        launch_end = time.perf_counter_ns()
        child = psutil.Process(proc.pid)
        deadline = time.monotonic() + seconds + 20
        while proc.poll() is None:
            try:
                peak = max(peak, child.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak >= MAX_RSS_BYTES:
                guard = "rss_guard"
                proc.kill()
                break
            if time.monotonic() >= deadline:
                guard = "external_watchdog"
                proc.kill()
                break
            time.sleep(0.02)
        code = proc.wait()
    end = time.perf_counter_ns()
    return {"command": command, "exit_code": code,
            "process_launch_ns": launch_end - start,
            "solver_wall_ns": end - launch_end,
            "sampled_peak_child_rss_bytes": peak,
            "memory_guard_bytes": MAX_RSS_BYTES,
            "guard": guard, "stdout_sha256": file_hash(stdout_path),
            "stderr_sha256": file_hash(stderr_path),
            "status_lines": [line for line in stdout_path.read_text(errors="replace").splitlines()
                             if line.startswith("s ")]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoding", choices=("fc", "unary"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=DEFAULT_SECONDS)
    parser.add_argument("--conflicts", type=int, default=DEFAULT_CONFLICTS)
    args = parser.parse_args()
    if args.seconds < 1 or args.conflicts < 1:
        raise ValueError("limits must be positive")
    out = args.out.resolve()
    if out.exists():
        raise FileExistsError("run output is immutable")
    if not CMS.is_file():
        raise FileNotFoundError(CMS)
    out.mkdir(parents=True)
    field = Field()
    curve = Curve(field)
    setup_start = time.perf_counter_ns()
    assert curve.on_curve(GENERATOR) and curve.on_curve(TARGET)
    assert curve.mul(GENERATOR, R) is None and curve.mul(TARGET, R) is None
    alpha, conjugates = normal_basis(field)
    setup_ns = time.perf_counter_ns() - setup_start
    base_start = time.perf_counter_ns()
    base = geometry(field, curve, conjugates)
    base_ns = time.perf_counter_ns() - base_start
    circuit = Circuit(N, list(LOW_TERMS))
    build_start = time.perf_counter_ns()
    meta = build(circuit, conjugates, base["rejected_pairs"], args.encoding)
    build_ns = time.perf_counter_ns() - build_start
    xcnf = out / "system.xcnf"
    write_start = time.perf_counter_ns()
    circuit.write(xcnf)
    write_ns = time.perf_counter_ns() - write_start
    attempt = solve(xcnf, out, args.seconds, args.conflicts)
    model = parse_model((out / "solver.stdout.txt").read_text(errors="replace"))
    model_verified = model is not None and verify_model(circuit, model)
    group_lift = lift_model(curve, base["raw_to_projected"], conjugates, meta, model) if model_verified else None
    if group_lift and group_lift["verified"]:
        status = "VERIFIED_DECOMPOSITION"
    elif model is not None:
        status = "INVALID_MODEL_OR_GROUP_LIFT"
    elif attempt["guard"]:
        status = attempt["guard"].upper()
    else:
        status = "INDETERMINATE"
    field_record = {"p": 2, "n": N, "basis": "polynomial",
                    "defining_polynomial_int": MODULUS,
                    "element_encoding": "nonnegative polynomial coefficient bit mask"}
    curve_record = {"model": "y^2+x*y=x^3+1",
                    "coefficients": {"a1": 1, "a2": 0, "a3": 0, "a4": 0, "a6": 1},
                    "curve_order": R * COFACTOR,
                    "trace": (1 << N) + 1 - R * COFACTOR,
                    "r": R, "cofactor": COFACTOR, "G": list(GENERATOR),
                    "target_group": "prime_order_r_subgroup"}
    curve_id = "EC1N53Ckb1h" + digest({"field": field_record, "curve": curve_record})[:12]
    fixture = {"curve_id": curve_id, "target": list(TARGET),
               "law": "published_subgroup_point_from_frozen_N53_target_fixture",
               "previous_fixture_scalar_validation_only": 596471236405,
               "target_count": 1, "input_state": "ordinary_unplanted_for_weight2_base"}
    source_paths = [Path(__file__), HERE / "n53_group.py", HERE / "circuit.py",
                    HERE / "fc_hamming.py", HERE / "unary_hamming.py"]
    report = {"kind": "n53_weight2_s3_hamming_paired_pdp_stage",
              "status": status, "candidate_id": None, "proposal_id": None,
              "curve_id": curve_id, "field": field_record, "curve": curve_record,
              "factor_base": {"normal_element": alpha, "normal_basis_rank": N,
                              "nominal_weight": WEIGHT, "nominal_masks": 1378,
                              "rational_x_count": base["raw_points"] // 2,
                              "geometric_points": base["raw_points"],
                              "actual_usable_points": base["usable_projected_points"],
                              "effective_columns": base["signed_frobenius_columns"],
                              "projected_set_sha256": base["projected_set_sha256"],
                              "column_set_sha256": base["column_set_sha256"]},
              "encoding": args.encoding, "summands": M, "target": list(TARGET),
              "fixture": fixture, "workload_id": "W" + digest(fixture)[:12],
              "formula": {key: value for key, value in meta.items()
                          if key not in ("x_rows", "middle_rows")},
              "x_rows": meta["x_rows"], "middle_rows": meta["middle_rows"],
              "limits": {"seconds": args.seconds, "conflicts": args.conflicts,
                         "solver_threads": 1, "sampled_rss_guard_bytes": MAX_RSS_BYTES},
              "phase_wall_ns": {"setup_and_fixture": setup_ns,
                                "factor_base": base_ns,
                                "formula_build": build_ns,
                                "xcnf_write": write_ns,
                                "solver": attempt["solver_wall_ns"]},
              "attempt": attempt, "model_xcnf_verified": model_verified,
              "group_lift": group_lift,
              "xcnf_sha256": file_hash(xcnf), "solver_binary_sha256": file_hash(CMS),
              "source_sha256": {str(p.relative_to(ROOT)): file_hash(p)
                                for p in source_paths},
              "host": {"platform": platform.platform(), "machine": platform.machine(),
                       "python": platform.python_version()},
              "peak_parent_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "claim_boundary": "One bounded ordinary PDP stage only; no relations, rank, target log, or IC/rho speedup."}
    (out / "receipt.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"encoding": args.encoding, "status": status,
                      "geometry": report["factor_base"], "formula": report["formula"],
                      "phase_wall_ns": report["phase_wall_ns"],
                      "sampled_peak_child_rss_bytes": attempt["sampled_peak_child_rss_bytes"]},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
