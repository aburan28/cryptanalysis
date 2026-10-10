#!/usr/bin/env sage -python
"""Replay the selected prefix and both residual target equations in Sage."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    inp = json.loads((HERE / "input.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert inp["status"] == "PASS_TARGET_INDEPENDENT_PREFIX_AND_RESIDUALS"
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    g = field.gen()

    def decode(value):
        return sum((g**bit for bit in range(131) if value >> bit & 1), field.zero())

    def point(values):
        return curve(decode(values[0]), decode(values[1]))

    leaves = [point(values) for values in inp["prefix_raw_leaves"]]
    assert inp["prefix_masks"] == [4, 17]
    assert inp["prefix_columns"] == [4, 17]
    for leaf, mask in zip(leaves, inp["prefix_masks"]):
        assert leaf[0] != 0 and 1/leaf[0] == decode(mask << 1)
    raw = leaves[0]+leaves[1]
    assert raw == point(inp["prefix_raw_sum"])
    projected = 4*raw
    assert projected == point(inp["prefix_projected_sum"])
    r = int(protocol["support"]["subgroup_order"])
    assert r*projected == curve(0)
    public = point(inp["public_target_q"])
    residual = point(inp["public_residual_target_q"])
    assert r*public == r*residual == curve(0)
    assert residual+projected == public
    constructed_residual = point(inp["constructed_residual_target_q"])
    constructed_raw = point(inp["constructed_residual_raw"])
    assert 4*constructed_raw == constructed_residual
    assert constructed_residual+projected == point(inp["constructed_full_target_q"])
    assert protocol["target_q"] == inp["public_target_q"]
    assert protocol["public_residual_target_q"] == inp["public_residual_target_q"]
    receipt = {"status": "PASS_INDEPENDENT_SAGE_PREFIX_AND_RESIDUALS",
               "curve_id": protocol["curve_id"],
               "prefix_masks": inp["prefix_masks"],
               "prefix_columns": inp["prefix_columns"],
               "public_target_q": inp["public_target_q"],
               "public_residual_target_q": inp["public_residual_target_q"],
               "subgroup_order": str(r),
               "source_sha256": {"script": sha(Path(__file__)),
                                 "input": sha(HERE / "input.json"),
                                 "protocol": sha(HERE / "protocol.json"),
                                 "runtime": sha(HERE / "sage_runtime_info.json")}}
    with (HERE / "prefix_sage_audit.json").open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "prefix_masks": inp["prefix_masks"]}))


if __name__ == "__main__":
    main()
