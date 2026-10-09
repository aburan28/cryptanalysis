#!/usr/bin/env python3
"""Follow-up algebraic gates for the seven IC proposals.

Run with the repository's checked Sage launcher.  These are stage experiments;
none defines a complete IC candidate or measures a one-target DLP speedup.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
import random
import time
from pathlib import Path

from sage.all import GF, Matrix, PolynomialRing, matrix, set_random_seed, vector

from boolean_core import ANFField, echelon, sparse_macaulay
from sage_probes import (
    bits, candidate_x_points, curve, field, frobenius_orbits, from_bits,
    multiplier_orbit, norm_multipliers, normal_basis, planted_targets,
    ring_mul, ring_s3,
)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def receipt(idea, **data):
    return {
        "schema_version": 1, "proposal_id": idea, "candidate_id": None,
        "run_id": None, "source_sha256": sha(Path(__file__)),
        "sage_probes_sha256": sha(HERE / "sage_probes.py"),
        "boolean_core_sha256": sha(HERE / "boolean_core.py"),
        "scope": "bounded stage diagnostic; no complete IC pipeline, target DLP, or speedup",
        **data,
    }


def g1(args):
    """Cache target-independent Macaulay structure, then check every row."""
    K, modulus = field(31)
    E = curve(K)
    dimension = 3
    basis, points = candidate_x_points(E, K, dimension)
    anf = ANFField(31, modulus)
    cells = []
    for arity in (2, 3):
        targets = planted_targets(points, arity, args.targets)
        leaves = [anf.linear(list(range(i * dimension, (i + 1) * dimension)),
                             [bits(value) for value in basis]) for i in range(arity)]
        systems = []
        for Q, _ in targets:
            target = anf.constant(bits(Q[0]))
            systems.append(anf.s3(leaves[0], leaves[1], target) if arity == 2
                           else anf.s4(leaves[0], leaves[1], leaves[2], target))
        # These are structural degree bounds from S3 and S4 with constant
        # target coordinates, fixed before inspecting any replay target.
        degree = 2 if arity == 2 else 6
        fixed_degrees = [degree]*31
        assert all(term.bit_count() <= degree for system in systems
                   for equation in system for term in equation)
        nvars = dimension * arity
        first = sparse_macaulay(systems[0], nvars, degree, fixed_degrees=fixed_degrees,
                                max_columns=100_000, max_rows=100_000)
        positions = {term: i for i, term in enumerate(first.columns)}
        sources = first.sources
        _, captured_trace = echelon(first.packed_rows())
        matches = []
        pivot_trace_matches = []
        cached_build_ns = []
        fresh_build_ns = []
        for equations in systems:
            t0 = time.perf_counter_ns()
            packed = []
            for equation_index, multiplier in sources:
                row = 0
                for term in equations[equation_index]:
                    row ^= 1 << positions[term | multiplier]
                packed.append(row)
            cached_build_ns.append(time.perf_counter_ns() - t0)
            t0 = time.perf_counter_ns()
            fresh = sparse_macaulay(equations, nvars, degree,
                                    fixed_degrees=fixed_degrees,
                                    max_columns=100_000, max_rows=100_000)
            fresh_build_ns.append(time.perf_counter_ns() - t0)
            matches.append(tuple(packed) == fresh.packed_rows() and sources == fresh.sources)
            _, this_trace = echelon(tuple(packed))
            pivot_trace_matches.append(tuple(step for step in this_trace if step[0] == "pivot") ==
                                       tuple(step for step in captured_trace if step[0] == "pivot"))
        assert all(matches)
        cells.append({
            "arity": arity, "targets": len(targets), "boolean_variables": nvars,
            "macaulay_degree": degree, "rows": len(sources),
            "columns": len(first.columns), "cached_rows_equal_fresh": matches,
            "same_pivot_schedule_as_first": pivot_trace_matches,
            "cached_build_ns": cached_build_ns, "fresh_build_ns": fresh_build_ns,
            "fixed_degree_schedule": fixed_degrees,
        })
    return receipt("G1", field_degree=31, field_modulus_bits=modulus, cells=cells,
                   conclusion="The symbolic row/column schedule is reusable and exact. Dynamic coefficients still require elimination; this is not F4 trace reuse.")


def shift_polynomial(poly, n, direction):
    answer = set()
    for monomial in poly:
        shifted = 0
        for block in range(3):
            for i in range(n):
                if monomial >> (block*n+i) & 1:
                    shifted |= 1 << (block*n+(i+direction) % n)
        answer.add(shifted)
    return answer


def g2(args):
    """Build actual descended S3 rows with a cyclic target barrel."""
    cells = []
    for n in (19, 23):
        K, modulus = field(n)
        normal = normal_basis(K)
        inverse = matrix(GF(2), n, n,
                         lambda i, j: (bits(normal[j]) >> i) & 1).inverse()
        anf = ANFField(n, modulus)
        variables = [anf.linear(list(range(block*n, (block+1)*n)),
                                [bits(value) for value in normal]) for block in range(3)]
        power_equations = anf.s3(*variables)
        equations = []
        for j in range(n):
            row = set()
            for i in range(n):
                if inverse[j, i]:
                    row.symmetric_difference_update(power_equations[i])
            equations.append(row)
        plus = all(shift_polynomial(equations[j], n, 1) == equations[(j+1) % n]
                   for j in range(n))
        minus = all(shift_polynomial(equations[j], n, -1) == equations[(j+1) % n]
                    for j in range(n))
        assert plus or minus
        one_hot_pairs = {((1 << (2*n+i)) | (1 << (2*n+j)))
                         for i in range(n) for j in range(i+1, n)}
        one_hot_linear = {0} | {1 << (2*n+i) for i in range(n)}
        assert {next(iter(shift_polynomial({term}, n, 1)))
                for term in one_hot_pairs} == one_hot_pairs
        assert shift_polynomial(one_hot_linear, n, 1) == one_hot_linear
        columns = {term for equation in equations for term in equation}
        index = {term: i for i, term in enumerate(sorted(columns))}
        rows = tuple(sum(1 << index[term] for term in equation) for equation in equations)
        reduced, _ = echelon(rows)
        binary_rank = sum(bool(row) for row in reduced)
        extension_degree = n-1 if n == 19 else 11
        L = GF(2**extension_degree, f"u{n}")
        root = L.multiplicative_generator()**((2**extension_degree-1)//n)
        assert root.multiplicative_order() == n
        nonzero_characters = []
        for k in range(n):
            transformed = {}
            for j, equation in enumerate(equations):
                scalar = root**(j*k)
                for term in equation:
                    transformed[term] = transformed.get(term, L(0)) + scalar
            if any(transformed.values()):
                nonzero_characters.append(k)
        assert len(nonzero_characters) == binary_rank
        cells.append({
            "field_degree": n, "field_modulus_bits": modulus,
            "normal_basis_bits": [bits(value) for value in normal],
            "s3_equation_rows": n, "active_monomials": len(columns),
            "cyclic_shift_orientation": "+1" if plus else "-1",
            "binary_row_rank": binary_rank,
            "dft_nonzero_character_count": len(nonzero_characters),
            "dft_nonzero_characters": nonzero_characters,
            "target_barrel_rule": "third field input is a one-hot Frobenius orbit of the normal-basis generator",
            "one_hot_constraints_cyclic": True,
        })
    return receipt("G2", cells=cells,
                   conclusion="The unmultiplied S3 row module is cyclic and its DFT rank agrees with binary rank. A Macaulay/F4 block solve and speedup remain unmeasured.")


def g4(args):
    """Use Frobenius rationality on the mixed intermediate exactly."""
    K, modulus = field(19)
    E = curve(K)
    basis, points = candidate_x_points(E, K, 2)
    targets = planted_targets(points, 3, args.targets)
    T = PolynomialRing(K, "z")
    z = T.gen()
    def power_mod(base, exponent, modulus):
        answer = T(1)
        base %= modulus
        while exponent:
            if exponent & 1:
                answer = (answer*base) % modulus
            base = (base*base) % modulus
            exponent >>= 1
        return answer
    cells = []
    for Q, _ in targets:
        rational = 0
        closure = 0
        filtered = 0
        trace_filtered = 0
        quadratic_common = 0
        for mask in range(64):
            xs = [sum((basis[j] for j in range(2) if mask >> (2*i+j) & 1), K(0))
                  for i in range(3)]
            first = (xs[0]*xs[1] + xs[0]*z + xs[1]*z)**2 + xs[0]*xs[1]*z + 1
            second = (z*xs[2] + z*Q[0] + xs[2]*Q[0])**2 + z*xs[2]*Q[0] + 1
            common = first.gcd(second)
            has_closure = common.degree() > 0
            # z^(2^19)-z is reduced modulo the quadratic common factor before
            # taking a gcd, so the subfield gate remains degree at most two.
            has_rational = has_closure and common.gcd(power_mod(z, 2**19, common) + z).degree() > 0
            if common.degree() == 2:
                quadratic_common += 1
                A, B, C = common[2], common[1], common[0]
                trace_root = B == 0 or (A*C/(B*B)).trace() == 0
            else:
                trace_root = common.degree() == 1
            assert trace_root == has_rational
            direct = any(second(root) == 0 for root, _ in first.roots())
            assert has_rational == direct
            closure += has_closure
            rational += direct
            filtered += has_rational
            trace_filtered += trace_root
        cells.append({"target_point": [bits(Q[0]), bits(Q[1])],
                      "leaf_assignments": 64, "algebraic_closure_hits": closure,
                      "field_rational_hits": rational,
                      "frobenius_filtered_hits": filtered,
                      "trace_filtered_hits": trace_filtered,
                      "quadratic_common_factor_assignments": quadratic_common,
                      "false_positives_removed": closure-rational})
    return receipt("G4", field_degree=19, field_modulus_bits=modulus,
                   mixed_variables=7, boolean_variables=25, cells=cells,
                   conclusion="The finite-field intermediate gate is exact on these exhaustive leaf cells. Its cost in a full mixed-field F4 solve is unknown.")


def rank_mod(rows, modulus):
    work = [list(map(lambda x: x % modulus, row)) for row in rows]
    pivot = 0
    for col in range(len(work[0])):
        source = next((i for i in range(pivot, len(work)) if work[i][col]), None)
        if source is None:
            continue
        work[pivot], work[source] = work[source], work[pivot]
        inverse = pow(work[pivot][col], -1, modulus)
        work[pivot] = [(x*inverse) % modulus for x in work[pivot]]
        for i in range(len(work)):
            if i != pivot and work[i][col]:
                factor = work[i][col]
                work[i] = [(a-factor*b) % modulus for a, b in zip(work[i], work[pivot])]
        pivot += 1
        if pivot == len(work):
            break
    return pivot


def a1(args):
    """Test multiplier closure after known log transport is imposed."""
    source = RESULTS / "a1_final.json"
    old = json.loads(source.read_text())
    r = old["subgroup_order"]
    lam = old["frobenius_scalar"]
    classes = sorted({multiplier_orbit((a+b*lam) % r, lam, 53, r)
                      for a, b, _ in norm_multipliers(16)})
    rng = random.Random(20261008)
    rows = [[rng.randrange(r) for _ in range(6)] for _ in range(12)]
    original_rank = rank_mod(rows, r)
    transported = [[(alpha*entry) % r for entry in row]
                   for alpha in classes for row in rows]
    transported_rank = rank_mod(transported, r)
    assert original_rank == transported_rank
    prior = json.loads((HERE.parent / "koblitz-cofactor-fiber-20260928" /
                        "n53_frobenius_relation_rows_replay.json").read_text())
    assert prior["source_matrix_rank"] == prior["maximum_rank_after_adding_conjugates"]
    return receipt("A1", curve_id=old["curve_id"], subgroup_order=r,
                   frobenius_scalar=lam, norm_bound=16,
                   multipliers_up_to_sign=len(norm_multipliers(16)),
                   classes_after_sign_frobenius=len(classes), classes=classes,
                   toy_original_rank=original_rank,
                   toy_rank_after_known_log_transport=transported_rank,
                   actual_frobenius_source_rank=prior["source_matrix_rank"],
                   actual_frobenius_extended_rank=prior["maximum_rank_after_adding_conjugates"],
                   prior_rank_receipt_sha256=sha(HERE.parent / "koblitz-cofactor-fiber-20260928" /
                                                 "n53_frobenius_relation_rows_replay.json"),
                   conclusion="Uniform multiplier images yield known scalar multiples of the same relation after pulling derived log variables back. They add zero independent rank in that column model; a different factor-base design requires its own rank test.")


def a2(args):
    """Measure whether sparse cyclotomic coordinates have a unique encoding."""
    K, modulus = field(23)
    gamma = K.multiplicative_generator()**((2**23-1)//47)
    powers = [gamma**i for i in range(47)]
    representations = {}
    by_weight = Counter()
    for weight in (2, 3):
        for indices in itertools.combinations(range(47), weight):
            value = bits(sum((powers[i] for i in indices), K(0)))
            by_weight[weight] += 1
            representations.setdefault(value, []).append(indices)
    collision_histogram = Counter(len(v) for v in representations.values())
    weight2_values = {value for value, reps in representations.items()
                      if any(len(rep) == 2 for rep in reps)}
    weight3_values = {value for value, reps in representations.items()
                      if any(len(rep) == 3 for rep in reps)}
    assert all(bits(sum((powers[i] for i in reps[0]), K(0))) == value
               for value, reps in representations.items())
    return receipt("A2", field_degree=23, field_modulus_bits=modulus,
                   gamma_bits=bits(gamma), gamma_order=47,
                   support_bits=47, source_supports_by_weight=dict(by_weight),
                   distinct_x=len(representations), collision_histogram=dict(collision_histogram),
                   weight2_x=len(weight2_values), weight3_x=len(weight3_values),
                   weight2_weight3_overlap=len(weight2_values & weight3_values),
                   x47_equals_1=sum(from_bits(K, x)**47 == 1 for x in representations),
                   x263_equals_1=sum(from_bits(K, x)**263 == 1 for x in representations),
                   frobenius_x_orbits=len(frobenius_orbits(K, {from_bits(K, x)
                                                               for x in representations})),
                   conclusion="The exact selector encoding uses 47 support bits at n=23. Root-power equations do not encode the sparse-sum family; its PDP solving degree remains unknown.")


def n1(args):
    """Construct exact group-algebra lifts via a central CRT idempotent."""
    K, modulus = field(23)
    E = curve(K)
    gamma = K.multiplicative_generator()**((2**23-1)//47)
    basis = [gamma**i for i in range(23)]
    change = matrix(GF(2), 23, 23,
                    lambda i, j: (bits(basis[j]) >> i) & 1).inverse()
    def section(value):
        coordinates = change*vector(GF(2), [(bits(value) >> i) & 1 for i in range(23)])
        return sum(int(coordinates[i]) << i for i in range(23))
    def project(value):
        return sum((gamma**i for i in range(47) if value >> i & 1), K(0))
    R = PolynomialRing(GF(2), "z")
    z = R.gen()
    group_modulus = z**47+1
    selected = R(gamma.minpoly().list())
    assert group_modulus % selected == 0
    complement_factor = group_modulus // selected
    idempotent_poly = (complement_factor*
                       (complement_factor % selected).inverse_mod(selected)) % group_modulus
    idempotent = sum(int(c) << i for i, c in enumerate(idempotent_poly.list()))
    complement = idempotent ^ 1
    assert project(idempotent) == 1
    assert ring_mul(idempotent, idempotent, 47) == idempotent
    assert ring_mul(idempotent, complement, 47) == 0
    def exact_lift(a, b, c):
        # On the complementary CRT factors choose (0,1,1), an S3 root.
        return (ring_mul(idempotent, section(a), 47),
                ring_mul(idempotent, section(b), 47) ^ complement,
                ring_mul(idempotent, section(c), 47) ^ complement)
    rng = random.Random(20261007)
    G = E.random_point()
    while G.is_zero():
        G = E.random_point()
    tested = 0
    naive_exact = 0
    crt_exact = 0
    naive_weights = []
    crt_weights = []
    for _ in range(args.targets):
        P = rng.randrange(1, 1 << 22)*G
        Q = rng.randrange(1, 1 << 22)*G
        S = P+Q
        if P.is_zero() or Q.is_zero() or S.is_zero():
            continue
        values = (P[0], Q[0], S[0])
        naive = tuple(section(v) for v in values)
        lifted = exact_lift(*values)
        assert tuple(project(v) for v in lifted) == values
        assert project(ring_s3(*naive, 47)) == 0
        naive_exact += ring_s3(*naive, 47) == 0
        crt_exact += ring_s3(*lifted, 47) == 0
        naive_weights.append(sum(v.bit_count() for v in naive))
        crt_weights.append(sum(v.bit_count() for v in lifted))
        tested += 1
    assert crt_exact == tested
    return receipt("N1", field_degree=23, field_modulus_bits=modulus,
                   group_algebra_length=47, kernel_dimension=24,
                   selected_factor_degree=int(selected.degree()),
                   idempotent_bits=idempotent, idempotent_weight=idempotent.bit_count(),
                   planted_samples=tested, polynomial_section_exact=naive_exact,
                   crt_section_exact=crt_exact,
                   mean_polynomial_section_total_weight=sum(naive_weights)/tested,
                   mean_crt_section_total_weight=sum(crt_weights)/tested,
                   conclusion="Exact lifting always exists for these true S3 solutions via CRT; the earlier 0/256 result only falsified the sparse polynomial section. The CRT lift is dense and gives no additive-combinatoric PDP shortcut.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe", choices=("g1", "g2", "g4", "a1", "a2", "n1"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--targets", type=int, default=16)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve prior receipt")
    if args.targets < 1:
        parser.error("targets must be positive")
    set_random_seed(20261008)
    start = time.perf_counter_ns()
    result = globals()[args.probe](args)
    result["stage_wall_ns"] = time.perf_counter_ns()-start
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"proposal_id": result["proposal_id"],
                      "stage_wall_ns": result["stage_wall_ns"],
                      "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
