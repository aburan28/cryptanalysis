"""Independent GF(2^131) point and target-binding replay for the public query."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PUBLIC = ROOT / 'n131_fixed_seed_eight_pair_circuit_20261010/target_preimages.json'
N = 131
MODULUS = (1 << N) | (1 << 13) | (1 << 2) | (1 << 1) | 1
MASK = (1 << N) - 1


def mul(a, b):
    out = 0
    while b:
        if b & 1:
            out ^= a
        b >>= 1
        a <<= 1
        if a >> N:
            a ^= MODULUS
    return out


def inverse(a):
    assert a
    u, v = a, MODULUS
    g, h = 1, 0
    while u != 1:
        shift = u.bit_length() - v.bit_length()
        if shift < 0:
            u, v = v, u
            g, h = h, g
            shift = -shift
        u ^= v << shift
        g ^= h << shift
    while g.bit_length() > N:
        g ^= MODULUS << (g.bit_length() - N - 1)
    return g


def square(a):
    return mul(a, a)


def trace(a):
    value, total = a, 0
    for _ in range(N):
        total ^= value
        value = square(value)
    assert total in (0, 1)
    return total


def on_curve(point):
    x, y = point
    return square(y) ^ mul(x, y) == mul(square(x), x) ^ 1


def double(point):
    x, y = point
    if x == 0:
        return None
    slope = x ^ mul(y, inverse(x))
    xx = square(slope) ^ slope
    yy = square(x) ^ mul(slope ^ 1, xx)
    return (xx, yy)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    public = json.loads(PUBLIC.read_text())
    protocol = json.loads((HERE / 'protocol.json').read_text())
    target = tuple(public['public_target'])
    assert protocol['public_target'] == list(target)
    assert protocol['public_workload_id'] == public['workload_id']
    assert len(public['preimages']) == len(protocol['raw_target_preimage_z']) == 4
    rows = []
    for index, (source, z) in enumerate(zip(public['preimages'],
                                             protocol['raw_target_preimage_z'])):
        assert source['index'] == index
        point = tuple(source['point'])
        x = point[0]
        shifted = source['reciprocal_x_z']
        assert on_curve(point)
        assert mul(x, z) == 1
        assert mul(x ^ 1, shifted) == 1
        assert z == inverse(x) and shifted != z
        assert double(double(point)) == target
        rows.append({'index': index, 'x': x, 'standard_z': z,
                     'standard_trace': trace(z),
                     'archived_shifted_z': shifted, 'quadruple_equals_public': True})
    # The circuit's two-bit mux uses index = flag0 + 2*flag1.
    zs = protocol['raw_target_preimage_z']
    for index in range(4):
        f0, f1 = index & 1, index >> 1
        selected = zs[0]
        if f0:
            selected ^= zs[0] ^ zs[1]
        if f1:
            selected ^= zs[0] ^ zs[2]
        if f0 & f1:
            selected ^= zs[0] ^ zs[1] ^ zs[2] ^ zs[3]
        assert selected == zs[index]
    assert protocol['source_sha256']['target_preimages.json'] == sha(PUBLIC)
    assert protocol['source_sha256']['run.py'] == sha(HERE / 'run.py')
    assert protocol['source_sha256']['circuit.py'] == sha(HERE / 'circuit.py')
    result = {'status': 'PASS_FOUR_PUBLIC_POINT_BINDINGS_AND_MUX',
              'public_target': list(target), 'preimages': rows,
              'protocol_sha256': sha(HERE / 'protocol.json'),
              'source_sha256': sha(Path(__file__))}
    (HERE / 'binding_audit.json').write_text(json.dumps(result, indent=2,
                                                       sort_keys=True) + '\n')
    print(json.dumps({'status': result['status'], 'preimages': len(rows),
                      'standard_traces': [row['standard_trace'] for row in rows]}))


if __name__ == '__main__':
    main()
