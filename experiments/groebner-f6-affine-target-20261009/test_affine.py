"""Check the affine S3 template against direct polynomial construction."""
import hashlib
import json
import random

from affine_query import HERE, AffineContext, AffineEquations, equations, s3
from chain_fixture import GF2n, coordinate, fixture


def canonical_rows(rows):
    return [frozenset(row) for row in rows]


def main():
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    for name, digest in receipt['sources'].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest
    rng = random.Random(20261009)
    count = 0
    for n in (4, 6, 9):
        field = GF2n(n)
        auxiliary, summand = coordinate(0, n), coordinate(n, 3)
        for curve_b in (0, 1):
            compiled = AffineEquations(field, curve_b, auxiliary, summand)
            for target_x in [0, (1 << n) - 1] + [rng.randrange(1 << n)
                                                   for _ in range(100)]:
                direct = equations(field, s3(field, curve_b, auxiliary,
                                              summand, {0: target_x}))
                assert canonical_rows(compiled.build(target_x)) == canonical_rows(direct)
                count += 1
            for invalid in (-1, 1 << n, None, 0.5):
                try:
                    compiled.build(invalid)
                except ValueError:
                    pass
                else:
                    raise AssertionError('accepted invalid target encoding')
    case = fixture(9, 4, 3, 1)
    for sanitized in (False, True):
        context = AffineContext(case, sanitized=sanitized)
        try:
            for target in (0, 1, 2, 9, 100, 511):
                old, new = context.run(target, 'compact'), context.run(target, 'affine')
                for key in ('status', 'assignment', 'point_verified', 'equation_verified'):
                    assert new[key] == old[key], (target, key)
                assert (new['equations_ns'] + new['solver_ns'] +
                        new['point_replay_ns'] == new['online_ns'])
        finally:
            context.close()
    print('F6_AFFINE_EXACT_PASS', count, 'direct S3 equations and six targets', flush=True)


if __name__ == '__main__':
    main()
