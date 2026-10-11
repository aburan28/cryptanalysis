#!/usr/bin/env python3
"""Measure exact N83 Frobenius-shifted subspace base geometry."""

from __future__ import annotations

import argparse
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import resource
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent / "hamming-ic-e2e-20260929"
PUBLIC = EXPERIMENTS / "runs/n83_w34_sat_fixture_v1/public_input.json"
BASELINE = EXPERIMENTS / "runs/n83_full_w4_geometry_v1/geometry.json"
PROTOCOL = HERE / "protocol.json"
N = 83
MASK_N = (1 << N) - 1


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def rank_bits(columns: list[int]) -> int:
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


def rotate(mask: int, shift: int) -> int:
    return ((mask << shift) | (mask >> (N - shift))) & MASK_N


def mask_orbit_key(mask: int) -> int:
    return min(rotate(mask, shift) for shift in range(N))


def ratio(numerator: int, denominator: int) -> str:
    with localcontext() as context:
        context.prec = 50
        return format(Decimal(numerator) / Decimal(denominator), ".40g")


def main(label: str, out: Path, protocol_path: Path = PROTOCOL) -> None:
    out = out.resolve()
    protocol_path = protocol_path.resolve()
    runtime = out / "sage_runtime_info.json"
    if not out.is_dir() or not runtime.is_file():
        raise FileNotFoundError("create output and save checked Sage runtime first")
    if (out / "started.json").exists() or (out / "geometry.json").exists():
        raise FileExistsError("geometry output is immutable")
    protocol = json.loads(protocol_path.read_text())
    public = json.loads(PUBLIC.read_text())
    baseline = json.loads(BASELINE.read_text())
    options = {option["label"]: option for option in protocol["options"]}
    if label not in options:
        raise ValueError("unknown frozen option")
    option = options[label]
    m, d = option["arity"], option["dimension"]
    assert sha(PUBLIC) == protocol["public_field_fixture_sha256"]
    assert sha(BASELINE) == protocol["baseline_full_w4_geometry_sha256"]
    assert public["curve_id"] == baseline["curve_id"] == protocol["curve_id"]
    assert public["field_degree"] == protocol["field_degree"] == N
    assert public["field_polynomial_low_terms"] == protocol["field_polynomial_low_terms"]
    r = int(protocol["subgroup_order_decimal"])
    h = protocol["cofactor"]
    assert r == int(public["subgroup_order_decimal"]) and h == public["cofactor"]
    started_ns = time.perf_counter_ns()
    save(out / "started.json", {
        "kind": "n83_shifted_subspace_geometry_start",
        "label": label, "candidate_id": None, "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(protocol_path), "source_sha256": sha(Path(__file__)),
        "public_input_sha256": sha(PUBLIC), "sage_runtime_info_sha256": sha(runtime),
    })

    result = {
        "schema_version": 1, "kind": "n83_shifted_subspace_geometry",
        "status": "INCOMPLETE", "label": label, "candidate_id": None,
        "curve_id": protocol["curve_id"], "arity": m, "dimension": d,
        "protocol_sha256": sha(protocol_path), "source_sha256": sha(Path(__file__)),
        "public_input_sha256": sha(PUBLIC),
        "sage_runtime_info_sha256": sha(runtime),
        "claim_boundary": protocol["claim_boundary"],
    }
    try:
        binary = GF(2)
        ring = PolynomialRing(binary, "u")
        u = ring.gen()
        modulus = u**N + u**7 + u**4 + u**2 + 1
        assert modulus.is_irreducible()
        field = GF(2**N, "z", modulus=modulus)
        curve = EllipticCurve(field, [1, 0, 0, 0, 1])
        assert ZZ(r).is_prime(proof=True) and curve.cardinality() == h * r

        def element(code: int):
            return field(ring([(code >> bit) & 1 for bit in range(N)]))

        def code(value) -> int:
            return sum(int(coefficient) << bit for bit, coefficient in
                       enumerate(value.polynomial().list()))

        gx, gy = baseline["curve_identity_record"]["curve"]["G"]
        generator = curve(element(gx), element(gy))
        assert generator != curve(0) and r * generator == curve(0)
        alpha = element(int(public["normal_element_polynomial_bits_decimal"]))
        conjugates = [alpha]
        for _ in range(1, N):
            conjugates.append(conjugates[-1]**2)
        assert conjugates[-1]**2 == alpha
        assert rank_bits([code(value) for value in conjugates]) == N
        assert [str(code(value)) for value in conjugates] == \
            public["normal_conjugates_polynomial_bits_decimal"]

        slots = [[(m * j + i) % N for j in range(d)] for i in range(m)]
        assert all(len(set(slot)) == d for slot in slots)
        assert all(slots[i] == [(index + i) % N for index in slots[0]]
                   for i in range(m))
        occupied = set().union(*(set(slot) for slot in slots))
        result["slot_normal_basis_indices"] = slots
        result["distinct_slot_basis_indices"] = len(occupied)
        result["overlap_count_with_multiplicity"] = m * d - len(occupied)
        result["setup_wall_ms_exploratory"] = (time.perf_counter_ns() - started_ns) / 1e6

        # Gray-code traversal changes exactly one normal-basis coordinate.
        base_vectors = [conjugates[index] for index in slots[0]]
        previous_gray = 0
        x = field(0)
        points: set[tuple[int, int]] = set()
        orbit_seeds = {}
        rational_x = projected_identity_x = 0
        enumeration_start = time.perf_counter_ns()
        for cursor in range(1, 1 << d):
            gray = cursor ^ (cursor >> 1)
            changed = gray ^ previous_gray
            bit = changed.bit_length() - 1
            assert changed == 1 << bit
            x += base_vectors[bit]
            previous_gray = gray
            assert x != 0
            c = x + x**(-2)
            if c.trace() == 0:
                rational_x += 1
                term, half_trace = c, field(0)
                for step in range((N - 1) // 2 + 1):
                    if step:
                        term = term**4
                    half_trace += term
                assert half_trace**2 + half_trace == c
                raw = curve(x, x * half_trace)
                projected = h * raw
                if projected == curve(0):
                    projected_identity_x += 1
                else:
                    if rational_x % 2048 == 0:
                        assert r * projected == curve(0)
                    p = (code(projected[0]), code(projected[1]))
                    points.add(p)
                    points.add((p[0], p[0] ^ p[1]))
                    full_mask = sum(1 << slots[0][j] for j in range(d)
                                    if gray & (1 << j))
                    orbit_seeds.setdefault(mask_orbit_key(full_mask), projected)
            if cursor % 4096 == 0 or cursor == (1 << d) - 1:
                elapsed = (time.perf_counter_ns() - started_ns) / 1e9
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                save(out / "progress.json", {
                    "label": label, "processed_nonzero_x": cursor,
                    "rational_x": rational_x,
                    "usable_projected_points_so_far": len(points),
                    "wall_seconds_exploratory": elapsed,
                    "peak_rss_bytes_on_macos": peak,
                })
                if elapsed > protocol["resource_limit_seconds_per_base"]:
                    raise TimeoutError("frozen base wall limit exceeded")
                if peak > protocol["resource_limit_peak_rss_bytes_per_base"]:
                    raise MemoryError("frozen base RSS limit exceeded")

        result["enumeration_wall_ms_exploratory"] = \
            (time.perf_counter_ns() - enumeration_start) / 1e6
        assert previous_gray == (1 << (d - 1))
        signed_reps = {min(p, (p[0], p[0] ^ p[1])) for p in points}
        assert len(points) == 2 * len(signed_reps)
        orbit_start = time.perf_counter_ns()
        orbit_reps = set()
        orbit_sizes = {}
        for orbit_cursor, seed in enumerate(orbit_seeds.values(), 1):
            xx, yy = seed[0], seed[1]
            values = set()
            for _ in range(N):
                pair = (code(xx), code(yy))
                values.add(pair)
                values.add((pair[0], pair[0] ^ pair[1]))
                xx, yy = xx**2, yy**2
            assert xx == seed[0] and yy == seed[1]
            size = len(values)
            orbit_sizes[size] = orbit_sizes.get(size, 0) + 1
            orbit_reps.add(min(values))
            if orbit_cursor % 256 == 0:
                elapsed = (time.perf_counter_ns() - started_ns) / 1e9
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                save(out / "progress.json", {
                    "label": label, "processed_nonzero_x": (1 << d) - 1,
                    "rational_x": rational_x,
                    "usable_projected_points_so_far": len(points),
                    "processed_frobenius_orbit_seeds": orbit_cursor,
                    "wall_seconds_exploratory": elapsed,
                    "peak_rss_bytes_on_macos": peak,
                })
                if elapsed > protocol["resource_limit_seconds_per_base"]:
                    raise TimeoutError("frozen base wall limit exceeded during orbit fold")
                if peak > protocol["resource_limit_peak_rss_bytes_per_base"]:
                    raise MemoryError("frozen base RSS limit exceeded during orbit fold")
        result["orbit_fold_wall_ms_exploratory"] = \
            (time.perf_counter_ns() - orbit_start) / 1e6
        assert orbit_sizes == {2 * N: len(orbit_seeds)}
        assert len(orbit_reps) <= len(signed_reps)
        b = len(points)
        ordered = b**m
        save(out / "representatives.json", {
            "kind": "n83_shifted_subspace_signed_frobenius_representatives",
            "label": label, "curve_id": protocol["curve_id"],
            "representatives": [list(pair) for pair in sorted(orbit_reps)],
        })
        result.update({
            "status": "EXACT_GEOMETRY_PASS",
            "nonzero_x_candidates": (1 << d) - 1,
            "rational_nonzero_x": rational_x,
            "nonrational_nonzero_x": (1 << d) - 1 - rational_x,
            "projected_identity_x": projected_identity_x,
            "actual_usable_projected_points_B_per_slot": b,
            "signed_columns_before_frobenius": len(signed_reps),
            "effective_signed_frobenius_columns_K": len(orbit_reps),
            "local_projected_point_set_sha256": hashlib.sha256(
                canonical(sorted(points))).hexdigest(),
            "representatives_sha256": sha(out / "representatives.json"),
            "distinct_rational_normal_mask_orbits": len(orbit_seeds),
            "signed_frobenius_orbit_size_counts": {
                str(size): count for size, count in orbit_sizes.items()},
            "ordered_slot_tuples": str(ordered),
            "ordered_tuples_per_subgroup_element": ratio(ordered, r),
            "support_ceiling_fraction": ratio(min(ordered, r), r),
            "subgroup_order": str(r), "cofactor": h,
            "whole_process_from_main_wall_ms_exploratory":
                (time.perf_counter_ns() - started_ns) / 1e6,
            "peak_rss_bytes_on_macos":
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        })
    except (TimeoutError, MemoryError) as error:
        result["status"] = "BUDGET"
        result["reason"] = str(error)
        result["whole_process_from_main_wall_ms_exploratory"] = \
            (time.perf_counter_ns() - started_ns) / 1e6
        result["peak_rss_bytes_on_macos"] = \
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception as error:
        result["status"] = "ERROR"
        result["reason"] = f"{type(error).__name__}: {error}"
        save(out / "geometry.json", result)
        raise
    save(out / "geometry.json", result)
    print(json.dumps({key: result.get(key) for key in (
        "label", "status", "actual_usable_projected_points_B_per_slot",
        "effective_signed_frobenius_columns_K",
        "ordered_tuples_per_subgroup_element")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("out", type=Path)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    args = parser.parse_args()
    main(args.label, args.out, args.protocol)
