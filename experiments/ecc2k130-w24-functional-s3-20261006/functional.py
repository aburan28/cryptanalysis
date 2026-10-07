"""Functional GF(2^131) inverse and complete S3 quadratic roots for XCNF."""

from functools import lru_cache

import arithmetic as a


def square_n(circuit, value, count):
    for _ in range(count):
        value = circuit.square(value)
    return value


def inverse_131(circuit, value):
    """Compute value^(2^131-2); zero maps to zero for branch handling."""
    assert circuit.n == a.N == 131
    b = {1: value}
    for k in (1, 2, 4, 8, 16, 32, 64):
        b[2*k] = circuit.mul(b[k], square_n(circuit, b[k], k))
    b130 = circuit.mul(b[128], square_n(circuit, b[2], 128))
    return circuit.square(b130)


def halftrace_unchecked(value):
    """Linear H on every field element, including trace-one inputs."""
    term = value
    result = 0
    for _ in range((a.N + 1)//2):
        result ^= term
        term = a.square(a.square(term))
    return result


@lru_cache(maxsize=1)
def halftrace_images():
    return tuple(halftrace_unchecked(1 << i) for i in range(a.N))


def is_zero_wire(circuit, value):
    occupied = 0
    for wire in value:
        # Boolean OR = left XOR right XOR (left AND right).
        occupied = circuit.xor((occupied, wire,
                                circuit.and_(occupied, wire)))
    return circuit.xor((occupied, -1))


def mux_element(circuit, selector, when_true, when_false):
    delta = circuit.add(when_true, when_false)
    return circuit.add(when_false, [circuit.and_(selector, bit)
                                    for bit in delta])


def s3_root(circuit, u1, w1, u2, w2, choice):
    """Build one complete quadratic root, including B=0 and B=1 cases."""
    b = circuit.mul(w1, w2)
    aa = circuit.add(b, circuit.constant(1))
    sum_u = circuit.add(u1, u2)
    cc = circuit.square(sum_u)
    b_zero = is_zero_wire(circuit, b)
    a_zero = is_zero_wire(circuit, aa)

    b_inv = inverse_131(circuit, b)
    a_inv = inverse_131(circuit, aa)
    s = circuit.mul(circuit.mul(cc, aa), circuit.square(b_inv))
    d = circuit.mul(b, a_inv)
    h = circuit.linear_element(s, halftrace_images())
    h[0] = circuit.xor((h[0], choice))
    regular = circuit.mul(d, h)
    root = mux_element(circuit, b_zero, sum_u, regular)
    root = mux_element(circuit, a_zero, cc, root)

    residual = circuit.add_many((circuit.mul(aa, circuit.square(root)),
                                 circuit.mul(b, root), cc))
    circuit.require_zero(residual)
    return root, circuit.add(circuit.square(root), root), (b_zero, a_zero)


def numeric_inverse_131(value):
    """Independent numeric shape check of the fixed exponent chain."""
    b = {1: value}
    for k in (1, 2, 4, 8, 16, 32, 64):
        term = b[k]
        for _ in range(k):
            term = a.square(term)
        b[2*k] = a.mul(b[k], term)
    term = b[2]
    for _ in range(128):
        term = a.square(term)
    return a.square(a.mul(b[128], term))


def numeric_s3_root(u1, u2, choice):
    w1, w2 = a.square(u1) ^ u1, a.square(u2) ^ u2
    b = a.mul(w1, w2)
    aa = b ^ 1
    cc = a.square(u1 ^ u2)
    if b == 0:
        root = u1 ^ u2
        branch = "B0"
    elif aa == 0:
        root = cc
        branch = "B1"
    else:
        s = a.mul(a.mul(cc, aa), a.square(a.inv(b)))
        h = halftrace_unchecked(s)
        d = a.mul(b, a.inv(aa))
        root = a.mul(d, h ^ int(bool(choice)))
        branch = "regular" if a.trace(s) == 0 else "trace_one"
    return root, branch, a.s3_cleared(u1, u2, root)
