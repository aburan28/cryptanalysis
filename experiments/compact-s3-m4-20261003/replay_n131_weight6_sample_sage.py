#!/usr/bin/env python3
"""Independent Sage field and curve replay of Q1303 sparse-x sampling."""

from __future__ import annotations

import itertools
import json
import resource
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

from run_probe import HERE, sha


N = 131
MINPOLY_BITS = 0xd1d0d000d0000000d000000000000000d


def main():
    output = HERE / "runs/n131_weight6_sage_independent_replay.json"
    assert not output.exists()
    protocol_path = HERE / "protocol.json"
    sample_path = HERE / "runs/n131_weight6_stratified_sample.json"
    runtime_path = HERE / "n131_sample_sage_runtime_info.json"
    protocol = json.loads(protocol_path.read_text())
    sample = json.loads(sample_path.read_text())
    design = protocol["degree_131_design"]
    assert sample["protocol_sha256"] == sha(protocol_path)
    assert sample["curve_id"] == design["curve"]["curve_id"]
    assert sample["source_sha256"] == sha(HERE / "estimate_n131_weight6_base.py")
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
    for i in range(1, N + 1):
        twice = 2 * i % (2 * N + 1)
        folded = min(twice, 2 * N + 1 - twice)
        assert gammas[i]**2 == gammas[folded]
        assert int(gammas[i].trace()) == 1
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    subgroup_order = design["curve"]["subgroup_order"]

    def x_for_mask(mask):
        value = field(0)
        while mask:
            bit = mask & -mask
            value += gammas[bit.bit_length()]
            mask ^= bit
        return value

    control_checks = 0
    subgroup_checks = 0
    weight_two_control_projections = set()
    for stratum in sample["strata"]:
        for control in stratum["independent_replay_control_masks"]:
            mask = control["normal_x_mask"]
            x = x_for_mask(mask)
            rational = bool(curve.is_x_coord(x))
            assert rational == control["rational"]
            assert rational == (int((x + x**(-2)).trace()) == 0)
            if stratum["weight"] == 2 and rational:
                lifts = curve.lift_x(x, all=True)
                assert len(lifts) == 2
                for point in lifts:
                    projected = 4 * point
                    assert projected != curve(0)
                    weight_two_control_projections.add(projected)
            if rational and subgroup_checks < 12:
                point = curve.lift_x(x)
                projected = 4 * point
                assert projected != curve(0)
                assert subgroup_order * projected == curve(0)
                subgroup_checks += 1
            control_checks += 1
    assert len(weight_two_control_projections) == 16

    exact_counts = {}
    for weight in (1, 2):
        rational_x = 0
        for positions in itertools.combinations(range(N), weight):
            mask = sum(1 << i for i in positions)
            x = x_for_mask(mask)
            rational_x += int(int((x + x**(-1)).trace()) == 0)
        expected = next(row for row in sample["strata"]
                        if row["weight"] == weight)
        assert rational_x == expected["rational_x_count_in_sample"]
        exact_counts[str(weight)] = rational_x
    receipt = {
        "kind": "independent_sage_n131_weight6_sample_replay",
        "proposal_id": "Q1303", "candidate_id": None,
        "run_id": None, "workload_id": None,
        "curve_id": design["curve"]["curve_id"],
        "isogeny": "none", "n": N,
        "sage_field_minpoly_hex": hex(MINPOLY_BITS),
        "sage_field_minpoly_irreducible": True,
        "normal_basis_gamma_squaring_checks": N,
        "sample_control_masks_checked": control_checks,
        "sample_control_subgroup_checks": subgroup_checks,
        "exact_rational_x_counts_weights_one_two": exact_counts,
        "distinct_weight_two_control_projected_points": (
            len(weight_two_control_projections)),
        "producer_exact_weight_at_most_two_projected_B": sample[
            "exact_weight_at_most_two_projected_B"],
        "producer_w2_projected_B_exhaustively_replayed": False,
        "status": "PASS",
        "wall_seconds": time.perf_counter() - started,
        "peak_parent_rss_raw": resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss,
        "peak_parent_rss_units": "bytes on Darwin, KiB on Linux",
        "protocol_sha256": sha(protocol_path),
        "sample_receipt_sha256": sha(sample_path),
        "runtime_info_sha256": sha(runtime_path),
        "source_sha256": sha(Path(__file__)),
        "complete_solve_work_log2": None,
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "control_masks": control_checks,
                      "exact_w2_rational_x": exact_counts["2"],
                      "distinct_w2_control_projected_points": len(
                          weight_two_control_projections),
                      "seconds": receipt["wall_seconds"]}))


if __name__ == "__main__":
    main()
