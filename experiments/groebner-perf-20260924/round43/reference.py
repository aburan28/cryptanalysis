"""Bounded mathematical prototype; independent witnesses restrict root search.

Each equation is an integer whose bit at position m is the coefficient of
Boolean monomial m. A certificate carries only original-equation row masks.
The checker recomputes each consequence and its rank from scratch.
"""
from dataclasses import dataclass


class InvalidCertificate(ValueError):
    pass


class BudgetExceeded(RuntimeError):
    pass


def validate(y, equations):
    if type(y) is not int or not 1 <= y <= 10 or len(equations) > 128:
        raise ValueError('bounded ring: 1 <= y <= 10 and at most 128 equations')
    if any(type(p) is not int or p < 0 or p.bit_length() > 1 << y for p in equations):
        raise ValueError('equation outside Boolean ring')


def producer(y, equations):
    """Cancel nonlinear columns, retaining exact original-row combinations."""
    validate(y, equations)
    nonlinear = sum(1 << m for m in range(1 << y) if m.bit_count() >= 2)
    high, low = {}, {}
    for index, source in enumerate(equations):
        polynomial, witness = source, 1 << index
        while polynomial & nonlinear:
            pivot = (polynomial & nonlinear).bit_length() - 1
            if pivot not in high:
                high[pivot] = polynomial, witness
                break
            p, u = high[pivot]
            polynomial ^= p
            witness ^= u
        else:
            while polynomial:
                pivot = polynomial.bit_length() - 1
                if pivot not in low:
                    low[pivot] = polynomial, witness
                    break
                p, u = low[pivot]
                polynomial ^= p
                witness ^= u
    return tuple(u for _, u in low.values())


@dataclass(frozen=True)
class Checked:
    roots: tuple
    rank: int
    inconsistent: bool
    candidates: int
    witness_terms: int


def evaluate(polynomial, assignment):
    value = 0
    while polynomial:
        bit = polynomial & -polynomial
        monomial = bit.bit_length() - 1
        value ^= int(assignment & monomial == monomial)
        polynomial ^= bit
    return value


def checker(y, equations, witnesses, assignment_budget=1024):
    """Validate identities; solve their affine system; check original equations.

    Neither producer pivots nor a producer-reported rank/root set is accepted.
    Budget failure raises before enumeration; no partial answer is returned.
    """
    validate(y, equations)
    if type(assignment_budget) is not int or assignment_budget < 0:
        raise ValueError('nonnegative integer assignment budget required')
    if len(witnesses) > 128:
        raise InvalidCertificate('too many witness rows')
    rows, witness_terms = [], 0
    for witness in witnesses:
        if type(witness) is not int or not 0 <= witness < 1 << len(equations):
            raise InvalidCertificate('witness outside original equation space')
        consequence = 0
        for e, polynomial in enumerate(equations):
            if witness & (1 << e):
                consequence ^= polynomial
                witness_terms += polynomial.bit_count()
        row = consequence & 1
        for m in range(1, 1 << y):
            if consequence & (1 << m):
                if m & (m - 1):
                    raise InvalidCertificate('witness consequence is nonlinear')
                row ^= 1 << m.bit_length()
        rows.append(row)

    # Independent ascending-column Gauss-Jordan elimination.
    pivot_columns, rank = [], 0
    for column in range(1, y + 1):
        found = next((i for i in range(rank, len(rows)) if rows[i] & (1 << column)), None)
        if found is None:
            continue
        rows[rank], rows[found] = rows[found], rows[rank]
        for i in range(len(rows)):
            if i != rank and rows[i] & (1 << column):
                rows[i] ^= rows[rank]
        pivot_columns.append(column)
        rank += 1
    if any(row == 1 for row in rows):
        return Checked((), rank, True, 0, witness_terms)
    assert all(row == 0 for row in rows[rank:])
    free = [j for j in range(1, y + 1) if j not in pivot_columns]
    candidates = 1 << len(free)
    if candidates > assignment_budget:
        raise BudgetExceeded('complete affine subspace exceeds assignment budget')
    roots = []
    for bits in range(candidates):
        assignment = sum(((bits >> i) & 1) << (column - 1) for i, column in enumerate(free))
        for row, column in zip(rows[:rank], pivot_columns):
            value = (row & 1) ^ ((row >> 1) & assignment).bit_count() % 2
            assignment |= value << (column - 1)
        if all(evaluate(p, assignment) == 0 for p in equations):
            roots.append(assignment)
    return Checked(tuple(sorted(roots)), rank, False, candidates, witness_terms)


def direct_roots(y, equations):
    """Deliberately simple truth reference, independent of affine elimination."""
    return tuple(a for a in range(1 << y) if all(
        sum((p >> m) & 1 for m in range(1 << y) if m & a == m) % 2 == 0
        for p in equations))


def truth_transform(y, equations):
    """Reference truth transform over each complete original polynomial."""
    survive = bytearray([1]) * (1 << y)
    for polynomial in equations:
        values = [(polynomial >> m) & 1 for m in range(1 << y)]
        for bit in range(y):
            for mask in range(1 << y):
                if mask & (1 << bit):
                    values[mask] ^= values[mask ^ (1 << bit)]
        for a, value in enumerate(values):
            survive[a] &= value ^ 1
    return tuple(a for a, value in enumerate(survive) if value)
