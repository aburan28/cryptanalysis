"""Eight diagonal atoms with reciprocal-coordinate S3 links."""

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


def reciprocal_s3(circuit, a, b, c):
    """(a+b+c)^2 + abc + (abc)^2 = 0, with a,b,c=1/x."""
    product = circuit.mul(circuit.mul(a, b), c)
    linear_square = circuit.square(circuit.add(circuit.add(a, b), c))
    circuit.require_zero(circuit.add(circuit.add(linear_square, product),
                                     circuit.square(product)))


def build(circuit, bases_w, mask_columns, target_reciprocals):
    assert len(bases_w) == len(mask_columns) == ATOMS
    assert len(target_reciprocals) == 4
    masks = [[circuit.variable() for _ in range(WIDTH)] for _ in range(ATOMS)]
    flags = [circuit.variable() for _ in range(4)]
    one_hot(circuit, flags)
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
    target = circuit.linear_element(flags, target_reciprocals)
    for i in range(4):
        reciprocal_s3(circuit, leaves[2*i], leaves[2*i+1], middle[i])
    reciprocal_s3(circuit, middle[0], middle[1], middle[4])
    reciprocal_s3(circuit, middle[2], middle[3], middle[5])
    reciprocal_s3(circuit, middle[4], middle[5], target)
    return {"masks": masks, "flags": flags, "middle": middle,
            "primary_variables": ATOMS * WIDTH + 4 + 6 * N,
            "chain": "four pair joins, two four-atom joins, one target join"}
