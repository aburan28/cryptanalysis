"""Fixed-seed N131 W15 quartic factor as a native-XOR Boolean circuit."""

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GOAL = HERE.parent
sys.path.insert(0, str(ROOT / "experiments/koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402

N = 131
MODULUS = (1 << N) | (1 << 13) | (1 << 2) | (1 << 1) | 1
FACTORS = GOAL / "rotated_fouratom_factorization_20261010/n131_positive.json"
CONTROL = GOAL / "n131_w15_rotated_fouratom_inverse_20261010/control_result.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mul(a, b):
    out = 0
    while b:
        if b & 1:
            out ^= a
        b >>= 1
        a <<= 1
        if a >> N:
            a ^= MODULUS
    return out


def frob(a, count):
    for _ in range(count):
        a = mul(a, a)
    return a


def product_basis(seed, rotation):
    pivots = {}
    basis = []
    for i in range(1, 16):
        w = 1 << i
        image = frob(mul(w, w) ^ mul(seed, w), rotation)
        reduced = image
        while reduced:
            pivot = reduced.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = reduced
                basis.append(image)
                break
            reduced ^= pivots[pivot]
    assert len(basis) == 14
    return basis


def element(code, basis):
    return sum((v for i, v in enumerate(basis) if code >> i & 1), 0)


def code_for(value, basis):
    values = [0] * (1 << 14)
    for code in range(1, 1 << 14):
        low = code & -code
        values[code] = values[code ^ low] ^ basis[low.bit_length() - 1]
    return next(code for code, item in enumerate(values) if item == value)


def factor_value(terms, p, q):
    powers_p, powers_q = [1], [1]
    for _ in range(4):
        powers_p.append(mul(powers_p[-1], p))
        powers_q.append(mul(powers_q[-1], q))
    out = 0
    for ep, eq, coefficient in terms:
        out ^= mul(coefficient, mul(powers_p[ep], powers_q[eq]))
    return out


def build(factor, left_basis, right_basis):
    circuit = KaratsubaCircuit(N, [0, 1, 2, 13])
    left_bits = [circuit.variable() for _ in range(14)]
    right_bits = [circuit.variable() for _ in range(14)]
    p = circuit.linear_element(left_bits, left_basis)
    q = circuit.linear_element(right_bits, right_basis)
    # The 14-by-14 source product uses 196 primary ANDs rather than a
    # dense field multiplier. Its powers share six nonlinear field products.
    gates = [circuit.and_(a, b) for a in left_bits for b in right_bits]
    images = [mul(a, b) for a in left_basis for b in right_basis]
    t = circuit.linear_element(gates, images)
    p2, q2, t2 = circuit.square(p), circuit.square(q), circuit.square(t)
    p4, q4, t4 = circuit.square(p2), circuit.square(q2), circuit.square(t2)
    tp, tq = circuit.mul(t, p), circuit.mul(t, q)
    monomials = {
        (0, 0): circuit.constant(1), (0, 2): q2, (0, 4): q4,
        (1, 1): t, (1, 3): circuit.mul(t, q2),
        (2, 0): p2, (2, 2): t2, (2, 4): circuit.square(tq),
        (3, 1): circuit.mul(t, p2), (3, 3): circuit.mul(t, t2),
        (4, 0): p4, (4, 2): circuit.square(tp), (4, 4): t4,
    }
    result = circuit.constant(0)
    for ep, eq, coefficient in factor["terms"]:
        value = monomials[ep, eq]
        if coefficient != 1:
            images = [mul(coefficient, 1 << bit) for bit in range(N)]
            value = circuit.linear_element(value, images)
        result = circuit.add(result, value)
    circuit.require_zero(result)
    return circuit, left_bits, right_bits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("factor", type=int, choices=(0, 1))
    args = parser.parse_args()
    data = json.loads(FACTORS.read_text())
    witness = json.loads(CONTROL.read_text())["n131"]
    seed = sum((1 << (i + 1) for i in range(15) if witness["seed_mask"] >> i & 1), 0)
    left_basis = product_basis(seed, 26)
    right_basis = product_basis(seed, 39)
    known_p, known_q = witness["rotated_pair_products"]
    pcode, qcode = code_for(known_p, left_basis), code_for(known_q, right_basis)
    values = [factor_value(f["terms"], known_p, known_q) for f in data["factors"]]
    assert values.count(0) == 1 and values[args.factor] == 0
    factor = data["factors"][args.factor]
    circuit, left_bits, right_bits = build(factor, left_basis, right_basis)
    formula = HERE / f"factor{args.factor}.xcnf.gz"
    with gzip.open(formula, "xt", compresslevel=6) as out:
        out.write(f"p cnf {circuit.next_var-1} {len(circuit.clauses)+len(circuit.xors)}\n")
        out.write("\n".join(circuit.clauses) + "\n")
        out.write("\n".join(circuit.xors) + "\n")
    record = {"status": "BUILT_POSITIVE_QUARTIC_XCNF", "factor_index": args.factor,
              "primary_product_bits": 28, "known_product_codes": [pcode, qcode],
              "known_factor_values": values, "factor_terms": len(factor["terms"]),
              "variables": circuit.next_var-1, "and_gates": circuit.and_count,
              "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
              "formula_gzip_sha256": sha(formula),
              "source_sha256": {"build.py": sha(__file__),
                                "factor_data": sha(FACTORS), "control": sha(CONTROL)}}
    (HERE / f"factor{args.factor}_build.json").write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
