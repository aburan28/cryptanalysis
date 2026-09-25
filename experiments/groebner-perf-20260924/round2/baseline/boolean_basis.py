"""Cheap exact filtering of assignments by a computed Boolean basis."""


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
