"""Full ten-source N131 S3 system with Frobenius-frame leaf links."""

N = 131
WIDTH = 14
BLOCKS = 10


def frob(field, value, power):
    for _ in range(power):
        value = field.mul(value, value)
    return value


def forbidden(code, row):
    return " ".join(str(-wire if code >> i & 1 else wire)
                    for i, wire in enumerate(row)) + " 0"


def generic_link(circuit, left, right, output):
    a = circuit.add(circuit.square(left), left)
    b = circuit.add(circuit.square(right), right)
    lhs = circuit.mul(circuit.mul(a, b),
                      circuit.add(circuit.square(output), output))
    rhs = circuit.square(circuit.add(circuit.add(left, right), output))
    circuit.require_zero(circuit.add(lhs, rhs))


def frame_link(circuit, mask_a, mask_b, source_w, source_u,
               relative_rotation, output, inverse_transform, field):
    basis_w_b = [frob(field, w, relative_rotation) for w in source_w]
    basis_u_b = [frob(field, u, relative_rotation) for u in source_u]
    w_a = circuit.linear_element(mask_a, source_w)
    w_b = circuit.linear_element(mask_b, basis_w_b)
    u_a = circuit.linear_element(mask_a, source_u)
    u_b = circuit.linear_element(mask_b, basis_u_b)
    local_z = circuit.linear_element(output, inverse_transform)
    lhs = circuit.mul(circuit.mul(w_a, w_b),
                      circuit.add(circuit.square(local_z), local_z))
    rhs = circuit.square(circuit.add(circuit.add(u_a, u_b), local_z))
    circuit.require_zero(circuit.add(lhs, rhs))


def build(circuit, field, source_w, source_u, rotations,
          valid_masks, columns, target_us):
    if (circuit.n != N or len(source_w) != WIDTH or
            len(source_u) != WIDTH or len(rotations) != BLOCKS or
            len(target_us) != 4):
        raise ValueError("invalid N131 W14 ten-source configuration")
    masks = [[circuit.variable() for _ in range(WIDTH)]
             for _ in range(BLOCKS)]
    flags = [circuit.variable() for _ in range(4)]
    circuit.clauses.append(" ".join(map(str, flags)) + " 0")
    for i in range(4):
        for j in range(i + 1, 4):
            circuit.clauses.append(f"-{flags[i]} -{flags[j]} 0")
    middle = [[circuit.variable() for _ in range(N)] for _ in range(8)]
    valid_masks = set(valid_masks)
    for row in masks:
        for code in range(1 << WIDTH):
            if code not in valid_masks:
                circuit.clauses.append(forbidden(code, row))
    aliases = {}
    for mask, column in columns.items():
        aliases.setdefault(column, []).append(mask)
    duplicate_clauses = 0
    for i in range(BLOCKS):
        for j in range(i + 1, BLOCKS):
            for group in aliases.values():
                for first in group:
                    for second in group:
                        circuit.clauses.append(forbidden(first, masks[i])[:-2] +
                                               " " + forbidden(second, masks[j]))
                        duplicate_clauses += 1
    for row in middle:
        circuit.clauses.append(" ".join(map(str, row)) + " 0")
        circuit.clauses.append(" ".join(map(str, row[1:])) + " 0")
    inverse_transforms = {}
    for i in range(5):
        rotation = rotations[2 * i]
        if rotation not in inverse_transforms:
            inverse_transforms[rotation] = [
                frob(field, 1 << bit, (N - rotation) % N)
                for bit in range(N)]
        frame_link(circuit, masks[2 * i], masks[2 * i + 1],
                   source_w, source_u,
                   (rotations[2 * i + 1] - rotation) % N,
                   middle[i], inverse_transforms[rotation], field)
    generic_link(circuit, middle[0], middle[1], middle[5])
    generic_link(circuit, middle[2], middle[3], middle[6])
    generic_link(circuit, middle[5], middle[6], middle[7])
    target = circuit.linear_element(flags, target_us)
    generic_link(circuit, middle[7], middle[4], target)
    return {"masks": masks, "flags": flags, "middle": middle,
            "duplicate_column_clauses": duplicate_clauses,
            "primary_variables": BLOCKS * WIDTH + 4 + 8 * N,
            "frame_rotations": rotations}
