#!/usr/bin/env python3
"""Derive exact forward-root bits for the independently replayed public N41 row."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n41_n131_zero_sum_triple_20261009"
JOINT = GOAL / "n41_n131_zero_sum_joint_20261009"
N, ORDER = 41, 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def main():
    output = HERE / "forward_chart.json"
    if output.exists():
        raise FileExistsError(output)
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    old = json.loads((JOINT / "witness_chart.json").read_text())
    public = json.loads((SOURCE / "public/result.json").read_text())
    assert old["status"] == "PASS_EXACT_ALGEBRAIC_CHART"
    polynomial = PolynomialRing(GF(2), "t")
    t = polynomial.gen()
    field = GF(2**N, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(polynomial([(int(value) >> i) & 1 for i in range(N)]))

    def half_trace(value):
        answer = field.zero()
        for _ in range((N + 1)//2):
            answer += value
            value = value**4
        return answer

    def transformed(point):
        assert point != curve(0) and point[0] != 1
        return 1/(point[0] + 1)

    def root_bit(left, middle, output_u):
        product = (left*left + left)*(middle*middle + middle)
        assert product != 0
        a = product + 1
        assert a != 0
        argument = a*(left + middle)**2/(product*product)
        h = half_trace(argument)
        assert h*h + h == argument
        y = output_u*a/product
        branch = y + h
        assert branch in (0, 1)
        assert output_u == product/a*(h + branch)
        assert product*(output_u*output_u + output_u) == \
            (left + middle + output_u)**2
        return int(branch), product

    pair_u = []
    block_u = []
    branches = []
    products = []
    for block in range(4):
        raw = []
        u_values = []
        for leaf in public["row"][3*block:3*block+3]:
            w = sum((field(t**(i + 1)) for i in range(7)
                     if (leaf["mask"] >> i) & 1), field.zero())
            u = half_trace(w)**(2**leaf["rotation"])
            projected = curve(*map(decode, leaf["point"]))
            matching = [point for point in curve.lift_x(1 + 1/u, all=True)
                        if 4*point == projected]
            assert len(matching) == 1
            raw.append(matching[0])
            u_values.append(u)
        pair_sum = raw[0] + raw[1]
        block_sum = pair_sum + raw[2]
        pair_output = transformed(pair_sum)
        block_output = transformed(block_sum)
        first_bit, first_product = root_bit(u_values[0], u_values[1],
                                          pair_output)
        second_bit, second_product = root_bit(pair_output, u_values[2],
                                            block_output)
        assert first_product == decode(old["block_q"][block])
        assert encode(block_output) == old["block_u"][block]
        pair_u.append(encode(pair_output))
        block_u.append(encode(block_output))
        branches.append([first_bit, second_bit])
        products.append([encode(first_product), encode(second_product)])
    result = {"status": "PASS_FORWARD_ROOT_CHART",
              "proposal_id": "Q20261009220100", "candidate_id": None,
              "target": public["target"],
              "source_masks": old["source_masks"],
              "pair_u": pair_u,
              "block_u": block_u,
              "root_branch_bits": branches,
              "link_products": products,
              "target_fiber_index": old["target_fiber_index"],
              "sha256": {"source": sha(__file__),
                         "runtime": sha(HERE / "sage_runtime_info.json"),
                         "public_row": sha(SOURCE / "public/result.json"),
                         "prior_chart": sha(JOINT / "witness_chart.json")}}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
