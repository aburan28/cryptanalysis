"""Independent Sage replay of fixed-output group completion and GF(2) ranks."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector

HERE = Path(__file__).resolve().parent
result = json.loads((HERE/'linear_result.json').read_text())
protocol = json.loads((HERE/'linear_protocol.json').read_text())
runtime = json.loads((HERE/'sage_runtime_info.json').read_text())
assert runtime['status'] == 'verified'
assert result['status'] == 'PASS_SUPPLIED_OUTPUT_COMPLETION_PANEL'
assert result['source_sha256']['linear_protocol.json'] == hashlib.sha256(
    (HERE/'linear_protocol.json').read_bytes()).hexdigest()

ring = PolynomialRing(GF(2), 't')
t = ring.gen()
field = GF(2**41, 't', modulus=t**41+t**3+1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])


def dec(value):
    return field(ring([(int(value) >> i) & 1 for i in range(41)]))


def enc(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def point(value):
    return curve(dec(value[0]), dec(value[1]))


def halftrace(value):
    output = field.zero()
    for _ in range(21):
        output += value
        value = value**4
    return output


def linear_replay(z_integer):
    z = dec(z_integer)
    assert z and z.trace() == 0
    seed_basis = [dec(1 << (i+1))**(2**30) for i in range(6)]
    product_basis = [dec(1 << (i+2))**(2**30) for i in range(11)]
    columns = [halftrace(value**2) for value in seed_basis]
    columns += [value*z for value in product_basis]
    columns += [field.one()]
    rhs = halftrace(z**2)
    bits = [enc(value) for value in columns]
    A = matrix(GF(2), 41, 18, lambda i, j: (bits[j] >> i) & 1)
    b = vector(GF(2), [(enc(rhs) >> i) & 1 for i in range(41)])
    rank = int(A.rank())
    if b not in A.column_space():
        return {'rank': rank, 'status': 'NO_MEMBER'}
    solution = A.solve_right(b)
    mask = sum(int(bit) << i for i, bit in enumerate(solution))
    if not (mask & 63):
        assert rank == 18
        return {'rank': rank, 'status': 'NO_MEMBER'}
    seed, product, branch = mask & 63, (mask >> 6) & 2047, (mask >> 17) & 1
    assert (sum((seed >> i & 1)*seed_basis[i] for i in range(6))
            + field.zero()) != 0
    s = sum((seed >> i & 1)*seed_basis[i] for i in range(6))
    p = sum((product >> i & 1)*product_basis[i] for i in range(11))
    assert p*z + halftrace((s+z)**2) + field(branch) == 0
    return {'rank': rank, 'status': 'RELAXED_PAIR_MEMBER',
            'seed_sum': seed, 'product_mask': product, 'branch': branch}


left = point(result['left_point'])
assert left[0] == 1/dec(result['left_reciprocal_z'])
checks = []
for query in result['queries']:
    target = point(query['target'])
    signs = []
    for item in query['signs']:
        lp, rp = point(item['left_point']), point(item['right_point'])
        assert lp in (left, -left)
        assert lp + rp == target
        inverse = item['inverse']
        assert rp[0] == 1/dec(inverse.get('reciprocal_z', enc(1/rp[0])))
        actual = linear_replay(enc(1/rp[0]))
        assert actual['rank'] == inverse['rank']
        assert actual['status'] == inverse['status']
        if actual['status'] == 'RELAXED_PAIR_MEMBER':
            assert all(actual[key] == inverse[key]
                       for key in ('seed_sum', 'product_mask', 'branch'))
        signs.append(actual)
    assert (sum(x['status'] == 'RELAXED_PAIR_MEMBER' for x in signs) ==
            query['hit_signs'])
    checks.append({'label': query['label'], 'signs': signs,
                   'status': query['status']})
assert checks[0]['status'] == 'RELAXED_SUM_HIT'
assert checks[1]['status'] == 'COMPLETE_RELAXED_NO_SUM'
output = {'status': 'PASS_INDEPENDENT_SAGE_GROUP_AND_GF2_REPLAY',
          'checks': checks,
          'source_sha256': {'linear_protocol.json': hashlib.sha256(
              (HERE/'linear_protocol.json').read_bytes()).hexdigest(),
              'linear_result.json': hashlib.sha256(
              (HERE/'linear_result.json').read_bytes()).hexdigest(),
              'verify_sage.py': hashlib.sha256(
              (HERE/'verify_sage.py').read_bytes()).hexdigest(),
              'sage_runtime_info.json': hashlib.sha256(
              (HERE/'sage_runtime_info.json').read_bytes()).hexdigest()}}
(HERE/'sage_replay.json').write_text(json.dumps(output, indent=2, sort_keys=True)+'\n')
print(output['status'])
