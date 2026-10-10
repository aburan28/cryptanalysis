#!/usr/bin/env python3
"""Build functional two-root triple blocks joined by the public target S5."""

import hashlib
import json
from pathlib import Path
import sys
import time

import psutil
from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
JOINT = GOAL / "n41_n131_zero_sum_joint_20261009"
SOURCE = GOAL / "n41_n131_zero_sum_triple_20261009"
ROOT = HERE.parents[2]
sys.path[:0] = [str(JOINT), str(GOAL),
                str(ROOT / "experiments/koblitz-polynomial-w-pair-20260925")]

from build_n41 import (D, N, ORDER, ROTATIONS, false_or_true, less_than,
                       low_power_product, one_hot, read_input,
                       require_allowed_mask)
from build_s5 import target_ended_s5
from karatsuba_circuit import KaratsubaCircuit
from n41_lowpower_w8_s6_circuit import nonzero_nonone, pair_root_product
from functional_pair_root_circuit import pair_root


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    outputs = [HERE / name for name in (
        "public.xcnf", "public_build.json", "control.xcnf", "control_build.json")]
    if any(path.exists() for path in outputs):
        raise FileExistsError("preserve previous forward circuit build")
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    chart = json.loads((HERE / "forward_chart.json").read_text())
    assert runtime["status"] == "verified"
    assert chart["status"] == "PASS_FORWARD_ROOT_CHART"
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
        answer = field.zero()
        for _ in range((N + 1)//2):
            answer += value
            value = value**4
        return answer

    target = curve(decode(qx), decode(qy))
    assert ORDER*target == curve(0)
    torsion = curve(field(1), field(1))
    start = pow(4, -1, ORDER)*target
    fiber = [start + i*torsion for i in range(4)]
    assert len(set(fiber)) == 4 and all(4*point == target for point in fiber)
    target_us = [encode(1/(point[0]+1)) for point in fiber]
    bases = [
        ([encode(half_trace(field(t**(i+1)))**(2**rotation))
          for i in range(D)],
         [encode(field(t**(i+2))**(2**rotation))
          for i in range(2*D-1)])
        for rotation in ROTATIONS]
    process = psutil.Process()

    for mode in ("public", "control"):
        started = time.monotonic_ns()
        circuit = KaratsubaCircuit(N, [0, 3])
        original_and = circuit.and_
        operations = [0]

        def guarded_and(a, b):
            operations[0] += 1
            if operations[0] % 8192 == 0 and \
                    process.memory_info().rss >= 3_758_096_384:
                raise MemoryError("forward circuit builder reached RSS guard")
            return original_and(a, b)

        circuit.and_ = guarded_and
        mask_rows, pair_rows, block_rows, branch_rows = [], [], [], []
        for half_basis, product_basis in bases:
            a = [circuit.variable() for _ in range(D)]
            b = [circuit.variable() for _ in range(D)]
            third = [circuit.xor((x, y)) for x, y in zip(a, b)]
            less_than(circuit, a, b)
            less_than(circuit, b, third)
            for row in (a, b, third):
                require_allowed_mask(circuit, row, allowed)
            u1 = circuit.linear_element(a, half_basis)
            u2 = circuit.linear_element(b, half_basis)
            s = circuit.add(u1, u2)
            product = low_power_product(circuit, a, b, product_basis)
            pair_u, first = pair_root_product(circuit, product, u1, u2)
            nonzero_nonone(circuit, pair_u)
            wp = circuit.add(circuit.square(pair_u), pair_u)
            ws = circuit.add(circuit.square(s), s)
            block_u, second = pair_root(circuit, wp, ws, pair_u, s)
            nonzero_nonone(circuit, block_u)
            mask_rows.append((a, b))
            pair_rows.append(pair_u)
            block_rows.append(block_u)
            branch_rows.append([first["root_branch"], second["root_branch"]])
        flags = [circuit.variable() for _ in range(4)]
        one_hot(circuit, flags)
        target_u = circuit.linear_element(flags, target_us)
        target_ended_s5(circuit, block_rows + [target_u])
        control_masks = None
        if mode == "control":
            control_masks = chart["source_masks"]
            for (a, b), triple in zip(mask_rows, control_masks):
                assert triple[0] ^ triple[1] == triple[2]
                for wires, mask in ((a, triple[0]), (b, triple[1])):
                    for i, wire in enumerate(wires):
                        false_or_true(circuit, wire, bool((mask >> i) & 1))
        build_ns = time.monotonic_ns() - started
        formula = HERE / f"{mode}.xcnf"
        receipt_path = HERE / f"{mode}_build.json"
        circuit.write(formula)
        receipt = {
            "status": "BUILT", "mode": mode,
            "proposal_id": "Q20261009220100", "candidate_id": None,
            "target_count": 1, "target": [qx, qy],
            "target_u_fiber": target_us,
            "rotations": list(ROTATIONS), "source_dimension": D,
            "accepted_masks": len(allowed),
            "control_masks": control_masks,
            "mask_wire_rows": [[list(a), list(b)] for a, b in mask_rows],
            "pair_output_wire_rows": pair_rows,
            "block_output_wire_rows": block_rows,
            "root_branch_wires": branch_rows,
            "target_flag_wires": flags,
            "formula_variables": circuit.next_var - 1,
            "cnf_clauses": len(circuit.clauses),
            "native_xor_rows": len(circuit.xors),
            "and_gates": circuit.and_count,
            "build_ns": build_ns,
            "builder_peak_rss_bytes": process.memory_info().rss,
            "formula_bytes": formula.stat().st_size,
            "sha256": {"source": sha(__file__),
                       "formula": sha(formula),
                       "runtime": sha(HERE / "sage_runtime_info.json"),
                       "forward_chart": sha(HERE / "forward_chart.json"),
                       "input_public": sha(SOURCE / "input_public.txt"),
                       "joint_block_builder": sha(JOINT / "build_n41.py"),
                       "joint_s5_builder": sha(JOINT / "build_s5.py"),
                       "karatsuba": sha(ROOT / "experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py"),
                       "root_circuit": sha(GOAL / "functional_pair_root_circuit.py"),
                       "inverse_circuit": sha(GOAL / "functional_inverse_circuit.py")},
        }
        if mode == "control":
            receipt["sha256"]["public_witness"] = sha(SOURCE / "public/result.json")
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(json.dumps({key: receipt[key] for key in
                          ("status", "mode", "formula_variables",
                           "cnf_clauses", "native_xor_rows", "and_gates",
                           "build_ns", "formula_bytes",
                           "builder_peak_rss_bytes")}, sort_keys=True),
              flush=True)


if __name__ == "__main__":
    main()
