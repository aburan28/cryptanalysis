#!/usr/bin/env sage -python
"""Compute all four raw preimages of one frozen public N131 subgroup point."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parent / "n131_fresh_sparse_target_20260930" / "public_target.json"
R = 680564733841876926932320129493409985129


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "target_preimage_protocol.json").read_text())
    paths = {"script": Path(__file__), "public": PUBLIC,
             "runtime": HERE / "sage_runtime_info.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    public = json.loads(PUBLIC.read_text())
    assert public["target_count"] == 1 and public["subgroup_order"] == R
    assert public["field_modulus"] == "t^131+t^13+t^2+t+1"
    base = PolynomialRing(GF(2), "t")
    t = base.gen()
    field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(base([(int(value) >> i) & 1 for i in range(131)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def point(pair):
        return curve(decode(pair[0]), decode(pair[1]))

    q = point(public["target_q"])
    assert R*q == curve(0)
    start = time.monotonic_ns()
    base_preimage = pow(4, -1, R) * q
    torsion = [curve(0), curve(field(0), field(1)),
               curve(field(1), field(0)), curve(field(1), field(1))]
    assert len(set(torsion)) == 4
    assert all(4*point == curve(0) for point in torsion)
    preimages = []
    for index, offset in enumerate(torsion):
        raw = base_preimage + offset
        assert 4*raw == q and raw != curve(0) and raw[0] != 1
        z = 1/(raw[0]+1)
        preimages.append({"index": index, "point": [encode(raw[0]), encode(raw[1])],
                          "reciprocal_x_z": encode(z),
                          "torsion_offset": None if offset == curve(0) else
                              [encode(offset[0]), encode(offset[1])]})
    elapsed_ns = time.monotonic_ns() - start
    result = {"status": "PASS_FOUR_RAW_PREIMAGES_OF_FRESH_N131_POINT",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "prior_curve_id_alias": public["curve_id"],
              "workload_id": public["workload_id"], "public_target": public["target_q"],
              "preimages": preimages, "target_dependent_preimage_ns": elapsed_ns,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(HERE / "target_preimage_protocol.json")}
    with (HERE / "target_preimages.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "preimages": len(preimages),
                      "target_dependent_preimage_ns": elapsed_ns}))


if __name__ == "__main__":
    main()
