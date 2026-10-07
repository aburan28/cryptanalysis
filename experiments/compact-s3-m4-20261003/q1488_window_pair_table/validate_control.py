#!/usr/bin/env python3
"""Check Q1488 quotient collision and full N83 window-base sampler."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from build_n53_base import (HERE, PARENT, Q1481, onb_x_from_cycle_mask,
                            read_points, sha)
from sample_window import WindowOrbitSampler, representative

sys.path.insert(0, str(PARENT / "q1445_matched_pair_table"))
from pair_probe import OrbitKey, curves, field, reconstruct  # noqa: E402
sys.path.insert(0, str(Q1481))
from enumerate_base import canonical_rotation, representatives  # noqa: E402
from verify_base import read_keys  # noqa: E402

OUTPUT = HERE / "validation.json"


def validate() -> dict:
    for d in range(2, 11):
        expected = [mask for mask, _ in representatives(d)]
        actual = [representative(i, d) for i in range(1 << (d - 1))]
        assert actual == expected
    onb53 = field.Onb(53)
    curve53 = curves.Curve(onb53)
    orbit53 = OrbitKey(onb53)
    base = read_points()
    chosen, columns = [], set()
    for point in base:
        key = orbit53.canonical(point)[0]
        if key not in columns:
            chosen.append(point)
            columns.add(key)
        if len(chosen) == 4:
            break
    assert len(chosen) == 4
    p0, p1, q0, q1 = chosen
    table_pair = curve53.add(p0, p1)
    key0, exponent0, sign0 = orbit53.canonical(table_pair)
    shifted = [curve53.neg(curve53.frob(point, 7)) for point in (p0, p1)]
    target = curve53.add(curve53.add(*shifted), curve53.add(q0, q1))
    residual = curve53.add(target, curve53.neg(curve53.add(q0, q1)))
    key1, exponent1, sign1 = orbit53.canonical(residual)
    assert key0 == key1
    witness = reconstruct(curve53, orbit53, target,
                          (p0, p1, exponent0, sign0),
                          (q0, q1, exponent1, sign1), 21044858204113)
    assert witness is not None
    assert witness["points"] == [list(p) for p in shifted + [q0, q1]]
    assert witness["frobenius_shift_of_table_pair"] == 7
    assert witness["sign_of_table_pair"] == -1

    onb83 = field.Onb(83)
    curve83 = curves.Curve(onb83)
    orbit83 = OrbitKey(onb83)
    keys = set(read_keys(Q1481 / "n83_d23_projected_keys.bin", 83))
    assert len(keys) == 2096424
    sampler = WindowOrbitSampler(onb83, curve83, orbit83, 4, 23,
                                 random.Random(148883))
    for _ in range(64):
        point = sampler.point()
        cert = sampler.certificate(point)
        mask = cert["raw_cycle_mask"]
        assert mask == representative(cert["raw_orbit_ordinal"], 23)
        raw = curve83.pointFromX(onb_x_from_cycle_mask(
            mask, onb83, orbit83))
        assert raw is not None
        projected = curve83.mul(raw, 4)
        assert projected is not None
        expected = curve83.frob(projected, cert["frobenius_shift"])
        if cert["sign_bit"]:
            expected = curve83.neg(expected)
        assert expected == point
        assert curve83.onCurve(point)
        assert curve83.mul(point, 2417851639230796216685689) is None
        assert canonical_rotation(orbit83.cycle_bits(point[0]), 83) in keys
    return {
        "kind": "q1488_matched_window_base_pair_table_pre_run_control",
        "proposal_id": "Q1488", "candidate_id": None,
        "isogeny": "none", "status": "passed",
        "representative_bijections_checked_d": list(range(2, 11)),
        "n53_complete_materialized_B": len(base),
        "n53_four_column_synthetic_shift_and_sign": [7, -1],
        "n83_full_base_sampler_controls": 64,
        "n83_sampler_counters": sampler.counters(),
        "n53_materialized_base_sha256": sha(HERE / "n53_window_points.bin"),
        "n83_q1481_base_sha256": sha(
            Q1481 / "n83_d23_projected_keys.bin"),
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    current = validate()
    if args.check:
        assert json.loads(OUTPUT.read_text()) == current
    else:
        assert not OUTPUT.exists(), "refuse overwrite"
        OUTPUT.write_text(json.dumps(current, indent=2, sort_keys=True) +
                          "\n")
    print("Q1488 matched pair-table controls: PASS")
