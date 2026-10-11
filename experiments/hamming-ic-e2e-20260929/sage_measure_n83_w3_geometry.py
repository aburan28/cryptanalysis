#!/usr/bin/env python3
"""Exact N83 transfer gate for the N53 normal-basis W3 four-sum base."""

from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
import hashlib
import itertools
import json
from math import comb
from pathlib import Path
import resource
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

N = 83
R = 2417851639230796216685689
H = 4
GENERATOR = (5280806513304026927410462, 9094931664963527384518944)
FIELD_RECORD = {
    "p": 2, "n": N, "basis": "polynomial",
    "defining_polynomial_int": (1 << N) | (1 << 7) | (1 << 4) | (1 << 2) | 1,
    "element_encoding": "nonnegative polynomial coefficient bit mask",
}
CURVE_RECORD = {
    "model": "y^2+xy=x^3+1",
    "coefficients": {"a1": 1, "a2": 0, "a3": 0, "a4": 0, "a6": 1},
    "curve_order": R * H, "trace": (1 << N) + 1 - R * H,
    "r": R, "cofactor": H, "G": list(GENERATOR),
    "target_group": "prime_order_r_subgroup",
}
CURVE_ID = "EC1N83Ckb1h2bcb59d56ad6"
WEIGHT = 3
SUMMANDS = 4


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_bytes(json.dumps(value, indent=2, sort_keys=True).encode() + b"\n")


def rank_bits(columns):
    pivots = {}
    for column in columns:
        value = column
        while value:
            bit = value.bit_length() - 1
            if bit not in pivots:
                pivots[bit] = value
                break
            value ^= pivots[bit]
    return len(pivots)


def decimal_ratio(numerator, denominator):
    with localcontext() as context:
        context.prec = 45
        return format(Decimal(numerator) / Decimal(denominator), ".35g")


def main(out):
    out = out.resolve()
    if not out.is_dir() or not (out / "sage_runtime_info.json").is_file():
        raise FileNotFoundError("create output and save checked Sage runtime first")
    if (out / "geometry.json").exists() or (out / "representatives.json").exists():
        raise FileExistsError("N83 geometry output is immutable")
    started_ns = time.perf_counter_ns()
    assert "EC1N83Ckb1h" + hashlib.sha256(canonical({
        "field": FIELD_RECORD, "curve": CURVE_RECORD})).hexdigest()[:12] == CURVE_ID
    save(out / "started.json", {
        "kind": "n83_w3_four_sum_geometry_start", "curve_id": CURVE_ID,
        "field_degree": N, "nominal_hamming_weight": WEIGHT,
        "summand_count": SUMMANDS, "candidate_id": None,
        "sage_runtime_info_sha256": sha(out / "sage_runtime_info.json"),
        "source_sha256": sha(Path(__file__)),
    })

    binary = GF(2)
    ring = PolynomialRing(binary, "u")
    u = ring.gen()
    modulus = u**N + u**7 + u**4 + u**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**N, "z", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert ZZ(R).is_prime(proof=True)
    assert curve.cardinality() == R * H

    def from_bits(bits):
        return field(ring([(bits >> i) & 1 for i in range(N)]))

    def bits(value):
        return sum(int(coefficient) << i
                   for i, coefficient in enumerate(value.polynomial().list()))

    generator = curve(from_bits(GENERATOR[0]), from_bits(GENERATOR[1]))
    assert generator != curve(0) and R * generator == curve(0)

    normal_element = None
    conjugates = None
    for candidate in range(2, 1 << 16):
        alpha = from_bits(candidate)
        values = [alpha]
        for _ in range(1, N):
            values.append(values[-1]**2)
        assert values[-1]**2 == alpha
        if rank_bits([bits(value) for value in values]) == N:
            normal_element, conjugates = candidate, values
            break
    assert normal_element is not None and conjugates is not None
    setup_ns = time.perf_counter_ns() - started_ns

    visited_masks = set()
    rational_orbits = 0
    nonrational_orbits = 0
    raw_points = set()
    projected_points = set()
    representative_keys = set()
    identity_projections = 0
    duplicate_projected_orbits = 0
    enumeration_started = time.perf_counter_ns()
    for ordinal, mask in enumerate(itertools.combinations(range(N), WEIGHT)):
        if mask in visited_masks:
            continue
        orbit = {tuple(sorted(((index + shift) % N for index in mask)))
                 for shift in range(N)}
        assert len(orbit) == N
        visited_masks.update(orbit)
        x = sum((conjugates[index] for index in mask), field(0))
        assert x != 0
        c = x + x**(-2)
        if c.trace() != 0:
            nonrational_orbits += 1
            continue
        term = c
        half_trace = field(0)
        for step in range((N - 1) // 2 + 1):
            if step:
                term = term**4
            half_trace += term
        assert half_trace**2 + half_trace == c
        point = curve(x, x * half_trace)
        assert point[1]**2 + point[0] * point[1] == point[0]**3 + 1
        rational_orbits += 1
        projected = H * point
        if projected == curve(0):
            identity_projections += 1
            continue
        assert R * projected == curve(0)
        for origin, target in ((point, raw_points),
                               (projected, projected_points)):
            cx, cy = origin[0], origin[1]
            for _ in range(N):
                x_code, y_code = bits(cx), bits(cy)
                target.add((x_code, y_code))
                target.add((x_code, x_code ^ y_code))
                cx, cy = cx**2, cy**2
            assert cx == origin[0] and cy == origin[1]
        px, py = projected[0], projected[1]
        candidates = []
        for _ in range(N):
            x_code, y_code = bits(px), bits(py)
            candidates.extend(((x_code, y_code), (x_code, x_code ^ y_code)))
            px, py = px**2, py**2
        representative = min(candidates)
        if representative in representative_keys:
            duplicate_projected_orbits += 1
        representative_keys.add(representative)
        if (rational_orbits + nonrational_orbits) % 100 == 0:
            save(out / "progress.json", {
                "mask_orbits_processed": rational_orbits + nonrational_orbits,
                "rational_orbits": rational_orbits,
                "nonrational_orbits": nonrational_orbits,
                "distinct_projected_points": len(projected_points),
            })

    enumeration_ns = time.perf_counter_ns() - enumeration_started
    nominal_masks = comb(N, WEIGHT)
    assert len(visited_masks) == nominal_masks
    assert rational_orbits + nonrational_orbits == nominal_masks // N
    assert len(raw_points) <= 2 * N * rational_orbits
    assert len(projected_points) == 2 * N * len(representative_keys)
    representatives = {
        "kind": "n83_w3_projected_signed_frobenius_representatives",
        "curve_id": CURVE_ID, "field_polynomial_low_terms": [0, 2, 4, 7],
        "normal_element_polynomial_bits": normal_element,
        "subgroup_order": str(R), "cofactor": H,
        "representatives": [list(pair) for pair in sorted(representative_keys)],
    }
    save(out / "representatives.json", representatives)
    base_size = len(projected_points)
    four_multisets = comb(base_size + SUMMANDS - 1, SUMMANDS)
    generous_B_ceiling = 2 * nominal_masks
    generous_multisets = comb(generous_B_ceiling + SUMMANDS - 1, SUMMANDS)
    record = {
        "schema_version": 1, "kind": "n83_w3_four_sum_geometry_gate",
        "status": "EXACT_GEOMETRY_PASS", "candidate_id": None,
        "curve_id": CURVE_ID, "field_degree": N,
        "curve_identity_record": {"field": FIELD_RECORD, "curve": CURVE_RECORD},
        "field_characteristic": 2, "field_basis": "polynomial",
        "field_polynomial_low_terms": [0, 2, 4, 7],
        "field_element_encoding": "nonnegative polynomial coefficient bit mask",
        "curve_model": "y^2+x*y=x^3+1", "curve_order": str(R * H),
        "subgroup_order": str(R), "cofactor": H,
        "normal_element_polynomial_bits": normal_element,
        "normal_basis_rank": N, "nominal_hamming_weight": WEIGHT,
        "nominal_masks": nominal_masks, "mask_frobenius_orbits": nominal_masks // N,
        "rational_x_orbits": rational_orbits,
        "nonrational_x_orbits": nonrational_orbits,
        "identity_projections": identity_projections,
        "duplicate_projected_orbits": duplicate_projected_orbits,
        "geometric_raw_points": len(raw_points),
        "actual_usable_projected_points_B": base_size,
        "effective_signed_frobenius_columns": len(representative_keys),
        "raw_point_set_sha256": hashlib.sha256(canonical(sorted(raw_points))).hexdigest(),
        "projected_point_set_sha256": hashlib.sha256(canonical(sorted(projected_points))).hexdigest(),
        "representatives_sha256": sha(out / "representatives.json"),
        "summand_count": SUMMANDS,
        "four_point_multisets_with_repetition": str(four_multisets),
        "uniform_subgroup_support_ceiling_fraction": decimal_ratio(four_multisets, R),
        "generous_B_ceiling": generous_B_ceiling,
        "generous_uniform_support_ceiling_fraction": decimal_ratio(generous_multisets, R),
        "timing_ms_exploratory": {
            "curve_and_normal_basis_setup": setup_ns / 1e6,
            "base_enumeration_and_orbit_expansion": enumeration_ns / 1e6,
            "whole_sage_process_from_main": (time.perf_counter_ns() - started_ns) / 1e6,
        },
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "sage_runtime_info_sha256": sha(out / "sage_runtime_info.json"),
        "source_sha256": sha(Path(__file__)),
        "claim_boundary": "Exact base geometry and rigorous four-multiset support ceiling for uniformly selected subgroup targets; no ordinary-query PDP run, relation, DLP, rho pair, or speedup",
    }
    save(out / "geometry.json", record)
    print(json.dumps({key: record[key] for key in (
        "status", "normal_element_polynomial_bits", "rational_x_orbits",
        "actual_usable_projected_points_B", "effective_signed_frobenius_columns",
        "uniform_subgroup_support_ceiling_fraction")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    main(parser.parse_args().out)
