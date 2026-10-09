"""Exact bitplane controls against exhaustive systems and S3 replay."""
import hashlib
import json
import random

from bitplane_query import (HERE, BitplaneContext, BitplaneLayout,
                            canonical, satisfies)
from chain_fixture import fixture


def dynamic_rows(template, nbits, target_x):
    base = template[:nbits]
    result = []
    for row in range(nbits):
        terms = set(canonical(base[row]))
        for bit in range(nbits):
            if target_x >> bit & 1:
                terms.symmetric_difference_update(canonical(base[row]))
                terms.symmetric_difference_update(
                    canonical(template[(bit + 1) * nbits + row]))
        result.append(sorted(terms))
    return result


def main():
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    for name, digest in receipt['binaries'].items():
        assert hashlib.sha256((HERE / 'build' / name).read_bytes()).hexdigest() == digest
    rng = random.Random(20261009)
    controls = 0
    for nvars in range(1, 7):
        for _ in range(15):
            nbits = min(nvars, 3)
            static = [[rng.randrange(1 << nvars) for _ in range(rng.randrange(1, 5))]
                      for _ in range(rng.randrange(1, 5))]
            template = [[rng.randrange(1 << nvars)
                         for _ in range(rng.randrange(1, 5))]
                        for _ in range((nbits + 1) * nbits)]
            boundary = 0
            for row in template:
                for term in row:
                    boundary |= term
            for sanitized in (False, True):
                layout = BitplaneLayout(nvars, static, boundary, nbits, template,
                                        max_bag=nvars, sanitized=sanitized)
                try:
                    for target in range(1 << nbits):
                        dynamic = dynamic_rows(template, nbits, target)
                        expected = any(all(satisfies(canonical(row), assignment)
                                           for row in static + dynamic)
                                       for assignment in range(1 << nvars))
                        result = layout.run(target)
                        assert (result['status'] == 'satisfiable') == expected
                        if expected:
                            assert all(satisfies(canonical(row), result['assignment'])
                                       for row in static + dynamic)
                        controls += 1
                finally:
                    layout.close()
    for sanitized in (False, True):
        try:
            BitplaneLayout(3, [[0]], 0, 1, [[1], [1]],
                           max_bag=3, sanitized=sanitized)
        except RuntimeError:
            pass
        else:
            raise AssertionError('accepted target term outside declared boundary')
    case = fixture(9, 4, 3, 1)
    for sanitized in (False, True):
        context = BitplaneContext(case, sanitized=sanitized)
        try:
            assert context.index.setup['static_assignments'] == 4096
            for target in (0, 1, 2, 9, 100, 511):
                baseline, candidate = context.run(target, 'packed'), context.run(target, 'bitplane')
                assert baseline['status'] == candidate['status']
                if candidate['assignment'] is not None:
                    assert candidate['equation_verified'] is True
                    assert candidate['point_verified'] is True
                assert (candidate['native_ns'] + candidate['verify_ns'] +
                        candidate['point_replay_ns'] == candidate['online_ns'])
        finally:
            context.close()
    print('F6_BITPLANE_EXACT_PASS', controls, 'exhaustive calls and six S3 targets', flush=True)


if __name__ == '__main__':
    main()
