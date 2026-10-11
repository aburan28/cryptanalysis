"""Independent bounded-memory Boolean truth enumeration; no branch proofs."""


def chunked_roots(nvars, equations, items, *, chunk_bits=14, root_limit=256):
    if not 1 <= nvars <= 24 or not 1 <= equations <= 128 or not 1 <= chunk_bits <= 14:
        raise ValueError('reference dimensions')
    items = list(items)
    for mask, coefficient in items:
        if type(mask) is not int or not 0 <= mask < 1 << nvars:
            raise ValueError('reference mask')
        if type(coefficient) is not int or not 0 <= coefficient < 1 << equations:
            raise ValueError('reference coefficient')
    bits = min(nvars, chunk_bits)
    low_mask, ones = (1 << bits)-1, (1 << (1 << bits))-1
    variables = [(ones // ((1 << (1 << j))+1)) << (1 << j) for j in range(bits)]
    cache = {0: ones}

    def monomial(mask):
        if mask not in cache:
            bit = mask & -mask
            cache[mask] = monomial(mask^bit) & variables[bit.bit_length()-1]
        return cache[mask]

    terms = [(mask >> bits, monomial(mask & low_mask), coefficient)
             for mask, coefficient in items if coefficient]
    answer = []
    for upper in range(1 << (nvars-bits)):
        equations_bits = [0]*equations
        for high_mask, values, coefficient in terms:
            if upper & high_mask != high_mask:
                continue
            while coefficient:
                bit = coefficient & -coefficient
                equations_bits[bit.bit_length()-1] ^= values
                coefficient ^= bit
        nonroots = 0
        for values in equations_bits:
            nonroots |= values
        alive = ones ^ nonroots
        while alive:
            bit = alive & -alive
            answer.append((upper << bits) | (bit.bit_length()-1))
            if len(answer) > root_limit:
                raise ValueError('reference root limit')
            alive ^= bit
    return answer
