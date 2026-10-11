"""Portable exact correctness gates; timing thresholds are deliberately absent."""
import ctypes
import hashlib
import json
from pathlib import Path
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent/'pdp-scaling'), str(HERE/'round2')]
from boolean_basis import certify_boolean_basis
from boolean_certificate_native import certify_boolean_basis_native, Certificate, load_library, DEFAULT_LIBRARY
from boolean_f5b import BooleanF5B
from solve_dual import compute_dual_basis, _in_process, solve_dual, make_instance


def main():
    checked = 0
    libraries = [DEFAULT_LIBRARY, DEFAULT_LIBRARY.with_name('boolean-certificate-ubsan'+DEFAULT_LIBRARY.suffix)]
    def compare(nvars, equations, basis):
        nonlocal checked
        expected = certify_boolean_basis(nvars, equations, basis, monomial_cache=nvars <= 12)
        for library in libraries:
            actual = certify_boolean_basis_native(nvars, equations, basis, library=library)
            assert actual['verified'] == expected['verified'], (nvars, expected, actual)
            if expected['verified']:
                for key in ('root_count', 'standard_monomials', 'solutions'):
                    assert actual[key] == expected[key], (key, expected, actual)
            else:
                assert actual['reason'] == expected['reason'], (expected, actual)
            checked += 1
    for case in json.loads((HERE/'round3/inputs.json').read_text())['cases']:
        data = case['input']
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert digest == case['workload_sha256']
        compare(data['nvars'], data['equations'], data['basis'])
    rng = random.Random(2026092501)
    for n in range(1, 8):
        for _ in range(16):
            equations = [[rng.randrange(1 << n) for _ in range(rng.randrange(1, 12))] for _ in range(n+1)]
            engine = BooleanF5B(n, timeout=30)
            normalized = []
            for row in equations:
                s = set()
                for m in row:
                    s.symmetric_difference_update((m,))
                normalized.append(engine.from_terms(s))
            basis = [sorted(engine.terms(p)) for p in engine.basis(normalized)]
            compare(n, equations, basis)
            dual, _, _ = _in_process(n, equations)
            assert sorted(dual) == sorted(basis)
            for mutation in ([], [[0]], [[]], basis[:-1], basis+basis, [[0,0]]):
                compare(n, equations, mutation)
    for n in (6, 7, 13, 18, 20):
        for equations, basis in (([], []), ([[0]], [[0]]),
                                 ([[1 << (n-1)]], [[1 << (n-1)]]),
                                 ([[1 << i] for i in range(n)], [[1 << i] for i in range(n)])):
            compare(n, equations, basis)
    for library in libraries:
        for n, equations, basis in ((0, [], []), (21, [], []), (2, [[4]], []), (2, [], [[-1]]), (2, [[1.0]], [])):
            try:
                certify_boolean_basis_native(n, equations, basis, library=library)
            except ValueError:
                pass
            else:
                raise AssertionError('invalid mask or variable count accepted')
        lib = load_library(library)
        data = (ctypes.c_uint32*1)(1)
        zero = (ctypes.c_uint32*1)(0)
        for starts in ((1,1), (0,2)):
            offsets = (ctypes.c_uint32*2)(*starts)
            stats = Certificate()
            assert lib.boolean_certificate(2, data, 1, offsets, 1, data, 0, zero, 0, ctypes.byref(stats)) == 6
    def concurrent(i):
        equations = [[1 << k] if not (i >> k)&1 else [0,1 << k] for k in range(10)]
        return certify_boolean_basis_native(10, equations, equations)['solutions'] == [i]
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(concurrent, range(128)))
    instance = make_instance(11, 3, 2, seed=101)
    answers = [solve_dual(instance, verifier=v, transport=t) for v in ('python','native','auto') for t in ('library','subprocess')]
    assert all(a['verified'] and a['groebner_verified'] for a in answers)
    assert len({(a['basis_sha256'], a['assignment']) for a in answers}) == 1
    with patch('solve_dual.CERTIFICATE_LIBRARY', HERE/'absent-library'):
        fallback = solve_dual(instance, verifier='auto')
    assert fallback['verified'] and fallback['verifier'] == 'python'
    assert compute_dual_basis(9, [], verifier='native')['status'] == 'inconclusive'
    print(json.dumps({'status':'PASS','differential_checks':checked,'concurrent_checks':128,
                      'frozen_inputs':10,'transport_verifier_combinations':6,'ubsan':True}))


if __name__ == '__main__':
    main()
