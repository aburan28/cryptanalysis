#!/usr/bin/env python3
"""Audit the strict pair-order clause law and its exact source orbit count."""

import hashlib
import json
import random
from decimal import Decimal, getcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "n131_w15_two_fixed_seeds_public_20261010"
CONTROL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010" / "control.json"
R = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clauses_accept(left, right, width):
    differences = [((left ^ right) >> bit) & 1 for bit in range(width)]
    return all(any(differences[bit+1:]) or not (left >> bit & 1) or
               (right >> bit & 1) for bit in range(width))


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    count = json.loads((HERE / "support_count.json").read_text())
    control = json.loads(CONTROL.read_text())
    assert protocol["status"] == "FROZEN_W15_PAIR_LEX_PUBLIC_GATE"
    assert protocol["source_sha256"]["circuit"] == sha(HERE / "circuit.py")
    assert protocol["source_sha256"]["baseline_circuit"] == sha(BASELINE / "circuit.py")
    checked8 = 0
    for left in range(256):
        for right in range(256):
            assert clauses_accept(left, right, 8) == (left <= right)
            checked8 += 1
    generator = random.Random(20261010)
    checked15 = 0
    for _ in range(200000):
        left = generator.randrange(1 << 15)
        right = generator.randrange(1 << 15)
        assert clauses_accept(left, right, 15) == (left <= right)
        checked15 += 1
    masks = control["masks"]
    assert len(masks) == 12 and len(set(masks)) == 12
    assert all(masks[2*i] < masks[2*i+1] for i in range(6))
    accepted = 0
    for swaps in range(64):
        oriented = masks.copy()
        for pair in range(6):
            if swaps >> pair & 1:
                oriented[2*pair:2*pair+2] = list(reversed(oriented[2*pair:2*pair+2]))
        assert [oriented[2*i] ^ oriented[2*i+1] for i in range(6)] == \
            [masks[2*i] ^ masks[2*i+1] for i in range(6)]
        accepted += all(clauses_accept(oriented[2*i], oriented[2*i+1], 15)
                        for i in range(6))
    assert accepted == 1
    source_count = int(count["distinct_column_signed_sixpair_tuples"])
    assert source_count % 64 == 0
    getcontext().prec = 55
    mean = str(Decimal(source_count // 64)/Decimal(R))
    assert protocol["lex_source_count"] == str(source_count // 64)
    assert protocol["lex_uniform_target_mean"] == mean
    receipt = {"status": "PASS_W15_PAIR_LEX_SEMANTICS",
               "curve_id": protocol["curve_id"],
               "eight_bit_ordered_pairs_checked": checked8,
               "fifteen_bit_seeded_pairs_checked": checked15,
               "constructed_swap_orbit_size": 64,
               "constructed_canonical_orientations": accepted,
               "exact_lex_source_count": protocol["lex_source_count"],
               "lex_uniform_target_mean": mean,
               "source_sha256": {"script": sha(Path(__file__)),
                                 "protocol": sha(HERE / "protocol.json"),
                                 "circuit": sha(HERE / "circuit.py"),
                                 "support_count": sha(HERE / "support_count.json"),
                                 "constructed_input": sha(CONTROL)}}
    with (HERE / "lex_semantics.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "lex_mean": mean, "orbit": accepted}))


if __name__ == "__main__":
    main()
