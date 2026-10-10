"""One W16 five-pair XCNF jointly selecting 32 signed first-pair prefixes."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMPACT = ROOT / "n131_w16_bdd_membership_20261010"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bdd = load("joint_prefix_bdd", COMPACT / "bdd.py")
prior = load("joint_prefix_old_core", COMPACT / "core.py")
original = prior.prior.original


def build(circuit, field, bases_w, columns, reciprocal_by_prefix,
          fixed_columns_by_prefix, rotations, frobenius):
    if (circuit.n != 131 or len(columns) != 32796 or len(bases_w) != 10 or
            len(rotations) != 10 or len(reciprocal_by_prefix) != 32 or
            len(fixed_columns_by_prefix) != 32 or
            any(len(row) != 4 for row in reciprocal_by_prefix) or
            any(len(row) != 2 for row in fixed_columns_by_prefix)):
        raise ValueError("invalid joint-prefix W16 circuit")
    masks = [[circuit.variable() for _ in range(16)] for _ in range(10)]
    flags = [circuit.variable() for _ in range(128)]
    original.nonzero(circuit, flags)
    for i in range(128):
        for j in range(i + 1, 128):
            circuit.clauses.append(f"-{flags[i]} -{flags[j]} 0")
    root, graph = bdd.build(set(columns), 16)
    members = []
    for row in masks:
        wires, _ = bdd.emit(circuit, row, root, graph)
        members.append(wires)
    aliases = {}
    for mask, column in columns.items():
        aliases.setdefault(column, []).append(mask)
    conditional_exclusions = 0
    for prefix, fixed in enumerate(fixed_columns_by_prefix):
        if fixed[0] == fixed[1]:
            raise ValueError("fixed-pair column collision")
        for branch in range(4):
            choice = flags[4 * prefix + branch]
            for row in masks:
                for column in fixed:
                    for mask in aliases[column]:
                        circuit.clauses.append(f"-{choice} " + original.forbid(mask, row))
                        conditional_exclusions += 1
    for i in range(10):
        for j in range(i + 1, 10):
            differences = [circuit.xor((masks[i][bit], masks[j][bit]))
                           for bit in range(16)]
            original.nonzero(circuit, differences)
            for group in aliases.values():
                if len(group) == 1:
                    continue
                for a in group:
                    for b in group:
                        if a != b:
                            circuit.clauses.append(original.forbid(a, masks[i])[:-2] +
                                                   " " + original.forbid(b, masks[j]))
    for a, b, c, d in ((2, 3, 4, 5), (6, 7, 8, 9)):
        for bit in range(16):
            circuit.require_zero([circuit.xor((masks[a][bit], masks[b][bit],
                                               masks[c][bit], masks[d][bit]))])
    leaves = [circuit.linear_element(row, basis)
              for row, basis in zip(masks, bases_w)]
    middle = [[circuit.variable() for _ in range(131)] for _ in range(8)]
    for row in middle:
        original.nonzero(circuit, row)
    flat_targets = [value for row in reciprocal_by_prefix for value in row]
    target = circuit.linear_element(flags, flat_targets)
    for i in range(5):
        if rotations[2*i] != rotations[2*i+1] or bases_w[2*i] != bases_w[2*i+1]:
            raise ValueError("source pair rotation drift")
        product_basis = [frobenius(field, 1 << (k + 2), rotations[2*i])
                         for k in range(31)]
        original.bilinear_pair_constraint(
            circuit, field, masks[2*i], masks[2*i+1],
            leaves[2*i], leaves[2*i+1], middle[i], product_basis)
    original.reciprocal_s3(circuit, middle[0], middle[1], middle[5])
    original.reciprocal_s3(circuit, middle[2], middle[3], middle[6])
    original.reciprocal_s3(circuit, middle[5], middle[6], middle[7])
    original.target_linear_s3(circuit, field, middle[7], middle[4], flags,
                              flat_targets, target)
    return {"masks": masks, "flags": flags, "middle": middle,
            "member_wires": members, "member_graph": graph,
            "conditional_fixed_column_clauses": conditional_exclusions,
            "membership_nodes_per_mask": len(graph),
            "primary_variables": 10*16 + 128 + 8*131}
