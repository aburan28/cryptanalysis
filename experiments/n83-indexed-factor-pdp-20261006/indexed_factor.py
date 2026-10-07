"""Exact ordered-coordinate encoding of a weight-3-or-4 normal mask.

Three positions are in 0..n-1. The fourth is larger than the third and is
either in 0..n-1 or the sentinel n. The sentinel contributes zero to x.
Each mask therefore has one positional witness, with no permutation copies.
"""

from __future__ import annotations


def _choice(circuit, width: int, allowed: range) -> dict:
    bits = [circuit.variable() for _ in range(width)]
    onehot = {}
    for value in allowed:
        wire = circuit.variable()
        literals = [bit if value & (1 << place) else -bit
                    for place, bit in enumerate(bits)]
        # wire iff the binary index has this value.
        circuit.clauses.extend(f"-{wire} {literal} 0" for literal in literals)
        circuit.clauses.append(" ".join(str(-literal) for literal in literals)
                               + f" {wire} 0")
        onehot[value] = wire
    # Reject all unused binary codes. Distinct codes cannot both be true.
    circuit.clauses.append(" ".join(map(str, onehot.values())) + " 0")
    return {"bits": bits, "onehot": onehot}


def factor(circuit, conjugates: list[int]) -> dict:
    degree = len(conjugates)
    if degree < 4 or len(set(conjugates)) != degree:
        raise ValueError("need at least four distinct basis elements")
    width = degree.bit_length()
    positions = [_choice(circuit, width, range(degree)) for _ in range(3)]
    positions.append(_choice(circuit, width, range(degree + 1)))
    for left, right in zip(positions, positions[1:]):
        for earlier, left_wire in left["onehot"].items():
            for later, right_wire in right["onehot"].items():
                if earlier >= later:
                    circuit.clauses.append(f"-{left_wire} -{right_wire} 0")
    selectors = []
    values = []
    for position in positions:
        for index, wire in position["onehot"].items():
            if index < degree:
                selectors.append(wire)
                values.append(conjugates[index])
    return {
        "positions": positions,
        "x": circuit.linear_element(selectors, values),
        "sentinel": degree,
    }


def pin_positions(circuit, encoded: dict, mask: list[int]) -> None:
    degree = encoded["sentinel"]
    if len(mask) not in (3, 4) or sorted(set(mask)) != sorted(mask) or \
            any(index < 0 or index >= degree for index in mask):
        raise ValueError("mask must have three or four distinct in-range positions")
    values = sorted(mask) + ([degree] if len(mask) == 3 else [])
    for position, value in zip(encoded["positions"], values):
        for place, bit in enumerate(position["bits"]):
            circuit.clauses.append(f"{bit if value & (1 << place) else -bit} 0")


def decode_positions(model: dict[int, bool], encoded: dict) -> list[int]:
    values = [sum((1 << place) for place, bit in enumerate(position["bits"])
                  if model[bit]) for position in encoded["positions"]]
    degree = encoded["sentinel"]
    if not (0 <= values[0] < values[1] < values[2] < values[3] <= degree):
        raise ValueError("SAT model violates ordered position domain")
    return values[:3] if values[3] == degree else values
