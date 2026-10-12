"""Compare reused packed ANF buffers to fresh direct S3 equations."""
import hashlib
import json
import random

from packed_query import HERE, PackedAffineRows, PackedContext
from affine_query import AffineEquations, equations, s3
from chain_fixture import GF2n, coordinate, fixture


def unpack(packed):
    return [frozenset(packed.terms[packed.offsets[i]:packed.offsets[i + 1]])
            for i in range(packed.template.n)]


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
            template = AffineEquations(field, curve_b, auxiliary, summand)
            packed = PackedAffineRows(template)
            offsets_id, terms_id = id(packed.offsets), id(packed.terms)
            targets = [0, (1 << n) - 1] + [rng.randrange(1 << n)
                                             for _ in range(100)]
            for target_x in targets:
                count_terms = packed.fill(target_x)
                assert packed.offsets[n] == count_terms <= packed.capacity
                direct = equations(field, s3(field, curve_b, auxiliary,
                                              summand, {0: target_x}))
                assert unpack(packed) == [frozenset(row) for row in direct]
                assert id(packed.offsets) == offsets_id and id(packed.terms) == terms_id
                count += 1
            for invalid in (-1, 1 << n, None, 0.5):
                try:
                    packed.fill(invalid)
                except ValueError:
                    pass
                else:
                    raise AssertionError('accepted invalid target')
    case = fixture(9, 4, 3, 1)
    for sanitized in (False, True):
        context = PackedContext(case, sanitized=sanitized)
        try:
            for target in (0, 1, 2, 9, 100, 511):
                old, candidate = context.run(target, 'affine'), context.run(target, 'packed')
                for key in ('status', 'assignment', 'point_verified', 'equation_verified'):
                    assert candidate[key] == old[key], (target, key)
                assert sum(candidate[key] for key in
                           ('pack_ns', 'native_ns', 'verify_ns', 'point_replay_ns')) == candidate['online_ns']
        finally:
            context.close()
    print('F6_PACKED_TARGET_EXACT_PASS', count, 'direct S3 equations and six targets', flush=True)


if __name__ == '__main__':
    main()
