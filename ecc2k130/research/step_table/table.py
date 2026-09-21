"""Reproducible, synthetic ECC2K-130 step tables and exact reference steps.

No target input, collision service, or production client is used.  The target is
Q=[65537]P.  Coordinates use the repository's permuted type-II normal basis.
"""

import argparse
import hashlib
import json
import pathlib
import random
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'codegen'))
from curves import Curve, curveOrder, frobeniusEigenvalue, isPrimeBig
from field import Onb

MASK64 = (1 << 64) - 1
KNOWN = 65537

try:
    _nativeBitCount = int.bit_count
except AttributeError:  # Python 3.8/3.9
    def popcount(value):
        return bin(value).count('1')
else:
    def popcount(value):
        return _nativeBitCount(value)


def mix64(value):
    value = ((value ^ (value >> 30)) * 0xbf58476d1ce4e5b9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94d049bb133111eb) & MASK64
    return value ^ (value >> 31)


class Selector:
    """A phase-normalized x fingerprint, invariant under +/- Frobenius.

    Convert permuted ONB coordinates to cyclic coordinates indexed by L(i).
    k=sum(L(i)*x_i)/HW(x) mod m.  Rotating by -k selects one x per orbit
    without searching its m conjugates.  A support bit selects the sign.
    This is a reference implementation, not a measured GPU selector.
    """

    def __init__(self, m):
        self.m = m
        self.mask = (1 << m) - 1
        self.order = []
        e = 1
        for _ in range(m):
            self.order.append(min(e, 2 * m + 1 - e) - 1)
            e = 2 * e % (2 * m + 1)
        if sorted(self.order) != list(range(m)):
            raise ValueError('field does not have the required cyclic ONB')

    def cyclic(self, coords):
        return sum(((coords >> i) & 1) << t for t, i in enumerate(self.order))

    def orient(self, x, y):
        xx, yy = self.cyclic(x), self.cyclic(y)
        weight = popcount(xx)
        if weight == 0 or weight == self.m:
            raise ValueError('phase undefined: reject infinity/subfield inputs')
        phase = sum(t for t in range(self.m) if (xx >> t) & 1)
        phase = phase * pow(weight, -1, self.m) % self.m
        normalized = ((xx >> phase) | (xx << (self.m - phase))) & self.mask
        pivot = (normalized.bit_length() - 1 + phase) % self.m
        eps = (yy >> pivot) & 1
        return weight, phase, eps, normalized

    def tag(self, x, y, branches, selector='orbit', salt=0):
        weight, phase, eps, normalized = self.orient(x, y)
        if selector == 'weight':
            branch = (weight // 2) & (branches - 1)
        elif selector == 'orbit':
            fingerprint = salt
            for shift in range(0, self.m, 64):
                fingerprint = mix64(fingerprint ^ ((normalized >> shift) & MASK64))
            branch = fingerprint & (branches - 1)
        else:
            raise ValueError('unknown selector')
        return branch, phase, eps


def fruitless(tag, history):
    def opposite(a, b):
        return a[:2] == b[:2] and a[2] != b[2]
    return ((len(history) >= 1 and opposite(tag, history[-1])) or
            (len(history) >= 3 and opposite(tag, history[-2]) and
             opposite(history[-1], history[-3])))


def resolve(tag, history, branches):
    for _ in range(branches):
        if not fruitless(tag, history):
            return tag
        tag = ((tag[0] + 1) % branches, tag[1], tag[2])
    raise RuntimeError('cycle rule exhausted the table')


def coefficient(seed, branch, which, attempt, ell):
    # Rejection sampling, so arbitrary group orders introduce no modulo bias.
    counter = 0
    bits = ell.bit_length()
    while True:
        text = 'ecc2k-step-v1:%d:%d:%d:%d:%d' % (seed, branch, which, attempt, counter)
        value = int.from_bytes(hashlib.shake_256(text.encode()).digest((bits + 7) // 8), 'little')
        value &= (1 << bits) - 1
        if 0 < value < ell:
            return value
        counter += 1


class CountedCurve(Curve):
    def __init__(self, field):
        super().__init__(field)
        self.groupOps = 0

    def add(self, p, q):
        # Curve.add delegates equal points to dbl, which charges that call.
        if p is not None and q is not None and p != q:
            self.groupOps += 1
        return super().add(p, q)

    def dbl(self, p):
        if p is not None:
            self.groupOps += 1
        return super().dbl(p)


def instance(m):
    field = Onb(m)
    curve = CountedCurve(field)
    ell = curveOrder(m) // 4
    if curveOrder(m) != 4 * ell or not isPrimeBig(ell):
        raise ValueError('requires the prime order cofactor-four test family')
    if m == 131:
        # Read only the public generator, never the challenge target Q.
        header = (ROOT / 'generated/eccF131.h').read_text()
        def coord(name):
            values = re.search(r'\b%s\[3\] = \{([^}]+)' % name, header).group(1)
            return field.fromCoords(sum(int(v, 16) << (64 * i)
                                        for i, v in enumerate(re.findall(r'0x[0-9a-f]+', values))))
        base = coord('PX'), coord('PY')
    else:
        base = curve.randomPointOfOrder(ell, 4, random.Random(20260921 + m))
    if not curve.onCurve(base) or base is None or curve.mul(base, ell) is not None:
        raise AssertionError('invalid generator')
    eigen = frobeniusEigenvalue(curve, base, ell)
    target = curve.mul(base, KNOWN % ell)
    return field, curve, base, target, ell, eigen


def build(m=131, branches=32, seed=20260921):
    if branches not in (8, 16, 32, 64):
        raise ValueError('branches must be 8, 16, 32 or 64')
    started = time.perf_counter()
    field, curve, base, target, ell, eigen = instance(m)
    selector = Selector(m)
    rows, seen = [], set()
    setupStart = curve.groupOps
    for branch in range(branches):
        attempt = 0
        while True:
            a = coefficient(seed, branch, 0, attempt, ell)
            b = coefficient(seed, branch, 1, attempt, ell)
            point = curve.add(curve.mul(base, a), curve.mul(target, b))
            if point is not None:
                key = selector.orient(field.toCoords(point[0]), field.toCoords(point[1]))[3]
                if key not in seen:
                    break
            attempt += 1
            if attempt > 1024:
                raise ValueError('not enough distinct signed Frobenius orbits')
        seen.add(key)
        rows.append({'branch': branch, 'attempt': attempt, 'a': str(a), 'b': str(b),
                     'x': hex(field.toCoords(point[0])), 'y': hex(field.toCoords(point[1]))})
    setupOps = curve.groupOps - setupStart
    # Independent check against a single effective scalar; subgroup membership
    # follows from the checked prime-order generator and these exact equalities.
    auditStart = curve.groupOps
    for row in rows:
        expected = curve.mul(base, (int(row['a']) + KNOWN * int(row['b'])) % ell)
        actual = tuple(field.fromCoords(int(row[c], 16)) for c in ('x', 'y'))
        if not curve.onCurve(actual) or expected != actual:
            raise AssertionError('invalid table entry')
    conjugates = []
    for k in range(m):
        for row in rows:
            point = tuple(field.fromCoords(int(row[c], 16)) for c in ('x', 'y'))
            point = curve.frob(point, k)
            conjugates.append([hex(field.toCoords(v)) for v in point])
    core = {'schema': 'ecc2k-step-table-v1', 'scope': 'synthetic-reference-only',
            'm': m, 'branches': branches, 'seed': seed, 'ell': str(ell),
            'eigenvalue': str(eigen), 'knownScalar': str(KNOWN % ell),
            'basis': 'permuted-type-II-ONB',
            'generator': [hex(field.toCoords(v)) for v in base],
            'target': [hex(field.toCoords(v)) for v in target], 'rows': rows,
            'conjugateLayout': 'k-major then branch; [x,y]; signs implicit',
            'conjugates': conjugates}
    digest = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    core.update({'identitySha256': digest, 'setupGroupOps': setupOps,
                 'auditGroupOps': curve.groupOps - auditStart,
                 'buildSeconds': time.perf_counter() - started,
                 'packedCoordinatesBytes': m * branches * 2 * ((m + 7) // 8),
                 'cudaNineWordCoordinatesBytes': m * branches * 36,
                 'gpuMeasured': False})
    return core


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--branches', type=int, default=32)
    parser.add_argument('--seed', type=int, default=20260921)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    args = parser.parse_args()
    result = build(branches=args.branches, seed=args.seed)
    # Evidence is additive: do not overwrite a previous table or measurement.
    with args.out.open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'conjugates')}, indent=2))


if __name__ == '__main__':
    main()
