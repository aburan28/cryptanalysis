"""Checked-Sage independent replay of the constructed N131 group witness."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
FIXTURE = HERE/'fixture.json'
RUNTIME = HERE/'sage_runtime_info.json'
R = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    fixture = json.loads(FIXTURE.read_text())
    runtime = json.loads(RUNTIME.read_text())
    assert runtime['status'] == 'verified'
    ring = PolynomialRing(GF(2), 't')
    t = ring.gen()
    field = GF(2**131, 't', modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def dec(value):
        return field(ring([(int(value) >> i) & 1 for i in range(131)]))

    def point(values):
        return curve(dec(values[0]), dec(values[1]))

    leaves = [point(values) for values in fixture['raw_leaves']]
    for leaf, mask, rotation in zip(leaves, fixture['masks'], fixture['rotations']):
        assert leaf[0] != 0
        assert 1/leaf[0] == dec(mask << 1)**(2**rotation)
        assert R*(4*leaf) == curve(0)
    pairs = [leaves[2*i]+leaves[2*i+1] for i in range(4)]
    middle = [pairs[2*i]+pairs[2*i+1] for i in range(2)]
    total = middle[0]+middle[1]
    assert pairs == [point(values) for values in fixture['pair_points']]
    assert middle == [point(values) for values in fixture['middle_points']]
    assert total == point(fixture['raw_target'])
    assert 4*total == point(fixture['projected_target'])
    assert R*(4*total) == curve(0)
    result = {'status': 'PASS_CHECKED_SAGE_N131_EIGHT_SLOT_GROUP_WITNESS',
              'curve_id': fixture['curve_id'], 'source_masks': fixture['masks'],
              'rotations': fixture['rotations'],
              'source_points_checked': len(leaves),
              'projected_target': fixture['projected_target'],
              'source_sha256': {'fixture.json': sha(FIXTURE),
                                'sage_runtime_info.json': sha(RUNTIME),
                                'verify_fixture_sage.py': sha(Path(__file__))}}
    (HERE/'sage_control_result.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': result['status'], 'source_points_checked': len(leaves)}))


if __name__ == '__main__':
    main()
