"""Run-06 solver control: matched finite direct-S5 and enumerative unordered-pair systems.

Port of ECC2K-130 run06_solver_controls.py to F_(2^83).  The pair-index
presentation is deliberately labelled enumerative: it tabulates the finite
unordered-pair image and is not a scalable radical-image algorithm.  Its
purpose is to test whether quotienting pair order lowers the observed solver
degree after complete membership and cross-pair distinctness are added.

Differences from the ECC2K-130 run: every cap is CPU time (the CPU alarm for
Sage stages, RLIMIT_CPU for msolve), so censoring does not depend on machine
load; field coordinates are 83 bits.  Targets are planted (a deterministic
four-point sum); planted rows never enter yield or rank.

    sage -python run06_solver_controls.py --k 4 --output ../outputs/run06-four-summand/solver-k4.json
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile
import time

from cysignals.alarm import AlarmInterrupt
from sage.all import GF, PolynomialRing, prod

import m83
from m83 import alarm, cancel_alarm
import run01_comparison as cc
from run02_attribution import top_components

N = m83.ELL


def formal_regularity(ring, equations):
    """Uncapped here; capped_regularity() arms the CPU alarm around it."""
    if any(f == 1 for f in equations):
        return {'degree_of_regularity': 0, 'top_quotient_dimension': 0}
    ideal = ring.ideal(top_components(ring, equations))
    basis = ideal.groebner_basis(algorithm='libsingular:std')
    ideal.groebner_basis.set_cache(basis)
    standard = ideal.normal_basis()
    return {'degree_of_regularity': 0 if not standard else 1 + max(int(m.degree()) for m in standard),
            'top_quotient_dimension': len(standard)}


def planted_target(domain, masks):
    ordered = sorted(masks)
    for four in itertools.combinations(ordered, 4):
        for signs in itertools.product(range(2), repeat=4):
            if sum(domain["tags"][mask][sign] for mask, sign in zip(four, signs)) % 4:
                continue
            points = [domain["lifts"][mask][sign] for mask, sign in zip(four, signs)]
            target = sum(points[1:], points[0])
            if not target.is_zero():
                return target, [[mask, sign] for mask, sign in zip(four, signs)]
    raise AssertionError("no planted target available")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_poly(left, right):
    size = max(len(left), len(right))
    zero = left[0].parent().zero() if left else right[0].parent().zero()
    out = [zero] * size
    for index in range(size):
        if index < len(left):
            out[index] += left[index]
        if index < len(right):
            out[index] += right[index]
    while len(out) > 1 and not out[-1]:
        out.pop()
    return out


def mul_poly(left, right):
    zero = left[0].parent().zero()
    out = [zero] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            out[i + j] += a * b
    while len(out) > 1 and not out[-1]:
        out.pop()
    return out


def scale_poly(poly, scalar):
    return [scalar * value for value in poly]


def square_poly(poly):
    zero = poly[0].parent().zero()
    out = [zero] * (2 * len(poly) - 1)
    for index, value in enumerate(poly):
        out[2 * index] = value * value
    while len(out) > 1 and not out[-1]:
        out.pop()
    return out


def determinant_char2(matrix_rows):
    """Subset-DP determinant; signs disappear in characteristic two."""
    field = matrix_rows[0][0].parent()
    dp = {0: field.one()}
    for row_index, row in enumerate(matrix_rows):
        nxt = {}
        for used, value in dp.items():
            for column, coefficient in enumerate(row):
                if used >> column & 1 or not coefficient:
                    continue
                mask = used | (1 << column)
                nxt[mask] = nxt.get(mask, field.zero()) + value * coefficient
        dp = {mask: value for mask, value in nxt.items() if value}
    return dp.get((1 << len(matrix_rows)) - 1, field.zero())


def resultant_2_4(p, q):
    """Resultant of ascending coefficient lists of degrees 2 and 4."""
    assert len(p) == 3 and len(q) == 5
    p0, p1, p2 = p
    q0, q1, q2, q3, q4 = q
    # The generic Sylvester determinant has only 17 terms in characteristic 2.
    # Keeping this straight-line form makes the 2^(4k) truth-table control at
    # k=4 and k=5 practical without changing the polynomial being evaluated.
    return (
        p2**4 * q0**2
        + p1 * p2**3 * q0 * q1
        + p0 * p2**3 * q1**2
        + p1**2 * p2**2 * q0 * q2
        + p0 * p1 * p2**2 * q1 * q2
        + p0**2 * p2**2 * q2**2
        + p1**3 * p2 * q0 * q3
        + p0 * p1 * p2**2 * q0 * q3
        + p0 * p1**2 * p2 * q1 * q3
        + p0**2 * p1 * p2 * q2 * q3
        + p0**3 * p2 * q3**2
        + p1**4 * q0 * q4
        + p0 * p1**3 * q1 * q4
        + p0**2 * p1 * p2 * q1 * q4
        + p0**2 * p1**2 * q2 * q4
        + p0**3 * p1 * q3 * q4
        + p0**4 * q4**2
    )


def second_pair_quartic(s, t, z, curve_b):
    """Eliminate v from S3(pair2,v) and S3(z,u,v); return in u."""
    field = s.parent()
    zero, one = field.zero(), field.one()
    a1 = s * s
    b1 = t
    c1 = t * t + curve_b
    a2 = [z * z, zero, one]
    b2 = [zero, z]
    c2 = [curve_b, zero, z * z]
    first = add_poly(scale_poly(c2, a1), scale_poly(a2, c1))
    second = add_poly(scale_poly(b2, a1), scale_poly(a2, b1))
    third = add_poly(scale_poly(c2, b1), scale_poly(b2, c1))
    result = add_poly(square_poly(first), mul_poly(second, third))
    result += [zero] * (5 - len(result))
    assert len(result) == 5
    return result


def s5_symmetric(s1, t1, s2, t2, z, curve_b):
    p = [t1 * t1 + curve_b, t1, s1 * s1]
    q = second_pair_quartic(s2, t2, z, curve_b)
    return resultant_2_4(p, q)


def s5_direct(x1, x2, x3, x4, z, curve_b):
    return s5_symmetric(x1 + x2, x1 * x2, x3 + x4, x3 * x4, z, curve_b)


def self_test_resultant(field) -> None:
    ring = PolynomialRing(field, "U")
    for seed in range(5):
        values = [field.from_integer((seed + 2) * (index + 3)) for index in range(8)]
        p = values[:3]
        q = values[3:8]
        assert resultant_2_4(p, q) == ring(p).resultant(ring(q))


def mobius(values: list[int], variables: int) -> list[int]:
    assert len(values) == 1 << variables
    values = values[:]
    for bit in range(variables):
        step = 1 << bit
        for mask in range(1 << variables):
            if mask & step:
                values[mask] ^= values[mask ^ step]
    return values


def indicator_anf(valid: set[int], variables: int) -> list[int]:
    return mobius([0 if mask in valid else 1 for mask in range(1 << variables)], variables)


def shifted_anf(coefficients: list[int], shift: int) -> dict[int, int]:
    return {mask << shift: 1 for mask, value in enumerate(coefficients) if value}


def field_coordinate_rows(field_anf: list[int]) -> list[dict[int, int]]:
    monomials = [mask for mask, coefficient in enumerate(field_anf) if coefficient]
    rows = [0] * m83.M
    for column, mask in enumerate(monomials):
        coefficient = field_anf[mask]
        while coefficient:
            low = coefficient & -coefficient
            rows[low.bit_length() - 1] |= 1 << column
            coefficient ^= low
    pivots = {}
    for row in rows:
        while row:
            pivot = row.bit_length() - 1
            if pivot in pivots:
                row ^= pivots[pivot]
            else:
                pivots[pivot] = row
                break
    result = []
    for pivot in sorted(pivots, reverse=True):
        row = pivots[pivot]
        polynomial = {}
        while row:
            low = row & -row
            polynomial[monomials[low.bit_length() - 1]] = 1
            row ^= low
        result.append(polynomial)
    return result


def dict_to_sage(ring, polynomial: dict[int, int]):
    variables = ring.ngens()
    return ring({tuple((mask >> index) & 1 for index in range(variables)): value
                 for mask, value in polynomial.items() if value})


def direct_system(curve_b, target_x, domain: dict, k: int):
    started = time.perf_counter()
    variables = 4 * k
    block_mask = (1 << k) - 1
    values = domain["values"][:1 << k]
    truth = []
    valid_solution_masks = []
    allowed = {mask for mask in domain["lifts"] if mask < (1 << k)}
    for assignment in range(1 << variables):
        masks = tuple((assignment >> (block * k)) & block_mask for block in range(4))
        value = s5_direct(*(values[mask] for mask in masks), target_x, curve_b)
        encoded = m83.enc(value)
        truth.append(encoded)
        if not encoded and all(mask in allowed for mask in masks) and len(set(masks)) == 4:
            valid_solution_masks.append(masks)
    field_anf = mobius(truth, variables)
    coordinate_rows = field_coordinate_rows(field_anf)
    ring = PolynomialRing(GF(2), variables, names=[f"x{i}" for i in range(variables)],
                          order="degrevlex")
    equations = [dict_to_sage(ring, row) for row in coordinate_rows]
    membership = indicator_anf(allowed, k)
    for block in range(4):
        equations.append(dict_to_sage(ring, shifted_anf(membership, block * k)))
    gens = ring.gens()
    for left, right in itertools.combinations(range(4), 2):
        equations.append(prod(1 + gens[left * k + bit] + gens[right * k + bit]
                              for bit in range(k)))
    equations.extend(variable * variable + variable for variable in gens)
    equations = [equation for equation in equations if equation]
    return {
        "ring": ring,
        "equations": equations,
        "solutions": valid_solution_masks,
        "field_anf_terms": sum(bool(value) for value in field_anf),
        "field_coordinate_rank": len(coordinate_rows),
        "construction_seconds": time.perf_counter() - started,
    }


def pair_system(curve_b, target_x, domain: dict, k: int):
    started = time.perf_counter()
    allowed = sorted(mask for mask in domain["lifts"] if mask < (1 << k))
    pairs = list(itertools.combinations(allowed, 2))
    pair_values = []
    for left, right in pairs:
        x, y = domain["values"][left], domain["values"][right]
        pair_values.append((x + y, x * y))
    bits = max(1, (len(pairs) - 1).bit_length())
    variables = 2 * bits
    truth = []
    disjoint_truth = []
    valid_solution_indices = []
    for assignment in range(1 << variables):
        left_index = assignment & ((1 << bits) - 1)
        right_index = assignment >> bits
        valid = left_index < len(pairs) and right_index < len(pairs)
        if valid:
            s1, t1 = pair_values[left_index]
            s2, t2 = pair_values[right_index]
            encoded = m83.enc(s5_symmetric(s1, t1, s2, t2, target_x, curve_b))
            disjoint = set(pairs[left_index]).isdisjoint(pairs[right_index])
            if not encoded and disjoint:
                valid_solution_indices.append((left_index, right_index))
            disjoint_truth.append(0 if disjoint else 1)
        else:
            encoded = 0
            disjoint_truth.append(0)
        truth.append(encoded)
    field_anf = mobius(truth, variables)
    disjoint_anf = mobius(disjoint_truth, variables)
    coordinate_rows = field_coordinate_rows(field_anf)
    ring = PolynomialRing(GF(2), variables, names=[f"p{i}" for i in range(variables)],
                          order="degrevlex")
    equations = [dict_to_sage(ring, row) for row in coordinate_rows]
    valid_indices = set(range(len(pairs)))
    membership = indicator_anf(valid_indices, bits)
    equations.append(dict_to_sage(ring, shifted_anf(membership, 0)))
    equations.append(dict_to_sage(ring, shifted_anf(membership, bits)))
    equations.append(dict_to_sage(ring, {mask: 1 for mask, value in enumerate(disjoint_anf) if value}))
    equations.extend(variable * variable + variable for variable in ring.gens())
    equations = [equation for equation in equations if equation]
    return {
        "ring": ring,
        "equations": equations,
        "solutions": valid_solution_indices,
        "pairs": pairs,
        "index_bits_per_pair": bits,
        "field_anf_terms": sum(bool(value) for value in field_anf),
        "cross_pair_distinctness_anf_terms": sum(bool(value) for value in disjoint_anf),
        "field_coordinate_rank": len(coordinate_rows),
        "construction_seconds": time.perf_counter() - started,
    }


def enumerate_valid_direct_solutions(curve_b, target_x, domain: dict, k: int):
    allowed = sorted(mask for mask in domain["lifts"] if mask < (1 << k))
    solutions = []
    for masks in itertools.permutations(allowed, 4):
        values = [domain["values"][mask] for mask in masks]
        if not s5_direct(*values, target_x, curve_b):
            solutions.append(masks)
    return solutions


def capped_build(builder, cap_seconds: int):
    started = time.perf_counter()
    try:
        alarm(cap_seconds)
        result = builder()
        return result, None
    except AlarmInterrupt:
        return None, {
            "status": "censored",
            "censored_stage": "complete_system_construction",
            "cap_cpu_seconds": cap_seconds,
            "elapsed_seconds": time.perf_counter() - started,
            "degree_of_regularity": None,
            "max_f4_degree": None,
        }
    finally:
        cancel_alarm()


def capped_regularity(ring, equations, cap_seconds: int) -> dict:
    try:
        alarm(cap_seconds)
        result = formal_regularity(ring, equations)
        result["status"] = "verified"
        return result
    except AlarmInterrupt:
        return {
            "status": "censored",
            "cap_cpu_seconds": cap_seconds,
            "degree_of_regularity": None,
            "top_quotient_dimension": None,
        }
    finally:
        cancel_alarm()


def msolve_measure(ring, equations, cap_seconds: int, log_path: Path) -> dict:
    with tempfile.NamedTemporaryFile(mode="w", encoding="ascii", dir="/private/tmp",
                                     delete=False) as handle:
        print(",".join(ring.variable_names()), file=handle)
        print(2, file=handle)
        print(*(str(poly).replace(" ", "").replace("^", "^") for poly in equations),
              sep=",\n", file=handle)
        input_path = Path(handle.name)
    command = ["/opt/homebrew/bin/msolve", "-f", str(input_path), "-g", "1",
               "-v", "2", "-l", "2", "-t", "1", "--random-seed", "0"]
    started = time.perf_counter()

    def cpu_limit():
        resource.setrlimit(resource.RLIMIT_CPU, (int(cap_seconds), int(cap_seconds) + 1))
    try:
        completed = subprocess.run(command, capture_output=True, text=True, preexec_fn=cpu_limit,
                                   timeout=cap_seconds * 40)
        if completed.returncode in (-24, -9, 152, 137):     # SIGXCPU / SIGKILL at the CPU cap
            elapsed = time.perf_counter() - started
            log_path.write_text(completed.stdout + "\nSTDERR\n" + completed.stderr)
            return {"status": "censored", "cap_cpu_seconds": cap_seconds, "seconds": elapsed,
                    "max_f4_degree": None, "log": str(log_path)}
        elapsed = time.perf_counter() - started
        log_path.write_text(completed.stdout + "\nSTDERR\n" + completed.stderr)
        if completed.returncode:
            return {"status": "error", "returncode": completed.returncode,
                    "seconds": elapsed, "log": str(log_path)}
        pattern = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+x\s+(\d+)\s+")
        degrees = []
        for line in completed.stdout.splitlines():
            match = pattern.match(line)
            if match:
                degrees.append(int(match.group(1)))
        return {
            "status": "complete",
            "seconds": elapsed,
            "max_f4_degree": max(degrees) if degrees else None,
            "f4_round_degrees": degrees,
            "log": str(log_path),
            "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        log_path.write_text(stdout + "\nSTDERR\n" + stderr)
        return {"status": "censored", "cap_wall_seconds": cap_seconds * 40,
                "seconds": elapsed, "max_f4_degree": None, "log": str(log_path)}
    finally:
        input_path.unlink(missing_ok=True)


def validate_group_solutions(E, target, domain, solutions) -> int:
    replayed = 0
    for masks in solutions:
        found = False
        for signs in itertools.product(range(2), repeat=4):
            points = [domain["lifts"][mask][sign] for mask, sign in zip(masks, signs)]
            total = sum(points[1:], points[0])
            if total == target or total == -target:
                found = True
                break
        assert found, masks
        replayed += 1
    return replayed


def analyze_system(name: str, built: dict, cap_seconds: int, log_path: Path) -> dict:
    ring, raw = built["ring"], built["equations"]
    reduced, row_seconds = cc.row_reduce(ring, raw)
    summary = {
        "presentation": name,
        "variables": ring.ngens(),
        "raw_equations": len(raw),
        "row_reduced_equations": len(reduced),
        "raw_max_degree": max(int(poly.total_degree()) for poly in raw),
        "row_reduced_max_degree": max(int(poly.total_degree()) for poly in reduced),
        "row_reduction_seconds": row_seconds,
        "solution_assignments_by_exhaustive_truth_table": len(built["solutions"]),
        "construction_seconds": built["construction_seconds"],
        "field_anf_terms": built["field_anf_terms"],
        "field_coordinate_rank": built["field_coordinate_rank"],
    }
    if name == "enumerative_pair_index":
        summary.update({
            "unordered_pair_count": len(built["pairs"]),
            "index_bits_per_pair": built["index_bits_per_pair"],
            "cross_pair_distinctness_anf_terms": built["cross_pair_distinctness_anf_terms"],
            "scalability": "enumerative finite control; table size is quadratic in factor-base x count",
        })
    summary["formal_regularity"] = capped_regularity(ring, reduced, cap_seconds)
    summary["msolve"] = msolve_measure(ring, reduced, cap_seconds, log_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--cap", type=int, default=60)
    parser.add_argument("--construction-cap", type=int, default=300)
    args = parser.parse_args()
    if args.k > 5:
        raise ValueError("truth-table controls are frozen to k<=5")
    output = Path(args.output)
    if output.exists():
        raise ValueError("refusing to overwrite existing output")
    logs = output.parent / "solver-logs"
    logs.mkdir(parents=True, exist_ok=True)
    self_test_resultant(m83.FIELD)
    inventory = {row["curve_id"]: row for row in m83.load_inventory()}
    sel = json.loads((m83.OUT / "run04-explicit-descent" / "selection.json").read_text())
    selected_ids = ["E0"] + [p["curve_id"] for p in sel["selected"]]
    rows = []
    for curve_id in selected_ids:
        curve = inventory[curve_id]
        E = m83.curve(curve["b"])
        domain = cc.factor_domain(E, args.k, "polynomial")
        masks = set(domain["lifts"])
        target, source = planted_target(domain, masks)
        curve_b = m83.dec(curve["b"])
        direct, direct_censored = capped_build(
            lambda: direct_system(curve_b, target[0], domain, args.k), args.construction_cap)
        pair, pair_censored = capped_build(
            lambda: pair_system(curve_b, target[0], domain, args.k), args.construction_cap)
        if pair is None:
            pair_result, pair_solutions = pair_censored, []
        else:
            pair_result = analyze_system("enumerative_pair_index", pair, args.cap,
                                         logs / f"{curve_id}-k{args.k}-pair.txt")
            pair_solutions = pair["solutions"]
        if direct is None:
            direct_result = {**direct_censored, "presentation": "direct_s5",
                             "variables": 4 * args.k, "truth_table_cells": 1 << (4 * args.k)}
            direct_solutions = enumerate_valid_direct_solutions(curve_b, target[0], domain, args.k)
        else:
            direct_result = analyze_system("direct_s5", direct, args.cap,
                                           logs / f"{curve_id}-k{args.k}-direct.txt")
            direct_solutions = direct["solutions"]
        if pair is not None:
            assert len(direct_solutions) == 4 * len(pair_solutions)
        replayed = validate_group_solutions(E, target, domain, direct_solutions)
        row = {"curve_id": curve_id, "k": args.k, "factor_base_x_count": len(masks),
               "target_x": str(m83.enc(target[0])), "target_y": str(m83.enc(target[1])),
               "planted_source": source, "direct_group_solution_assignments_replayed": replayed,
               "direct_to_pair_solution_ratio": 4, "direct": direct_result, "pair": pair_result}
        rows.append(row)
        print(json.dumps({"curve_id": curve_id, "k": args.k, "x_count": len(masks),
                          "direct_variables": direct_result["variables"],
                          "pair_variables": pair_result.get("variables"),
                          "direct_dreg": direct_result.get("formal_regularity", {}).get("degree_of_regularity"),
                          "pair_dreg": pair_result.get("formal_regularity", {}).get("degree_of_regularity"),
                          "direct_f4": direct_result.get("msolve", {}).get("max_f4_degree"),
                          "pair_f4": pair_result.get("msolve", {}).get("max_f4_degree"),
                          "direct_status": direct_result.get("msolve", {}).get("status", direct_result.get("status")),
                          "pair_status": pair_result.get("msolve", {}).get("status", pair_result.get("status"))}),
              flush=True)
    result = {"schema": "m83-run06-solver-control-v1", "status": "complete",
              "source_sha256": sha256(Path(__file__)), "k": args.k,
              "cap_cpu_seconds_per_solver_or_regularity_stage": args.cap,
              "construction_cap_cpu_seconds_per_presentation": args.construction_cap,
              "rows": rows,
              "claim_boundary": ("matched finite planted-target solver control; pair-index preprocessing is "
                                 "enumerative and supplies no natural relation-yield or cryptographic-scale claim"),
              "no_discrete_log_computed": True}
    output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
