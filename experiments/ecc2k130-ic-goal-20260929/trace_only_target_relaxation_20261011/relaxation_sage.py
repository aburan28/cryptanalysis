"""Complete N41 first-pair census with only the fourth pair's trace retained."""

import hashlib
import json
import time
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
    assert protocol['status'] == 'FROZEN_N41_THREE_EXACT_PAIRS_FOURTH_TRACE_RELAXATION'
    for name, path in {'input': INPUT, 'fixture': FIXTURE,
                       'producer': HERE/'relaxation_sage.py',
                       'runtime': HERE/'sage_runtime_info.json'}.items():
        assert protocol['source_sha256'][name] == sha(path)
    fixture = json.loads(FIXTURE.read_text())
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

    def ordinary(point):
        return point != zero and point[0] != 0

    def chi(point):
        assert ordinary(point)
        return int((1/point[0]).trace())

    tokens = list(map(int, INPUT.read_text().split()))
    assert tokens[2:4] == [R, 8]
    target = transport(curve(dec(tokens[0]), dec(tokens[1])))
    assert coords(target) == fixture['public_target_transported']
    assert chi(target) == 0
    slots, cursor = [], 4
    for _ in range(8):
        count = tokens[cursor]
        cursor += 1
        assert count == 64
        slot = []
        for _ in range(count):
            x, y, column, mask, branch, sign = tokens[cursor:cursor+6]
            cursor += 6
            point = transport(curve(dec(x), dec(y)))
            assert R*point == zero and ordinary(point) and chi(point) == 0
            slot.append((point, column, mask, branch, sign))
        slots.append(slot)
    assert cursor == len(tokens)
    assert all(slots[2*i] == slots[2*i+1] for i in range(4))

    started = time.monotonic_ns()
    pairs = []
    for group in range(4):
        rows = []
        slot = slots[2*group]
        for i in range(64):
            for j in range(i+1, 64):
                if slot[i][1] == slot[j][1]:
                    continue
                total = slot[i][0]+slot[j][0]
                assert ordinary(total) and chi(total) == 0
                rows.append((total, slot[i][2]^slot[j][2],
                             (slot[i][1], slot[j][1]), (i, j)))
        assert len(rows) == 1956
        pairs.append(rows)
    pair_build_ns = time.monotonic_ns()-started
    first_by_sum = {}
    for row in pairs[0]:
        first_by_sum.setdefault(row[1], row)
    assert set(first_by_sum) == set(range(1, 64))

    query_start = time.monotonic_ns()
    completions, candidate_checks = [], 0
    for seed_sum in range(1, 64):
        A = first_by_sum[seed_sum]
        found = None
        for B in pairs[1]:
            if len(set(A[2]+B[2])) != 4:
                continue
            middle0 = A[0]+B[0]
            if not ordinary(middle0):
                continue
            for C in pairs[2]:
                if len(set(A[2]+B[2]+C[2])) != 6:
                    continue
                candidate_checks += 1
                D = target-A[0]-B[0]-C[0]
                middle1 = C[0]+D
                if not ordinary(D) or not ordinary(middle1):
                    continue
                assert all(chi(point) == 0 for point in (A[0], B[0], C[0], D,
                                                        middle0, middle1))
                assert middle0+middle1 == target
                assert R*D == zero
                found = {'first_seed_sum': seed_sum,
                         'exact_pair_ids': [A[3], B[3], C[3]],
                         'exact_pair_columns': [A[2], B[2], C[2]],
                         'first_three_pair_points': [coords(A[0]), coords(B[0]),
                                                     coords(C[0])],
                         'relaxed_fourth_pair_point': coords(D),
                         'middle_points': [coords(middle0), coords(middle1)]}
                break
            if found:
                break
        assert found is not None, 'unexpected missing relaxed completion for sum '+str(seed_sum)
        completions.append(found)
    query_ns = time.monotonic_ns()-query_start
    result = {'status': 'PASS_ALL_63_N41_FIRST_PAIR_SUMS_SURVIVE_TRACE_RELAXATION',
              'curve_id': fixture['curve_id'],
              'target': coords(target),
              'pair_list_sizes': [len(rows) for rows in pairs],
              'first_pair_seed_sum_domain': list(range(1, 64)),
              'accepted_first_pair_seed_sums': [row['first_seed_sum'] for row in completions],
              'candidate_checks': candidate_checks,
              'completions': completions,
              'phase_ns_exploratory': {'pair_build': pair_build_ns,
                                      'target_dependent_relaxation': query_ns},
              'source_sha256': {'protocol': sha(HERE/'protocol.json'),
                                'input': sha(INPUT), 'fixture': sha(FIXTURE),
                                'producer': sha(HERE/'relaxation_sage.py'),
                                'runtime': sha(HERE/'sage_runtime_info.json')}}
    (HERE/'result.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': result['status'],
                      'candidate_checks': candidate_checks,
                      'phase_ns_exploratory': result['phase_ns_exploratory']}))


if __name__ == '__main__':
    main()
