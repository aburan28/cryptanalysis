"""Six fixed-sum blocks with seven-coordinate bilinear pair equations."""

N = 41
BLOCKS = 6
WIDTH = 8


def forbid_mask(circuit, wires, code):
    literals = [(-wire if code & (1 << bit) else wire)
                for bit, wire in enumerate(wires)]
    circuit.clauses.append(" ".join(map(str, literals)) + " 0")


def nonzero_nonone(circuit, row):
    for values in (row, row[1:]):
        circuit.clauses.append(" ".join(map(str, values)) + " 0")


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


def pair_product(circuit, z, masks, product_basis, sum_code):
    """Compute A(z)*L_s(a) with seven bilinear selector coordinates.

    L_s(s)=0, so one seed coordinate is redundant. Multiplication by each
    fixed product-basis element is binary linear in A(z); only the seven
    selector-by-output products require AND gates.
    """
    drop = sum_code.bit_length() - 1
    if len(product_basis) != WIDTH or not (0 < sum_code < (1 << WIDTH)):
        raise ValueError("invalid fixed-sum product basis")
    kernel = 0
    for i in range(WIDTH):
        if sum_code & (1 << i):
            kernel ^= product_basis[i]
    if kernel != 0:
        raise ValueError("fixed-sum product map lost its kernel")
    az = circuit.add(circuit.square(z), z)
    terms = []
    for i, value in enumerate(product_basis):
        if i == drop:
            continue
        selector = (circuit.xor((masks[i], masks[drop]))
                    if sum_code & (1 << i) else masks[i])
        # Multiplication by this fixed field element is one binary linear
        # transform; materialize its 41 output parity rows directly.
        images = [circuit.reduce(value << bit) for bit in range(N)]
        linear = circuit.linear_element(az, images)
        terms.append([circuit.and_(selector, wire) for wire in linear])
    return [circuit.xor(bits) for bits in zip(*terms)]


def build(circuit, geometry, target_us):
    if (len(geometry["blocks"]) < BLOCKS or
            len(target_us) != 4 or
            geometry["fixed_seed_sum_code"] != 56 or
            geometry["permitted_mask_pairs"] != 40 or
            geometry["product_map_rank"] != 7):
        raise ValueError("frozen fixed-sum geometry changed")
    allowed = set(geometry["permitted_canonical_a"])
    columns = {int(k): v for k, v in geometry["mask_columns"].items()}
    mask_wires = [[circuit.variable() for _ in range(WIDTH)]
                  for _ in range(BLOCKS)]
    pair_outputs = [[circuit.variable() for _ in range(N)]
                    for _ in range(BLOCKS)]
    flags = [circuit.variable() for _ in range(4)]
    one_hot(circuit, flags)
    for block in range(BLOCKS):
        masks = mask_wires[block]
        for code in range(1 << WIDTH):
            if code not in allowed:
                forbid_mask(circuit, masks, code)
        z = pair_outputs[block]
        nonzero_nonone(circuit, z)
        s = circuit.constant(geometry["blocks"][block]["s"])
        product = pair_product(circuit, z, masks,
                               geometry["blocks"][block]["product_basis"], 56)
        rhs = circuit.add(circuit.square(s), circuit.square(z))
        circuit.require_zero(circuit.add(product, rhs))
    duplicate_clauses = 0
    for i in range(BLOCKS):
        for j in range(i + 1, BLOCKS):
            for a in allowed:
                ca = {columns[a], columns[a ^ 56]}
                for b in allowed:
                    if ca.isdisjoint({columns[b], columns[b ^ 56]}):
                        continue
                    literals = [(-wire if a & (1 << bit) else wire)
                                for bit, wire in enumerate(mask_wires[i])]
                    literals += [(-wire if b & (1 << bit) else wire)
                                 for bit, wire in enumerate(mask_wires[j])]
                    circuit.clauses.append(" ".join(map(str, literals)) + " 0")
                    duplicate_clauses += 1
    middle = [[circuit.variable() for _ in range(N)] for _ in range(4)]
    for row in middle:
        nonzero_nonone(circuit, row)
    link(circuit, pair_outputs[0], pair_outputs[1], middle[0])
    link(circuit, pair_outputs[2], pair_outputs[3], middle[1])
    link(circuit, pair_outputs[4], pair_outputs[5], middle[2])
    link(circuit, middle[0], middle[1], middle[3])
    target = circuit.linear_element(flags, target_us)
    link(circuit, middle[3], middle[2], target)
    return {"mask_wires": mask_wires, "pair_output_wires": pair_outputs,
            "target_flag_wires": flags, "middle_wires": middle,
            "target_us": target_us, "duplicate_column_clauses": duplicate_clauses,
            "direct_pair_product_map_rank": geometry["product_map_rank"],
            "primary_variables": BLOCKS * (WIDTH + N) + 4 + 4*N,
            "chain": "six rank-seven pair links and five balanced target links"}
