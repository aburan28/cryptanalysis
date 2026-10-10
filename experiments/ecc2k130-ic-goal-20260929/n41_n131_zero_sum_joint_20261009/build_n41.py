#!/usr/bin/env python3
"""Build an implicit, target-conditioned four-triple XCNF on the public N41 point."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n41_n131_zero_sum_triple_20261009"
ROOT = HERE.parents[2]
KARATSUBA = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py"
CIRCUIT = ROOT / "experiments/koblitz-s5-invariant-20260924/circuit_sat.py"
sys.path.insert(0, str(KARATSUBA.parent))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402

N, D, ORDER = 41, 7, 549756390943
ROTATIONS = (0, 10, 20, 30)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def false_or_true(circuit, wire, required):
    if wire == (-1 if required else 0):
        return
    if wire == (0 if required else -1):
        circuit.clauses.append("0")
        return
    circuit.clauses.append(f"{wire if required else -wire} 0")


def negate(circuit, wire):
    return circuit.xor((wire, -1))


def disjoin(circuit, left, right):
    return negate(circuit, circuit.and_(negate(circuit, left),
                                        negate(circuit, right)))


def less_than(circuit, left, right):
    equal, smaller = -1, 0
    for a, b in reversed(tuple(zip(left, right))):
        first = circuit.and_(equal, circuit.and_(negate(circuit, a), b))
        smaller = disjoin(circuit, smaller, first)
        equal = circuit.and_(equal, negate(circuit, circuit.xor((a, b))))
    false_or_true(circuit, smaller, True)


def require_chart(circuit, row):
    # Field element differs from zero and one in polynomial basis.
    assert all(wire > 0 for wire in row)
    circuit.clauses.append(" ".join(map(str, row)) + " 0")
    circuit.clauses.append(" ".join([str(-row[0])] +
                                    list(map(str, row[1:]))) + " 0")


def require_allowed_mask(circuit, row, allowed):
    for mask in range(1 << D):
        if mask in allowed:
            continue
        circuit.clauses.append(" ".join(
            str(-wire if (mask >> i) & 1 else wire)
            for i, wire in enumerate(row)) + " 0")


def one_hot(circuit, flags):
    circuit.clauses.append(" ".join(map(str, flags)) + " 0")
    for i in range(len(flags)):
        for j in range(i + 1, len(flags)):
            circuit.clauses.append(f"-{flags[i]} -{flags[j]} 0")


def low_power_product(circuit, left, right, basis):
    # w1*w2 lives in a 13-dimensional degree-2..14 polynomial product space.
    product_bits = [circuit.xor(circuit.and_(left[i], right[j])
                                for i in range(D) for j in range(D)
                                if i + j == degree)
                    for degree in range(2*D - 1)]
    return circuit.linear_element(product_bits, basis)


def triple_quartic(circuit, u1, u2, w_product, output):
    """Six-product resultant, including one low-power product outside this call.

    q=w1*w2, s=u1+u2, r=(s^2+s)(z^2+z), f=(s+z)^2,
    C=q*f+s^2*r. The exact eliminant is
    F=(C+f+s^2)^2+(q+r)*C.
    """
    s = circuit.add(u1, u2)
    ss = circuit.square(s)
    wz = circuit.add(circuit.square(output), output)
    r = circuit.mul(circuit.add(ss, s), wz)
    f = circuit.square(circuit.add(s, output))
    c = circuit.add(circuit.mul(w_product, f), circuit.mul(ss, r))
    resultant = circuit.add(circuit.square(circuit.add(
        circuit.add(c, f), ss)), circuit.mul(circuit.add(w_product, r), c))
    circuit.require_zero(resultant)


def s3(circuit, left, middle, right):
    first = circuit.add(circuit.square(left), left)
    second = circuit.add(circuit.square(middle), middle)
    third = circuit.add(circuit.square(right), right)
    total = circuit.add(circuit.add(left, middle), right)
    circuit.require_zero(circuit.add(
        circuit.mul(circuit.mul(first, second), third),
        circuit.square(total)))


def read_input():
    path = SOURCE / "input_public.txt"
    lines = path.read_text().splitlines()
    qx, qy, order, blocks = map(int, lines[0].split())
    assert order == ORDER and blocks == 4
    allowed = None
    position = 1
    for rotation in ROTATIONS:
        actual, count = map(int, lines[position].split())
        assert actual == rotation and count == 126
        position += 1
        block = [tuple(map(int, lines[position+i].split())) for i in range(count)]
        position += count
        accepted = {row[0] for row in block}
        assert len(accepted) == 63
        assert all({row[1] for row in block if row[0] == mask} == {0, 1}
                   for mask in accepted)
        if allowed is None:
            allowed = accepted
        else:
            assert accepted == allowed
    assert position == len(lines)
    return qx, qy, allowed


def build(mode):
    output = HERE / f"{mode}.xcnf"
    receipt = HERE / f"{mode}_build.json"
    if output.exists() or receipt.exists():
        raise FileExistsError("preserve previous formula and build receipt")
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    qx, qy, allowed = read_input()
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**N, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(ring([(int(value) >> i) & 1 for i in range(N)]))

    target = curve(decode(qx), decode(qy))
    assert ORDER*target == curve(0)
    torsion = curve(field(1), field(1))
    assert 4*torsion == curve(0) and 2*torsion != curve(0)
    subgroup_preimage = pow(4, -1, ORDER)*target
    targets = [subgroup_preimage + i*torsion for i in range(4)]
    assert len(set(targets)) == 4 and all(4*point == target for point in targets)
    target_us = [encode(1/(point[0]+1)) for point in targets]
    assert all(value not in (0, 1) for value in target_us)

    def half_trace(value):
        answer = field.zero()
        for _ in range((N + 1)//2):
            answer += value
            value = value**4
        return answer

    started = time.monotonic_ns()
    circuit = KaratsubaCircuit(N, [0, 3])
    output_rows, mask_rows = [], []
    for rotation in ROTATIONS:
        a = [circuit.variable() for _ in range(D)]
        b = [circuit.variable() for _ in range(D)]
        third = [circuit.xor((x, y)) for x, y in zip(a, b)]
        less_than(circuit, a, b)
        less_than(circuit, b, third)
        for row in (a, b, third):
            require_allowed_mask(circuit, row, allowed)
        half_basis = [encode(half_trace(field(t**(i+1)))**(2**rotation))
                      for i in range(D)]
        product_basis = [encode(field(t**(i+2))**(2**rotation))
                         for i in range(2*D - 1)]
        u1 = circuit.linear_element(a, half_basis)
        u2 = circuit.linear_element(b, half_basis)
        q = low_power_product(circuit, a, b, product_basis)
        z = [circuit.variable() for _ in range(N)]
        require_chart(circuit, z)
        triple_quartic(circuit, u1, u2, q, z)
        output_rows.append(z)
        mask_rows.append((a, b))

    h01 = [circuit.variable() for _ in range(N)]
    h23 = [circuit.variable() for _ in range(N)]
    for row in (h01, h23):
        require_chart(circuit, row)
    flags = [circuit.variable() for _ in range(4)]
    one_hot(circuit, flags)
    target_u = circuit.linear_element(flags, target_us)
    s3(circuit, output_rows[0], output_rows[1], h01)
    s3(circuit, output_rows[2], output_rows[3], h23)
    s3(circuit, h01, h23, target_u)

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
    else:
        assert mode == "public"

    build_ns = time.monotonic_ns() - started
    circuit.write(output)
    metadata = {
        "status": "BUILT", "mode": mode, "proposal_id": "Q20261009200400",
        "candidate_id": None, "target_count": 1,
        "target": [qx, qy], "target_u_fiber": target_us,
        "rotations": list(ROTATIONS), "source_dimension": D,
        "accepted_masks": len(allowed),
        "mask_order": "a<b<a XOR b in each block",
        "control_masks": control_masks,
        "mask_wire_rows": [[list(a), list(b)] for a, b in mask_rows],
        "block_output_wire_rows": output_rows,
        "middle_wire_rows": [h01, h23],
        "target_flag_wires": flags,
        "primary_mask_bits": 4*2*D,
        "formula_variables": circuit.next_var - 1,
        "cnf_clauses": len(circuit.clauses),
        "native_xor_rows": len(circuit.xors),
        "and_gates": circuit.and_count,
        "build_ns": build_ns,
        "formula_bytes": output.stat().st_size,
        "sha256": {"source": sha(__file__), "xcnf": sha(output),
                   "input_public": sha(SOURCE / "input_public.txt"),
                   "runtime": sha(HERE / "sage_runtime_info.json"),
                   "karatsuba": sha(KARATSUBA), "circuit": sha(CIRCUIT)},
    }
    if mode == "control":
        metadata["sha256"]["public_witness"] = sha(SOURCE / "public/result.json")
    receipt.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: metadata[key] for key in
                      ("status", "mode", "formula_variables", "cnf_clauses",
                       "native_xor_rows", "and_gates", "build_ns",
                       "formula_bytes")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("public", "control"))
    build(parser.parse_args().mode)
