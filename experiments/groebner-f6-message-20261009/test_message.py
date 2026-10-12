"""Exhaustive small systems and S3 controls for cached separator messages."""
import hashlib
import json
import random

from message_query import HERE, MessageContext, MessageLayout, satisfies
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
            all_equations = static + dynamic
            expected = any(all(sum((a & term) == term for term in row) % 2 == 0
                               for row in all_equations)
                           for a in range(1 << nvars))
            cold = cold_solve(nvars, all_equations, max_bag=nvars)
            for sanitized in (False, True):
                layout = MessageLayout(nvars, static, boundary, max_bag=nvars,
                                       sanitized=sanitized)
                try:
                    result = layout.run(dynamic)
                finally:
                    layout.close()
                assert (result['status'] == 'satisfiable') == expected
                assert result['status'] == cold['status']
                if expected:
                    assert result['independently_verified'] is True
                    assert all(satisfies(row, result['assignment'])
                               for row in all_equations)
            controls += 1
    case = fixture(9, 4, 3, 1)
    for sanitized in (False, True):
        context = MessageContext(case, sanitized=sanitized)
        try:
            assert context.boundary_mask.bit_count() == 12
            assert context.message.setup['residual_factor_words'] <= 32
            for target in (0, 1, 2, 9, 100, 511):
                prepared = context.run(target, 'prepared')
                message = context.run(target, 'message')
                assert (message['status'], message['point_verified']) == (
                    prepared['status'], prepared['point_verified'])
                assert message['assignment'] == prepared['assignment']
                if message['assignment'] is not None:
                    assert message['equation_verified'] is True
        finally:
            context.close()
    print('F6_MESSAGE_EXACT_PASS', controls, 'random systems and six S3 targets', flush=True)


if __name__ == '__main__':
    main()
