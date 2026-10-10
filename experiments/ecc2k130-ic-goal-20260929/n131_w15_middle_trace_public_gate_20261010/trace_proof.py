#!/usr/bin/env sage -python
"""Audit the exact polynomial-basis trace and all constructed middle words."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010/control.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    g = field.gen()
    support = [i for i in range(131) if int((g**i).trace())]
    assert support == [0, 129]

    def decode(value):
        return sum((g**bit for bit in range(131) if value >> bit & 1), field.zero())

    fixture = json.loads(FIXTURE.read_text())
    middles = fixture["middle_reciprocals"]
    assert len(middles) == 10
    traces = [int(decode(value).trace()) for value in middles]
    assert traces == [0] * 10
    assert all(((value >> 0) ^ (value >> 129)) & 1 == 0 for value in middles)
    receipt = {"status": "PASS_EXACT_N131_TRACE_PARITY_AND_CONSTRUCTED_MIDDLES",
               "field_modulus": "t^131+t^13+t^2+t+1",
               "polynomial_basis_trace_support": support,
               "constructed_middle_reciprocal_traces": traces,
               "source_sha256": {"script": sha(Path(__file__)),
                                 "fixture": sha(FIXTURE),
                                 "checked_runtime": sha(HERE / "sage_runtime_info.json")}}
    with (HERE / "trace_proof.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "trace_support": support}))


if __name__ == "__main__":
    main()
