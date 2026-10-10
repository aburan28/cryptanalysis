#!/usr/bin/env sage -python
"""Independent Sage field and opposite-direction S3 join replay."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_pair_output_prefix_gate_20261010"
CONTROL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010" / "control.json"
R = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return sum(int(coefficient) << index for index, coefficient in
               enumerate(value.polynomial().list()))


def halftrace(value, field):
    out = field.zero()
    for _ in range(66):
        out += value
        value = value**4
    return out


def right_roots(left, q, field):
    product = left*q
    a = field.one()+product**2
    c = left**2+q**2
    if a == 0:
        return [c/product] if product != 0 else []
    if product == 0:
        return [(c/a).sqrt()]
    argument = a*c/product**2
    h = halftrace(argument, field)
    if h**2+h != argument:
        return []
    scale = product/a
    return [scale*h, scale*(h+1)]


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    roots = json.loads((BASE / "pair_roots.json").read_text())
    control = json.loads(CONTROL.read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    assert protocol["status"] == "FROZEN_W15_FIXEDSEED_S3_JOIN"
    assert result["status"] == "COMPLETE"
    assert result["sha256"]["pair_roots"] == sha(BASE / "pair_roots.json")
    assert result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    field = GF(2**131, "z", modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    source = []
    for block in roots["pair_rows"]:
        domain = set()
        for a, b, c0, c1 in block["pairs"]:
            assert a != b and c0 != c1
            domain.update((c0, c1))
        source.append(domain)
    left, right = source
    assert [len(left), len(right)] == result["domain_sizes"] == [8176, 8340]
    right_sage = {field.from_integer(value) for value in right}
    audits = []
    started = time.monotonic()
    for case in result["cases"]:
        assert case["status"] == "COMPLETE"
        q = field.from_integer(case["target_reciprocal"])
        actual = set()
        for ordinal, c_int in enumerate(left):
            if ordinal % 128 == 0:
                assert time.monotonic()-started < 300
            c = field.from_integer(c_int)
            for d in right_roots(c, q, field):
                assert (c+d+q)**2+c*d*q+(c*d*q)**2 == 0
                if d in right_sage:
                    actual.add((c_int, encode(d)))
        expected = {(row["left_output"], row["right_output"])
                    for row in case["algebraic_hits"]}
        assert actual == expected
        assert case["right_outputs_visited"] == len(right)
        audits.append({"name": case["name"], "algebraic_hit_pairs": len(actual),
                       "pair_digest": hashlib.sha256(json.dumps(sorted(actual)).encode()).hexdigest()})
    leaf_points = [curve(field.from_integer(x), field.from_integer(y))
                   for x, y in control["raw_leaves"][:4]]
    first = leaf_points[0]+leaf_points[1]
    second = leaf_points[2]+leaf_points[3]
    four = first+second
    assert not first.is_zero() and not second.is_zero() and not four.is_zero()
    assert encode(1/first[0]) == control["middle_reciprocals"][0]
    assert encode(1/second[0]) == control["middle_reciprocals"][1]
    assert encode(1/four[0]) == control["middle_reciprocals"][6]
    assert R*(4*four) == curve(0)
    assert audits[0]["algebraic_hit_pairs"] > 0
    assert all(row["algebraic_hit_pairs"] == 0 for row in audits[1:])
    receipt = {"status": "PASS_INDEPENDENT_SAGE_W15_S3_JOIN_AUDIT",
               "curve_id": protocol["curve_id"],
               "domain_sizes": [len(left), len(right)],
               "positive_group_replay": "PASS",
               "cases": audits, "elapsed_seconds": time.monotonic()-started,
               "sha256": {"auditor": sha(Path(__file__)),
                          "protocol": sha(HERE / "protocol.json"),
                          "producer_result": sha(HERE / "result.json"),
                          "pair_roots": sha(BASE / "pair_roots.json"),
                          "constructed_input": sha(CONTROL),
                          "runtime": sha(HERE / "sage_runtime_info.json")}}
    with (HERE / "sage_audit.json").open("x") as out:
        json.dump(receipt, out, sort_keys=True, indent=2)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "cases": audits,
                      "elapsed_seconds": receipt["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
