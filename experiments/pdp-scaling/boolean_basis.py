"""Exact certificates and assignment filtering for small Boolean bases."""


def canonical_terms(terms):
    """Canonical ANF: repeated terms cancel in characteristic two."""
    if isinstance(terms, (set, frozenset)):
        return sorted(terms)
    result = set()
    for term in terms:
        result.symmetric_difference_update((term,))
    return sorted(result)


def certify_boolean_basis(nvars: int, equations, basis_terms, *, monomial_cache=True) -> dict:
    """Certify the complete reduced GB using exact Boolean dimension counts.

    In R = GF(2)[x]/(x_i^2+x_i), every ideal is radical and is determined by
    its zeros. Let Z be ALL input zeros and S the squarefree monomials not
    divisible by any output leading monomial. If G vanishes on Z, then
    <G> is contained in I(Z), while |Z| <= dim(R/<G>) <= |S|. Equality
    |S| = |Z| therefore proves ideal equality AND the Groebner property.
    Checking minimal leading terms and standard tails proves reducedness.

    Monomial evaluation uses independent bitset AND/XOR arithmetic, with one
    bit per assignment. The default caps n at 12: a truth table of every
    monomial uses O(4^n) bits. The explicit uncached mode supports n <= 20,
    retaining only n variable truth tables (O(n*2^n) bits) and recomputing
    each monomial's AND. It costs more operations per term but less memory.
    No solver-supplied root set, rank, or completion flag is trusted.
    """
    if not 1 <= nvars <= (12 if monomial_cache else 20):
        raise ValueError("certificate variable bound: cached 1..12, uncached 1..20")
    universe = 1 << nvars
    equations = [canonical_terms(g) for g in equations]
    basis = [list(g) for g in basis_terms]
    for g in equations + basis:
        if any(not isinstance(m, int) or not 0 <= m < universe for m in g):
            raise ValueError("monomial outside the Boolean ring")
    invalid = {"verified": False, "method": "exact-Boolean-zeros-and-staircase"}
    if any(not g or len(g) != len(set(g)) for g in basis):
        return {**invalid, "reason": "noncanonical or zero basis row"}
    all_bits = (1 << universe) - 1
    variables = []
    for v in range(nvars):
        step = 1 << v
        # Repeated doubling avoids large-integer division at larger n.
        pattern = ((1 << step) - 1) << step
        span = step * 2
        while span < universe:
            pattern |= pattern << span
            span *= 2
        variables.append(pattern)
    truth = [all_bits] if monomial_cache else None
    if truth is not None:
        for mask in range(1, universe):
            bit = mask & -mask
            truth.append(truth[mask ^ bit] & variables[bit.bit_length() - 1])
    def monomial_truth(mask):
        if truth is not None:
            return truth[mask]
        value = all_bits
        while mask:
            bit = mask & -mask
            value &= variables[bit.bit_length() - 1]
            mask ^= bit
        return value
    def evaluate(g):
        value = 0
        for mask in g:
            value ^= monomial_truth(mask)
        return value
    nonroots = 0
    for g in equations:
        nonroots |= evaluate(g)
    roots = all_bits ^ nonroots
    root_count = roots.bit_count()
    if any(evaluate(g) & roots for g in basis):
        return {**invalid, "reason": "basis removes an input root", "root_count": root_count}
    leading = [max(g, key=lambda m: (m.bit_count(), -m)) for g in basis]
    forbidden = 0
    for lm in leading:
        # Assignment a makes monomial lm equal one iff lm divides mask a.
        forbidden |= monomial_truth(lm)
    standard = all_bits ^ forbidden
    dimension = standard.bit_count()
    if dimension != root_count:
        return {**invalid, "reason": "staircase dimension differs from root count",
                "root_count": root_count, "standard_monomials": dimension}
    for i, (g, lm) in enumerate(zip(basis, leading)):
        if any(j != i and other & lm == other for j, other in enumerate(leading)):
            return {**invalid, "reason": "nonminimal leading monomial"}
        if any(m != lm and not ((standard >> m) & 1) for m in g):
            return {**invalid, "reason": "nonstandard tail monomial"}
    solutions = None
    if root_count <= 256:
        solutions = []
        remaining = roots
        while remaining:
            bit = remaining & -remaining
            solutions.append(bit.bit_length() - 1)
            remaining ^= bit
    return {"verified": True, "method": "exact-Boolean-zeros-and-staircase",
            "root_count": root_count, "standard_monomials": dimension,
            "monomial_cache": monomial_cache,
            "solutions": solutions,
            "ideal_equality": True, "reduced_groebner_basis": True}


def basis_vanishes(basis_terms, assignment: int) -> bool:
    """Evaluate squarefree ANF rows, stopping at the first violated equation.

    The caller still checks surviving candidates against the original system
    and the curve. This filter preserves ascending assignment enumeration.
    """
    for polynomial in basis_terms:
        parity = False
        for mask in polynomial:
            parity ^= mask & assignment == mask
        if parity:
            return False
    return True
