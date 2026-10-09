"""Check compact-boundary answers against exhaustive and message controls."""
import hashlib
import json
import random

from compact_query import HERE, CompactContext, CompactLayout, satisfies
from message_query import MessageLayout
from prepared_query import cold_solve
from chain_fixture import fixture


def main():
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    for name, digest in receipt['binaries'].items():
        assert hashlib.sha256((HERE / 'build' / name).read_bytes()).hexdigest() == digest
    rng = random.Random(20261009)
    controls = 0
    for nvars in range(1, 7):
        for _ in range(15):
            static = [[rng.randrange(1 << nvars)
                       for _ in range(rng.randrange(1, 6))]
                      for _ in range(rng.randrange(1, 6))]
            dynamic = [[rng.randrange(1 << nvars)
                        for _ in range(rng.randrange(1, 6))]]
            boundary = 0
            for term in dynamic[0]:
                boundary |= term
            equations = static + dynamic
            expected = any(all(sum((a & term) == term for term in row) % 2 == 0
                               for row in equations)
                           for a in range(1 << nvars))
            cold = cold_solve(nvars, equations, max_bag=nvars)
            for sanitized in (False, True):
                baseline = MessageLayout(nvars, static, boundary,
                                         max_bag=nvars, sanitized=sanitized)
                compact = CompactLayout(nvars, static, boundary,
                                        max_bag=nvars, sanitized=sanitized)
                try:
                    old, new = baseline.run(dynamic), compact.run(dynamic)
                finally:
                    compact.close()
                    baseline.close()
                assert new['status'] == old['status'] == cold['status']
                assert (new['status'] == 'satisfiable') == expected
                assert new['assignment'] == old['assignment']
                if expected:
                    assert new['independently_verified'] is True
                    assert all(satisfies(row, new['assignment']) for row in equations)
                    assert old['eliminated'] - new['eliminated'] == nvars - boundary.bit_count()
            controls += 1
    for sanitized in (False, True):
        baseline = MessageLayout(6, [[1]], 1, max_bag=6, sanitized=sanitized)
        compact = CompactLayout(6, [[1]], 1, max_bag=6, sanitized=sanitized)
        try:
            assert baseline.run([[1 << 5]])['status'] == 'invalid'
            assert compact.run([[1 << 5]])['status'] == 'invalid'
        finally:
            compact.close()
            baseline.close()
    case = fixture(9, 4, 3, 1)
    for sanitized in (False, True):
        context = CompactContext(case, sanitized=sanitized)
        try:
            assert context.compact.setup['boundary_variables'] == 12
            assert context.compact.setup['residual_factor_words'] <= 32
            for target in (0, 1, 2, 9, 100, 511):
                old, new = context.run(target, 'message'), context.run(target, 'compact')
                assert (new['status'], new['assignment'], new['point_verified'],
                        new['equation_verified']) == (
                        old['status'], old['assignment'], old['point_verified'],
                        old['equation_verified'])
                if new['assignment'] is not None:
                    assert new['equation_verified'] is True
                    assert old['solver']['eliminated'] - new['solver']['eliminated'] == 18
        finally:
            context.close()
    print('F6_COMPACT_EXACT_PASS', controls, 'random systems and six S3 targets', flush=True)


if __name__ == '__main__':
    main()
