"""Independent checked-Sage replay of every transported N41 fiber row."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INPUT = ROOT/'n131_w18_four_pairs/native_join/native_input.txt'
FIXTURE = ROOT/'n41_transport_cubic_s8_20261011/fixture.json'
R = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE/'protocol.json').read_text())
    receipt = json.loads((HERE/'receipt.json').read_text())
    fixture = json.loads(FIXTURE.read_text())
    assert protocol['status'] == 'FROZEN_BEFORE_COMPLETE_N41_TARGET_FIBER'
    assert receipt['status'] == 'COMPLETE_EXACT_FIBER'
    assert protocol['source_sha256']['input.txt'] == sha(INPUT)
    assert protocol['source_sha256']['fixture.json'] == sha(FIXTURE)
    assert protocol['source_sha256']['projection.cpp'] == sha(HERE/'projection.cpp')
    assert protocol['source_sha256']['projection_native'] == sha(HERE/'projection_native')
    assert json.loads((HERE/'sage_runtime_info.json').read_text())['status'] == 'verified'
    ring = PolynomialRing(GF(2), 't')
    t = ring.gen()
    field = GF(2**41, 't', modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)

    def dec(value):
        return field(ring([(value >> i) & 1 for i in range(41)]))

    def enc(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def coords(point):
        return [enc(point[0]), enc(point[1])]

    def transport(point):
        return point+curve(point[0]**2, point[1]**2)

    tokens = list(map(int, INPUT.read_text().split()))
    original = curve(dec(tokens[0]), dec(tokens[1]))
    assert tokens[2:4] == [R, 8]
    assert coords(original) == fixture['public_target_original']
    target = transport(original)
    assert coords(target) == fixture['public_target_transported']
    slots, cursor = [], 4
    for _ in range(8):
        count = tokens[cursor]
        cursor += 1
        assert count == 64
        slot = []
        for _ in range(count):
            x, y, column, mask, branch, sign = tokens[cursor:cursor+6]
            cursor += 6
            point = curve(dec(x), dec(y))
            moved = transport(point)
            assert R*moved == zero and moved != zero
            slot.append((moved, column, mask, branch, sign))
        slots.append(slot)
    assert cursor == len(tokens)
    for i in range(4):
        assert slots[2*i] == slots[2*i+1]
    assert receipt['pair_list_sizes'] == [1956]*4
    assert receipt['right_four_probes'] == 1956**2
    assert receipt['raw_exact_sum_hits'] == (receipt['verified_rows']+
                                             receipt['cross_column_rejections'])
    assert receipt['verified_rows'] == len(receipt['first_witnesses']) == 12
    assert receipt['witnesses_truncated'] is False
    prefixes = [set() for _ in range(4)]
    rows = []
    for witness in receipt['first_witnesses']:
        ids = witness['ids']
        assert len(ids) == 8 and all(0 <= index < 64 for index in ids)
        selected = [slots[i][index] for i, index in enumerate(ids)]
        points = [item[0] for item in selected]
        columns = [item[1] for item in selected]
        masks = [item[2] for item in selected]
        assert len(set(columns)) == 8
        assert sum(points, zero) == target
        sums = [masks[2*i] ^ masks[2*i+1] for i in range(4)]
        assert sums == witness['seed_sums']
        packed = 0
        for i, value in enumerate(sums):
            packed |= value << (6*i)
            prefixes[i].add(packed & ((1 << (6*(i+1)))-1))
        rows.append({'masks': masks, 'columns': columns,
                     'source_points_transported': [coords(point) for point in points],
                     'seed_sums': sums})
    assert [sorted(p) for p in prefixes] == receipt['prefix_support']
    assert [len(p) for p in prefixes] == receipt['prefix_support_sizes']
    assert rows[0]['masks'] == fixture['known_masks']
    result = {'status': 'PASS_ALL_12_TRANSPORTED_N41_ROWS_SAGE',
              'curve_id': protocol['curve_id'],
              'target_original': coords(original),
              'target_transported': coords(target),
              'verified_rows': len(rows),
              'prefix_support_sizes': [len(p) for p in prefixes],
              'rows': rows,
              'sha256': {'protocol.json': sha(HERE/'protocol.json'),
                         'receipt.json': sha(HERE/'receipt.json'),
                         'input.txt': sha(INPUT), 'fixture.json': sha(FIXTURE),
                         'replay_sage.py': sha(HERE/'replay_sage.py'),
                         'sage_runtime_info.json': sha(HERE/'sage_runtime_info.json')}}
    (HERE/'sage_replay.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': result['status'],
                      'prefix_support_sizes': result['prefix_support_sizes']}))


if __name__ == '__main__':
    main()
