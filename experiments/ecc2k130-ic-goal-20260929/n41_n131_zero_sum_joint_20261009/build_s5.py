#!/usr/bin/env python3
"""Build zero-sum triple blocks joined by a direct target-ended S5 invariant."""

import hashlib
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing

from build_n41 import (D, HERE, N, ORDER, ROTATIONS, ROOT, SOURCE,
                       false_or_true, less_than, low_power_product, one_hot,
                       read_input, require_allowed_mask, require_chart,
                       triple_quartic)
from karatsuba_circuit import KaratsubaCircuit


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def add_many(circuit, elements):
    result = circuit.constant(0)
    for element in elements:
        result = circuit.add(result, element)
    return result


def target_ended_s5(circuit, values):
    assert len(values) == 5
    w = [circuit.add(circuit.square(value), value) for value in values]
    sum_u = add_many(circuit, values)
    e = [circuit.constant(1)] + [circuit.constant(0) for _ in range(5)]
    for index, wi in enumerate(w):
        for k in range(index + 1, 0, -1):
            e[k] = circuit.add(e[k], circuit.mul(e[k-1], wi))
    v = circuit.square(sum_u)
    e3sq, e4sq, e5sq = (circuit.square(e[i]) for i in (3, 4, 5))
    constant = circuit.square(add_many(circuit, (
        circuit.mul(e[2], e[5]), e3sq, e5sq)))
    linear = circuit.mul(e[5], circuit.add(e3sq, e5sq))
    cubic = circuit.mul(e[5], e5sq)
    result = circuit.add(v, e[5])
    result = circuit.add(circuit.mul(result, v), e4sq)
    result = circuit.add(circuit.mul(result, v), linear)
    result = add_many(circuit, (circuit.mul(result, v), constant, cubic))
    circuit.require_zero(result)


def main():
    outputs = [HERE / name for name in (
        "s5_public.xcnf", "s5_public_build.json",
        "s5_control.xcnf", "s5_control_build.json")]
    if any(path.exists() for path in outputs):
        raise FileExistsError("preserve previous S5 formulas")
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    audit = json.loads((HERE / "s5_identity.json").read_text())
    assert runtime["status"] == "verified"
    assert audit["status"] == "PASS_EXACT_S5_CHART"
    qx, qy, allowed = read_input()
    polynomial = PolynomialRing(GF(2), "t")
    t = polynomial.gen()
    field = GF(2**N, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(polynomial([(int(value) >> i) & 1 for i in range(N)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def half_trace(value):
        result = field.zero()
        for _ in range((N + 1)//2):
            result += value
            value = value**4
        return result

    target = curve(decode(qx), decode(qy))
    assert ORDER*target == curve(0)
    torsion = curve(field(1), field(1))
    assert 4*torsion == curve(0) and 2*torsion != curve(0)
    base = pow(4, -1, ORDER)*target
    fiber = [base + i*torsion for i in range(4)]
    assert len(set(fiber)) == 4 and all(4*point == target for point in fiber)
    target_us = [encode(1/(point[0]+1)) for point in fiber]
    basis_by_block = [
        ([encode(half_trace(field(t**(i+1)))**(2**rotation))
          for i in range(D)],
         [encode(field(t**(i+2))**(2**rotation))
          for i in range(2*D-1)])
        for rotation in ROTATIONS]

    for mode in ("public", "control"):
        started = time.monotonic_ns()
        circuit = KaratsubaCircuit(N, [0, 3])
        output_rows, mask_rows = [], []
        for half_basis, product_basis in basis_by_block:
            a = [circuit.variable() for _ in range(D)]
            b = [circuit.variable() for _ in range(D)]
            third = [circuit.xor((x, y)) for x, y in zip(a, b)]
            less_than(circuit, a, b)
            less_than(circuit, b, third)
            for row in (a, b, third):
                require_allowed_mask(circuit, row, allowed)
            u1 = circuit.linear_element(a, half_basis)
            u2 = circuit.linear_element(b, half_basis)
            product = low_power_product(circuit, a, b, product_basis)
            z = [circuit.variable() for _ in range(N)]
            require_chart(circuit, z)
            triple_quartic(circuit, u1, u2, product, z)
            mask_rows.append((a, b))
            output_rows.append(z)
        flags = [circuit.variable() for _ in range(4)]
        one_hot(circuit, flags)
        target_u = circuit.linear_element(flags, target_us)
        target_ended_s5(circuit, output_rows + [target_u])
        control_masks = None
        if mode == "control":
            row = json.loads((SOURCE / "public/result.json").read_text())["row"]
            control_masks = [[leaf["mask"] for leaf in row[3*i:3*i+3]]
                             for i in range(4)]
            for (a, b), triple in zip(mask_rows, control_masks):
                assert triple[0] ^ triple[1] == triple[2]
                for wires, mask in ((a, triple[0]), (b, triple[1])):
                    for i, wire in enumerate(wires):
                        false_or_true(circuit, wire, bool((mask >> i) & 1))
        build_ns = time.monotonic_ns() - started
        formula = HERE / f"s5_{mode}.xcnf"
        receipt_path = HERE / f"s5_{mode}_build.json"
        circuit.write(formula)
        receipt = {
            "status": "BUILT", "mode": mode,
            "proposal_id": "Q20261009205500", "candidate_id": None,
            "target_count": 1, "target": [qx, qy],
            "target_u_fiber": target_us,
            "rotations": list(ROTATIONS), "source_dimension": D,
            "accepted_masks": len(allowed),
            "control_masks": control_masks,
            "mask_wire_rows": [[list(a), list(b)] for a, b in mask_rows],
            "block_output_wire_rows": output_rows,
            "target_flag_wires": flags,
            "formula_variables": circuit.next_var - 1,
            "cnf_clauses": len(circuit.clauses),
            "native_xor_rows": len(circuit.xors),
            "and_gates": circuit.and_count,
            "build_ns": build_ns,
            "formula_bytes": formula.stat().st_size,
            "sha256": {"source": sha(__file__),
                       "helper": sha(HERE / "build_n41.py"),
                       "s5_audit": sha(HERE / "s5_identity.json"),
                       "runtime": sha(HERE / "sage_runtime_info.json"),
                       "input_public": sha(SOURCE / "input_public.txt"),
                       "karatsuba": sha(ROOT / "experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py"),
                       "circuit": sha(ROOT / "experiments/koblitz-s5-invariant-20260924/circuit_sat.py"),
                       "formula": sha(formula)},
        }
        if mode == "control":
            receipt["sha256"]["public_witness"] = sha(SOURCE / "public/result.json")
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(json.dumps({key: receipt[key] for key in
                          ("status", "mode", "formula_variables",
                           "cnf_clauses", "native_xor_rows", "and_gates",
                           "build_ns", "formula_bytes")}, sort_keys=True),
              flush=True)


if __name__ == "__main__":
    main()
