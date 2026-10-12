"""Public-input binary-curve witnesses with an independent, inversion-free checker.

Only field/curve parameters survive between queries. This is a bounded research
adapter for odd-degree polynomial-basis fields, not a constant-time crypto API.
"""
from dataclasses import dataclass
from pathlib import Path
import ctypes as C
import sys
import threading

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE.parent.parent / 'pdp-scaling'))
from gf2n import Curve, GF2n, INF, Point, is_irreducible


@dataclass(frozen=True)
class PublicQuery:
    n: int
    mod: int
    b: int
    m: int
    l: int
    target: Point
    anf: object

    @property
    def nvars(self):
        return self.m * self.l

    @property
    def xR(self):
        return self.target.x

    def evaluate(self, assignment):
        value = 0
        for mask, coefficient in self.anf.items():
            if mask & ~assignment == 0:
                value ^= coefficient
        return value


def point_record(point):
    return [point.x, point.y, int(point.inf)]


class PublicReplay:
    """Prepared reference arithmetic and strict proof verification.

    Setup validates the field once. Every verification rechecks the public
    target, assignment, original equations, all points and all group-law steps.
    """
    def __init__(self, n, mod, b):
        if type(n) is not int or n < 3 or n % 2 != 1:
            raise ValueError('odd field degree >= 3 required')
        if type(mod) is not int or mod <= 0 or mod.bit_length() != n + 1:
            raise ValueError('invalid field modulus degree')
        if type(b) is not int or not 0 < b < 1 << n:
            raise ValueError('nonzero canonical curve coefficient required')
        if not is_irreducible(mod):
            raise ValueError('reducible field modulus')
        self.F = GF2n(n, mod)
        self.E = Curve(self.F, b)
        self.ring = (n, mod, b)

    def _point(self, record, finite=False):
        if type(record) is not list or len(record) != 3:
            raise ValueError('point shape')
        x, y, inf = record
        if any(type(v) is not int for v in record) or inf not in (0, 1):
            raise ValueError('point encoding')
        if not 0 <= x < 1 << self.F.n or not 0 <= y < 1 << self.F.n:
            raise ValueError('point range')
        if inf and (finite or x != 0 or y != 0):
            raise ValueError('noncanonical infinity')
        p = Point(x, y, bool(inf))
        if not self.E.on_curve(p):
            raise ValueError('point off curve')
        return p

    def validate_query(self, query, assignment):
        if (any(type(v) is not int for v in (query.n, query.mod, query.b))
                or (query.n, query.mod, query.b) != self.ring):
            raise ValueError('wrong ring')
        if (type(query.m) is not int or type(query.l) is not int
                or not 1 <= query.m <= 8 or not 1 <= query.l <= query.n
                or query.nvars > 64):
            raise ValueError('unsupported factor shape')
        if type(assignment) is not int or not 0 <= assignment < 1 << query.nvars:
            raise ValueError('assignment range')
        if type(query.target) is not Point or query.target.inf is not False:
            raise ValueError('finite public Point required')
        self._point(point_record(query.target), finite=True)

    def _add_witness(self, p, q):
        F = self.F
        if p.inf:
            return q, 0
        if q.inf:
            return p, 0
        if p.x == q.x:
            if p.y != q.y or p.x == 0:
                return INF, 0
            slope = p.x ^ F.mul(p.y, F.inv(p.x))
            x = F.sqr(slope) ^ slope
            return Point(x, F.sqr(p.x) ^ F.mul(slope ^ 1, x)), slope
        slope = F.mul(p.y ^ q.y, F.inv(p.x ^ q.x))
        x = F.sqr(slope) ^ slope ^ p.x ^ q.x
        return Point(x, F.mul(slope, p.x ^ x) ^ x ^ p.y), slope

    def find(self, query, assignment, max_signs=256):
        self.validate_query(query, assignment)
        if type(max_signs) is not int or not 0 <= max_signs <= 256:
            raise ValueError('sign budget range')
        result = {'status': 'budget', 'signs_checked': 0, 'lifts_checked': 0}
        if max_signs == 0:
            return result
        points = []
        for i in range(query.m):
            x = (assignment >> (i * query.l)) & ((1 << query.l) - 1)
            point = self.E.lift_x(x)
            result['lifts_checked'] += 1
            if point is None:
                result['status'] = 'no-match'
                return result
            points.append(point)
        for signs in range(min(max_signs, 1 << query.m)):
            signed = [self.E.neg(p) if signs >> i & 1 else p for i, p in enumerate(points)]
            current, steps, slopes = INF, [], []
            for point in signed:
                current, slope = self._add_witness(current, point)
                steps.append(point_record(current))
                slopes.append(slope)
            result['signs_checked'] += 1
            if current == query.target:
                result.update(status='match', sign_mask=signs, witness={
                    'ring': list(self.ring), 'assignment': assignment,
                    'target': point_record(query.target),
                    'points': [point_record(p) for p in signed],
                    'steps': steps, 'slopes': slopes})
                return result
        if max_signs >= 1 << query.m:
            result['status'] = 'no-match'
        return result

    def verify(self, query, assignment, witness):
        """Check a certificate; malformed or false certificates fail closed."""
        try:
            self.validate_query(query, assignment)
            if type(witness) is not dict or set(witness) != {
                    'ring', 'assignment', 'target', 'points', 'steps', 'slopes'}:
                return False
            if witness['ring'] != list(self.ring) or witness['target'] != point_record(query.target):
                return False
            if any(type(witness[k]) is not list or any(type(v) is not int for v in witness[k])
                   for k in ('ring', 'target')):
                return False
            if type(witness['assignment']) is not int or witness['assignment'] != assignment:
                return False
            if any(type(witness[k]) is not list or len(witness[k]) != query.m
                   for k in ('points', 'steps', 'slopes')):
                return False
            if query.evaluate(assignment):
                return False
            F, previous = self.F, INF
            for i, (pr, rr, slope) in enumerate(zip(witness['points'], witness['steps'], witness['slopes'])):
                p = self._point(pr, finite=True)
                r = self._point(rr)
                if p.x != (assignment >> (i * query.l)) & ((1 << query.l) - 1):
                    return False
                if type(slope) is not int or not 0 <= slope < 1 << query.n:
                    return False
                if previous.inf:
                    if r != p or slope != 0:
                        return False
                elif previous.x == p.x and (previous.y != p.y or p.x == 0):
                    if previous.y != p.y and previous.y ^ p.y != p.x:
                        return False
                    if r != INF or slope != 0:
                        return False
                elif previous.x == p.x:
                    if F.mul(slope, p.x) != F.sqr(p.x) ^ p.y:
                        return False
                    if r.inf or r.x != F.sqr(slope) ^ slope:
                        return False
                    if r.y != F.sqr(p.x) ^ F.mul(slope ^ 1, r.x):
                        return False
                else:
                    if F.mul(slope, previous.x ^ p.x) != previous.y ^ p.y:
                        return False
                    if r.inf or r.x != F.sqr(slope) ^ slope ^ previous.x ^ p.x:
                        return False
                    if r.y != F.mul(slope, previous.x ^ r.x) ^ r.x ^ previous.y:
                        return False
                previous = r
            return previous == query.target
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            return False


class _Point(C.Structure):
    _fields_ = [('x', C.c_uint64), ('y', C.c_uint64), ('inf', C.c_uint64)]


class _Result(C.Structure):
    _fields_ = [('status', C.c_uint64), ('signs_checked', C.c_uint64),
                ('lifts_checked', C.c_uint64), ('sign_mask', C.c_uint64),
                ('points', _Point * 8), ('steps', _Point * 8), ('slopes', C.c_uint64 * 8)]


class NativeReplay:
    def __init__(self, reference, sanitizer=False):
        self.reference = reference
        self.ring = reference.ring
        if self.ring[0] > 63:
            raise ValueError('native replay supports odd degrees 3 through 63')
        suffix = '.dylib' if sys.platform == 'darwin' else '.so'
        self.lib = C.CDLL(str(HERE / 'build' / (('replay_ubsan' if sanitizer else 'replay') + suffix)))
        self.lib.replay_result_size.restype = C.c_size_t
        if self.lib.replay_result_size() != C.sizeof(_Result):
            raise RuntimeError('native result ABI mismatch')
        self.lib.replay_create.argtypes = [C.c_uint64] * 3
        self.lib.replay_create.restype = C.c_void_p
        self.lib.replay_destroy.argtypes = [C.c_void_p]
        self.lib.replay_destroy.restype = None
        self.lib.replay_find.argtypes = [C.c_void_p] + [C.c_uint64] * 6 + [C.POINTER(_Result)]
        self.lib.replay_find.restype = None
        self._lock = threading.Lock()
        self._context = self.lib.replay_create(*self.ring)
        if not self._context:
            raise ValueError('native field validation failed')

    def close(self):
        with self._lock:
            if self._context:
                self.lib.replay_destroy(self._context)
                self._context = None

    def find(self, query, assignment, max_signs=256):
        self.reference.validate_query(query, assignment)
        if type(max_signs) is not int or not 0 <= max_signs <= 256:
            raise ValueError('sign budget range')
        raw = _Result()  # Fresh target-dependent output; never shared across calls.
        with self._lock:
            if not self._context:
                raise RuntimeError('closed replay context')
            self.lib.replay_find(self._context, query.m, query.l, assignment,
                                 query.target.x, query.target.y, max_signs, C.byref(raw))
        if raw.status not in (0, 1, 2):
            raise ValueError('native replay rejected input')
        result = {'status': ('no-match', 'match', 'budget')[raw.status],
                  'signs_checked': int(raw.signs_checked), 'lifts_checked': int(raw.lifts_checked)}
        if raw.status == 1:
            result['sign_mask'] = int(raw.sign_mask)
            result['witness'] = {
                'ring': list(self.ring), 'assignment': assignment,
                'target': point_record(query.target),
                'points': [[p.x, p.y, p.inf] for p in raw.points[:query.m]],
                'steps': [[p.x, p.y, p.inf] for p in raw.steps[:query.m]],
                'slopes': list(raw.slopes[:query.m])}
        return result
