"""Exact transformed-S3 tree for six same-rotation W6 leaf pairs."""

from __future__ import annotations

import n41_w6_s8_four_pairs_circuit as four
import n41_lowpower_w8_s6_circuit as helper
from n41_lowpower_w8_s6_implicit_resultant_circuit import exact_pair_equation

N = 41
WIDTH = 6
PAIRS = 6
SLOTS = 2 * PAIRS


def build(circuit, field, bases_w, half_bases, target_us, mask_columns):
    if len(bases_w) != SLOTS or len(half_bases) != SLOTS:
        raise ValueError("expected twelve W6 slots")
    if len(mask_columns) != SLOTS or len(target_us) != 4:
        raise ValueError("expected twelve mask maps and four raw target lifts")
    if any(len(row) != WIDTH for row in bases_w + half_bases):
        raise ValueError("W6 basis length mismatch")

    masks = [[circuit.variable() for _ in range(WIDTH)] for _ in range(SLOTS)]
    flags = [circuit.variable() for _ in range(4)]
    helper.one_hot(circuit, flags)
    seed_u = []
    for slot, row in enumerate(masks):
        u = circuit.linear_element(row, half_bases[slot])
        helper.nonzero_nonone(circuit, u)
        seed_u.append(u)
        for mask in range(1 << WIDTH):
            if mask not in mask_columns[slot]:
                literals = [(-wire if mask & (1 << bit) else wire)
                            for bit, wire in enumerate(row)]
                circuit.clauses.append(" ".join(map(str, literals)) + " 0")

    duplicate_column_clauses = 0
    for left in range(SLOTS):
        for right in range(left + 1, SLOTS):
            right_by_column = {}
            for mask, column in mask_columns[right].items():
                right_by_column.setdefault(column, []).append(mask)
            for left_mask, column in mask_columns[left].items():
                for right_mask in right_by_column.get(column, []):
                    literals = [(-wire if left_mask & (1 << bit) else wire)
                                for bit, wire in enumerate(masks[left])]
                    literals += [(-wire if right_mask & (1 << bit) else wire)
                                 for bit, wire in enumerate(masks[right])]
                    circuit.clauses.append(" ".join(map(str, literals)) + " 0")
                    duplicate_column_clauses += 1

    pair_outputs = [[circuit.variable() for _ in range(N)] for _ in range(PAIRS)]
    first_level = [[circuit.variable() for _ in range(N)] for _ in range(3)]
    second_level = [circuit.variable() for _ in range(N)]
    for pair in range(PAIRS):
        left = 2 * pair
        product, _ = four.lowpower_product(
            circuit, field, masks[left], masks[left + 1],
            bases_w[left], bases_w[left + 1])
        helper.nonzero_nonone(circuit, pair_outputs[pair])
        exact_pair_equation(circuit, product, seed_u[left],
                            seed_u[left + 1], pair_outputs[pair])

    def link(left, right, output):
        wa = circuit.add(circuit.square(left), left)
        wb = circuit.add(circuit.square(right), right)
        helper.nonzero_nonone(circuit, output)
        exact_pair_equation(circuit, circuit.mul(wa, wb), left, right, output)

    for i in range(3):
        link(pair_outputs[2 * i], pair_outputs[2 * i + 1], first_level[i])
    link(first_level[0], first_level[1], second_level)
    target_u = circuit.linear_element(flags, target_us)
    wa = circuit.add(circuit.square(second_level), second_level)
    wb = circuit.add(circuit.square(first_level[2]), first_level[2])
    exact_pair_equation(circuit, circuit.mul(wa, wb),
                        second_level, first_level[2], target_u)
    return {
        "masks": masks, "flags": flags, "seed_u": seed_u,
        "pair_outputs": pair_outputs, "first_level": first_level,
        "second_level": second_level, "target_us": list(map(int, target_us)),
        "duplicate_column_clauses": duplicate_column_clauses,
        "primary_variables": SLOTS * WIDTH + 4 + 10 * N,
        "chain": "six rank-11 pair links, three pair-pair links, one four-pair link, one public target link",
    }
