#!/usr/bin/env sage -python
"""Independent Sage group replay of the signed-prefix five-pair residual."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
R = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    inp = json.loads((HERE / "fivepair_input.json").read_text())
    control = json.loads((HERE / "fivepair_control_result.json").read_text())
    lifted = json.loads((HERE / "fivepair_control_group_lift.json").read_text())
    assert inp["status"] == "PASS_EXACT_CONSTRUCTED_W15_FIVE_PAIR_RESIDUAL"
    assert control["status"] == "PASS_FULL_XCNF_AND_GROUP_FIVE_PAIR_CONTROL"
    assert lifted["status"] == "GROUP_LIFT_FOUND"
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, name="t", modulus=t**131 + t**13 + t**2 + t + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    def decode(value):
        return sum((field.gen()**i for i in range(131) if value >> i & 1),
                   field.zero())
    def point(values):
        return curve(decode(values[0]), decode(values[1]))
    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))
    fixed = point(inp["first_pair_raw"])
    residual_q = point(inp["residual_target_q"])
    original_q = point(inp["original_target_q"])
    assert R * residual_q == curve(0)
    assert R * original_q == curve(0)
    assert 4 * fixed == point(inp["first_pair_projected"])
    assert residual_q + 4 * fixed == original_q
    assert len(set(inp["first_pair_columns"] + inp["remaining_columns"])) == 12
    checks = 0
    for solution in lifted["solutions"]:
        assert solution["masks"] == inp["remaining_masks"]
        assert solution["masks"][2] ^ solution["masks"][3] == \
            solution["masks"][4] ^ solution["masks"][5]
        assert solution["masks"][6] ^ solution["masks"][7] == \
            solution["masks"][8] ^ solution["masks"][9]
        assert len(set(inp["first_pair_columns"] + solution["folded_columns"])) == 12
        total = curve(0)
        for item in solution["raw_leaves"]:
            total += point(item)
        assert [encode(total[0]), encode(total[1])] == solution["raw_sum"]
        assert 4 * total == residual_q
        assert 4 * (fixed + total) == original_q
        checks += 1
    result = {
        "status": "PASS_INDEPENDENT_SAGE_FIVE_PAIR_RESIDUAL_GROUP_REPLAY",
        "checked_control_solutions": checks,
        "residual_target_q": inp["residual_target_q"],
        "original_target_q": inp["original_target_q"],
        "source_sha256": {"script": sha(__file__),
                          "input": sha(HERE / "fivepair_input.json"),
                          "control_result": sha(HERE / "fivepair_control_result.json"),
                          "control_group_lift": sha(HERE / "fivepair_control_group_lift.json"),
                          "runtime": sha(HERE / "sage_runtime_info.json")},
    }
    with (HERE / "fivepair_sage_audit.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "solutions": checks}))


if __name__ == "__main__":
    main()
