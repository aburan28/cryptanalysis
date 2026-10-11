"""Check the 1+Frobenius transport behind the sparse reciprocal source."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE/'n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv'
RUNTIME = HERE/'sage_runtime_info.json'
FIXTURE = HERE/'fixture.json'
R = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert json.loads(RUNTIME.read_text())['status'] == 'verified'
    ring = PolynomialRing(GF(2), 't')
    t = ring.gen()
    field = GF(2**131, 't', modulus=t**131+t**13+t**2+t+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    small = EllipticCurve(GF(2), [1, 0, 0, 0, 1])
    assert small.cardinality() == 4
    support = {int(a): int(b) for a, b in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    fixture = json.loads(FIXTURE.read_text())
    ordered = sorted(support)
    masks = list(fixture['masks']) + [ordered[i*len(ordered)//56] for i in range(56)]

    def dec(value):
        return field(ring([(int(value) >> i) & 1 for i in range(131)]))

    def point(values):
        return curve(dec(values[0]), dec(values[1]))

    def halftrace(value):
        original = value
        result = field.zero()
        for _ in range(66):
            result += value
            value = value**4
        assert result**2 + result == original
        return result

    def pi(P):
        return curve(P[0]**2, P[1]**2)

    for index, mask in enumerate(masks):
        w = dec(mask << 1)
        assert w.trace() == 0
        u = halftrace(w)
        assert u**2 + u == w and u not in (0, 1)
        P = curve.lift_x(1+1/u, all=True)[0]
        D = P+pi(P)
        assert D != curve(0) and D[0] == 1/w
        assert pi(pi(P))+pi(P)+2*P == curve(0)
        assert -pi(D) == 2*P
        assert R*(4*P) == R*(4*D) == curve(0)
        if index < 8:
            actual = point(fixture['raw_leaves'][index])
            for _ in range(fixture['rotations'][index]):
                D = pi(D)
            assert actual in (D, -D)
            assert 4*actual in (4*D, -4*D)
    result = {'status': 'PASS_SAGE_1_PLUS_FROBENIUS_FACTOR_BASE_TRANSPORT',
              'base_field_curve_order': 4,
              'frobenius_polynomial': 'pi^2+pi+2=0',
              'norm_identity': '(1+pi)(-pi)=[2]',
              'source_masks_checked': len(masks),
              'fixture_points_checked': 8,
              'subgroup_order': str(R),
              'source_sha256': {'support_w18.tsv': sha(SUPPORT),
                                'fixture.json': sha(FIXTURE),
                                'sage_runtime_info.json': sha(RUNTIME),
                                'transport_audit_sage.py': sha(Path(__file__))}}
    (HERE/'transport_audit_result.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': result['status'],
                      'source_masks_checked': result['source_masks_checked']}))


if __name__ == '__main__':
    main()
