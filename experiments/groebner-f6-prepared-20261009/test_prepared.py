"""Exhaustive small systems and frozen S3 controls for prepared factors."""
import hashlib
import json
import random

from prepared_query import HERE, PreparedLayout, QueryContext, cold_solve
from chain_fixture import fixture


def main():
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    for name, digest in receipt['binaries'].items():
        assert hashlib.sha256((HERE / 'build' / name).read_bytes()).hexdigest() == digest
    rng = random.Random(20261009)
    controls = 0
    for nvars in range(1, 7):
        for _ in range(15):
            equations = [[rng.randrange(1 << nvars)
                          for _ in range(rng.randrange(1, 6))]
                         for _ in range(rng.randrange(1, 6))]
            index = rng.randrange(len(equations))
            static = equations[:index] + equations[index + 1:]
            expected = any(all(sum((assignment & term) == term for term in row) % 2 == 0
                               for row in equations) for assignment in range(1 << nvars))
            cold = cold_solve(nvars, equations, max_bag=nvars)
            for sanitized in (False, True):
                layout = PreparedLayout(nvars, static, index, max_bag=nvars,
                                        sanitized=sanitized)
                try:
                    prepared = layout.run([equations[index]])
                finally:
                    layout.close()
                assert (prepared['status'] == 'satisfiable') == expected
                assert prepared['status'] == cold['status']
                if expected:
                    assert prepared['assignment'] == cold['assignment']
                    assert prepared['independently_verified'] is True
            controls += 1
    empty = PreparedLayout(64, [], 0, max_bag=1)
    try:
        result = empty.run([])
        assert result['status'] == 'satisfiable' and result['assignment'] == 0
    finally:
        empty.close()
    case = fixture(9, 4, 3, 1)
    for sanitized in (False, True):
        context = QueryContext(case, sanitized=sanitized)
        try:
            for target in (0, 1, 2, 9, 100, 511):
                cold = context.run(target, 'cold')
                prepared = context.run(target, 'prepared')
                assert (prepared['status'], prepared['assignment'],
                        prepared['point_verified']) == (
                            cold['status'], cold['assignment'], cold['point_verified'])
                for key in ('width', 'factor_states', 'elimination_states',
                            'transform_xors', 'membership_tests'):
                    assert prepared['solver'][key] == cold['solver'][key], key
                assert prepared['solver']['reused_factor_states'] > 0
        finally:
            context.close()
    print('F6_PREPARED_EXACT_PASS', controls, 'random systems and six S3 targets', flush=True)


if __name__ == '__main__':
    main()
