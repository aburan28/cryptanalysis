#!/usr/bin/env python3
"""Independent Sage group-law replay of Q1413's x-only [4] projection."""

from __future__ import annotations

import json
import random
import resource
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

from enumerate_q1413_projected_x import projected_x
from run_probe import HERE, field, sha

N = 131
MINPOLY_BITS = 0xd1d0d000d0000000d000000000000000d
SEED = 1413


def main():
    output = HERE / "runs/n131_q1413_sage_projection_replay.json"
    assert not output.exists()
    protocol_path = HERE / "q1413_projected_x_protocol.json"
    parent_path = HERE / "protocol.json"
    runtime_path = HERE / "q1413_sage_runtime_info.json"
    protocol = json.loads(protocol_path.read_text())
    parent = json.loads(parent_path.read_text())["degree_131_design"]
    assert protocol["proposal_id"] == "Q1413"
    assert protocol["instances"]["131"]["curve_id"] == parent[
        "curve"]["curve_id"]
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    started = time.perf_counter()
    poly_ring = PolynomialRing(GF(2), "t")
    t = poly_ring.gen()
    modulus = sum(((MINPOLY_BITS >> i) & 1) * t**i
                  for i in range(N + 1))
    assert modulus.degree() == N and modulus.is_irreducible()
    sage_field = GF(2**N, name="c", modulus=modulus)
    c = sage_field.gen()
    gammas = [sage_field(0), c]
    for _ in range(1, N):
        gammas.append(c * gammas[-1] + gammas[-2])
    assert sum(gammas[1:], sage_field(0)) == sage_field(1)
    sage_curve = EllipticCurve(sage_field, [1, 0, 0, 0, 1])
    onb = field.Onb(N)
    r = parent["curve"]["subgroup_order"]

    def sage_from_mask(mask):
        value = sage_field(0)
        while mask:
            bit = mask & -mask
            value += gammas[bit.bit_length()]
            mask ^= bit
        return value

    rng = random.Random(SEED)
    rows = []
    subgroup_checks = 0
    for weight in range(2, 7):
        masks = set()
        while len(masks) < 16:
            masks.add(sum(1 << bit for bit in rng.sample(range(N), weight)))
        rational_count = identity_count = 0
        for mask in sorted(masks):
            sx = sage_from_mask(mask)
            rational = bool(sage_curve.is_x_coord(sx))
            predicted_rational, predicted_x = projected_x(
                onb, onb.fromCoords(mask))
            assert rational == predicted_rational
            if not rational:
                assert predicted_x is None
                continue
            rational_count += 1
            lifts = sage_curve.lift_x(sx, all=True)
            assert len(lifts) == 2
            projected = [4 * point for point in lifts]
            assert projected[0] == -projected[1]
            if projected[0] == sage_curve(0):
                assert predicted_x is None
                identity_count += 1
                continue
            assert predicted_x is not None
            converted = sage_from_mask(onb.toCoords(predicted_x))
            assert all(point[0] == converted for point in projected)
            assert sage_from_mask(onb.toCoords(onb.sqr(predicted_x))) == (
                converted**2)
            if subgroup_checks < 16:
                assert r * projected[0] == sage_curve(0)
                subgroup_checks += 1
        rows.append({"weight": weight, "sampled_supports": len(masks),
                     "rational_supports": rational_count,
                     "identity_projections": identity_count})
    receipt = {
        "kind": "q1413_independent_sage_projection_replay",
        "proposal_id": "Q1413", "parent_base_proposal_id": "Q1303",
        "candidate_id": None, "run_id": None, "workload_id": None,
        "curve_id": parent["curve"]["curve_id"],
        "isogeny": "none", "status": "PASS",
        "sample_seed": SEED, "rows": rows,
        "independent_subgroup_checks": subgroup_checks,
        "sage_field_minpoly_hex": hex(MINPOLY_BITS),
        "wall_seconds": time.perf_counter() - started,
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "q1413_protocol_sha256": sha(protocol_path),
        "parent_protocol_sha256": sha(parent_path),
        "runtime_info_sha256": sha(runtime_path),
        "producer_source_sha256": sha(HERE / "enumerate_q1413_projected_x.py"),
        "source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "sampled_supports": sum(
        row["sampled_supports"] for row in rows),
        "subgroup_checks": subgroup_checks,
        "seconds": receipt["wall_seconds"]}))


if __name__ == "__main__":
    main()
