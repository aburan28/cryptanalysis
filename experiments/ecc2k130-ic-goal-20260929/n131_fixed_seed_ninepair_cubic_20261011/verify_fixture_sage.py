#!/usr/bin/env sage -python
"""Independently replay the nine-pair constructed control on the curve."""

import hashlib
import itertools
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
R = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    fixture = json.loads((HERE / "control_fixture.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["source_sha256"]["fixture"] == sha(HERE / "control_fixture.json")
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def coordinate(mask):
        return sum((field(t**(bit+1)) for bit in range(18) if mask >> bit & 1),
                   field.zero())

    def halftrace(value):
        result, power = field.zero(), value
        for _ in range(66):
            result += power
            power = power**4
        assert result**2 + result == value
        return result

    def pair_options(item):
        points = []
        for mask in item["masks"]:
            u = halftrace(coordinate(mask))
            x = 1 + 1/u
            lifts = sorted(curve.lift_x(x, all=True), key=lambda p: encode(p[1]))
            assert len(lifts) == 2
            points.append(lifts)
        outputs = []
        for left, right in itertools.product(*points):
            raw = left + right
            if raw == curve(0) or raw[0] in (0, 1):
                continue
            if encode(1/(raw[0] + 1)) != item["unrotated_pair_output_z"]:
                continue
            rotation = item["rotation"]
            rotated = curve(raw[0]**(1 << rotation), raw[1]**(1 << rotation))
            outputs.append(rotated)
        assert outputs
        return outputs

    selected = fixture["selected"]
    assert len(selected) == 9
    pair_outputs = []
    for item in selected[:8]:
        slot = item["slot"]
        points = []
        for mask in item["masks"]:
            u = halftrace(coordinate(mask))
            x = 1 + 1/u
            points.append(sorted(curve.lift_x(x, all=True),
                                 key=lambda p: encode(p[1])))
        raw = points[0][slot & 1] + points[1][(slot >> 1) & 1]
        rotated = curve(raw[0]**(1 << item["rotation"]),
                        raw[1]**(1 << item["rotation"]))
        pair_outputs.append(rotated)
    running = curve(0)
    for point in pair_outputs:
        running += point
    old_target = json.loads((OLD / "planted_chain_result.json").read_text())["raw_target"]
    assert [encode(running[0]), encode(running[1])] == old_target
    matching = []
    for ninth in pair_options(selected[8]):
        result = running + ninth
        if result != curve(0) and [encode(result[0]), encode(result[1])] == fixture["raw_target"]:
            matching.append(ninth)
    assert matching
    target = running + matching[0]
    assert encode(1/(target[0] + 1)) == fixture["raw_target_z"]
    assert R * (4 * target) == curve(0)
    result = {"status": "PASS_INDEPENDENT_SAGE_NINE_PAIR_GROUP_REPLAY",
              "matching_ninth_signs": len(matching), "raw_target": fixture["raw_target"],
              "projected_target": [encode((4 * target)[0]), encode((4 * target)[1])],
              "source_sha256": {"script": sha(Path(__file__)),
                                "fixture": sha(HERE / "control_fixture.json"),
                                "protocol": sha(HERE / "protocol.json"),
                                "sage_runtime": sha(HERE / "sage_runtime_info.json")}}
    with (HERE / "sage_fixture_result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(result["status"])


if __name__ == "__main__":
    main()
