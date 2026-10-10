"""Seven same-sign Frobenius-diagonal pair blocks in a balanced S3 tree."""

N = 41
WIDTH = 6
BLOCKS = 7


def nonzero_nonone(circuit, row):
    circuit.clauses.append(" ".join(map(str, row)) + " 0")
    circuit.clauses.append(" ".join(map(str, row[1:])) + " 0")


def one_hot(circuit, row):
    circuit.clauses.append(" ".join(map(str, row)) + " 0")
    for i in range(len(row)):
        for j in range(i + 1, len(row)):
            circuit.clauses.append(f"-{row[i]} -{row[j]} 0")


def link(circuit, left, right, output):
    a = circuit.add(circuit.square(left), left)
    b = circuit.add(circuit.square(right), right)
    product = circuit.mul(a, b)
    lhs = circuit.mul(product, circuit.add(circuit.square(output), output))
    rhs = circuit.square(circuit.add(circuit.add(left, right), output))
    circuit.require_zero(circuit.add(lhs, rhs))


def build(circuit, bases_w, mask_columns, target_us):
    if (len(bases_w) != BLOCKS or len(mask_columns) != BLOCKS or
            len(target_us) != 4 or any(len(row) != WIDTH for row in bases_w)):
        raise ValueError("seven W6 diagonal blocks and four target lifts required")
    masks = [[circuit.variable() for _ in range(WIDTH)] for _ in range(BLOCKS)]
    flags = [circuit.variable() for _ in range(4)]
    one_hot(circuit, flags)
    leaves = [[circuit.variable() for _ in range(N)] for _ in range(BLOCKS)]
    middle = [[circuit.variable() for _ in range(N)] for _ in range(5)]

    for i, row in enumerate(masks):
        permitted = mask_columns[i]
        for code in range(1 << WIDTH):
            if code not in permitted:
                literals = [(-wire if code >> bit & 1 else wire)
                            for bit, wire in enumerate(row)]
                circuit.clauses.append(" ".join(map(str, literals)) + " 0")
        w = circuit.linear_element(row, bases_w[i])
        z = leaves[i]
        nonzero_nonone(circuit, z)
        # z = w/(w+1), exactly the x-coordinate of P + Frobenius(P)
        # under the transformed coordinate z = 1/(x+1).
        circuit.require_zero(circuit.add(
            circuit.mul(z, circuit.add(w, circuit.constant(1))), w))

    duplicate_column_clauses = 0
    for i in range(BLOCKS):
        for j in range(i + 1, BLOCKS):
            for code_i, column_i in mask_columns[i].items():
                for code_j, column_j in mask_columns[j].items():
                    if column_i != column_j:
                        continue
                    literals = [(-wire if code_i >> bit & 1 else wire)
                                for bit, wire in enumerate(masks[i])]
                    literals += [(-wire if code_j >> bit & 1 else wire)
                                 for bit, wire in enumerate(masks[j])]
                    circuit.clauses.append(" ".join(map(str, literals)) + " 0")
                    duplicate_column_clauses += 1

    for row in middle:
        nonzero_nonone(circuit, row)
    link(circuit, leaves[0], leaves[1], middle[0])
    link(circuit, leaves[2], leaves[3], middle[1])
    link(circuit, leaves[4], leaves[5], middle[2])
    link(circuit, middle[0], middle[1], middle[3])
    link(circuit, middle[3], middle[2], middle[4])
    target = circuit.linear_element(flags, target_us)
    link(circuit, middle[4], leaves[6], target)
    return {"masks": masks, "flags": flags, "leaves": leaves,
            "middle": middle, "target_us": target_us,
            "duplicate_column_clauses": duplicate_column_clauses,
            "primary_variables": BLOCKS * WIDTH + 4 + (BLOCKS + 5) * N,
            "chain": "three diagonal-pair joins, one four-block join, one six-block join, one target join"}
