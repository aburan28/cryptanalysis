"""Compare every native output coefficient with independent subset arithmetic."""
import ctypes as ct
import hashlib
import json
from pathlib import Path
import platform
import random
import sys

import reference

HERE = Path(__file__).resolve().parent
METHODS = ('accepted-full', 'full-axes', 'triangular', 'triangular-tile16',
           'recursive', 'recursive-leaf8', 'recursive-leaf16', 'recursive-leaf32')


def bind(path, width):
    word = ct.c_uint32 if width == 32 else ct.c_uint64
    lib = ct.CDLL(str(path))
    fn = getattr(lib, 'transform'+str(width))
    fn.argtypes = [ct.POINTER(word), ct.c_uint64, ct.c_uint32, ct.c_uint32,
                  ct.c_uint32, ct.POINTER(ct.c_uint64)]
    fn.restype = ct.c_int
    return word, fn


def native(word, fn, flat, k, method):
    data = (word*len(flat))(*flat)
    counts = (ct.c_uint64*4)()
    assert fn(data, len(flat), k, method, 1, counts) == 0
    return list(data), list(counts)


def main():
    output = HERE/'native-validation.json'
    if output.exists():
        raise FileExistsError(output)
    receipt = json.loads((HERE/'build/receipt.json').read_text())
    bindings = dict(receipt['sources']) | dict(receipt['binaries'])
    bindings.update({str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (Path(__file__).resolve(), HERE/'reference.py')})
    rows = []
    for path in receipt['binaries']:
        for width in (32, 64):
            word, fn = bind(Path(path), width)
            counters = {'exhaustive_symmetric': 0, 'seeded_symmetric': 0,
                        'asymmetric_fallback': 0, 'coefficient_comparisons': 0}
            def verify(matrix, category):
                n, k = len(matrix), len(matrix).bit_length()-1
                flat = [v for row in matrix for v in row]
                expected, _ = reference.full_transform(matrix)
                expected = [v for row in expected for v in row]
                symmetric = category != 'asymmetric_fallback'
                if n <= 8:
                    assert expected == [v for row in reference.direct_definition(matrix) for v in row]
                for method in range(len(METHODS)):
                    actual, counts = native(word, fn, flat, k, method)
                    assert actual == expected, (path, width, k, METHODS[method], category)
                    selected = method if symmetric else min(method, 1)
                    if not symmetric and method >= 2:
                        selected = 0
                    assert counts[3] == selected
                    if selected < 2:
                        xors, copies = k*n*n, 0
                    elif selected < 4:
                        xors = k*n*n//2 + n*((k-1)*n+k+1)//4
                        copies = n*(n-1)//2
                    else:
                        xors = (n*n*(2*k+1)-n*(k+1))//4
                        copies = (3*n*n-n*(k+3))//4
                        t = min(k, (0,3,4,5)[selected-4])
                        m, nodes = 1 << t, 1 << (k-t)
                        leaf_xors = (m*m*(2*t+1)-m*(t+1))//4
                        leaf_copies = (3*m*m-m*(t+3))//4
                        xors += nodes*(t*m*m-leaf_xors)
                        copies -= nodes*leaf_copies
                    assert counts[:2] == [xors, copies], (k, method, counts)
                    if method >= 2 and symmetric:
                        assert counts[2] == n*(n-1)//2
                    counters['coefficient_comparisons'] += len(flat)
                counters[category] += 1
            for n in (2, 4):
                entries = [(a,b) for a in range(n) for b in range(a+1)]
                for bits in range(1 << len(entries)):
                    matrix = [[0]*n for _ in range(n)]
                    for j,(a,b) in enumerate(entries):
                        matrix[a][b] = matrix[b][a] = (bits>>j)&1
                    verify(matrix, 'exhaustive_symmetric')
            verify([[(1 << width)-1]], 'seeded_symmetric')
            rng = random.Random(202610014602)
            for k in range(1, 11):
                n = 1 << k
                for shape in ('dense', 'sparse', 'diagonal', 'zero'):
                    matrix = [[0]*n for _ in range(n)]
                    for a in range(n):
                        for b in range(a+1):
                            value = rng.getrandbits(width)
                            if shape == 'zero' or (shape == 'diagonal' and a != b) or (shape == 'sparse' and rng.randrange(16)):
                                value = 0
                            matrix[a][b] = matrix[b][a] = value
                    verify(matrix, 'seeded_symmetric')
                    matrix[0][n-1] ^= 1 << (width-1)
                    verify(matrix, 'asymmetric_fallback')
                print('PASS', Path(path).name, width, k, flush=True)
            # ABI failure does not write output or statistics.
            data = (word*4)(1,2,3,4)
            stats = (ct.c_uint64*4)(8,8,8,8)
            for length, k, method, guard in ((3,1,0,1),(4,11,0,1),(4,1,8,1),(4,1,0,2)):
                assert fn(data,length,k,method,guard,stats) == 1
                assert list(data) == [1,2,3,4] and list(stats) == [8]*4
            rows.append({'binary':path, 'word_bits':width, **counters})
    for p,h in bindings.items():
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest() == h
    report = {'schema':'recursive-symmetric-transform-native-validation/1', 'status':'PASS',
              'python':platform.python_version(), 'architecture':platform.machine(),
              'platform':platform.platform(), 'bindings':bindings, 'records':rows,
              'methods':METHODS, 'maximum_fixed_variables':20,
              'scope':'Standalone coefficient kernels only; full checker and GPU integration untested.',
              'timing_eligible':False, 'candidate_id':None, 'online_speedup':None}
    output.write_text(json.dumps(report,indent=2)+'\n')
    print('NATIVE_VALIDATION_PASS', json.dumps(rows), flush=True)


if __name__ == '__main__':
    main()
