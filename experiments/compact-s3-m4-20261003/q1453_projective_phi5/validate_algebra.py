#!/usr/bin/env python3
"""Check D^8 P_phi5 equals the inverse-free projective polynomial."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1449_phi5_native_xor.common import sha, sha_bytes  # noqa: E402

OUTPUT = HERE / "algebra_validation.json"


def original(onb, xs):
    mul, sqr = onb.mul, onb.sqr
    one = onb.one()
    us = [onb.pow(x ^ one, (1 << onb.m) - 2) for x in xs]
    e = 0
    s = [one] + [0] * 5
    for count, u in enumerate(us):
        e ^= u
        y = sqr(u) ^ u
        for j in range(min(count + 1, 5), 0, -1):
            s[j] ^= mul(s[j - 1], y)
    e2, e4 = sqr(e), sqr(sqr(e))
    e8 = sqr(e4)
    e6 = mul(e2, e4)
    s2_2, s3_2, s4_2, s5_2 = (sqr(s[j]) for j in (2, 3, 4, 5))
    s5_3 = mul(s[5], s5_2)
    terms = [
        e8, mul(e6, s[5]), mul(e4, s4_2),
        mul(mul(e2, s3_2), s[5]), sqr(s3_2),
        mul(e2, s5_3), mul(s2_2, s5_2), sqr(s5_2), s5_3,
    ]
    return _xor_all(terms)


def projective(onb, xs):
    mul, sqr = onb.mul, onb.sqr
    one = onb.one()
    d, e = one, 0
    s = [one] + [0] * 5
    for count, x in enumerate(xs):
        dx = x ^ one
        dx2 = sqr(dx)
        new_s = [0] * 6
        for j in range(1, min(count + 1, 5) + 1):
            new_s[j] = mul(s[j], dx2) ^ mul(s[j - 1], x)
        new_d = mul(d, dx)
        new_s[0] = sqr(new_d)
        e = mul(e, dx) ^ d
        d, s = new_d, new_s
    e2, e4 = sqr(e), sqr(sqr(e))
    e8 = sqr(e4)
    e6 = mul(e2, e4)
    s2_2, s3_2, s4_2, s5_2 = (sqr(s[j]) for j in (2, 3, 4, 5))
    s5_3 = mul(s[5], s5_2)
    terms = [
        e8, mul(e6, s[5]), mul(e4, s4_2),
        mul(mul(e2, s3_2), s[5]), sqr(s3_2),
        mul(e2, s5_3), mul(s2_2, s5_2), sqr(s5_2),
        mul(sqr(d), s5_3),
    ]
    return d, _xor_all(terms)


def _xor_all(values):
    result = 0
    for value in values:
        result ^= value
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    validation_path = PARENT / "q1448_torsion_phi5/validation.json"
    validation = json.loads(validation_path.read_text())
    rows = []
    for n in (53, 83):
        onb = field.Onb(n)
        one = onb.one()
        witness = next(row for row in validation["rows"]
                       if row["degree_n"] == n)
        rng = random.Random(1453 + n)
        vectors = [[*witness["raw_leaf_x"], witness["raw_target_x"]]]
        for _ in range(64):
            vector = [rng.getrandbits(n) for _ in range(5)]
            vectors.append(vector)
        outputs = []
        for number, vector in enumerate(vectors):
            xs = [onb.fromCoords(mask) for mask in vector]
            assert all(x != one for x in xs)
            old = original(onb, xs)
            d, new = projective(onb, xs)
            assert d != 0
            d8 = onb.sqr(onb.sqr(onb.sqr(d)))
            assert new == onb.mul(d8, old), (n, number)
            if number == 0:
                assert old == new == 0, n
            outputs.append([onb.toCoords(old), onb.toCoords(new)])
        encoded = json.dumps(vectors, sort_keys=True,
                             separators=(",", ":")).encode()
        out_encoded = json.dumps(outputs, sort_keys=True,
                                 separators=(",", ":")).encode()
        rows.append({
            "degree_n": n, "random_seed": 1453 + n,
            "random_tuple_count": 64,
            "archived_witness_tuple_count": 1,
            "sample_input_sha256": sha_bytes(encoded),
            "sample_output_sha256": sha_bytes(out_encoded),
            "all_projective_equal_D8_times_original": True,
            "archived_witness_zero_in_both_forms": True,
        })
    result = {
        "kind": "q1453_projective_phi5_field_identity_validation",
        "proposal_id": "Q1453", "candidate_id": None,
        "isogeny": "none", "status": "pass", "rows": rows,
        "q1448_validation_sha256": sha(validation_path),
        "complete_n131_log2_work": None,
    }
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1453 projective phi5 algebra validation: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print("Q1453 projective phi5 algebra validation: PASS")


if __name__ == "__main__":
    main()
