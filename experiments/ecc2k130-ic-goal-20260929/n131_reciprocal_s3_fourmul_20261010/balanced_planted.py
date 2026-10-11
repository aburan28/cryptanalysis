#!/usr/bin/env sage -python
"""Replay the frozen 16-point row through a balanced reciprocal S3 tree."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
ROTATIONS = [0, 16, 32, 48, 64, 80, 96, 112]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "balanced_planted_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "derive": BASE / "derive_result.json",
             "chain_control": BASE / "planted_chain_result.json",
             "runtime": HERE / "sage_runtime_info.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    source = json.loads(paths["derive"].read_text())
    chain = json.loads(paths["chain_control"].read_text())
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
        assert acc**2 + acc == value
        return acc

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def reciprocal(point):
        assert point != curve(0) and point[0] != 1
        return 1/(point[0]+1)

    pair_outputs = []
    for item in source["selected"]:
        slot = item["slot"]
        point_options = []
        for mask in item["masks"]:
            u = half_trace(coordinate(mask))
            x = 1 + 1/u
            point_options.append(sorted(curve.lift_x(x, all=True),
                                        key=lambda point: encode(point[1])))
        raw = point_options[0][slot & 1] + point_options[1][(slot >> 1) & 1]
        assert encode(reciprocal(raw)) == item["unrotated_pair_output_z"]
        rotation = ROTATIONS[slot]
        pair_outputs.append(curve(raw[0]**(1 << rotation),
                                  raw[1]**(1 << rotation)))
    level1 = [pair_outputs[i] + pair_outputs[i+1] for i in (0, 2, 4, 6)]
    level2 = [level1[0] + level1[1], level1[2] + level1[3]]
    root = level2[0] + level2[1]
    assert [encode(root[0]), encode(root[1])] == chain["raw_target"]
    intermediate = [encode(reciprocal(point)) for point in level1+level2]
    assert len(intermediate) == 6
    result = {"status": "PASS_SAGE_BALANCED_EIGHT_PAIR_CHAIN",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "pair_rotated_z": [encode(reciprocal(point)) for point in pair_outputs],
              "balanced_intermediate_z": intermediate,
              "raw_target_z": encode(reciprocal(root)),
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "balanced_planted_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "intermediate_count": len(intermediate)}))


if __name__ == "__main__":
    main()
