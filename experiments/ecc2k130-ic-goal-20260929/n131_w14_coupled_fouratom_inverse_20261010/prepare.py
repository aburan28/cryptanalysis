#!/usr/bin/env sage -python
"""Freeze exact positive and trace-zero control outputs for two field widths."""

import hashlib
import json
import random
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
W14 = GOAL / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
W6 = GOAL / "n41_n131_diagonal_atom_20261010/screen.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup(n):
    base = PolynomialRing(GF(2), "t")
    t = base.gen()
    modulus = t**41 + t**3 + 1 if n == 41 else t**131 + t**13 + t**2 + t + 1
    field = GF(2**n, name="t", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(base([(int(value) >> i) & 1 for i in range(n)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def point_key(value):
        return [encode(value[0]), encode(value[1])]

    def half_trace(value):
        answer = field.zero()
        term = value
        for _ in range((n + 1) // 2):
            answer += term
            term = term**4
        assert answer**2 + answer == value
        return answer

    return field, curve, decode, encode, point_key, half_trace


def panel(n):
    field, curve, decode, encode, key, half_trace = setup(n)
    if n == 41:
        screen = json.loads(W6.read_text())
        columns = {int(row["mask"]): int(row["source_column"])
                   for row in screen["slots"][0]}
        prior_raw = {int(row["mask"]): row["raw_pair_point"]
                     for row in screen["raw_audit"]}
        d = 6
        curve_id = "EC1N41Ckb1h7d5e80d3c4d0"
        order = 549756390943
    else:
        columns = {int(a): int(b) for a, b in
                   (line.split() for line in W14.read_text().splitlines())}
        prior_raw = None
        d = 14
        curve_id = "EC1N131Ckb1heb5f1998f20b"
        order = 680564733841876926932320129493409985129
    basis_w = [field.gen()**i for i in range(1, d + 1)]
    basis_u = [half_trace(w) for w in basis_w]

    def atom(mask):
        w = sum((basis_w[i] for i in range(d) if mask >> i & 1), field.zero())
        u = sum((basis_u[i] for i in range(d) if mask >> i & 1), field.zero())
        assert u**2 + u == w and w != 0 and u != 0
        choices = curve.lift_x(1 + 1/u, all=True)
        assert len(choices) == 2
        point = min(choices, key=lambda item: tuple(key(item)))
        diagonal = point + curve(point[0]**2, point[1]**2)
        assert diagonal != curve(0) and diagonal[0] == 1/w
        if prior_raw is not None:
            original = curve(decode(prior_raw[mask][0]), decode(prior_raw[mask][1]))
            assert diagonal == original or diagonal == -original
        return diagonal, w

    s_mask = 1
    pairs = [(a, a ^ s_mask) for a in sorted(columns)
             if a < a ^ s_mask and a ^ s_mask in columns and
             columns[a] != columns[a ^ s_mask]]
    selected = None
    for i, first in enumerate(pairs):
        for second in pairs[i + 1:]:
            masks = [*first, *second]
            if len({columns[value] for value in masks}) != 4:
                continue
            atoms = [atom(mask) for mask in masks]
            summed = sum((row[0] for row in atoms), curve(0))
            if summed == curve(0) or summed[0] == 0:
                continue
            selected = masks, atoms, summed
            break
        if selected is not None:
            break
    assert selected is not None
    masks, atoms, total = selected
    z = 1 / total[0]
    assert int(z.trace()) == 0
    products = [encode(atoms[2*i][1] * atoms[2*i+1][1]) for i in range(2)]
    rng = random.Random(20261010 + n)
    while True:
        value = decode(rng.getrandbits(n))
        negative = value**2 + value
        if negative not in (0, 1, z):
            break
    assert order * (4 * total) == curve(0)
    return {
        "curve_id": curve_id, "field_degree": n,
        "field_modulus_exponents": [0, 3, 41] if n == 41 else [0, 1, 2, 13, 131],
        "subgroup_order": str(order), "source_dimension": d,
        "source_mask_sum": s_mask, "source_sum_field": encode(basis_w[0]),
        "masks": masks, "folded_columns": [columns[mask] for mask in masks],
        "raw_diagonal_atoms": [key(item[0]) for item in atoms],
        "raw_four_atom_sum": key(total),
        "pair_products": products,
        "positive_z": encode(z), "trace_zero_control_z": encode(negative),
        "positive_target_projected": key(4 * total),
    }


def main():
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    result = {"status": "PASS_FROZEN_FOUR_ATOM_OUTPUT_CONTROLS",
              "target_count": 0, "panels": {str(n): panel(n) for n in (41, 131)},
              "source_sha256": {"script": sha(Path(__file__)),
                                "w6_screen": sha(W6), "w14_support": sha(W14),
                                "resultant_terms": sha(HERE / "resultant_terms.json"),
                                "runtime": sha(HERE / "sage_runtime_info.json")}}
    with (HERE / "inputs.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "panels": {n: {"masks": item["masks"], "seed": item["source_mask_sum"]}
                                 for n, item in result["panels"].items()}}))


if __name__ == "__main__":
    main()
