#!/usr/bin/env python3
"""Independently replay the cofactor-four sparse-x identity in Sage."""

from __future__ import annotations

import json
import resource
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

from run_probe import HERE, sha


N = 131
MINPOLY_BITS = 0xd1d0d000d0000000d000000000000000d


def main():
    output = HERE / "runs/n131_projected_sparse_sage_replay.json"
    assert not output.exists()
    screen_path = HERE / "runs/n131_projected_sparse_geometry.json"
    protocol_path = HERE / "protocol.json"
    runtime_path = HERE / "projected_sparse_sage_runtime_info.json"
    screen = json.loads(screen_path.read_text())
    protocol = json.loads(protocol_path.read_text())
    assert screen["proposal_id"] == "Q1318"
    assert screen["protocol_sha256"] == sha(protocol_path)
    assert screen["group_control_count"] == 40
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    started = time.perf_counter()

    poly_ring = PolynomialRing(GF(2), "t")
    t = poly_ring.gen()
    modulus = sum(((MINPOLY_BITS >> i) & 1) * t**i
                  for i in range(N + 1))
    assert modulus.degree() == N and modulus.is_irreducible()
    field = GF(2**N, name="c", modulus=modulus)
    c = field.gen()
    gammas = [field(0), c]
    for i in range(1, N):
        gammas.append(c * gammas[i] + gammas[i - 1])
    assert len(gammas) == N + 1
    assert sum(gammas[1:], field(0)) == field(1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    order = int(protocol["degree_131_design"]["curve"]["subgroup_order"])

    checked = 0
    for mask in screen["group_control_raw_x_masks"]:
        assert 2 <= mask.bit_count() <= 6
        x = field(0)
        remaining = mask
        while remaining:
            bit = remaining & -remaining
            x += gammas[bit.bit_length()]
            remaining ^= bit
        assert x and curve.is_x_coord(x)
        assert int((x + x**(-1)).trace()) == 0
        lifts = curve.lift_x(x, all=True)
        assert len(lifts) == 2
        first, second = [4 * point for point in lifts]
        assert first != curve(0) and second == -first
        assert order * first == curve(0)
        assert first[0] * (x**12 + x**4) == x**16 + x**8 + 1
        checked += 1
    assert checked == 40

    receipt = {
        "kind": "independent_sage_n131_projected_sparse_formula_replay",
        "proposal_id": "Q1318", "candidate_id": None,
        "workload_id": None, "run_id": None,
        "curve_id": screen["curve_id"], "isogeny": "none",
        "n": N, "sage_field_minpoly_hex": hex(MINPOLY_BITS),
        "sage_field_minpoly_irreducible": True,
        "control_masks_checked": checked,
        "both_lifts_projected_and_subgroup_checked": checked,
        "status": "PASS",
        "wall_seconds": time.perf_counter() - started,
        "peak_parent_rss_raw": resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss,
        "peak_parent_rss_units": "bytes on Darwin, KiB on Linux",
        "screen_receipt_sha256": sha(screen_path),
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime_path),
        "source_sha256": sha(Path(__file__)),
        "complete_solve_work_log2": None,
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "control_masks": checked,
                      "seconds": receipt["wall_seconds"]}))


if __name__ == "__main__":
    main()
