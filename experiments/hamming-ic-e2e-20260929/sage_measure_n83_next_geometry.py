#!/usr/bin/env python3
"""Exact N83 W3 + deterministic W4-prefix geometry for the next IC screen."""

from __future__ import annotations

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
CURVE_ID = "EC1N83Ckb1h2bcb59d56ad6"
CHECKPOINTS = (0, 1000, 1600, 2000, 4000)
ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "runs/n83_w3_geometry_v2"
PROTOCOL = ROOT / "n83_next_protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def save(path, value):
    path.write_bytes(json.dumps(value, sort_keys=True, indent=2).encode() + b"\n")


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


def threshold(m):
    lo, hi = 0, 1
    while comb(hi + m - 1, m) < R:
        hi *= 2
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if comb(mid + m - 1, m) >= R:
            hi = mid
        else:
            lo = mid
    assert comb(hi + m - 2, m) < R <= comb(hi + m - 1, m)
    return hi


def ratio(numerator):
    with localcontext() as context:
        context.prec = 45
        return format(Decimal(numerator) / Decimal(R), ".35g")


def screen(points, representatives, w4_orbits, rational, nonrational):
    b = len(points)
    k = len(representatives)
    assert b == 2 * N * k
    counts = {str(m): str(comb(b + m - 1, m)) for m in (4, 5, 6)}
    return {
        "w4_mask_orbits": w4_orbits,
        "w4_rational_orbits": rational,
        "w4_nonrational_orbits": nonrational,
        "actual_usable_projected_points_B": b,
        "effective_signed_frobenius_columns": k,
        "root_index_pair_state_loops_NK2": N * k * k,
        "multisets_with_repetition": counts,
        "multisets_per_subgroup_element": {
            str(m): ratio(int(counts[str(m)])) for m in (4, 5, 6)
        },
        "support_ceiling_fraction": {
            str(m): ratio(min(R, int(counts[str(m)]))) for m in (4, 5, 6)
        },
    }


def main(out):
    out = out.resolve()
    runtime = out / "sage_runtime_info.json"
    if not out.is_dir() or not runtime.is_file():
        raise FileNotFoundError("create output and save checked Sage runtime first")
    if (out / "started.json").exists() or (out / "geometry.json").exists():
        raise FileExistsError("this N83 geometry output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["curve_id"] == CURVE_ID
    assert protocol["checkpoints_w4_mask_orbits"] == list(CHECKPOINTS)
    assert sha(BASELINE / "geometry.json") == protocol["baseline_w3_geometry_sha256"]
    assert sha(BASELINE / "representatives.json") == protocol["baseline_w3_representatives_sha256"]
    baseline = json.loads((BASELINE / "geometry.json").read_text())
    archived = json.loads((BASELINE / "representatives.json").read_text())
    assert baseline["curve_id"] == archived["curve_id"] == CURVE_ID
    assert baseline["status"] == "EXACT_GEOMETRY_PASS"
    start = time.perf_counter_ns()
    save(out / "started.json", {
        "kind": "n83_next_geometry_start", "curve_id": CURVE_ID,
        "candidate_id": None, "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime),
    })

    binary = GF(2)
    ring = PolynomialRing(binary, "u")
    u = ring.gen()
    modulus = u**N + u**7 + u**4 + u**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**N, "z", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert ZZ(R).is_prime(proof=True) and curve.cardinality() == R * H

    def element(code):
        return field(ring([(code >> i) & 1 for i in range(N)]))

    def code(value):
        return sum(int(coefficient) << i
                   for i, coefficient in enumerate(value.polynomial().list()))

    identity = baseline["curve_identity_record"]
    assert CURVE_ID == "EC1N83Ckb1h" + hashlib.sha256(canonical(identity)).hexdigest()[:12]
    gx, gy = identity["curve"]["G"]
    generator = curve(element(gx), element(gy))
    assert generator != curve(0) and R * generator == curve(0)
    alpha = element(baseline["normal_element_polynomial_bits"])
    conjugates = [alpha]
    for _ in range(1, N):
        conjugates.append(conjugates[-1]**2)
    assert conjugates[-1]**2 == alpha
    assert rank_bits([code(value) for value in conjugates]) == N

    def orbit(point):
        x, y = point[0], point[1]
        values = set()
        for _ in range(N):
            x_code, y_code = code(x), code(y)
            values.add((x_code, y_code))
            values.add((x_code, x_code ^ y_code))
            x, y = x**2, y**2
        assert x == point[0] and y == point[1]
        assert len(values) == 2 * N
        return values

    representatives = {tuple(pair) for pair in archived["representatives"]}
    points = set()
    for x_code, y_code in sorted(representatives):
        point = curve(element(x_code), element(y_code))
        assert R * point == curve(0)
        points.update(orbit(point))
    assert len(points) == baseline["actual_usable_projected_points_B"]
    assert hashlib.sha256(canonical(sorted(points))).hexdigest() == baseline["projected_point_set_sha256"]
    checkpoints = [screen(points, representatives, 0, 0, 0)]
    baseline_ns = time.perf_counter_ns() - start

    visited = set()
    w4_orbits = rational = nonrational = duplicate_projected = identity_projected = 0
    for mask in itertools.combinations(range(N), 4):
        if mask in visited:
            continue
        shifts = {tuple(sorted((index + shift) % N for index in mask))
                  for shift in range(N)}
        assert len(shifts) == N
        visited.update(shifts)
        w4_orbits += 1
        x = sum((conjugates[i] for i in mask), field(0))
        assert x != 0
        c = x + x**(-2)
        if c.trace() != 0:
            nonrational += 1
        else:
            rational += 1
            term, half_trace = c, field(0)
            for step in range((N - 1) // 2 + 1):
                if step:
                    term = term**4
                half_trace += term
            assert half_trace**2 + half_trace == c
            raw = curve(x, x * half_trace)
            image = H * raw
            if image == curve(0):
                identity_projected += 1
            else:
                assert R * image == curve(0)
                values = orbit(image)
                representative = min(values)
                if representative in representatives:
                    duplicate_projected += 1
                else:
                    representatives.add(representative)
                    points.update(values)
        if w4_orbits in CHECKPOINTS:
            checkpoints.append(screen(points, representatives, w4_orbits,
                                      rational, nonrational))
            save(out / "progress.json", checkpoints[-1])
        if w4_orbits == CHECKPOINTS[-1]:
            break

    assert w4_orbits == CHECKPOINTS[-1]
    assert len(visited) == N * w4_orbits
    assert rational + nonrational == w4_orbits
    assert [row["w4_mask_orbits"] for row in checkpoints] == list(CHECKPOINTS)
    assert len(points) == 2 * N * len(representatives)
    representatives_record = {
        "kind": "n83_w3_plus_w4_prefix_representatives",
        "curve_id": CURVE_ID,
        "w4_mask_orbits": w4_orbits,
        "representatives": [list(pair) for pair in sorted(representatives)],
    }
    save(out / "representatives.json", representatives_record)
    minimum_b = {str(m): threshold(m) for m in (4, 5, 6)}
    minimum_k = {str(m): (minimum_b[str(m)] + 2 * N - 1) // (2 * N)
                 for m in (4, 5, 6)}
    record = {
        "schema_version": 1, "kind": "n83_next_calculus_geometry_screen",
        "status": "EXACT_GEOMETRY_PASS", "candidate_id": None,
        "curve_id": CURVE_ID, "curve_identity_record": identity,
        "subgroup_order": str(R), "cofactor": H,
        "normal_element_polynomial_bits": code(alpha),
        "baseline_w3_geometry_sha256": sha(BASELINE / "geometry.json"),
        "baseline_w3_representatives_sha256": sha(BASELINE / "representatives.json"),
        "w4_mask_orbit_prefix_count": w4_orbits,
        "w4_rational_orbits": rational,
        "w4_nonrational_orbits": nonrational,
        "w4_identity_projections": identity_projected,
        "w4_duplicate_projected_orbits": duplicate_projected,
        "checkpoints": checkpoints,
        "projected_point_set_sha256": hashlib.sha256(canonical(sorted(points))).hexdigest(),
        "representatives_sha256": sha(out / "representatives.json"),
        "minimum_B_for_multiset_ratio_at_least_one": minimum_b,
        "minimum_folded_columns_if_all_orbits_full": minimum_k,
        "minimum_root_index_pair_state_loops_NK2": {
            str(m): N * minimum_k[str(m)]**2 for m in (4, 5, 6)
        },
        "timing_ms_exploratory": {
            "baseline_reconstruction_and_checks": baseline_ns / 1e6,
            "whole_sage_process_from_main": (time.perf_counter_ns() - start) / 1e6,
        },
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime),
        "claim_boundary": protocol["claim_boundary"],
    }
    save(out / "geometry.json", record)
    print(json.dumps({
        "status": record["status"],
        "checkpoints": [{key: row[key] for key in (
            "w4_mask_orbits", "actual_usable_projected_points_B",
            "effective_signed_frobenius_columns", "root_index_pair_state_loops_NK2",
            "multisets_per_subgroup_element")}
                        for row in checkpoints],
    }, sort_keys=True))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    main(parser.parse_args().out)
