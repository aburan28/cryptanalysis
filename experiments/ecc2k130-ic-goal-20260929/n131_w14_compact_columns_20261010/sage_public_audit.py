#!/usr/bin/env sage -python
"""Independent Sage replay when the compact N131 query yields a group lift."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010"
SUPPORT = HERE.parent / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
R = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "public_query/result.json").read_text())
    lift = json.loads((HERE / "public_query/group_lift.json").read_text())
    control = json.loads((ORIGINAL / "control.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    assert result["status"] == "GROUP_RELATION_PENDING_INDEPENDENT_SAGE"
    assert lift["status"] == "GROUP_LIFT_FOUND" and lift["solutions"]
    assert result["target_q"] == protocol["public_target_q"]
    assert result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["sha256"]["stdout"] == sha(HERE / "public_query/solver.stdout.txt")
    f2 = GF(2)
    ring = PolynomialRing(f2, "t")
    t = ring.gen()
    field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def element(value):
        return field(ring([(int(value) >> bit) & 1 for bit in range(131)]))

    def point(pair):
        return curve(element(pair[0]), element(pair[1]))

    def encoded(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def s3(a, b, c):
        product = a*b*c
        return (a+b+c)**2 + product + product**2 == 0

    q = point(protocol["public_target_q"])
    assert q != curve(0) and R*q == curve(0)
    columns = dict(tuple(map(int, row.split())) for row in SUPPORT.read_text().splitlines())
    assert len(columns) == 8220
    verified = []
    for solution in lift["solutions"]:
        masks = solution["masks"]
        leaves = [point(pair) for pair in solution["raw_leaves"]]
        assert len(masks) == len(leaves) == 12
        assert [columns[mask] for mask in masks] == solution["folded_columns"]
        assert len(set(solution["folded_columns"])) == 12
        assert masks[4]^masks[5] == masks[6]^masks[7]
        assert masks[8]^masks[9] == masks[10]^masks[11]
        for mask, rotation, leaf in zip(masks, control["rotations"], leaves):
            w = sum((field.gen()**(i+1) for i in range(14) if mask >> i & 1),
                    field.zero())
            assert leaf != curve(0) and leaf[0] != 0
            assert 1/leaf[0] == w**(2**rotation)
            assert R*(4*leaf) == curve(0)
        middle = [leaves[2*i]+leaves[2*i+1] for i in range(6)]
        middle.extend((middle[0]+middle[1],middle[2]+middle[3],middle[4]+middle[5]))
        middle.append(middle[6]+middle[7])
        raw = middle[9]+middle[8]
        assert all(p != curve(0) and p[0] != 0 for p in [*middle,raw])
        assert [encoded(raw[0]),encoded(raw[1])] == solution["raw_sum"]
        assert 4*raw == q
        for i in range(6):
            assert s3(1/leaves[2*i][0], 1/leaves[2*i+1][0], 1/middle[i][0])
        for a,b,c in ((0,1,6),(2,3,7),(4,5,8),(6,7,9),(9,8,None)):
            assert s3(1/middle[a][0], 1/middle[b][0],
                      1/(raw if c is None else middle[c])[0])
        verified.append({"masks": masks, "folded_columns": solution["folded_columns"],
                         "shared_seed_sums": [masks[4]^masks[5],masks[8]^masks[9]]})
    receipt = {
        "status": "PASS_INDEPENDENT_SAGE_N131_PUBLIC_GROUP_DECOMPOSITION",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "target_q": protocol["public_target_q"],
        "verified_solutions": verified, "verified_relation_count": len(verified),
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "protocol": HERE / "protocol.json",
            "result": HERE / "public_query/result.json",
            "group_lift": HERE / "public_query/group_lift.json",
            "solver_stdout": HERE / "public_query/solver.stdout.txt",
            "formula_gzip": HERE / "public_query/system.xcnf.gz",
            "source_support": SUPPORT,
            "sage_runtime": HERE / "sage_runtime_info.json",
        }.items()},
    }
    with (HERE / "public_query/sage_audit.json").open("x") as out:
        json.dump(receipt,out,indent=2,sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "verified_relations": len(verified)}))


if __name__ == "__main__":
    main()
