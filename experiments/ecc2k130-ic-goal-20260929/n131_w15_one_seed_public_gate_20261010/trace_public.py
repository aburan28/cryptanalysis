#!/usr/bin/env sage -python
"""Independently audit the reciprocal-trace fiber of the published point."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_coupled_sixpair_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    protocol = json.loads((HERE / "protocol.json").read_text())
    original = json.loads((BASE / "public_query/result.json").read_text())
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return sum((field.gen()**bit for bit in range(131) if value >> bit & 1), field.zero())

    def point(values):
        return curve(decode(values[0]), decode(values[1]))

    q = point(protocol["target_q"])
    assert list(protocol["target_q"]) == original["target_q"]
    basis_traces = [int(decode(1 << bit).trace()) for bit in range(1, 16)]
    assert basis_traces == [0] * 15
    traces = []
    for values in original["raw_target_preimages"]:
        p = point(values)
        assert 4*p == q and p[0] != 0
        traces.append(int((1/p[0]).trace()))
    assert len(traces) == 4 and sorted(traces) == [0, 0, 1, 1]
    admissible = [index for index, value in enumerate(traces) if value == 0]
    receipt = {"status": "PASS_PUBLIC_RECIPROCAL_TRACE_FIBER",
               "curve_id": protocol["curve_id"], "target_q": protocol["target_q"],
               "source_basis_traces": basis_traces,
               "target_preimage_reciprocal_traces": traces,
               "admissible_target_preimage_indices": admissible,
               "source_sha256": {"script": sha(Path(__file__)),
                                 "protocol": sha(HERE / "protocol.json"),
                                 "original_public_result": sha(BASE / "public_query/result.json"),
                                 "checked_runtime": sha(HERE / "sage_runtime_info.json")}}
    with (HERE / "trace_result.json").open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "traces": traces,
                      "admissible_indices": admissible}))


if __name__ == "__main__":
    main()
