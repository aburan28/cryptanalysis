"""Differential certificate checks, including an independent Singular oracle."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import random
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'pdp-scaling'))
from boolean_basis import certify_boolean_basis
from boolean_certificate_native import certify_boolean_basis_native, load_library, Certificate, DEFAULT_LIBRARY
from sage.all import GF, PolynomialRing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument('--output', type=Path, default=HERE / 'results/validation.json')
    args = parser.parse_args()
    rng = random.Random(2026092404)
    checked = rejected = ideals = 0
    def compare(n, equations, basis):
        nonlocal checked, rejected
        expected = certify_boolean_basis(n, equations, basis, monomial_cache=n <= 12)
        actual = certify_boolean_basis_native(n, equations, basis, library=args.library)
        assert actual['verified'] == expected['verified'], (n, equations, basis, expected, actual)
        if expected['verified']:
            for key in ('root_count', 'standard_monomials', 'solutions', 'ideal_equality', 'reduced_groebner_basis'):
                assert actual[key] == expected[key], (key, actual, expected)
        else:
            assert actual['reason'] == expected['reason'], (actual, expected)
            rejected += 1
        checked += 1
    cases = [(1, []), (2, [[0, 3]]), (2, [[0]]), (2, [[1], [0, 1]]),
             (3, [[3, 4]]), (3, [[0, 7]]), (9, []), (4, [[1, 1], [2, 2, 4]]),
             (4, [[]]*64+[[0]]), (4, [[1]]*64+[[0, 1]])]
    for n in range(1, 9):
        for _ in range(24):
            cases.append((n, [[rng.randrange(1 << n) for _ in range(rng.randrange(1, 16))]
                              for _ in range(rng.randrange(1, n+3))]))
    for n, equations in cases:
        ring = PolynomialRing(GF(2), n, names='x', order='degrevlex')
        xs = ring.gens()
        def polynomial(row):
            result = ring.zero()
            for mask in row:
                term = ring.one()
                for i, x in enumerate(xs):
                    if mask & (1 << i): term *= x
                result += term
            return result
        oracle = ring.ideal([polynomial(row) for row in equations] + [x*x+x for x in xs]).groebner_basis()
        basis = []
        for polynomial in oracle:
            terms = set()
            for powers in polynomial.dict():
                terms.symmetric_difference_update((sum(1 << i for i, exponent in enumerate(powers) if exponent),))
            if terms: basis.append(sorted(terms))
        compare(n, equations, basis)
        ideals += 1
        for mutation in ([[]], [[0]], [], basis[:-1], basis+basis, [[0, 0]]):
            compare(n, equations, mutation)
        if basis:
            compare(n, equations, [basis[0]+[basis[0][0]]] + basis[1:])
    # Arbitrary candidate bases test all rejection paths, not only solver output.
    for _ in range(1000):
        n = rng.randrange(1, 9)
        equations = [[rng.randrange(1 << n) for _ in range(rng.randrange(10))] for _ in range(rng.randrange(8))]
        basis = [[rng.randrange(1 << n) for _ in range(rng.randrange(8))] for _ in range(rng.randrange(6))]
        compare(n, equations, basis)
    for n in (6, 7, 13, 18, 20):
        compare(n, [], [])
        compare(n, [[1 << (n-1)]], [[1 << (n-1)]])
        compare(n, [[1 << i] for i in range(n)], [[1 << i] for i in range(n)])
        compare(n, [[0]], [[0]])
    # Contiguous ABI validation: offsets are allocated, but logically malformed.
    lib = load_library(args.library)
    terms = (ctypes.c_uint32*1)(1)
    for starts in ((1, 1), (0, 2)):
        offsets = (ctypes.c_uint32*2)(*starts)
        zero = (ctypes.c_uint32*1)(0)
        result = Certificate()
        assert lib.boolean_certificate(2, terms, 1, offsets, 1, terms, 0, zero, 0, ctypes.byref(result)) == 6
    for n, equations, basis in ((0, [], []), (21, [], []), (2, [[4]], []), (2, [], [[-1]]), (2, [[1.0]], [])):
        try: certify_boolean_basis_native(n, equations, basis, library=args.library)
        except ValueError: pass
        else: raise AssertionError('invalid input accepted')
    def concurrent(i):
        equations = [[1 << k] if not (i >> k)&1 else [0, 1 << k] for k in range(10)]
        return certify_boolean_basis_native(10, equations, equations, library=args.library)['solutions'] == [i]
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(concurrent, range(128)))
    report = {'status': 'PASS', 'oracle_ideals': ideals, 'differential_checks': checked,
              'false_bases_rejected': rejected, 'concurrent_checks': 128,
              'malformed_abi_checks': 2, 'seed': 2026092404,
              'oracle': 'Sage/Singular GF(2) grevlex with explicit field equations',
              'library_sha256': hashlib.sha256(args.library.read_bytes()).hexdigest(),
              'bounds': '1..20 variables; complete certification above 256 roots; solutions=None above 256'}
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__': main()
