"""Deterministic exhaustive, word-boundary and fresh-symmetry controls."""
import random

def cases():
    for value in range(4096):
        items = [(m << 1, 1 << e) for e in range(3) for m in range(4) if value >> (4 * e + m) & 1]
        yield f'exhaustive-{value}', 1, 2, 3, items
    rng = random.Random(2026093043)
    for y in range(1, 11):
        for e in (31, 32, 33, 65):
            for repeat in range(4):
                x = 2 if repeat < 2 else 3
                terms = [(m, rng.getrandbits(e)) for m in range(1 << (x + y))
                         if (m >> x).bit_count() <= 2 and rng.randrange(8) == 0]
                terms += terms[:3] * 2 + [(0, 0)]
                yield f'random-y{y}-e{e}-{repeat}', x, y, e, terms
    for x in (3, 4):
        for y in (7, 8, 9, 10):
            for e in (31, 32, 33):
                a, b = 1 << (x + y - 2), 1 << (x + y - 1)
                impossible = [(a, 1), (b, 2), (a | b, 1 << (e - 1)), (0, 1 << (e - 1))]
                for label, terms in [('symmetric', impossible), ('asymmetric', impossible + [(1, 1)]),
                                     ('symmetric-again', impossible)]:
                    yield f'{label}-x{x}-y{y}-e{e}', x, y, e, terms
    # Exactly 32 independent lifted rows, including a pivot above bit 31.
    # Linear pins force the complete residual root set to {0}.
    monomials = [1 << i for i in range(10)]
    monomials += [(1 << i) | (1 << j) for i in range(10) for j in range(i + 1, 10)]
    selected = monomials[:31] + [monomials[-1]]
    yield 'rank32-high-word-pivot', 2, 10, 32, [(m << 2, 1 << e) for e, m in enumerate(selected)]
    # A constant inconsistency whose original-equation witness uses bit 31.
    yield 'high-equation-constant-witness', 2, 10, 32, [(0, 1 << 31)]
