#!/usr/bin/env sage -python
"""Sage group replay of a recovered fixed-pair N131 model, if produced."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing, EllipticCurve

HERE = Path(__file__).resolve().parent
R = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    lift = json.loads((HERE / "group_lift.json").read_text())
    assert result["status"] == "GROUP_LIFT_PENDING_INDEPENDENT_SAGE"
    assert lift["status"] == "GROUP_LIFT_FOUND" and lift["solutions"]
    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    field = GF(2**131, name="t", modulus=t**131 + t**13 + t**2 + t + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    def decode(value):
        return sum((field.gen()**i for i in range(131) if value >> i & 1),
                   field.zero())
    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))
    target = curve(decode(protocol["target_q"][0]),
                   decode(protocol["target_q"][1]))
    assert R * target == curve(0)
    checks = []
    for solution in lift["solutions"]:
        assert solution["masks"][:2] == protocol["pinned_masks"]
        assert len(set(solution["folded_columns"])) == 12
        total = curve(0)
        for x, y in solution["raw_leaves"]:
            total += curve(decode(x), decode(y))
        assert 4 * total == target
        assert [encode(total[0]), encode(total[1])] == solution["raw_sum"]
        checks.append(sha(HERE / "group_lift.json"))
    receipt = {"status": "PASS_INDEPENDENT_SAGE_FIXED_PAIR_GROUP_REPLAY",
               "solution_count": len(checks),
               "target_q": protocol["target_q"],
               "group_lift_sha256": sha(HERE / "group_lift.json"),
               "audit_source_sha256": sha(__file__)}
    with (HERE / "independent_group_audit.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
