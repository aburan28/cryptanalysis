#!/usr/bin/env sage -python
"""Independent Sage replay for a public SAT relation, when available."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
OUT = Path("/private/tmp/n131_w15_unrestricted_sixpair_gate_20261010")
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
ROTATIONS = [0, 0, 13, 13, 26, 26, 39, 39, 52, 52, 65, 65]
ORDER = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((OUT / "result.json").read_text())
    group = json.loads((OUT / "group_lift.json").read_text())
    assert result["status"] == "GROUP_RELATION_PENDING_INDEPENDENT_SAGE"
    assert group["status"] == "GROUP_LIFT_FOUND" and group["solutions"]
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    generator = field.gen()

    def decode(value):
        return sum((generator**bit for bit in range(131) if value >> bit & 1),
                   field.zero())

    def point(values):
        return curve(decode(values[0]), decode(values[1]))

    columns = dict(tuple(map(int, row.split()))
                   for row in SUPPORT.read_text().splitlines())
    target = point(protocol["target_q"])
    assert ORDER*target == curve(0)
    checked = []
    for solution in group["solutions"]:
        masks = solution["masks"]
        leaves = [point(values) for values in solution["raw_leaves"]]
        folded = [columns[mask] for mask in masks]
        assert len(masks) == len(leaves) == len(folded) == 12
        assert len(set(folded)) == 12
        assert folded == solution["folded_columns"]
        for leaf, mask, rotation in zip(leaves, masks, ROTATIONS):
            w = decode(mask << 1)
            x = 1/w
            for _ in range(rotation):
                x = x**2
            assert leaf[0] == x
            assert leaf in curve.lift_x(x, all=True)
            assert ORDER*(4*leaf) == curve(0)
        raw_sum = sum(leaves, curve(0))
        assert raw_sum == point(solution["raw_sum"])
        branch = solution["target_preimage_index"]
        assert raw_sum == point(result["raw_target_preimages"][branch])
        assert 4*raw_sum == target == point(solution["projected_sum"])
        checked.append({"branch": branch, "masks": masks,
                        "folded_columns": folded,
                        "raw_sum": solution["raw_sum"]})
    receipt = {"status": "PASS_INDEPENDENT_SAGE_PUBLIC_SIXPAIR_RELATION",
               "curve_id": protocol["curve_id"],
               "target_q": protocol["target_q"],
               "solutions_checked": len(checked), "relations": checked,
               "sha256": {"script": sha(Path(__file__)),
                          "protocol": sha(HERE / "protocol.json"),
                          "result": sha(OUT / "result.json"),
                          "group_lift": sha(OUT / "group_lift.json"),
                          "support": sha(SUPPORT)}}
    with (OUT / "independent_sage_relation.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "solutions_checked": receipt["solutions_checked"]}))


if __name__ == "__main__":
    main()
