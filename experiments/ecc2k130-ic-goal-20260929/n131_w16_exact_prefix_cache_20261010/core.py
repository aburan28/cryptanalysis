"""Byte-compatible split of the W16 signed-prefix five-pair circuit."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
W15 = HERE.parent / "n131_w15_coupled_sixpair_20261010"
spec = importlib.util.spec_from_file_location("exact_prefix_original_w15", W15 / "w15_circuit.py")
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)

N = 131
WIDTH = 16
ATOMS = 10
original.WIDTH = WIDTH


def prepare(circuit, columns):
    """Stop at the first target-dependent statement of the frozen builder."""
    if circuit.n != N or len(columns) != 32796:
        raise ValueError("invalid N131 W16 source prefix")
    masks = [[circuit.variable() for _ in range(WIDTH)] for _ in range(ATOMS)]
    flags = [circuit.variable() for _ in range(4)]
    original.nonzero(circuit, flags)
    for i in range(4):
        for j in range(i + 1, 4):
            circuit.clauses.append(f"-{flags[i]} -{flags[j]} 0")
    valid = set(columns)
    for row in masks:
        for code in range(1 << WIDTH):
            if code not in valid:
                circuit.clauses.append(original.forbid(code, row))
    aliases = {}
    for mask, column in columns.items():
        aliases.setdefault(column, []).append(mask)
    return {"masks": masks, "flags": flags, "aliases": aliases}


def finish(circuit, state, field, bases_w, target_reciprocals,
           rotations, frobenius, fixed_columns):
    if (circuit.n != N or len(bases_w) != ATOMS or
            len(target_reciprocals) != 4 or
            len(rotations) != ATOMS or len(fixed_columns) != 2):
        raise ValueError("invalid N131 W16 target suffix")
    masks = state["masks"]
    flags = state["flags"]
    aliases = state["aliases"]
    fixed_column_clauses = 0
    for row in masks:
        for column in fixed_columns:
            for mask in aliases[column]:
                circuit.clauses.append(original.forbid(mask, row))
                fixed_column_clauses += 1
    alias_clauses = 0
    inequality_clauses = 0
    inequality_xor_rows = 0
    for i in range(ATOMS):
        for j in range(i + 1, ATOMS):
            differences = [circuit.xor((masks[i][bit], masks[j][bit]))
                           for bit in range(WIDTH)]
            original.nonzero(circuit, differences)
            inequality_clauses += 1
            inequality_xor_rows += WIDTH
            for group in aliases.values():
                if len(group) == 1:
                    continue
                for a in group:
                    for b in group:
                        if a != b:
                            circuit.clauses.append(original.forbid(a, masks[i])[:-2] +
                                                   " " + original.forbid(b, masks[j]))
                            alias_clauses += 1
    seed_rows = 0
    for a, b, c, d in ((2, 3, 4, 5), (6, 7, 8, 9)):
        for bit in range(WIDTH):
            circuit.require_zero([circuit.xor((masks[a][bit], masks[b][bit],
                                               masks[c][bit], masks[d][bit]))])
            seed_rows += 1
    leaves = [circuit.linear_element(row, basis)
              for row, basis in zip(masks, bases_w)]
    middle = [[circuit.variable() for _ in range(N)] for _ in range(8)]
    for row in middle:
        original.nonzero(circuit, row)
    target = circuit.linear_element(flags, target_reciprocals)
    bilinear_ands = 0
    for i in range(5):
        if rotations[2*i] != rotations[2*i+1] or bases_w[2*i] != bases_w[2*i+1]:
            raise ValueError("each source pair must share a Frobenius rotation")
        product_basis = [frobenius(field, 1 << (k + 2), rotations[2*i])
                         for k in range(2*WIDTH - 1)]
        bilinear_ands += original.bilinear_pair_constraint(
            circuit, field, masks[2*i], masks[2*i+1],
            leaves[2*i], leaves[2*i+1], middle[i], product_basis)
    original.reciprocal_s3(circuit, middle[0], middle[1], middle[5])
    original.reciprocal_s3(circuit, middle[2], middle[3], middle[6])
    original.reciprocal_s3(circuit, middle[5], middle[6], middle[7])
    target_linear_ands = original.target_linear_s3(
        circuit, field, middle[7], middle[4], flags,
        target_reciprocals, target)
    return {"masks": masks, "flags": flags, "middle": middle,
            "bilinear_pair_ands": bilinear_ands,
            "target_linear_ands": target_linear_ands,
            "seed_equality_rows": seed_rows,
            "mask_inequality_clauses": inequality_clauses,
            "mask_inequality_xor_rows": inequality_xor_rows,
            "distinct_alias_clauses": alias_clauses,
            "fixed_column_clauses": fixed_column_clauses,
            "primary_variables": ATOMS*WIDTH + 4 + 8*N,
            "chain": "five bilinear pairs, two shared seed sums, three upper joins, target join"}
