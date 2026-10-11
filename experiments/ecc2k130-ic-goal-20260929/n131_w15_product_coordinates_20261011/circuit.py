"""Two exact product-coordinate pairs in the N131 W15 six-pair circuit."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SPEC = importlib.util.spec_from_file_location(
    "product_coordinate_prior", PARENT / "n131_w15_two_fixed_seeds_public_20261010" / "circuit.py")
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)

N = 131
WIDTH = 15
SEEDS = prior.FIXED_SEEDS


def clause(circuit, literals):
    """Append a clause, simplifying constant wires 0 and -1."""
    if -1 in literals:
        return
    circuit.clauses.append(" ".join(map(str, (x for x in literals if x != 0))) + " 0")


def mismatch_literal(wire, code_bit):
    if not code_bit:
        return wire
    if wire == 0:
        return -1
    if wire == -1:
        return 0
    return -wire


def forbid(circuit, code, row):
    clause(circuit, [mismatch_literal(wire, code >> i & 1)
                     for i, wire in enumerate(row)])


def pair_forbid(circuit, a, row_a, b, row_b):
    clause(circuit, [mismatch_literal(wire, a >> i & 1)
                     for i, wire in enumerate(row_a)] +
                    [mismatch_literal(wire, b >> i & 1)
                     for i, wire in enumerate(row_b)])


def product_image(field, bases, seed_code):
    seed = 0
    for i, basis in enumerate(bases):
        if seed_code >> i & 1:
            seed ^= basis
    return seed, [field.mul(w, w) ^ field.mul(seed, w) for w in bases]


def selected_positions(images, seed_code):
    reduced = {}
    selected = []
    for i, image in enumerate(images):
        value = image
        while value:
            pivot = value.bit_length() - 1
            if pivot not in reduced:
                reduced[pivot] = value
                selected.append(i)
                break
            value ^= reduced[pivot]
    missing = next(i for i in range(WIDTH) if i not in selected)
    assert len(selected) == 14 and seed_code >> missing & 1
    return selected, missing


def bdd(valid):
    nodes = [int(code in valid) for code in range(1 << 14)]
    graph, unique = {}, {}
    for bit in range(14):
        upper = []
        for i in range(0, len(nodes), 2):
            lo, hi = nodes[i], nodes[i + 1]
            if lo == hi:
                upper.append(lo)
            else:
                key = (bit, lo, hi)
                if key not in unique:
                    node = len(graph) + 2
                    unique[key] = node
                    graph[node] = key
                upper.append(unique[key])
        nodes = upper
    assert nodes[0] >= 2
    return nodes[0], graph


def pair_source(circuit, seed_code, bases, columns):
    seed, images = product_image(circuit.field, bases, seed_code)
    selected, missing = selected_positions(images, seed_code)
    bits = [circuit.variable() for _ in range(14)]
    left = [0] * WIDTH
    for i, wire in zip(selected, bits):
        left[i] = wire
    right = [circuit.xor((wire, -1 if seed_code >> i & 1 else 0))
             for i, wire in enumerate(left)]
    assert left[missing] == 0 and right[missing] == -1
    valid = set()
    for code in range(1 << 14):
        a = sum((code >> j & 1) << i for j, i in enumerate(selected))
        b = a ^ seed_code
        if a in columns and b in columns and columns[a] != columns[b]:
            valid.add(code)
    root, graph = bdd(valid)
    wires = {node: circuit.variable() for node in graph}
    for node, (bit, low, high) in graph.items():
        if low != 1:
            clause(circuit, [-wires[node], bits[bit],
                             wires[low] if low >= 2 else 0])
        if high != 1:
            clause(circuit, [-wires[node], -bits[bit],
                             wires[high] if high >= 2 else 0])
    clause(circuit, [wires[root]])
    return {"left": left, "right": right, "bits": bits,
            "basis": [images[i] for i in selected], "seed": seed,
            "selected": selected, "missing": missing,
            "valid_count": len(valid), "root": root, "graph": graph,
            "bdd_wires": wires}


def fixed_product_constraint(circuit, field, bits, product_basis, seed, output):
    assert len(bits) == len(product_basis) == 14
    squares = [field.mul(1 << j, 1 << j) for j in range(N)]
    buckets = [[] for _ in range(N)]
    gates = 0
    for source_bit, basis in zip(bits, product_basis):
        basis_square = field.mul(basis, basis)
        for j, output_bit in enumerate(output):
            gate = circuit.and_(source_bit, output_bit)
            gates += 1
            image = field.mul(basis, 1 << j) ^ field.mul(basis_square, squares[j])
            while image:
                low = image & -image
                buckets[low.bit_length()-1].append(gate)
                image ^= low
    bilinear = [circuit.xor(bucket) for bucket in buckets]
    equation = circuit.add(
        circuit.add(circuit.constant(field.mul(seed, seed)), circuit.square(output)),
        bilinear)
    circuit.require_zero(equation)
    return gates


def build(circuit, field, bases_w, columns, target_reciprocals,
          rotations, frobenius):
    if (circuit.n != N or len(bases_w) != 12 or len(columns) != 16441 or
            len(target_reciprocals) != 4 or len(rotations) != 12):
        raise ValueError("invalid N131 W15 product-coordinate source")
    # Circuit uses -1 as a Boolean constant; keep variable 1 unused so
    # negated CNF literals can be simplified without an ambiguity.
    assert circuit.variable() == 1
    circuit.field = field
    fixed = [pair_source(circuit, seed, bases_w[2*i], columns)
             for i, seed in enumerate(SEEDS)]
    masks = [row for pair in fixed for row in (pair["left"], pair["right"])]
    masks += [[circuit.variable() for _ in range(WIDTH)] for _ in range(8)]
    flags = [circuit.variable() for _ in range(4)]
    prior.nonzero(circuit, flags)
    for i in range(4):
        for j in range(i+1, 4):
            circuit.clauses.append(f"-{flags[i]} -{flags[j]} 0")
    valid = set(columns)
    for row in masks[4:]:
        for code in range(1 << WIDTH):
            if code not in valid:
                circuit.clauses.append(prior.forbid(code, row))
    aliases = {}
    for mask, column in columns.items():
        aliases.setdefault(column, []).append(mask)
    alias_pairs = [(a, b) for group in aliases.values() if len(group) > 1
                   for a in group for b in group if a != b]
    for i in range(12):
        for j in range(i+1, 12):
            differences = [circuit.xor((masks[i][k], masks[j][k]))
                           for k in range(WIDTH)]
            clause(circuit, differences)
            for a, b in alias_pairs:
                pair_forbid(circuit, a, masks[i], b, masks[j])
    leaves = [circuit.linear_element(row, basis)
              for row, basis in zip(masks, bases_w)]
    middle = [[circuit.variable() for _ in range(N)] for _ in range(10)]
    for row in middle:
        prior.nonzero(circuit, row)
    target = circuit.linear_element(flags, target_reciprocals)
    bilinear_ands = 0
    for i in range(6):
        if rotations[2*i] != rotations[2*i+1] or bases_w[2*i] != bases_w[2*i+1]:
            raise ValueError("pair source rotations disagree")
        if i < 2:
            part = fixed[i]
            bilinear_ands += fixed_product_constraint(
                circuit, field, part["bits"], part["basis"],
                part["seed"], middle[i])
        else:
            basis = [frobenius(field, 1 << (k+2), rotations[2*i])
                     for k in range(2*WIDTH-1)]
            bilinear_ands += prior.bilinear_pair_constraint(
                circuit, field, masks[2*i], masks[2*i+1],
                leaves[2*i], leaves[2*i+1], middle[i], basis)
    prior.reciprocal_s3(circuit, middle[0], middle[1], middle[6])
    prior.reciprocal_s3(circuit, middle[2], middle[3], middle[7])
    prior.reciprocal_s3(circuit, middle[4], middle[5], middle[8])
    prior.reciprocal_s3(circuit, middle[6], middle[7], middle[9])
    target_ands = prior.target_linear_s3(
        circuit, field, middle[9], middle[8], flags, target_reciprocals, target)
    return {"masks": masks, "flags": flags, "middle": middle,
            "fixed": fixed, "bilinear_pair_ands": bilinear_ands,
            "target_linear_ands": target_ands,
            "product_coordinate_pair_count": 2,
            "source_reconstruction": "canonical first mask with zero missing bit"}
