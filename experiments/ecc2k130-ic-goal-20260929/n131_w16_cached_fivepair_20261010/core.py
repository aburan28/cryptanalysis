"""Reusable W16 five-pair source circuit and target-specific S3 suffix."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
W15 = HERE.parent / "n131_w15_coupled_sixpair_20261010"
spec = importlib.util.spec_from_file_location("cached_fivepair_original", W15 / "w15_circuit.py")
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
original.WIDTH = 16

N = 131
WIDTH = 16
ATOMS = 10


def prepare(circuit, field, bases_w, columns, rotations, frobenius):
    if (circuit.n != N or len(bases_w) != ATOMS or len(columns) != 32796 or
            len(rotations) != ATOMS or any(len(row) != WIDTH for row in bases_w)):
        raise ValueError("invalid N131 W16 cached five-pair configuration")
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
    return {"masks": masks, "flags": flags, "middle": middle,
            "aliases": aliases, "bilinear_pair_ands": bilinear_ands,
            "seed_equality_rows": seed_rows,
            "mask_inequality_clauses": inequality_clauses,
            "mask_inequality_xor_rows": inequality_xor_rows,
            "distinct_alias_clauses": alias_clauses,
            "primary_variables": ATOMS*WIDTH + 4 + 8*N}


def finish(circuit, field, state, target_reciprocals, fixed_columns):
    if len(target_reciprocals) != 4 or len(fixed_columns) != 2:
        raise ValueError("invalid target fiber or fixed prefix")
    fixed_clauses = 0
    for row in state["masks"]:
        for column in fixed_columns:
            for mask in state["aliases"][column]:
                circuit.clauses.append(original.forbid(mask, row))
                fixed_clauses += 1
    target = circuit.linear_element(state["flags"], target_reciprocals)
    target_ands = original.target_linear_s3(
        circuit, field, state["middle"][7], state["middle"][4],
        state["flags"], target_reciprocals, target)
    return {**state, "fixed_column_clauses": fixed_clauses,
            "target_linear_ands": target_ands,
            "chain": "cached five pair products and three upper joins; target S3 suffix"}
