"""Exact indexed fifth-pair membership inside the ten-leaf S3 chain."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "n41_w5_ten_lowproduct_20261010" / "circuit.py"
spec = importlib.util.spec_from_file_location("n41_w5_lowproduct_for_pair_index", SOURCE)
method = importlib.util.module_from_spec(spec)
spec.loader.exec_module(method)
ROTATIONS = (0, 0, 8, 8, 16, 16, 24, 24, 32, 32)


def clause(circuit, literals):
    circuit.clauses.append(" ".join(map(str, literals)) + " 0")


def exactly_one(circuit, selectors):
    """Linear-size sequential at-most-one plus a single at-least-one row."""
    assert len(selectors) >= 2
    clause(circuit, selectors)
    sequence = [circuit.variable() for _ in range(len(selectors) - 1)]
    clause(circuit, [-selectors[0], sequence[0]])
    for i in range(1, len(selectors) - 1):
        clause(circuit, [-selectors[i], sequence[i]])
        clause(circuit, [-sequence[i-1], sequence[i]])
        clause(circuit, [-selectors[i], -sequence[i-1]])
    clause(circuit, [-selectors[-1], -sequence[-1]])
    return sequence


def imply_bits(circuit, selector, wires, value):
    for i, wire in enumerate(wires):
        bit = (value >> i) & 1
        if wire == 0:
            if bit:
                clause(circuit, [-selector])
        elif wire == -1:
            if not bit:
                clause(circuit, [-selector])
        else:
            clause(circuit, [-selector, wire if bit else -wire])


def build(circuit, field, geometry, target_us, entries):
    assert len(entries) == 264
    basis_w = [[method.frob(field, w, rotation)
                for w in geometry["source_basis_w"]]
               for rotation in ROTATIONS]
    basis_u = [geometry["bases_u"][rotation // 4]
               for rotation in ROTATIONS]
    columns = {int(mask): tuple(value)
               for mask, value in geometry["mask_columns"].items()}
    original = method.low_product_link
    call_count = 0
    selectors = []
    sequence = []

    def indexed_link(circuit, mask_a, mask_b, w_a_basis, w_b_basis,
                     u_a, u_b, output):
        nonlocal call_count, selectors, sequence
        call_count += 1
        if call_count != 5:
            return original(circuit, mask_a, mask_b, w_a_basis, w_b_basis,
                            u_a, u_b, output)
        selectors = [circuit.variable() for _ in entries]
        sequence = exactly_one(circuit, selectors)
        for selector, entry in zip(selectors, entries):
            imply_bits(circuit, selector, mask_a, entry["mask_a"])
            imply_bits(circuit, selector, mask_b, entry["mask_b"])
            imply_bits(circuit, selector, output, entry["z_local"])

    method.low_product_link = indexed_link
    try:
        meta = method.build(circuit, basis_w, basis_u, columns,
                            target_us, rotations=ROTATIONS, field=field)
    finally:
        method.low_product_link = original
    assert call_count == 5 and len(selectors) == 264
    meta["pair_selectors"] = selectors
    meta["pair_sequence"] = sequence
    meta["indexed_pair"] = 4
    meta["exact_arithmetic_pairs"] = 4
    return meta
