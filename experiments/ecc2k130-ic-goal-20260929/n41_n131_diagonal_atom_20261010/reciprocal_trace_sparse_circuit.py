"""Eight diagonal atoms with sparse products and explicit trace pruning."""

N = 41
WIDTH = 6
ATOMS = 8


def nonzero(circuit, bits):
    circuit.clauses.append(" ".join(map(str, bits)) + " 0")


def one_hot(circuit, bits):
    nonzero(circuit, bits)
    for i in range(len(bits)):
        for j in range(i + 1, len(bits)):
            circuit.clauses.append(f"-{bits[i]} -{bits[j]} 0")


def field_square(circuit, value):
    polynomial = sum(1 << (2 * i) for i in range(circuit.n)
                     if value >> i & 1)
    return circuit.reduce(polynomial)


def field_trace(circuit, value):
    acc = 0
    for _ in range(circuit.n):
        acc ^= value
        value = field_square(circuit, value)
    assert acc in (0, 1)
    return acc


def trace_zero(circuit, bits):
    terms = [wire for i, wire in enumerate(bits)
             if field_trace(circuit, 1 << i)]
    circuit.require_zero([circuit.xor(terms)])


def sparse_leaf_product(circuit, left_bits, right_bits, left_basis, right_basis):
    buckets = [[] for _ in range(circuit.n)]
    for i, a in enumerate(left_bits):
        for j, b in enumerate(right_bits):
            gate = circuit.and_(a, b)
            # Both bases are field constants; use the same reduction as Circuit.
            polynomial = 0
            x, y = left_basis[i], right_basis[j]
            while y:
                if y & 1:
                    polynomial ^= x
                x <<= 1
                y >>= 1
            value = circuit.reduce(polynomial)
            while value:
                low = value & -value
                buckets[low.bit_length() - 1].append(gate)
                value ^= low
    return [circuit.xor(bucket) for bucket in buckets]


def reciprocal_s3(circuit, a, b, c, product_ab=None):
    """(a+b+c)^2 + abc + (abc)^2 = 0, with a,b,c=1/x."""
    product = circuit.mul(circuit.mul(a, b) if product_ab is None else product_ab, c)
    linear_square = circuit.square(circuit.add(circuit.add(a, b), c))
    circuit.require_zero(circuit.add(circuit.add(linear_square, product),
                                     circuit.square(product)))


def build(circuit, bases_w, mask_columns, target_reciprocals):
    assert len(bases_w) == len(mask_columns) == ATOMS
    assert len(target_reciprocals) == 4
    masks = [[circuit.variable() for _ in range(WIDTH)] for _ in range(ATOMS)]
    flags = [circuit.variable() for _ in range(4)]
    one_hot(circuit, flags)
    for flag, reciprocal in zip(flags, target_reciprocals):
        if field_trace(circuit, reciprocal):
            circuit.clauses.append(f"-{flag} 0")
    leaves = []
    for i, row in enumerate(masks):
        permitted = mask_columns[i]
        for code in range(1 << WIDTH):
            if code not in permitted:
                literals = [(-wire if code >> bit & 1 else wire)
                            for bit, wire in enumerate(row)]
                circuit.clauses.append(" ".join(map(str, literals)) + " 0")
        leaves.append(circuit.linear_element(row, bases_w[i]))
    for i in range(ATOMS):
        for j in range(i + 1, ATOMS):
            for code_i, col_i in mask_columns[i].items():
                for code_j, col_j in mask_columns[j].items():
                    if col_i != col_j:
                        continue
                    literals = [(-wire if code_i >> bit & 1 else wire)
                                for bit, wire in enumerate(masks[i])]
                    literals += [(-wire if code_j >> bit & 1 else wire)
                                 for bit, wire in enumerate(masks[j])]
                    circuit.clauses.append(" ".join(map(str, literals)) + " 0")
    middle = [[circuit.variable() for _ in range(N)] for _ in range(6)]
    for row in middle:
        nonzero(circuit, row)
        trace_zero(circuit, row)
    target = circuit.linear_element(flags, target_reciprocals)
    for i in range(4):
        product = sparse_leaf_product(circuit, masks[2*i], masks[2*i+1],
                                      bases_w[2*i], bases_w[2*i+1])
        reciprocal_s3(circuit, leaves[2*i], leaves[2*i+1], middle[i], product)
    reciprocal_s3(circuit, middle[0], middle[1], middle[4])
    reciprocal_s3(circuit, middle[2], middle[3], middle[5])
    reciprocal_s3(circuit, middle[4], middle[5], target)
    return {"masks": masks, "flags": flags, "middle": middle,
            "primary_variables": ATOMS * WIDTH + 4 + 6 * N,
            "chain": "four pair joins, two four-atom joins, one target join"}
