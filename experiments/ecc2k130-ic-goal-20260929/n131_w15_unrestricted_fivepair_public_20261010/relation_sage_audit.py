#!/usr/bin/env sage -python
"""Independently replay any public five-pair model as twelve curve points."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = Path("/Volumes/SSD990/cryptanalysis/experiments/ecc2k130-ic-goal-20260929/n131_w15_coupled_sixpair_20261010")
ROTATIONS = [0, 0, 13, 13, 26, 26, 39, 39, 52, 52, 65, 65]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    inp = json.loads((HERE / "input.json").read_text())
    lift = json.loads((HERE / "group_lift.json").read_text())
    assert runtime["status"] == "verified"
    assert result["status"] == "GROUP_RELATION_PENDING_INDEPENDENT_SAGE"
    assert lift["status"] == "GROUP_LIFT_FOUND" and lift["solutions"]
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    g = field.gen()

    def decode(value):
        return sum((g**bit for bit in range(131) if value >> bit & 1), field.zero())

    def point(values):
        return curve(decode(values[0]), decode(values[1]))

    columns = {int(a): int(b) for a, b in
               (line.split() for line in (BASE / "support_w15.tsv").read_text().splitlines())}
    assert len(columns) == 16441
    r = int(protocol["support"]["subgroup_order"])
    q = point(protocol["target_q"])
    residual = point(protocol["public_residual_target_q"])
    prefix = [point(values) for values in inp["prefix_raw_leaves"]]
    assert 4*(prefix[0]+prefix[1]) + residual == q
    checked = []
    for solution in lift["solutions"]:
        masks = inp["prefix_masks"] + solution["masks"]
        leaves = prefix + [point(values) for values in solution["raw_leaves"]]
        folded = [columns[mask] for mask in masks]
        assert len(masks) == len(leaves) == len(folded) == 12
        assert len(set(folded)) == 12
        assert folded[:2] == inp["prefix_columns"]
        assert folded[2:] == solution["folded_columns"]
        for leaf, mask, rotation in zip(leaves, masks, ROTATIONS):
            assert leaf[0] != 0
            expected = decode(mask << 1)**(2**rotation)
            assert 1/leaf[0] == expected
            assert r*(4*leaf) == curve(0)
        pair_sums = [leaves[2*i]+leaves[2*i+1] for i in range(6)]
        assert all(pair != curve(0) and pair[0] != 0 for pair in pair_sums)
        upper0 = pair_sums[1]+pair_sums[2]
        upper1 = pair_sums[3]+pair_sums[4]
        upper2 = upper0+upper1
        assert all(point_ != curve(0) and point_[0] != 0
                   for point_ in (upper0, upper1, upper2))
        assert upper2+pair_sums[5] == point(solution["raw_sum"])
        assert 4*(upper2+pair_sums[5]) == residual
        assert 4*sum(leaves, curve(0)) == q
        checked.append({"masks": masks, "folded_columns": folded,
                        "prefix_columns": folded[:2],
                        "raw_sum": list(sum(leaves, curve(0))),
                        "projected_sum": protocol["target_q"]})
    receipt = {"status": "PASS_INDEPENDENT_SAGE_PUBLIC_TWELVE_POINT_RELATION",
               "curve_id": protocol["curve_id"], "target_q": protocol["target_q"],
               "verified_solutions": checked,
               "source_sha256": {"script": sha(Path(__file__)),
                                 "protocol": sha(HERE / "protocol.json"),
                                 "result": sha(HERE / "result.json"),
                                 "group_lift": sha(HERE / "group_lift.json"),
                                 "support": sha(BASE / "support_w15.tsv"),
                                 "runtime": sha(HERE / "sage_runtime_info.json")}}
    with (HERE / "relation_sage_audit.json").open("x") as stream:
        json.dump(receipt, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "solutions": len(checked)}))


if __name__ == "__main__":
    main()
