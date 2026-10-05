#!/usr/bin/env python3
"""Pre-run quotient collision, archived witness, and N83 sampler controls."""

from __future__ import annotations

import argparse
import json
import random

from build_n53_base import HERE, read_points, sha
from pair_probe import (FullBaseSampler, OrbitKey, check_known_n53_witness,
                        curves, field, reconstruct)

OUTPUT = HERE / "validation.json"


def validate():
    onb53 = field.Onb(53)
    curve53 = curves.Curve(onb53)
    orbit53 = OrbitKey(onb53)
    base = read_points()
    archived = check_known_n53_witness(curve53, orbit53, base,
                                       21044858204113)
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
    pair = curve53.add(p0, p1)
    key0, exponent0, sign0 = orbit53.canonical(pair)
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
    sampler = FullBaseSampler(onb83, curve83, 4, 6, random.Random(144583))
    for _ in range(64):
        point = sampler.point()
        cert = sampler.certificate(point)
        mask = cert["raw_normal_x_mask"]
        raw = curve83.pointFromX(onb83.fromCoords(mask))
        projected = curve83.mul(raw, 4)
        if cert["sign_bit"]:
            projected = curve83.neg(projected)
        assert projected == point
        assert curve83.onCurve(point)
        assert curve83.mul(point, 2417851639230796216685689) is None
        assert 1 <= mask.bit_count() <= 6
    return {"proposal_id": "Q1445", "status": "pass",
            "archived_n53_witness_status": archived["status"],
            "synthetic_shift_and_sign": [7, -1],
            "n83_full_base_sampler_controls": 64,
            "n83_sampler_counters": sampler.counters(),
            "n53_materialized_base_sha256": sha(HERE / "n53_w4_points.bin")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.check:
        assert json.loads(OUTPUT.read_text()) == result
        print("Q1445 controls: PASS")
    else:
        assert not OUTPUT.exists(), "refuse overwrite"
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps(result, sort_keys=True))
