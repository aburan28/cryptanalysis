"""Unpinned shared-seed two-pair mixed-rotation XCNF."""


def frob(field, value, steps):
    for _ in range(steps):
        value = field.mul(value, value)
    return value


def forbid(mask, wires):
    return " ".join(str(-v if (mask >> i) & 1 else v)
                    for i, v in enumerate(wires)) + " 0"


def pair_constraint(circuit, field, d, rotation, left_bits, right_bits,
                    left, right, output):
    n = circuit.n
    diagonals = [[] for _ in range(2*d-1)]
    for i, left_bit in enumerate(left_bits):
        for j, right_bit in enumerate(right_bits):
            diagonals[i+j].append(circuit.and_(left_bit, right_bit))
    products = [circuit.xor(items) for items in diagonals]
    product_basis = [frob(field, 1 << (i+2), rotation)
                     for i in range(2*d-1)]
    square_basis = [field.mul(1 << i, 1 << i) for i in range(n)]
    buckets = [[] for _ in range(n)]
    gates = 0
    for bit, basis in zip(products, product_basis):
        basis_square = field.mul(basis,basis)
        for j, outbit in enumerate(output):
            gate = circuit.and_(bit,outbit)
            image = field.mul(basis,1 << j) ^ field.mul(basis_square,square_basis[j])
            while image:
                low = image & -image
                buckets[low.bit_length()-1].append(gate)
                image ^= low
            gates += 1
    bilinear = [circuit.xor(bucket) for bucket in buckets]
    seed = circuit.add(left,right)
    equation = circuit.add(circuit.add(circuit.square(seed),
                                      circuit.square(output)),bilinear)
    circuit.require_zero(equation)
    return gates


def build(circuit, field, d, rotations, columns, target_z):
    n = circuit.n
    if len(rotations) != 2 or not columns or target_z in (0,):
        raise ValueError("invalid mixed-rotation four-atom configuration")
    masks = [[circuit.variable() for _ in range(d)] for _ in range(4)]
    valid = set(columns)
    for row in masks:
        for mask in range(1 << d):
            if mask not in valid:
                circuit.clauses.append(forbid(mask,row))
    aliases = {}
    for mask,column in columns.items():
        aliases.setdefault(column,[]).append(mask)
    duplicate_clauses = 0
    for i in range(4):
        for j in range(i+1,4):
            for group in aliases.values():
                for a in group:
                    for b in group:
                        circuit.clauses.append(forbid(a,masks[i])[:-2] +
                                               " " + forbid(b,masks[j]))
                        duplicate_clauses += 1
    for bit in range(d):
        circuit.require_zero([circuit.xor((masks[0][bit],masks[1][bit],
                                          masks[2][bit],masks[3][bit]))])
    leaves = []
    for i,row in enumerate(masks):
        rotation = rotations[0 if i<2 else 1]
        basis = [frob(field,1 << (j+1),rotation) for j in range(d)]
        leaves.append(circuit.linear_element(row,basis))
    outputs = [[circuit.variable() for _ in range(n)] for _ in range(2)]
    for row in outputs:
        circuit.clauses.append(" ".join(map(str,row))+" 0")
    pair_gates = 0
    for k,rotation in enumerate(rotations):
        pair_gates += pair_constraint(circuit,field,d,rotation,
                                      masks[2*k],masks[2*k+1],
                                      leaves[2*k],leaves[2*k+1],outputs[k])
    z = circuit.constant(target_z)
    product = circuit.mul(circuit.mul(outputs[0],outputs[1]),z)
    total = circuit.add(circuit.add(outputs[0],outputs[1]),z)
    circuit.require_zero(circuit.add(circuit.add(circuit.square(total),product),
                                     circuit.square(product)))
    return {"masks":masks,"outputs":outputs,
            "primary_variables":4*d+2*n,
            "seed_equality_rows":d,
            "duplicate_column_clauses":duplicate_clauses,
            "bilinear_pair_ands":pair_gates,
            "rotations":rotations}
