"""Independent exhaustive and S3-chain checks for packed Boolean factors."""
import hashlib
import json
from pathlib import Path
import random

from chain_fixture import fixture
from packed_separator import HERE, solve


def main():
    receipt = json.loads((HERE / 'build/receipt.json').read_text())
    for name, digest in receipt['binaries'].items():
        assert hashlib.sha256((HERE / 'build' / name).read_bytes()).hexdigest() == digest
    rng = random.Random(87109)
    controls = 0
    for n in range(1, 8):
        for _ in range(35):
            equations = [[rng.randrange(1 << n) for _ in range(rng.randrange(1, 6))]
                         for _ in range(rng.randrange(1, 6))]
            expected = any(all(sum((assignment & term) == term for term in row) % 2 == 0
                               for row in equations) for assignment in range(1 << n))
            for sanitized in (False, True):
                result = solve(n, equations, max_bag=n, sanitized=sanitized)
                assert (result['status'] == 'satisfiable') == expected
                assert result['status'] in ('satisfiable', 'unsatisfiable')
                if expected:
                    assert result['independently_verified'] is True
            controls += 1
    assert solve(10, [[(1 << 10) - 1]], max_bag=5)['status'] == 'width-cap'
    capped = solve(10, [[(1 << 10) - 1]], max_bag=10, max_states=100)
    assert capped['status'] == 'state-cap' and capped['stage'] == 'factor-construction'
    assert solve(3, [[8]], max_bag=3)['status'] == 'invalid'
    free = solve(64, [], max_bag=1)
    assert free['status'] == 'satisfiable' and free['assignment'] == 0
    chain = fixture(9, 4, 3, 1)
    for sanitized in (False, True):
        result = solve(chain['nvars'], chain['equations'], max_bag=21,
                       max_states=100_000_000, sanitized=sanitized)
        assert result['status'] == 'satisfiable'
        assert result['width'] == 21 and result['independently_verified'] is True
    print('F6_PACKED_EXACT_PASS', controls, 'random systems and n9 m4 S3 chain', flush=True)


if __name__ == '__main__':
    main()
