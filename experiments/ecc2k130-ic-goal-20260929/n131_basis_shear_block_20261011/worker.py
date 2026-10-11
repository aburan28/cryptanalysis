"""Build and witness-check one exact N131 W15 sheared quartic block."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASIS = ROOT / "n41_basis_shear_20261011"
sys.path.insert(0, str(BASIS))
sys.path.insert(0, str(ROOT.parent / "koblitz-polynomial-w-pair-20260925"))
from karatsuba_circuit import KaratsubaCircuit  # noqa: E402
from sparse import Algebra  # noqa: E402
import circuit as method  # noqa: E402

NORM = ROOT / "n41_quartic_joint_public_20261010" / "norm_result.json"
CONTROL = ROOT / "n41_quartic_joint_public_20261010" / "audit_result.json"
WITNESS = ROOT / "n131_w15_joint_block_resultant_20261010" / "restricted_result.json"


class Field:
    n = 131
    modulus = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1

    def mul(self, a, b):
        result = 0
        while b:
            if b & 1:
                result ^= a
            b >>= 1
            a <<= 1
            if a >> self.n:
                a ^= self.modulus
        return result

    def square(self, a):
        return self.mul(a, a)

    def frob(self, a, turns):
        for _ in range(turns):
            a = self.square(a)
        return a


def pair(circuit, field, algebra, left_mask, right_mask, rotation):
    basis = [1 << (j + 1) for j in range(15)]
    seed = [circuit.xor((a, b)) for a, b in zip(left_mask, right_mask)]
    a = algebra.expression((wire, field.frob(value, rotation))
                           for wire, value in zip(seed, basis))
    product_terms = []
    for diagonal in range(29):
        gates = [circuit.and_(left_mask[i], right_mask[j])
                 for i in range(15) for j in range(15) if i + j == diagonal]
        product_terms.append((circuit.xor(gates),
                              field.frob(1 << (diagonal + 2), rotation)))
    return seed, a, algebra.expression(product_terms)


def complete_assignment(circuit, initial):
    definitions = {int(out): ("and", int(a), int(b))
                   for (a, b), out in circuit.and_cache.items()}
    for line in circuit.xors:
        literals = [int(x) for x in line.split()[1:-1]]
        definitions[abs(literals[0])] = ("xor", literals)
    values = [None] * circuit.next_var
    for wire, bit in initial.items():
        values[wire] = int(bit)
    for wire in range(1, circuit.next_var):
        if values[wire] is not None:
            continue
        definition = definitions.get(wire)
        if definition is None:
            raise RuntimeError(f"unassigned primary wire {wire}")
        if definition[0] == "and":
            def value(x):
                return 1 if x == -1 else 0 if x == 0 else values[x]
            values[wire] = value(definition[1]) & value(definition[2])
        else:
            literals = definition[1]
            bit = int(literals[0] > 0)
            for literal in literals[1:]:
                bit ^= values[abs(literal)] ^ int(literal < 0)
            values[wire] = bit
    return values


def check_assignment(circuit, values):
    for row in circuit.clauses:
        literals = map(int, row.split()[:-1])
        assert any(values[abs(wire)] == int(wire > 0) for wire in literals)
    for row in circuit.xors:
        literals = map(int, row.split()[1:-1])
        assert sum(values[abs(wire)] ^ int(wire < 0) for wire in literals) & 1


def decode(wires, values):
    return sum((1 if wire == -1 else 0 if wire == 0 else values[wire]) << bit
               for bit, wire in enumerate(wires))


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    for name, path in protocol["source_paths"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == protocol["source_sha256"][name]
    norm = json.loads(NORM.read_text())
    control = json.loads(CONTROL.read_text())["n131_control"]
    witness = json.loads(WITNESS.read_text())
    known_masks = witness["masks"][4:8]
    assert known_masks == [5576, 8382, 3, 13685]
    field = Field()
    circuit = KaratsubaCircuit(131, [0, 1, 2, 13])
    algebra = Algebra(circuit, field)
    masks = [[circuit.variable() for _ in range(15)] for _ in range(4)]
    z_bits = [circuit.variable() for _ in range(131)]
    w_bits = [circuit.variable() for _ in range(131)]
    start = time.monotonic()
    _, a, P = pair(circuit, field, algebra, masks[0], masks[1], 26)
    _, b, Q = pair(circuit, field, algebra, masks[2], masks[3], 39)
    S = algebra.add(a, b)
    A, B = method.compile_quartic(algebra, (a, S, algebra.from_bits(z_bits), P, Q), norm)
    circuit.require_zero(circuit.add(A.bits(), algebra.mul(algebra.from_bits(w_bits), B).bits()))
    circuit.require_zero([circuit.xor(row) for row in zip(circuit.square(w_bits),
                                                          w_bits, z_bits, S.bits())])
    construction_seconds = time.monotonic() - start
    initial = {wire: value >> bit & 1
               for row, value in zip(masks, known_masks)
               for bit, wire in enumerate(row)}
    initial.update({wire: control["z"] >> bit & 1 for bit, wire in enumerate(z_bits)})
    initial.update({wire: control["existential_branch_witness"] >> bit & 1
                    for bit, wire in enumerate(w_bits)})
    assert len(initial) == 4 * 15 + 2 * 131
    assignment_start = time.monotonic()
    values = complete_assignment(circuit, initial)
    check_assignment(circuit, values)
    assignment_seconds = time.monotonic() - assignment_start
    assert decode(A.bits(), values) == control["A"]
    assert decode(B.bits(), values) == control["B"]
    assert decode(S.bits(), values) == control["a"] ^ control["b"]
    assert decode(P.bits(), values) == control["P"]
    assert decode(Q.bits(), values) == control["Q"]
    result = {"status": "PASS_N131_W15_BLOCK_EXACT_ASSIGNMENT",
              "field": "GF(2)[t]/(t^131+t^13+t^2+t+1)",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "rotations": [26, 39], "masks": known_masks,
              "z": control["z"], "w": control["existential_branch_witness"],
              "variables": circuit.next_var - 1, "and_gates": circuit.and_count,
              "clauses": len(circuit.clauses), "native_xor_rows": len(circuit.xors),
              "quartic_sparse_multiplications": algebra.sparse_mul_calls,
              "quartic_generic_multiplications": algebra.generic_mul_calls,
              "quartic_sparse_pair_products": algebra.sparse_pair_products,
              "construction_seconds_exploratory": construction_seconds,
              "assignment_seconds_exploratory": assignment_seconds,
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (HERE / "worker_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "and_gates": result["and_gates"],
                      "variables": result["variables"]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
