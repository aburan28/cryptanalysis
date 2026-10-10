#!/usr/bin/env python3
"""Independent resultant identity and exact public-row chart witness."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_n131_zero_sum_triple_20261009"
N, ORDER = 41, 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def main():
    output = HERE / "witness_chart.json"
    if output.exists():
        raise FileExistsError(output)
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"

    # Re-derive the optimized resultant from independent polynomial arithmetic.
    ring = PolynomialRing(GF(2), names=("s", "q", "z"))
    s, q, z = ring.gens()
    r = (s*s + s)*(z*z + z)
    f = (s + z)**2
    c = q*f + s*s*r
    compact = (c + f + s*s)**2 + (q + r)*c
    extended = PolynomialRing(ring, "X")
    X = extended.gen()
    first = (q + 1)*X*X + q*X + s*s
    second = (r + 1)*X*X + r*X + f
    assert ring(first.resultant(second)) == compact

    polynomial = PolynomialRing(GF(2), "t")
    t = polynomial.gen()
    field = GF(2**N, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(polynomial([(int(value) >> i) & 1 for i in range(N)]))

    def half_trace(value):
        result = field.zero()
        for _ in range((N + 1)//2):
            result += value
            value = value**4
        return result

    def u(point):
        assert point != curve(0) and point[0] != 1
        return 1/(point[0] + 1)

    def s3(left, middle, right):
        wl = left*left + left
        wm = middle*middle + middle
        wr = right*right + right
        return wl*wm*wr + (left + middle + right)**2

    public = json.loads((SOURCE / "public/result.json").read_text())
    q_point = curve(*map(decode, public["target"]))
    assert ORDER*q_point == curve(0)
    blocks = []
    u_outputs = []
    q_products = []
    raw_leaves = []
    for block in range(4):
        rows = public["row"][3*block:3*block+3]
        assert rows[0]["mask"] ^ rows[1]["mask"] == rows[2]["mask"]
        chosen = []
        us = []
        ws = []
        for leaf in rows:
            w = sum((field(t**(i + 1)) for i in range(7)
                     if (leaf["mask"] >> i) & 1), field.zero())
            base_u = half_trace(w)
            rotated_u = base_u**(2**leaf["rotation"])
            projected = curve(*map(decode, leaf["point"]))
            raw = [member for member in curve.lift_x(1 + 1/rotated_u, all=True)
                   if 4*member == projected]
            assert len(raw) == 1
            chosen.append(raw[0])
            raw_leaves.append(raw[0])
            us.append(rotated_u)
            ws.append(w**(2**leaf["rotation"]))
        assert us[0] + us[1] == us[2]
        block_sum = sum(chosen, curve(0))
        z_value = u(block_sum)
        q_product = ws[0]*ws[1]
        sv = us[0] + us[1]
        rv = (sv*sv + sv)*(z_value*z_value + z_value)
        fv = (sv + z_value)**2
        cv = q_product*fv + sv*sv*rv
        assert (cv + fv + sv*sv)**2 + (q_product + rv)*cv == 0
        blocks.append(block_sum)
        u_outputs.append(z_value)
        q_products.append(q_product)

    partials = [blocks[0] + blocks[1], blocks[2] + blocks[3]]
    h = [u(point) for point in partials]
    raw_sum = partials[0] + partials[1]
    assert raw_sum == sum(raw_leaves, curve(0)) and 4*raw_sum == q_point
    target_u = u(raw_sum)
    assert s3(u_outputs[0], u_outputs[1], h[0]) == 0
    assert s3(u_outputs[2], u_outputs[3], h[1]) == 0
    assert s3(h[0], h[1], target_u) == 0

    torsion = curve(field(1), field(1))
    start = pow(4, -1, ORDER)*q_point
    fiber = [start + i*torsion for i in range(4)]
    index = fiber.index(raw_sum)
    result = {
        "status": "PASS_EXACT_ALGEBRAIC_CHART",
        "proposal_id": "Q20261009200400",
        "target": public["target"],
        "source_masks": [[leaf["mask"] for leaf in public["row"][3*i:3*i+3]]
                         for i in range(4)],
        "block_u": list(map(encode, u_outputs)),
        "block_q": list(map(encode, q_products)),
        "middle_u": list(map(encode, h)),
        "target_u": encode(target_u),
        "target_fiber_index": index,
        "raw_sum": [encode(raw_sum[0]), encode(raw_sum[1])],
        "resultant_identity": "(C+f+s^2)^2+(q+r)C, C=qf+s^2r",
        "sha256": {"source": sha(__file__),
                   "runtime": sha(HERE / "sage_runtime_info.json"),
                   "public_witness": sha(SOURCE / "public/result.json")},
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
