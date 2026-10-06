"""Exact Boolean weight-three-or-four constraint for an XCNF circuit."""

from __future__ import annotations


def require_weight_three_or_four(circuit, variables: list[int]) -> dict:
    """Constrain the count of true inputs to be 3 or 4.

    A binary ripple counter is exact because its width can represent every
    value from zero through len(variables), so it cannot overflow. The final
    selector ties the low three bits to 011 or 100 and clears higher bits.
    """
    if len(variables) < 4 or len(set(variables)) != len(variables):
        raise ValueError("weight-three-or-four requires at least four distinct inputs")
    width = len(variables).bit_length()
    count = [0] * width
    for value in variables:
        carry = value
        for bit in range(width):
            prior = count[bit]
            count[bit] = circuit.xor((prior, carry))
            carry = circuit.and_(prior, carry)
    choose_three = circuit.variable()
    circuit.require_zero([
        circuit.xor((count[0], choose_three)),
        circuit.xor((count[1], choose_three)),
        circuit.xor((count[2], choose_three, -1)),
        *count[3:],
    ])
    return {
        "count_bits": count,
        "choose_three": choose_three,
        "allowed_weights": [3, 4],
        "counter_width": width,
    }
