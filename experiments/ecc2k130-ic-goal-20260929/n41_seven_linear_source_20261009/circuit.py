"""Seven source-point S3 chain after factoring (1 + Frobenius) from the target."""

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


def build(circuit, bases_u, columns, target_us):
    if (len(bases_u) != BLOCKS or len(columns) != BLOCKS or
            len(target_us) != 4 or any(len(row) != WIDTH for row in bases_u)):
        raise ValueError("seven W6 source blocks and four target lifts required")
    masks = [[circuit.variable() for _ in range(WIDTH)] for _ in range(BLOCKS)]
    flags = [circuit.variable() for _ in range(4)]
    one_hot(circuit, flags)
    middle = [[circuit.variable() for _ in range(N)] for _ in range(5)]
    leaves = []
    for i, row in enumerate(masks):
        for code in range(1 << WIDTH):
            if code not in columns[i]:
                literals = [(-wire if code >> bit & 1 else wire)
                            for bit, wire in enumerate(row)]
                circuit.clauses.append(" ".join(map(str, literals)) + " 0")
        # For raw x = 1 + 1/u, the transformed x-coordinate is u itself.
        leaves.append(circuit.linear_element(row, bases_u[i]))
    duplicate_clauses = 0
    for i in range(BLOCKS):
        for j in range(i + 1, BLOCKS):
            for code_i, column_i in columns[i].items():
                for code_j, column_j in columns[j].items():
                    if column_i != column_j:
                        continue
                    literals = [(-wire if code_i >> bit & 1 else wire)
                                for bit, wire in enumerate(masks[i])]
                    literals += [(-wire if code_j >> bit & 1 else wire)
                                 for bit, wire in enumerate(masks[j])]
                    circuit.clauses.append(" ".join(map(str, literals)) + " 0")
                    duplicate_clauses += 1
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
            "middle": middle, "duplicate_column_clauses": duplicate_clauses,
            "primary_variables": BLOCKS*WIDTH + 4 + 5*N}
