"""Freeze a public 1+Frobenius target and an eight-slot positive assignment."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCREEN = ROOT/'n131_w18_four_pairs/screen.json'
ROW = ROOT/'n131_w18_four_pairs/native_join/receipt.json'
RUNTIME = HERE/'sage_runtime_info.json'
R = 549756390943
ROTATIONS = (0, 0, 10, 10, 20, 20, 30, 30)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert json.loads(RUNTIME.read_text())['status'] == 'verified'
    screen = json.loads(SCREEN.read_text())['n41']
    receipt = json.loads(ROW.read_text())
    known = receipt['verified_relation']
    assert receipt['status'] == 'VERIFIED_EIGHT_POINT_ROW'
    assert screen['slot_rotations'] == list(ROTATIONS)
    assert known['seed_masks'] == [63, 34, 44, 18, 53, 59, 1, 6]
    ring = PolynomialRing(GF(2), 't')
    t = ring.gen()
    field = GF(2**41, 't', modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)

    def dec(value):
        return field(ring([(int(value) >> i) & 1 for i in range(41)]))

    def enc(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def coords(point):
        assert point != zero
        return [enc(point[0]), enc(point[1])]

    def pi(point):
        return curve(point[0]**2, point[1]**2)

    def halftrace(value):
        original = value
        result = field.zero()
        for _ in range(21):
            result += value
            value = value**4
        assert result**2+result == original
        return result

    def branch(a, b, c):
        rhs = (a+b+c)**2
        assert rhs.trace() == 0
        value = a*b*c + halftrace(rhs)
        assert value in (field.zero(), field.one())
        return int(value)

    tables = []
    for rotation in (0, 10, 20, 30):
        table = {}
        for x, y, column, mask, source_branch, sign in screen['point_rows_by_unique_rotation'][str(rotation)]:
            if mask in table:
                assert table[mask] == column
            table[mask] = column
        assert len(table) == 32
        tables.append(table)
    assert all(table == tables[0] for table in tables)
    columns = tables[0]
    assert len(set(columns.values())) == 26
    raw_P, raw_D = [], []
    for i, (mask, source_branch, sign, rotation) in enumerate(zip(
            known['seed_masks'], known['seed_branches'], known['curve_sign_indices'], ROTATIONS)):
        w = dec(mask << 1)**(2**rotation)
        u = halftrace(w) + source_branch
        P = curve.lift_x(1+1/u, all=True)[sign]
        assert coords(4*P) == known['points'][i]
        D = P+pi(P)
        assert D != zero and D[0] == 1/w
        assert R*(4*D) == zero
        raw_P.append(P)
        raw_D.append(D)
    public = curve(dec(screen['public_target_q'][0]), dec(screen['public_target_q'][1]))
    assert sum(raw_P, zero)*4 == public
    transport_start = time.monotonic_ns()
    transported = public+pi(public)
    transport_ns = time.monotonic_ns()-transport_start
    assert sum(raw_D, zero)*4 == transported
    assert transported == public+pi(public) and R*transported == zero
    pairs = [raw_D[2*i]+raw_D[2*i+1] for i in range(4)]
    middle = [pairs[0]+pairs[1], pairs[2]+pairs[3]]
    raw_sum = middle[0]+middle[1]
    assert raw_sum == sum(raw_D, zero)
    assert all(point != zero and point[0] != 0 for point in [*pairs, *middle, raw_sum])
    torsion = curve(field.one(), field.zero())
    assert 4*torsion == zero and 2*torsion != zero
    core = pow(4, -1, R)*transported
    preimages = [core, core+2*torsion, core+torsion, core+3*torsion]
    assert all(4*point == transported and point[0] != 0 for point in preimages)
    target_zs = [enc(1/point[0]) for point in preimages]
    target_cross_term = target_zs[0] ^ target_zs[1] ^ target_zs[2] ^ target_zs[3]
    matches = [i for i, point in enumerate(preimages) if point == raw_sum]
    assert len(matches) == 1
    source_z = [1/point[0] for point in raw_D]
    pair_z = [1/point[0] for point in pairs]
    middle_z = [1/point[0] for point in middle]
    raw_z = 1/raw_sum[0]
    branches = [branch(source_z[2*i], source_z[2*i+1], pair_z[i]) for i in range(4)]
    branches += [branch(pair_z[2*i], pair_z[2*i+1], middle_z[i]) for i in range(2)]
    branches += [branch(middle_z[0], middle_z[1], raw_z)]
    result = {'status': 'PASS_TRANSPORTED_N41_PUBLIC_EIGHT_SLOT_WITNESS',
              'curve_id': 'EC1N41Ckb1h023d9a38bbf7',
              'prior_curve_id_alias': screen['curve_id'],
              'public_target_original': coords(public),
              'public_target_transported': coords(transported),
              'target_transport_ns_exploratory': transport_ns,
              'raw_target_preimages': [coords(point) for point in preimages],
              'raw_target_reciprocals': target_zs,
              'target_selector_cross_term': target_cross_term,
              'known_raw_preimage_index': matches[0],
              'known_masks': known['seed_masks'],
              'known_columns': known['columns'],
              'mask_columns': {str(mask): column for mask, column in sorted(columns.items())},
              'rotations': ROTATIONS,
              'source_P': [coords(point) for point in raw_P],
              'source_D': [coords(point) for point in raw_D],
              'pair_points': [coords(point) for point in pairs],
              'middle_points': [coords(point) for point in middle],
              'raw_sum': coords(raw_sum),
              'pair_reciprocals': [enc(value) for value in pair_z],
              'middle_reciprocals': [enc(value) for value in middle_z],
              'branch_bits': branches,
              'source_sha256': {'screen.json': sha(SCREEN),
                                'native_receipt.json': sha(ROW),
                                'sage_runtime_info.json': sha(RUNTIME),
                                'prepare_sage.py': sha(Path(__file__))}}
    (HERE/'fixture.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': result['status'],
                      'transported_target': result['public_target_transported'],
                      'known_raw_preimage_index': matches[0]}))


if __name__ == '__main__':
    main()
