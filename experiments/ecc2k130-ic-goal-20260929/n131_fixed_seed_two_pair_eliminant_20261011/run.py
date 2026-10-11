"""Exact two-free-pair eliminant and Boolean-circuit size gate on N131."""

import argparse
import hashlib
import json
import psutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAIR = ROOT / "n131_fixed_seed_eight_pair_circuit_20261010"
CUBIC = ROOT / "n131_fixed_seed_halftrace_cubic_20261011"
sys.path[:0] = [str(PAIR), str(CUBIC),
                str(ROOT / "n41_basis_aware_quartic_20261011"),
                str(ROOT.parent / "koblitz-polynomial-w-pair-20260925")]
import fixed_pair_circuit as fixed  # noqa: E402
import run as cubic  # noqa: E402
from sparse import Algebra  # noqa: E402
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402

MUL = fixed.gf_mul
SQUARE = fixed.gf_square
POSITIVE = [772399585521899329371552173147159697739,
            514225577816051758939711888088519510037,
            459961288995423458429554548179202804119,
            2136898510889230156311441866525536276287]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sources():
    return {"runner": Path(__file__), "pair": PAIR / "fixed_pair_circuit.py",
            "derive": PAIR / "derive_result.json",
            "chain": PAIR / "planted_chain_result.json",
            "cubic_runner": CUBIC / "run.py",
            "cubic_audit": CUBIC / "audit_result.json",
            "sparse": ROOT / "n41_basis_aware_quartic_20261011" / "sparse.py",
            "karatsuba": ROOT.parent / "koblitz-polynomial-w-pair-20260925" / "karatsuba_circuit.py",
            "circuit_sat": ROOT.parent / "koblitz-s5-invariant-20260924" / "circuit_sat.py"}


def data():
    selected = json.loads((PAIR / "derive_result.json").read_text())["selected"]
    chain = json.loads((PAIR / "planted_chain_result.json").read_text())
    assert len(selected) == 8 and len(chain["pair_rotated_z"]) == 8
    assert chain["status"] == "PASS_INDEPENDENT_SAGE_EIGHT_PAIR_CHAIN_FIXTURE"
    return selected, chain


def pair_parameters(item):
    seed_h2 = SQUARE(fixed.gf_half_trace(fixed.coordinate(fixed.SEED)))
    t = fixed.gf_frobenius(seed_h2, item["rotation"])
    k = 1 ^ t
    p = fixed.gf_frobenius(fixed.product_from_code(
        fixed.selector_code(item["masks"][0])), item["rotation"])
    assert k and p
    return k, p, t


def s3(a, b, c):
    return MUL(MUL(SQUARE(a), SQUARE(b)), SQUARE(c)) ^ MUL(MUL(a, b), c) ^ SQUARE(a) ^ SQUARE(b) ^ SQUARE(c)


def eliminate(left, right, c):
    """Resultant of two pair quadratics and the standard-reciprocal S3."""
    k, p, t = left
    ell, q, u = right
    alpha, beta = MUL(p, cubic.inverse(k)), MUL(t, cubic.inverse(k))
    gamma, delta = MUL(q, cubic.inverse(ell)), MUL(u, cubic.inverse(ell))
    c2 = SQUARE(c)
    A = MUL(c2, MUL(alpha, gamma)) ^ c
    B = MUL(c2, MUL(alpha, delta)) ^ alpha
    C = MUL(c2, MUL(beta, gamma)) ^ gamma
    D = MUL(c2, MUL(beta, delta)) ^ beta ^ delta ^ c2
    L2 = MUL(ell, SQUARE(B)) ^ MUL(q, MUL(B, A)) ^ MUL(u, SQUARE(A))
    L1 = MUL(q, MUL(B, C) ^ MUL(D, A))
    L0 = MUL(ell, SQUARE(D)) ^ MUL(q, MUL(D, C)) ^ MUL(u, SQUARE(C))
    R, S = MUL(L2, alpha) ^ L1, MUL(L2, beta) ^ L0
    return MUL(k, SQUARE(S)) ^ MUL(p, MUL(S, R)) ^ MUL(t, SQUARE(R))


def polynomial(left, right):
    """Compute resultant coefficients as a polynomial in block output c."""
    def add(*values):
        result = [0] * max(map(len, values))
        for poly in values:
            for index, coefficient in enumerate(poly):
                result[index] ^= coefficient
        while len(result) > 1 and result[-1] == 0:
            result.pop()
        return result
    def product(a, b):
        result = [0] * (len(a) + len(b) - 1)
        for i, x in enumerate(a):
            for j, y in enumerate(b):
                result[i + j] ^= MUL(x, y)
        while len(result) > 1 and result[-1] == 0:
            result.pop()
        return result
    def square(a):
        result = [0] * (2 * len(a) - 1)
        for i, value in enumerate(a):
            result[2 * i] = SQUARE(value)
        while len(result) > 1 and result[-1] == 0:
            result.pop()
        return result
    def scale(a, value):
        return [MUL(x, value) for x in a]
    k, p, t = left
    ell, q, u = right
    alpha, beta = MUL(p, cubic.inverse(k)), MUL(t, cubic.inverse(k))
    gamma, delta = MUL(q, cubic.inverse(ell)), MUL(u, cubic.inverse(ell))
    c, c2 = [0, 1], [0, 0, 1]
    A = add(scale(c2, MUL(alpha, gamma)), c)
    B = scale(add(scale(c2, delta), [1]), alpha)
    C = scale(add(scale(c2, beta), [1]), gamma)
    D = add(scale(c2, MUL(beta, delta) ^ 1), [beta ^ delta])
    L2 = add(scale(square(B), ell), scale(product(B, A), q), scale(square(A), u))
    L1 = scale(add(product(B, C), product(D, A)), q)
    L0 = add(scale(square(D), ell), scale(product(D, C), q), scale(square(C), u))
    R, S = add(scale(L2, alpha), L1), add(scale(L2, beta), L0)
    return add(scale(square(S), k), scale(product(S, R), p), scale(square(R), t))


def polynomial_value(coefficients, x):
    value = 0
    for coefficient in reversed(coefficients):
        value = MUL(value, x) ^ coefficient
    return value


def s3_output_roots(a, b):
    product = MUL(a, b)
    quadratic = SQUARE(product) ^ 1
    constant = SQUARE(a) ^ SQUARE(b)
    if quadratic == 0:
        return {MUL(constant, cubic.inverse(product))}
    rhs = MUL(MUL(quadratic, constant), cubic.inverse(SQUARE(product)))
    h = fixed.gf_half_trace(rhs)
    assert SQUARE(h) ^ h == rhs
    scale = MUL(product, cubic.inverse(quadratic))
    return {MUL(scale, h), MUL(scale, h ^ 1)}


def freeze():
    selected, chain = data()
    assert json.loads((CUBIC / "audit_result.json").read_text())["status"] == "PASS_INDEPENDENT_N131_HALFTRACE_CUBIC_AUDIT"
    result = {"status": "FROZEN_BEFORE_TWO_PAIR_ELIMINANT_CONTROLS",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "field": "GF(2)[t]/(t^131+t^13+t^2+t+1)",
              "fixed_seed_mask": fixed.SEED,
              "source_pairs": [row["masks"] for row in selected],
              "positive_block_outputs": POSITIVE,
              "negative_controls": "positive_output_xor_each_bit_1_through_32",
              "one_worker": True, "wall_cap_seconds": 120,
              "rss_cap_bytes": 4 * 1024**3,
              "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save(HERE / "protocol.json", result)
    print(json.dumps({"status": result["status"], "positive_blocks": len(POSITIVE)}))


def checked_protocol():
    result = json.loads((HERE / "protocol.json").read_text())
    assert result["status"] == "FROZEN_BEFORE_TWO_PAIR_ELIMINANT_CONTROLS"
    assert result["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    return result


def circuit_gate(left, right, selected):
    circuit = KaratsubaCircuit(fixed.N, [0, 1, 2, 13])
    algebra = Algebra(circuit, cubic.Field(), dense_and_threshold=3000)
    first = [circuit.variable() for _ in range(17)]
    second = [circuit.variable() for _ in range(17)]
    output = [circuit.variable() for _ in range(fixed.N)]
    def expression(wires, images):
        return algebra.expression(zip(wires, images))
    def constant(value):
        return algebra.expression(((-1, value),))
    def scale(value, coefficient):
        return algebra.expression((wire, MUL(image, coefficient)) for wire, image in value.terms)
    def parameters(item, wires):
        k, _, t = pair_parameters(item)
        basis = [fixed.gf_frobenius(v, item["rotation"]) for v in fixed.product_basis()]
        p = expression(wires, basis)
        return k, p, t, scale(p, cubic.inverse(k)), constant(MUL(t, cubic.inverse(k)))
    k, p, t, alpha, beta = parameters(selected[0], first)
    ell, q, u, gamma, delta = parameters(selected[1], second)
    c = algebra.from_bits(output)
    c2 = algebra.square(c)
    A = algebra.add(algebra.mul(c2, algebra.mul(alpha, gamma)), c)
    B = algebra.mul(alpha, algebra.add(algebra.mul(c2, delta), algebra.one))
    C = algebra.mul(gamma, algebra.add(algebra.mul(c2, beta), algebra.one))
    D = algebra.add(algebra.mul(c2, algebra.add(algebra.mul(beta, delta), algebra.one)), beta, delta)
    L2 = algebra.add(scale(algebra.square(B), ell), algebra.mul(q, algebra.mul(B, A)), scale(algebra.square(A), u))
    L1 = algebra.mul(q, algebra.add(algebra.mul(B, C), algebra.mul(D, A)))
    L0 = algebra.add(scale(algebra.square(D), ell), algebra.mul(q, algebra.mul(D, C)), scale(algebra.square(C), u))
    R, S = algebra.add(algebra.mul(L2, alpha), L1), algebra.add(algebra.mul(L2, beta), L0)
    E = algebra.add(scale(algebra.square(S), k), algebra.mul(p, algebra.mul(S, R)), scale(algebra.square(R), t))
    circuit.require_zero(E.bits())
    return circuit, first, second, output


def run():
    protocol = checked_protocol()
    selected, chain = data()
    pair_outputs = [cubic.standard_reciprocal(z) for z in chain["pair_rotated_z"]]
    starts = time.monotonic()
    cases = []
    for block in range(4):
        index = 2 * block
        left, right = pair_parameters(selected[index]), pair_parameters(selected[index + 1])
        a, b = pair_outputs[index:index + 2]
        assert MUL(left[0], SQUARE(a)) ^ MUL(left[1], a) ^ left[2] == 0
        assert MUL(right[0], SQUARE(b)) ^ MUL(right[1], b) ^ right[2] == 0
        a2, b2 = a ^ MUL(left[1], cubic.inverse(left[0])), b ^ MUL(right[1], cubic.inverse(right[0]))
        positive = POSITIVE[block]
        assert s3(a, b, positive) == eliminate(left, right, positive) == 0
        coefficients = polynomial(left, right)
        assert len(coefficients) == 9 and coefficients[-1]
        assert polynomial_value(coefficients, positive) == 0
        roots = set()
        for x in (a, a2):
            for y in (b, b2):
                roots.update(s3_output_roots(x, y))
        assert len(roots) == 8 and positive in roots
        assert all(polynomial_value(coefficients, root) == 0 for root in roots)
        negative = 0
        for bit in range(1, 33):
            c = positive ^ (1 << bit)
            algebraic = eliminate(left, right, c) == 0
            enumerated = any(s3(x, y, c) == 0 for x in (a, a2) for y in (b, b2))
            assert algebraic == enumerated
            negative += not algebraic
        cases.append({"block": block, "positive_output": positive,
                      "polynomial_degree": len(coefficients) - 1,
                      "nonzero_coefficient_positions":
                          [bit for bit, value in enumerate(coefficients) if value],
                      "distinct_exact_roots": len(roots),
                      "negative_controls_rejected": negative})
    circuit, first, second, output = circuit_gate(
        pair_parameters(selected[0]), pair_parameters(selected[1]), selected[:2])
    initial = {}
    for wires, value in ((first, fixed.selector_code(selected[0]["masks"][0])),
                         (second, fixed.selector_code(selected[1]["masks"][0])),
                         (output, POSITIVE[0])):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(wires)})
    checked = cubic.check_assignment(circuit, cubic.complete_assignment(circuit, initial))
    result = {"status": "PASS_EXACT_N131_TWO_PAIR_ELIMINANT",
              "candidate_id": None, "curve_id": protocol["curve_id"],
              "cases": cases, "positive_controls": len(cases),
              "negative_controls": sum(row["negative_controls_rejected"] for row in cases),
              "circuit_gate": {"and_gates": circuit.and_count,
                               "variables": circuit.next_var - 1,
                               "clauses": len(circuit.clauses),
                               "native_xor_rows": len(circuit.xors),
                               "assignment_check": checked},
              "wall_seconds_exploratory": time.monotonic() - starts,
              "peak_rss_bytes": psutil.Process().memory_info().rss,
              "protocol_sha256": sha(HERE / "protocol.json")}
    assert result["wall_seconds_exploratory"] < protocol["wall_cap_seconds"]
    assert result["peak_rss_bytes"] < protocol["rss_cap_bytes"]
    save(HERE / "result.json", result)
    print(json.dumps({"status": result["status"], "gate": result["circuit_gate"],
                      "negative_controls": result["negative_controls"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "run"))
    args = parser.parse_args()
    {"freeze": freeze, "run": run}[args.mode]()
