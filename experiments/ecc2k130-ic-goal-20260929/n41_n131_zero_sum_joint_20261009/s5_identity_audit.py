#!/usr/bin/env python3
"""Check the target-ended five-point invariant on the exact public chart."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = HERE / "s5_identity.json"
    if output.exists():
        raise FileExistsError(output)
    chart = json.loads((HERE / "witness_chart.json").read_text())
    assert chart["status"] == "PASS_EXACT_ALGEBRAIC_CHART"
    p = PolynomialRing(GF(2), "t")
    t = p.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)

    def decode(value):
        return field(p([(int(value) >> i) & 1 for i in range(41)]))

    u = list(map(decode, chart["block_u"] + [chart["target_u"]]))
    w = [value*value + value for value in u]
    e = [field.one()] + [field.zero() for _ in range(5)]
    for index, wi in enumerate(w):
        for k in range(index + 1, 0, -1):
            e[k] += e[k-1]*wi
    v = (sum(u, field.zero()))**2
    e3sq, e4sq, e5sq = e[3]**2, e[4]**2, e[5]**2
    constant = (e[2]*e[5] + e3sq + e5sq)**2
    linear = e[5]*(e3sq + e5sq)
    cubic = e[5]*e5sq
    value = v + e[5]
    value = value*v + e4sq
    value = value*v + linear
    value = value*v + constant + cubic
    assert value == 0
    result = {"status": "PASS_EXACT_S5_CHART",
              "proposal_id": "Q20261009200400",
              "target_fiber_index": chart["target_fiber_index"],
              "target": chart["target"],
              "s5_value": 0,
              "sha256": {"source": sha(__file__),
                         "runtime": sha(HERE / "sage_runtime_info.json"),
                         "chart": sha(HERE / "witness_chart.json")}}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
