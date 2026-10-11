"""Independent replay of all 63 N41 trace-relaxed target completions."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INPUT = ROOT/'n131_w18_four_pairs/native_join/native_input.txt'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE/'protocol.json').read_text())
    result = json.loads((HERE/'result.json').read_text())
    assert result['status'] == 'PASS_ALL_63_N41_FIRST_PAIR_SUMS_SURVIVE_TRACE_RELAXATION'
    assert result['accepted_first_pair_seed_sums'] == list(range(1,64))
    assert protocol['source_sha256']['input'] == sha(INPUT)
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

    def move(point):
        return point+curve(point[0]**2, point[1]**2)

    def ordinary(point):
        return point != zero and point[0] != 0

    def chi(point):
        assert ordinary(point)
        return int((1/point[0]).trace())

    tokens = list(map(int, INPUT.read_text().split()))
    assert tokens[2:4] == [549756390943, 8]
    target = move(curve(dec(tokens[0]), dec(tokens[1])))
    assert coords(target) == result['target']
    slots, cursor = [], 4
    for _ in range(8):
        count = tokens[cursor]
        cursor += 1
        assert count == 64
        rows = []
        for _ in range(64):
            x,y,col,mask,branch,sign = tokens[cursor:cursor+6]
            cursor += 6
            rows.append((move(curve(dec(x),dec(y))),col,mask,branch,sign))
        slots.append(rows)
    assert cursor == len(tokens)
    fourth_exact_sums = set()
    for i in range(64):
        for j in range(i+1,64):
            if slots[6][i][1] == slots[7][j][1]:
                continue
            fourth_exact_sums.add(slots[6][i][0]+slots[7][j][0])
    relaxed_hit_exact_fourth = 0
    for record in result['completions']:
        selected, six_columns, seed_sum = [], [], record['first_seed_sum']
        for group, ids in enumerate(record['exact_pair_ids']):
            i,j = ids
            assert 0 <= i < j < 64
            left,right = slots[2*group][i],slots[2*group+1][j]
            assert left[1] != right[1]
            assert (left[1],right[1]) == tuple(record['exact_pair_columns'][group])
            six_columns.extend((left[1],right[1]))
            pair_sum = left[0]+right[0]
            assert coords(pair_sum) == record['first_three_pair_points'][group]
            selected.append(pair_sum)
            if group == 0:
                assert left[2]^right[2] == seed_sum
        assert len(set(six_columns)) == 6
        D = curve(*[dec(v) for v in record['relaxed_fourth_pair_point']])
        assert ordinary(D) and chi(D) == 0
        assert 549756390943*D == zero
        middle0 = selected[0]+selected[1]
        middle1 = selected[2]+D
        assert ordinary(middle0) and ordinary(middle1)
        assert coords(middle0) == record['middle_points'][0]
        assert coords(middle1) == record['middle_points'][1]
        assert all(chi(point) == 0 for point in selected+[D,middle0,middle1,target])
        assert middle0+middle1 == target
        relaxed_hit_exact_fourth += D in fourth_exact_sums
    audit = {'status': 'PASS_ALL_63_N41_TRACE_RELAXED_COMPLETIONS_INDEPENDENT_SAGE',
             'accepted_first_pair_sums': 63,
             'exact_fourth_pair_sum_set_size': len(fourth_exact_sums),
             'selected_relaxed_D_in_exact_fourth_pair_sum_set': relaxed_hit_exact_fourth,
             'sha256': {'protocol': sha(HERE/'protocol.json'),
                        'result': sha(HERE/'result.json'),
                        'input': sha(INPUT),
                        'audit_sage.py': sha(HERE/'audit_sage.py'),
                        'runtime': sha(HERE/'sage_runtime_info.json')}}
    (HERE/'audit.json').write_text(json.dumps(audit, sort_keys=True, indent=2)+'\n')
    print(json.dumps(audit))


if __name__ == '__main__':
    main()
