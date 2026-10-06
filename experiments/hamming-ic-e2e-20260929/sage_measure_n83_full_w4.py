#!/usr/bin/env python3
"""Extend the replayed N83 W4 prefix to every weight-four Frobenius orbit."""

from __future__ import annotations

import hashlib
import itertools
import json
from math import comb
from pathlib import Path
import resource
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

from sage_measure_n83_next_geometry import (
    CURVE_ID, H, N, R, canonical, rank_bits, save, screen, sha,
)


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "n83_full_w4_protocol.json"
PREFIX = HERE / "runs/n83_next_geometry_v1"


def main(out: Path) -> None:
    out = out.resolve()
    runtime = out / "sage_runtime_info.json"
    if not out.is_dir() or not runtime.is_file():
        raise FileNotFoundError("create output and save checked Sage runtime first")
    if (out / "started.json").exists() or (out / "geometry.json").exists():
        raise FileExistsError("this N83 full W4 output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["curve_id"] == CURVE_ID
    assert protocol["expected_w4_mask_orbits"] == comb(N, 4) // N == 22140
    assert sha(PREFIX / "geometry.json") == protocol["input_prefix_geometry_sha256"]
    assert sha(PREFIX / "representatives.json") == protocol["input_prefix_representatives_sha256"]
    prefix = json.loads((PREFIX / "geometry.json").read_text())
    archived = json.loads((PREFIX / "representatives.json").read_text())
    assert prefix["status"] == "EXACT_GEOMETRY_PASS"
    assert prefix["curve_id"] == archived["curve_id"] == CURVE_ID
    assert prefix["w4_mask_orbit_prefix_count"] == 4000
    started = time.perf_counter_ns()
    save(out / "started.json", {
        "kind": "n83_complete_w4_geometry_start", "curve_id": CURVE_ID,
        "candidate_id": None, "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "helper_source_sha256": sha(HERE / "sage_measure_n83_next_geometry.py"),
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

    def element(bits):
        return field(ring([(bits >> i) & 1 for i in range(N)]))

    def code(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    alpha = element(prefix["normal_element_polynomial_bits"])
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
    assert len(points) == prefix["checkpoints"][-1]["actual_usable_projected_points_B"]
    assert hashlib.sha256(canonical(sorted(points))).hexdigest() == prefix["projected_point_set_sha256"]
    checkpoints = [screen(points, representatives, 4000,
                          prefix["w4_rational_orbits"], prefix["w4_nonrational_orbits"])]
    assert checkpoints[0] == prefix["checkpoints"][-1]
    count = rational = nonrational = duplicate = identity_projection = 0
    rational = prefix["w4_rational_orbits"]
    nonrational = prefix["w4_nonrational_orbits"]
    duplicate = prefix["w4_duplicate_projected_orbits"]
    identity_projection = prefix["w4_identity_projections"]
    prefix_check_ns = time.perf_counter_ns() - started

    visited = set()
    for mask in itertools.combinations(range(N), 4):
        if mask in visited:
            continue
        shifts = {tuple(sorted((index + shift) % N for index in mask))
                  for shift in range(N)}
        assert len(shifts) == N
        visited.update(shifts)
        count += 1
        if count <= 4000:
            continue
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
            image = H * curve(x, x * half_trace)
            if image == curve(0):
                identity_projection += 1
            else:
                assert R * image == curve(0)
                values = orbit(image)
                representative = min(values)
                if representative in representatives:
                    duplicate += 1
                else:
                    representatives.add(representative)
                    points.update(values)
        if count in protocol["checkpoints_w4_mask_orbits"]:
            checkpoints.append(screen(points, representatives, count, rational, nonrational))
            save(out / "progress.json", {
                "last_checkpoint": checkpoints[-1],
                "elapsed_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            })

    assert count == protocol["expected_w4_mask_orbits"]
    assert len(visited) == N * count == comb(N, 4)
    assert rational + nonrational == count
    assert [row["w4_mask_orbits"] for row in checkpoints] == protocol["checkpoints_w4_mask_orbits"]
    assert len(points) == 2 * N * len(representatives)
    reps_record = {
        "kind": "n83_w3_plus_all_w4_representatives",
        "curve_id": CURVE_ID,
        "w4_mask_orbits": count,
        "representatives": [list(pair) for pair in sorted(representatives)],
    }
    save(out / "representatives.json", reps_record)
    record = {
        "schema_version": 1, "kind": "n83_complete_w4_geometry_screen",
        "status": "EXACT_GEOMETRY_PASS", "candidate_id": None,
        "curve_id": CURVE_ID, "curve_identity_record": prefix["curve_identity_record"],
        "subgroup_order": str(R), "cofactor": H,
        "normal_element_polynomial_bits": code(alpha),
        "input_prefix_geometry_sha256": sha(PREFIX / "geometry.json"),
        "input_prefix_representatives_sha256": sha(PREFIX / "representatives.json"),
        "w4_mask_orbits": count,
        "w4_rational_orbits": rational,
        "w4_nonrational_orbits": nonrational,
        "w4_identity_projections": identity_projection,
        "w4_duplicate_projected_orbits": duplicate,
        "checkpoints": checkpoints,
        "projected_point_set_sha256": hashlib.sha256(canonical(sorted(points))).hexdigest(),
        "representatives_sha256": sha(out / "representatives.json"),
        "timing_ms_exploratory": {
            "prefix_reconstruction_and_checks": prefix_check_ns / 1e6,
            "whole_sage_process_from_main": (time.perf_counter_ns() - started) / 1e6,
        },
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "helper_source_sha256": sha(HERE / "sage_measure_n83_next_geometry.py"),
        "sage_runtime_info_sha256": sha(runtime),
        "claim_boundary": protocol["claim_boundary"],
    }
    save(out / "geometry.json", record)
    print(json.dumps({"status": record["status"], "final_checkpoint": checkpoints[-1]}, sort_keys=True))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    main(parser.parse_args().out)
