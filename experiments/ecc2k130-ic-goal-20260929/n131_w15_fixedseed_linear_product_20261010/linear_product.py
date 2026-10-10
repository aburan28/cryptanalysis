"""Exact fixed-seed product basis for the two W15 constrained source pairs."""

SEED = 13686
N = 131
LEFT_FIRST_WIRES = {61: 76, 91: 106}


def specialized_pair_constraint(circuit, field, left_bits, right_bits,
                                left, right, output, product_basis):
    """Use p=w(w+s), linear in w for a fixed mask-XOR seed s."""
    assert len(left_bits) == len(right_bits) == 15
    assert len(product_basis) == 29 and circuit.n == N
    assert right_bits[0] == LEFT_FIRST_WIRES[left_bits[0]]
    # product_basis[k] is Frob(t^(k+2), rotation). In characteristic two,
    # w^2 has only even powers and s*w contributes the selected seed powers.
    reduced_basis = []
    for i in range(15):
        basis = product_basis[2*i]
        for j in range(15):
            if SEED >> j & 1:
                basis ^= product_basis[i+j]
        reduced_basis.append(basis)
    square_basis = [field.mul(1 << j, 1 << j) for j in range(N)]
    buckets = [[] for _ in range(N)]
    bilinear_ands = 0
    for product_bit, basis in zip(left_bits, reduced_basis):
        basis_square = field.mul(basis, basis)
        for j, output_bit in enumerate(output):
            gate = circuit.and_(product_bit, output_bit)
            bilinear_ands += 1
            image = field.mul(basis, 1 << j) ^ field.mul(basis_square, square_basis[j])
            while image:
                low = image & -image
                buckets[low.bit_length()-1].append(gate)
                image ^= low
    bilinear = [circuit.xor(bucket) for bucket in buckets]
    s = circuit.add(left, right)
    equation = circuit.add(circuit.add(circuit.square(s), circuit.square(output)),
                           bilinear)
    circuit.require_zero(equation)
    return bilinear_ands


def build(experiment, target):
    """Replace only pair slots 2 and 3 while building the baseline circuit."""
    compact = experiment.compact
    original = compact.bilinear_pair_constraint
    calls = []

    def chosen(circuit, field, left_bits, right_bits,
               left, right, output, product_basis):
        if left_bits[0] in LEFT_FIRST_WIRES:
            calls.append(left_bits[0])
            return specialized_pair_constraint(circuit, field, left_bits, right_bits,
                                               left, right, output, product_basis)
        return original(circuit, field, left_bits, right_bits,
                        left, right, output, product_basis)

    compact.bilinear_pair_constraint = chosen
    try:
        circuit, meta, lifts = experiment.run.formula_for(tuple(target))
    finally:
        compact.bilinear_pair_constraint = original
    assert calls == [61, 91]
    assert meta["bilinear_pair_ands"] == 4*29*N + 2*15*N
    return circuit, meta, lifts
