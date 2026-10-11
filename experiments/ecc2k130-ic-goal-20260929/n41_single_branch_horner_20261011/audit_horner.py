"""Replay Horner-emitted A/B wires against direct GF(2^41) monomials."""

import hashlib
import json
import random
from pathlib import Path

from circuit import Field, NORM, compile_quartic
from run import HERE, KaratsubaCircuit, complete_assignment, save


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def direct(field, terms, arguments):
    powers = [[1] for _ in arguments]
    for axis, degree in enumerate(map(max, zip(*terms))):
        for _ in range(degree):
            powers[axis].append(field.mul(powers[axis][-1], arguments[axis]))
    result = 0
    for term in terms:
        product = 1
        for axis, exponent in enumerate(term):
            product = field.mul(product, powers[axis][exponent])
        result ^= product
    return result


def decode(wires, assignment):
    return sum((1 if wire == -1 else 0 if wire == 0 else assignment[wire]) << bit
               for bit, wire in enumerate(wires))


def main():
    norm = json.loads(NORM.read_text())
    circuit = KaratsubaCircuit(41, [0, 3])
    inputs = [[circuit.variable() for _ in range(41)] for _ in range(5)]
    outputs = compile_quartic(circuit, inputs, norm)
    field = Field()
    rng = random.Random(20261011)
    vectors = [(0, 0, 0, 0, 0), (1, 1, 1, 1, 1)]
    vectors += [tuple(rng.getrandbits(41) for _ in range(5)) for _ in range(14)]
    for arguments in vectors:
        primary = {wire: arguments[axis] >> bit & 1
                   for axis, row in enumerate(inputs) for bit, wire in enumerate(row)}
        assignment = complete_assignment(circuit, primary)
        for output, terms in zip(outputs[:2], (norm["A_terms"], norm["B_terms"])):
            assert decode(output, assignment) == direct(field, terms, arguments)
    record = {
        "status": "PASS_16_DIRECT_FIELD_EVALUATIONS",
        "field": "GF(2)[t]/(t^41+t^3+1)",
        "input_law": "zero vector, unit vector, then 14 uniform 41-bit tuples",
        "seed": 20261011,
        "quartic_field_multiplications_per_block": outputs[2],
        "quartic_field_squares_per_block": outputs[3],
        "variables": circuit.next_var - 1,
        "and_gates": circuit.and_count,
        "source_sha256": {"circuit.py": digest(HERE / "circuit.py"),
                          "norm_result.json": digest(NORM),
                          "audit_horner.py": digest(__file__)},
    }
    save(HERE / "audit_result.json", record)
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
