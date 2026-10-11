#!/usr/bin/env sage -python
"""Compute the four raw lifts of the audited eight-pair constructed target."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_fixed_seed_eight_pair_circuit_20261010"
R = 680564733841876926932320129493409985129


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "planted_preimages_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "planted": BASE / "planted_chain_result.json",
             "runtime": HERE / "sage_runtime_info.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    planted = json.loads(paths["planted"].read_text())
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(ring([(int(value) >> bit) & 1 for bit in range(131)]))

    def encode(value):
        return sum(int(bit) << index for index, bit in
                   enumerate(value.polynomial().list()))

    def point(pair):
        return curve(decode(pair[0]), decode(pair[1]))

    raw = point(planted["raw_target"])
    public = point(planted["projected_target"])
    assert 4*raw == public and R*public == curve(0)
    torsion = [curve(0), curve(field(0), field(1)),
               curve(field(1), field(0)), curve(field(1), field(1))]
    assert len(set(torsion)) == 4
    assert all(4*offset == curve(0) for offset in torsion)
    preimages = []
    for index, offset in enumerate(torsion):
        current = raw+offset
        assert 4*current == public and current != curve(0) and current[0] != 1
        preimages.append({"index": index,
                          "point": [encode(current[0]), encode(current[1])],
                          "reciprocal_x_z": encode(1/(current[0]+1))})
    z = [entry["reciprocal_x_z"] for entry in preimages]
    assert z[0] == planted["raw_target_z"]
    assert z[1] == z[0] ^ 1 and z[3] == z[2] ^ 1
    assert len(set(z)) == 4
    result = {"status": "PASS_CONSTRUCTED_FOUR_PREIMAGES",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "public_target": planted["projected_target"],
              "preimages": preimages,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "planted_preimages_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "target_z": z}))


if __name__ == "__main__":
    main()
