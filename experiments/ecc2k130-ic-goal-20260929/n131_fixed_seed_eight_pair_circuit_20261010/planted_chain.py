#!/usr/bin/env sage -python
"""Replay the eight-pair control and expose intermediate reciprocal outputs."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "planted_chain_protocol.json").read_text())
    paths = {"script": Path(__file__), "derive": HERE / "derive_result.json",
             "runtime": HERE / "sage_runtime_info.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    source = json.loads(paths["derive"].read_text())
    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def coordinate(mask):
        return sum((field(t**(bit+1)) for bit in range(18) if mask >> bit & 1),
                   field.zero())

    def half_trace(value):
        acc, term = field.zero(), value
        for _ in range(66):
            acc += term
            term = term**4
        assert acc**2+acc == value
        return acc

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def reciprocal(point):
        assert point != curve(0) and point[0] != 1
        return 1/(point[0]+1)

    pair_outputs = []
    for item in source["selected"]:
        slot = item["slot"]
        points = []
        for mask in item["masks"]:
            u = half_trace(coordinate(mask))
            x = 1+1/u
            points.append(sorted(curve.lift_x(x, all=True),
                                 key=lambda point: encode(point[1])))
        raw = points[0][slot & 1] + points[1][(slot >> 1) & 1]
        assert encode(reciprocal(raw)) == item["unrotated_pair_output_z"]
        rotation = item["rotation"]
        rotated = curve(raw[0]**(1 << rotation), raw[1]**(1 << rotation))
        pair_outputs.append(rotated)
    running = pair_outputs[0]
    intermediate = []
    for index, point in enumerate(pair_outputs[1:], 1):
        running += point
        if index < 7:
            intermediate.append(encode(reciprocal(running)))
    target = [encode(running[0]), encode(running[1])]
    assert target == source["planted_raw_target"]
    assert len(intermediate) == 6
    result = {"status": "PASS_INDEPENDENT_SAGE_EIGHT_PAIR_CHAIN_FIXTURE",
              "candidate_id": None, "pair_rotated_z": [encode(reciprocal(point))
                                                     for point in pair_outputs],
              "intermediate_z": intermediate,
              "raw_target_z": encode(reciprocal(running)),
              "raw_target": target,
              "projected_target": source["planted_projected_target"],
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(HERE / "planted_chain_protocol.json")}
    with (HERE / "planted_chain_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "intermediate_count": len(intermediate)}))


if __name__ == "__main__":
    main()
