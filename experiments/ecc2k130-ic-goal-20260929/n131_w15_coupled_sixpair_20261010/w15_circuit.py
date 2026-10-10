"""Six N131 W15 diagonal pairs with two shared XOR seed sums."""

N = 131
WIDTH = 15
ATOMS = 12


def forbid(code, wires):
    return " ".join(str(-wire if code >> i & 1 else wire)
                    for i, wire in enumerate(wires)) + " 0"


def nonzero(circuit, bits):
    circuit.clauses.append(" ".join(map(str, bits)) + " 0")


def reciprocal_s3(circuit, left, right, output):
    product = circuit.mul(circuit.mul(left, right), output)
    total = circuit.add(circuit.add(left, right), output)
    circuit.require_zero(circuit.add(circuit.add(circuit.square(total), product),
                                     circuit.square(product)))


def target_linear_s3(circuit, field, left, right, flags, target_values, target):
    """Square(a+b+target) + sum_i flag_i*A(ab*target_i) = 0."""
    ab = circuit.mul(left, right)
    gates, images = [], []
    for flag, target_value in zip(flags, target_values):
        for bit, wire in enumerate(ab):
            gate = circuit.and_(flag, wire)
            value = field.mul(target_value, 1 << bit)
            gates.append(gate)
            images.append(value ^ field.mul(value, value))
    mixed = circuit.linear_element(gates, images)
    total = circuit.add(circuit.add(left, right), target)
    circuit.require_zero(circuit.add(circuit.square(total), mixed))
    return len(gates)


def pair_product_bits(circuit, left_bits, right_bits):
    """Coordinates of w_left*w_right in the t^2,...,t^30 basis."""
    diagonals = [[] for _ in range(2*WIDTH-1)]
    for i, left in enumerate(left_bits):
        for j, right in enumerate(right_bits):
            diagonals[i+j].append(circuit.and_(left, right))
    return [circuit.xor(items) for items in diagonals]


def bilinear_pair_constraint(circuit, field, left_bits, right_bits,
                             left, right, output, product_basis):
    """s^2+z^2+zp+(zp)^2=0, where p is a 29-bit W15 product."""
    product_bits = pair_product_bits(circuit, left_bits, right_bits)
    square_basis = [field.mul(1 << j, 1 << j) for j in range(N)]
    buckets = [[] for _ in range(N)]
    bilinear_ands = 0
    for product_bit, basis in zip(product_bits, product_basis):
        basis_square = field.mul(basis, basis)
        for j, output_bit in enumerate(output):
            gate = circuit.and_(product_bit, output_bit)
            bilinear_ands += 1
            image = field.mul(basis, 1 << j) ^ field.mul(basis_square, square_basis[j])
            while image:
                low = image & -image
                buckets[low.bit_length()-1].append(gate)
                image ^= low
    bilinear = [circuit.xor(bucket) for bucket in buckets]
    s = circuit.add(left, right)
    equation = circuit.add(circuit.add(circuit.square(s), circuit.square(output)),
                           bilinear)
    circuit.require_zero(equation)
    return bilinear_ands


def build(circuit, field, bases_w, columns, target_reciprocals,
          rotations, frobenius):
    if (circuit.n != N or len(bases_w) != ATOMS or
            len(target_reciprocals) != 4 or len(columns) != 16441 or
            len(rotations) != ATOMS):
        raise ValueError("invalid N131 W15 coupled six-pair configuration")
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
    alias_clauses = 0
    mask_inequality_clauses = 0
    mask_inequality_xor_rows = 0
    for i in range(ATOMS):
        for j in range(i+1, ATOMS):
            # Equal masks always denote the same folded column. Their exact
            # 15-bit inequality needs one OR clause and fourteen native XORs.
            differences = [circuit.xor((masks[i][bit], masks[j][bit]))
                           for bit in range(WIDTH)]
            nonzero(circuit, differences)
            mask_inequality_clauses += 1
            mask_inequality_xor_rows += WIDTH
            # The only remaining same-column pairs are distinct masks in
            # one signed-Frobenius orbit; those sparse aliases need forbids.
            for group in aliases.values():
                if len(group) == 1:
                    continue
                for a in group:
                    for b in group:
                        if a == b:
                            continue
                        circuit.clauses.append(forbid(a, masks[i])[:-2] +
                                               " " + forbid(b, masks[j]))
                        alias_clauses += 1
    seed_equality_rows = 0
    for a, b, c, d in ((4, 5, 6, 7), (8, 9, 10, 11)):
        for bit in range(WIDTH):
            circuit.require_zero([circuit.xor((masks[a][bit], masks[b][bit],
                                               masks[c][bit], masks[d][bit]))])
            seed_equality_rows += 1
    leaves = [circuit.linear_element(row, basis)
              for row, basis in zip(masks, bases_w)]
    middle = [[circuit.variable() for _ in range(N)] for _ in range(10)]
    for row in middle:
        nonzero(circuit, row)
    target = circuit.linear_element(flags, target_reciprocals)
    bilinear_ands = 0
    for i in range(6):
        if rotations[2*i] != rotations[2*i+1] or bases_w[2*i] != bases_w[2*i+1]:
            raise ValueError("bilinear W15 pair must share one Frobenius rotation")
        product_basis = [frobenius(field, 1 << (k+2), rotations[2*i])
                         for k in range(2*WIDTH-1)]
        bilinear_ands += bilinear_pair_constraint(
            circuit, field, masks[2*i], masks[2*i+1],
            leaves[2*i], leaves[2*i+1], middle[i], product_basis)
    reciprocal_s3(circuit, middle[0], middle[1], middle[6])
    reciprocal_s3(circuit, middle[2], middle[3], middle[7])
    reciprocal_s3(circuit, middle[4], middle[5], middle[8])
    reciprocal_s3(circuit, middle[6], middle[7], middle[9])
    target_linear_ands = target_linear_s3(
        circuit, field, middle[9], middle[8], flags,
        target_reciprocals, target)
    return {"masks": masks, "flags": flags, "middle": middle,
            "bilinear_pair_ands": bilinear_ands,
            "target_linear_ands": target_linear_ands,
            "seed_equality_rows": seed_equality_rows,
            "duplicate_column_clauses": mask_inequality_clauses + alias_clauses,
            "mask_inequality_clauses": mask_inequality_clauses,
            "mask_inequality_xor_rows": mask_inequality_xor_rows,
            "distinct_alias_clauses": alias_clauses,
            "primary_variables": ATOMS*WIDTH+4+10*N,
            "chain": "six bilinear diagonal pairs, two shared seed sums, four upper joins, target join"}
