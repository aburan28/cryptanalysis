"""Exact 9+9 one-hot source membership for the frozen N131 W18 circuit."""

from collections import defaultdict

D = 18
LOW = 9
GROUP = 6


def rows_from_codes(codes):
    rows = defaultdict(list)
    for code in codes:
        assert 0 <= code < 1 << D
        rows[code >> LOW].append(code & ((1 << LOW) - 1))
    return tuple(tuple(sorted(rows[index])) for index in range(1 << (D - LOW)))


def selectors(circuit, bits):
    """One-hot indicators in numeric mask order; each bit may be symbolic."""
    current = [-1]
    for bit in bits:
        complement = circuit.xor((bit, -1))
        following = [0] * (2 * len(current))
        for index, prefix in enumerate(current):
            following[index] = circuit.and_(prefix, complement)
            following[index + len(current)] = circuit.and_(prefix, bit)
        current = following
    return current


def emit(circuit, mask, rows):
    """Require membership using grouped parities of the low-half selectors."""
    assert len(mask) == D and len(rows) == 1 << (D - LOW)
    low = selectors(circuit, mask[:LOW])
    high = selectors(circuit, mask[LOW:])
    terms = []
    for upper, members in enumerate(rows):
        if not members:
            continue
        grouped = defaultdict(list)
        for lower in members:
            grouped[lower // GROUP].append(low[lower])
        row_wire = circuit.xor(circuit.xor(grouped[block]) for block in sorted(grouped))
        terms.append(circuit.and_(high[upper], row_wire))
    membership = circuit.xor(terms)
    circuit.require_zero([circuit.xor((membership, -1))])
    return membership
