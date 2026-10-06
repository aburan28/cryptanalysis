"""Exact recursive symmetric Boolean transform; standalone reference only."""
import hashlib
import json
from pathlib import Path
import platform
import random

HERE = Path(__file__).resolve().parent

def full_transform(matrix):
    values = [row[:] for row in matrix]
    n, xors = len(values), 0
    bit = n // 2
    while bit:
        for row in range(n):
            if row & bit:
                for column in range(n):
                    values[row][column] ^= values[row ^ bit][column]
                    xors += 1
        bit >>= 1
    bit = n // 2
    while bit:
        for row in range(n):
            for column in range(n):
                if column & bit:
                    values[row][column] ^= values[row][column ^ bit]
                    xors += 1
        bit >>= 1
    return values, xors


def direct_definition(matrix):
    """Subset-incidence definition, independent of butterfly traversal."""
    n = len(matrix)
    output = [[0] * n for _ in range(n)]
    for a in range(n):
        for b in range(n):
            for i in range(n):
                if i & a != i:
                    continue
                for j in range(n):
                    if j & b == j:
                        output[a][b] ^= matrix[i][j]
    return output



def recursive(matrix):
    n = len(matrix)
    if n == 1:
        return [matrix[0][:]], 0, 0
    h = n // 2
    e, xe, ce = recursive([row[:h] for row in matrix[:h]])
    f, xf, cf = recursive([row[h:] for row in matrix[h:]])
    d, xd = full_transform([row[h:] for row in matrix[:h]])
    xors, copies = xe + xf + xd, ce + cf
    # F <- F + E + D + D^T. Diagonal D terms cancel in characteristic two.
    for i in range(h):
        f[i][i] ^= e[i][i]
        xors += 1
        for j in range(i):
            f[i][j] ^= e[i][j] ^ d[i][j] ^ d[j][i]
            f[j][i] = f[i][j]
            xors += 3
            copies += 1
    output = [[0] * n for _ in range(n)]
    for i in range(h):
        for j in range(h):
            output[i][j] = e[i][j]
            output[i+h][j+h] = f[i][j]
            output[i][j+h] = output[j+h][i] = d[i][j] ^ e[i][j]
            xors += 1
            copies += 1
    return output, xors, copies


def verify(matrix):
    n = len(matrix)
    k = n.bit_length() - 1
    expected, full_xors = full_transform(matrix)
    symmetric = all(matrix[i][j] == matrix[j][i] for i in range(n) for j in range(i))
    if symmetric:
        actual, xors, copies = recursive(matrix)
        assert xors == (n*n*(2*k+1) - n*(k+1))//4
        assert copies == (3*n*n - n*(k+3))//4
    else:
        actual, xors = full_transform(matrix)
        copies = 0
    assert actual == expected
    assert full_xors == k*n*n
    if n <= 8:
        assert actual == direct_definition(matrix)
    return symmetric


def main():
    exhaustive = seeded = asymmetric = 0
    for n in (2, 4):
        entries = [(a, b) for a in range(n) for b in range(a+1)]
        for bits in range(1 << len(entries)):
            matrix = [[0]*n for _ in range(n)]
            for j, (a, b) in enumerate(entries):
                matrix[a][b] = matrix[b][a] = (bits >> j) & 1
            assert verify(matrix)
            exhaustive += 1
    rng = random.Random(202610014601)
    for k in range(1, 8):
        n = 1 << k
        for width in (1, 31, 32, 63, 64, 65, 127, 128):
            for _ in range(4):
                matrix = [[0]*n for _ in range(n)]
                for a in range(n):
                    for b in range(a+1):
                        matrix[a][b] = matrix[b][a] = rng.getrandbits(width)
                assert verify(matrix)
                seeded += 1
                matrix[0][n-1] ^= 1 << (width-1)
                assert not verify(matrix)
                asymmetric += 1
    predictions = []
    # Independently accumulate recurrences rather than only evaluating a formula.
    previous_xors = previous_copies = 0
    for k in range(1, 11):
        n, h = 1 << k, 1 << (k-1)
        xors = 2*previous_xors + (k-1)*h*h + 3*h*(h-1)//2 + h + h*h
        copies = 2*previous_copies + h*(h-1)//2 + h*h
        assert xors == (n*n*(2*k+1) - n*(k+1))//4
        assert copies == (3*n*n - n*(k+3))//4
        previous_xors, previous_copies = xors, copies
        predictions.append({'k': k, 'N': n, 'full_xors': k*n*n,
                            'recursive_xors': xors, 'mirror_copies': copies})
    report = {'schema': 'recursive-symmetric-Boolean-transform-reference/1',
              'status': 'PASS', 'python': platform.python_version(),
              'architecture': platform.machine(),
              'sources': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (Path(__file__).resolve(),)},
              'exhaustive_symmetric': exhaustive, 'seeded_symmetric': seeded,
              'asymmetric_fallback': asymmetric, 'operation_predictions': predictions,
              'scope': 'Standalone algebraic reference; no native integration, GPU or elapsed-time claim.',
              'timing_eligible': False, 'candidate_id': None, 'online_speedup': None}
    output = HERE / 'reference.json'
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
