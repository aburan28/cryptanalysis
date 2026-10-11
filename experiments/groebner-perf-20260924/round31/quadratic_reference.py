"""Independent truth bitmaps and direct specialization; no native solver calls."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location('quadratic_basis_reference',
    Path(__file__).resolve().parent.parent/'round27/reference.py')
_basis = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_basis)
verify_basis, evaluate = _basis.verify_basis, _basis.evaluate


def truth_roots(nvars, equations, items):
    if not 1 <= nvars <= 20 or not 1 <= equations <= 128:
        raise ValueError('reference dimensions')
    ones = (1 << (1 << nvars)) - 1
    variables = [(ones // ((1 << (1 << j)) + 1)) << (1 << j) for j in range(nvars)]
    monomials, rows = {0: ones}, [0]*equations

    def truth(mask):
        if mask not in monomials:
            bit = mask & -mask
            monomials[mask] = truth(mask ^ bit) & variables[bit.bit_length()-1]
        return monomials[mask]

    for mask, coefficient in items:
        if type(mask) is not int or not 0 <= mask < 1 << nvars:
            raise ValueError('reference mask')
        if type(coefficient) is not int or not 0 <= coefficient < 1 << equations:
            raise ValueError('reference coefficient')
        value = truth(mask)
        while coefficient:
            bit = coefficient & -coefficient
            rows[bit.bit_length()-1] ^= value
            coefficient ^= bit
    nonroots = 0
    for row in rows:
        nonroots |= row
    alive, roots = ones ^ nonroots, []
    while alive:
        bit = alive & -alive
        roots.append(bit.bit_length()-1)
        alive ^= bit
    return roots


def branch_counts(x, y, equations, items):
    """Different feature order, direct residual evaluation and equation pivots."""
    masks = sorted((m for m in range(1 << y) if m.bit_count() <= 2), reverse=True)
    # Constant is bit zero; all nonconstant feature columns have larger bits.
    feature = {m: len(masks)-1-i for i, m in enumerate(masks)}
    q = len(feature)-1
    low = (1 << x)-1
    terms = [(m&low, m>>x, c) for m, c in items if c]
    if any(m not in feature for _, m, _ in terms):
        raise ValueError('nonquadratic residual')
    counts = dict(branches=1 << x, consistent=0, max_nullity=0, lifted_candidates=0,
                  fallback_branches=0, fallback_assignments=0, features=q)
    for assignment in range(1 << x):
        residual = {}
        for left, right, c in terms:
            if assignment & left == left:
                residual[right] = residual.get(right, 0) ^ c
        rows = [0]*equations
        for right, c in residual.items():
            while c:
                bit = c & -c
                rows[bit.bit_length()-1] ^= 1 << feature[right]
                c ^= bit
        pivots, consistent = {}, True
        for row in rows:
            while row > 1:
                column = row.bit_length()-1
                if column not in pivots:
                    pivots[column] = row
                    break
                row ^= pivots[column]
            if row == 1:
                consistent = False
        nullity = q-len(pivots)
        counts['max_nullity'] = max(counts['max_nullity'], nullity)
        if consistent:
            counts['consistent'] += 1
            if nullity < y:
                counts['lifted_candidates'] += 1 << nullity
            else:
                counts['fallback_branches'] += 1
                counts['fallback_assignments'] += 1 << y
    return counts
