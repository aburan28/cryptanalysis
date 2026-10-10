"""Ten W14 diagonal atoms in a sparse reciprocal S3 tree."""

N = 131
WIDTH = 14
ATOMS = 10


def forbid(code, wires):
    return " ".join(str(-wire if code >> i & 1 else wire)
                    for i, wire in enumerate(wires)) + " 0"


def nonzero(circuit, bits):
    circuit.clauses.append(" ".join(map(str, bits)) + " 0")


def sparse_leaf_product(circuit, left_bits, right_bits, left_basis, right_basis):
    buckets = [[] for _ in range(circuit.n)]
    for i, a in enumerate(left_bits):
        for j, b in enumerate(right_bits):
            gate = circuit.and_(a, b)
            raw = 0
            x, y = left_basis[i], right_basis[j]
            while y:
                if y & 1:
                    raw ^= x
                x <<= 1
                y >>= 1
            value = circuit.reduce(raw)
            while value:
                low = value & -value
                buckets[low.bit_length()-1].append(gate)
                value ^= low
    return [circuit.xor(bucket) for bucket in buckets]


def reciprocal_s3(circuit, left, right, output, pair_product=None):
    product = circuit.mul(pair_product if pair_product is not None
                          else circuit.mul(left, right), output)
    s = circuit.add(circuit.add(left, right), output)
    circuit.require_zero(circuit.add(circuit.add(circuit.square(s), product),
                                     circuit.square(product)))


def build(circuit, bases_w, columns, target_reciprocals):
    if (circuit.n != N or len(bases_w) != ATOMS or
            len(target_reciprocals) != 4 or len(columns) != 8220):
        raise ValueError("invalid N131 diagonal sparse configuration")
    masks = [[circuit.variable() for _ in range(WIDTH)] for _ in range(ATOMS)]
    flags = [circuit.variable() for _ in range(4)]
    nonzero(circuit, flags)
    for i in range(4):
        for j in range(i+1, 4):
            circuit.clauses.append(f"-{flags[i]} -{flags[j]} 0")
    valid = set(columns)
    for row in masks:
        for code in range(1 << WIDTH):
            if code not in valid:
                circuit.clauses.append(forbid(code, row))
    aliases = {}
    for mask, column in columns.items():
        aliases.setdefault(column, []).append(mask)
    duplicate_clauses = 0
    for i in range(ATOMS):
        for j in range(i+1, ATOMS):
            for group in aliases.values():
                for a in group:
                    for b in group:
                        circuit.clauses.append(forbid(a, masks[i])[:-2] +
                                               " " + forbid(b, masks[j]))
                        duplicate_clauses += 1
    leaves = [circuit.linear_element(row, basis)
              for row, basis in zip(masks, bases_w)]
    middle = [[circuit.variable() for _ in range(N)] for _ in range(8)]
    for row in middle:
        nonzero(circuit, row)
    target = circuit.linear_element(flags, target_reciprocals)
    for i in range(5):
        pair_product = sparse_leaf_product(
            circuit, masks[2*i], masks[2*i+1],
            bases_w[2*i], bases_w[2*i+1])
        reciprocal_s3(circuit, leaves[2*i], leaves[2*i+1],
                      middle[i], pair_product)
    reciprocal_s3(circuit, middle[0], middle[1], middle[5])
    reciprocal_s3(circuit, middle[2], middle[3], middle[6])
    reciprocal_s3(circuit, middle[5], middle[6], middle[7])
    reciprocal_s3(circuit, middle[7], middle[4], target)
    return {"masks": masks, "flags": flags, "middle": middle,
            "duplicate_column_clauses": duplicate_clauses,
            "primary_variables": ATOMS*WIDTH+4+8*N,
            "chain": "five diagonal pairs, three upper joins, target join"}
