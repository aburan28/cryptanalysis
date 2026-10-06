"""Frozen exact controls shared with the preceding row-generation pilot."""
import random


def controls():
    cases = []
    for bits in range(256):
        cases.append((f'boolean3-{bits}', 1, 2, 1, [(m, 1) for m in range(8) if bits >> m & 1]))
    rng = random.Random(2026093040)
    for e in (1, 3, 31, 32, 33, 63, 64, 65, 127, 128):
        for i in range(10):
            items = [(m, rng.getrandbits(e)) for m in range(32) if (m >> 2).bit_count() <= 2 and rng.randrange(2)]
            items += items[:3] * 2 + [(0, 0)]
            cases.append((f'random-e{e}-{i}', 2, 3, e, items))
        if e >= 3:
            for y in range(2, 11):
                a, b = (1 << 2 + y - 2, 1 << 2 + y - 1)
                items = [(a | b, 1), (0, 1), (a, 1 << e - 1)]
                cases.append((f'affine-high-e{e}-y{y}', 2, y, e, items))
            cases.append((f'collision-e{e}', 2, 3, e, [(12, 1), (4, 1), (8, 1 << e - 1)]))
    impossible = [(16, 1), (32, 2), (48, 4), (0, 4)]
    for label, items in [('symmetric', impossible), ('asymmetric', impossible + [(1, 1)]), ('roots', [(1, 1), (4, 1), (2, 2), (8, 2), (16, 4), (32, 4)]), ('symmetric-again', impossible)]:
        cases.append((label, 4, 2, 3, items))
    assert len(cases) == 450
    return cases
