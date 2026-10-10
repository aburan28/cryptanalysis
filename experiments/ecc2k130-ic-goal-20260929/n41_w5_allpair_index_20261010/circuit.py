"""Exact table membership for all five N41 W5 leaf-pair outputs."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "n41_w5_pair_index_20261010" / "circuit.py"
spec = importlib.util.spec_from_file_location("n41_single_pair_index_for_all_five", SOURCE)
single = importlib.util.module_from_spec(spec)
spec.loader.exec_module(single)
method = single.method
ROTATIONS = single.ROTATIONS


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
    selectors_by_pair = []
    sequences_by_pair = []

    def indexed_link(circuit, mask_a, mask_b, w_a_basis, w_b_basis,
                     u_a, u_b, output):
        selectors = [circuit.variable() for _ in entries]
        sequence = single.exactly_one(circuit, selectors)
        for selector, entry in zip(selectors, entries):
            single.imply_bits(circuit, selector, mask_a, entry["mask_a"])
            single.imply_bits(circuit, selector, mask_b, entry["mask_b"])
            single.imply_bits(circuit, selector, output, entry["z_local"])
        selectors_by_pair.append(selectors)
        sequences_by_pair.append(sequence)

    method.low_product_link = indexed_link
    try:
        meta = method.build(circuit, basis_w, basis_u, columns,
                            target_us, rotations=ROTATIONS, field=field)
    finally:
        method.low_product_link = original
    assert len(selectors_by_pair) == len(sequences_by_pair) == 5
    meta["pair_selectors"] = selectors_by_pair
    meta["pair_sequences"] = sequences_by_pair
    meta["exact_indexed_pairs"] = 5
    meta["exact_arithmetic_pairs"] = 0
    return meta
