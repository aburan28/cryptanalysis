"""Four exact low-product links and one target-conditioned relaxed pair link."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "n41_w5_ten_lowproduct_20261010" / "circuit.py"
spec = importlib.util.spec_from_file_location("n41_w5_lowproduct_for_hybrid", SOURCE)
method = importlib.util.module_from_spec(spec)
spec.loader.exec_module(method)
ROTATION_SLOTS = (0, 0, 8, 8, 16, 16, 24, 24, 32, 32)


def build(circuit, field, geometry, target_us):
    """Relax the fifth pair product to its exact degree-2..10 linear span."""
    source_w = geometry["source_basis_w"]
    basis_w = [[method.frob(field, w, rotation) for w in source_w]
               for rotation in ROTATION_SLOTS]
    basis_u = [geometry["bases_u"][rotation // 4]
               for rotation in ROTATION_SLOTS]
    columns = {int(mask): tuple(value)
               for mask, value in geometry["mask_columns"].items()}
    original = method.low_product_link
    call_count = 0
    relaxed_bits = []

    def pair_link(circuit, mask_a, mask_b, w_a_basis, w_b_basis,
                  u_a, u_b, output):
        nonlocal call_count
        call_count += 1
        if call_count != 5:
            return original(circuit, mask_a, mask_b, w_a_basis, w_b_basis,
                            u_a, u_b, output)
        relaxed_bits.extend(circuit.variable() for _ in range(9))
        product = circuit.linear_element(relaxed_bits,
                                         [1 << degree for degree in range(2, 11)])
        left = circuit.mul(product,
                           circuit.add(circuit.square(output), output))
        right = circuit.square(circuit.add(circuit.add(u_a, u_b), output))
        circuit.require_zero(circuit.add(left, right))

    method.low_product_link = pair_link
    try:
        meta = method.build(circuit, basis_w, basis_u, columns,
                            target_us, rotations=ROTATION_SLOTS, field=field)
    finally:
        method.low_product_link = original
    assert call_count == 5 and len(relaxed_bits) == 9
    meta["relaxed_product_bits"] = relaxed_bits
    meta["exact_pair_links"] = 4
    meta["relaxed_pair_index"] = 4
    return meta
