"""Fresh independent curve witnesses from public target points, without fixtures."""
import ctypes as ct
import hashlib
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'pdp-scaling'))
from gf2n import Curve, GF2n, INF, Point, is_irreducible

MAX_POINTS = 12
U32, U64 = ct.c_uint32, ct.c_uint64


class NativeResult(ct.Structure):
    _fields_ = [('code', U32), ('signs', U32), ('patterns', U32), ('ys', U64 * MAX_POINTS)]


def ring_check(n, mod, b):
    if type(n) is not int or not 3 <= n <= 127 or n % 2 != 1:
        raise ValueError('replay requires odd field degree 3..127')
    if type(mod) is not int or mod < 0 or mod.bit_length() != n + 1:
        raise ValueError('field modulus degree mismatch')
    if type(b) is not int or not 0 < b < 1 << n:
        raise ValueError('nonsingular curve coefficient must be a nonzero field element')


def target_check(n, target):
    if not isinstance(target, Point) or type(target.inf) is not bool:
        raise ValueError('target must be a Point with a Boolean infinity flag')
    if any(type(v) is not int or not 0 <= v < 1 << n for v in (target.x, target.y)):
        raise ValueError('target coordinates outside field')
    if target.inf and (target.x or target.y):
        raise ValueError('identity uses canonical zero coordinates')


def input_check(n, xs, target):
    target_check(n, target)
    xs = tuple(xs)
    if not 1 <= len(xs) <= MAX_POINTS:
        raise ValueError('replay needs 1..12 x coordinates')
    if any(type(x) is not int or not 0 <= x < 1 << n for x in xs):
        raise ValueError('x coordinate outside field')
    return xs


def result(code, signs=None, patterns=0, points=()):
    return {'verified': code == 0, 'code': code, 'signs': signs,
            'patterns': patterns, 'points': [vars(p) for p in points]}


class PythonReplay:
    """Reference arithmetic is unchanged; only fixed field setup is reusable."""
    backend = 'python-public-point'
    binary_sha256 = None

    def __init__(self, n, mod, b):
        ring_check(n, mod, b)
        if not is_irreducible(mod):
            raise ValueError('reducible field modulus')
        self.n, self.mod, self.b = n, mod, b
        self.curve = Curve(GF2n(n, mod), b)
        self._lock, self._closed = threading.Lock(), False

    def validate_target(self, target):
        target_check(self.n, target)
        with self._lock:
            if self._closed:
                raise RuntimeError('replay is closed')
            if not self.curve.on_curve(target):
                raise ValueError('public target is not on the curve')

    def match(self, xs, target):
        xs = input_check(self.n, xs, target)
        with self._lock:
            if self._closed:
                raise RuntimeError('replay is closed')
            if not self.curve.on_curve(target):
                raise ValueError('public target is not on the curve')
            points = [self.curve.lift_x(x) for x in xs]
            if any(p is None for p in points):
                return result(2)
            for signs in range(1 << len(points)):
                signed = [self.curve.neg(p) if signs >> i & 1 else p for i, p in enumerate(points)]
                if self.curve.sum(signed) == target:
                    return result(0, signs, signs + 1, signed)
            return result(1, patterns=1 << len(points))

    def close(self):
        with self._lock:
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class NativeReplay:
    backend = 'native-public-point'

    def __init__(self, n, mod, b, *, sanitizer=False):
        ring_check(n, mod, b)
        if n > 63:
            raise ValueError('native replay supports odd degrees only through 63')
        self.n, self.mod, self.b = n, mod, b
        self._lock, self._handle = threading.Lock(), None
        suffix = ('-ubsan' if sanitizer else '') + ('.dylib' if sys.platform == 'darwin' else '.so')
        self.path = HERE / 'build' / ('replay' + suffix)
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.lib = ct.CDLL(str(self.path))
        self.lib.replay_create.argtypes = [U32, U64, U64]
        self.lib.replay_create.restype = ct.c_void_p
        self.lib.replay_destroy.argtypes = [ct.c_void_p]
        self.lib.replay_destroy.restype = None
        self.lib.replay_result_size.restype = U32
        self.lib.replay_target_valid.argtypes = [ct.c_void_p, U64, U64, U32]
        self.lib.replay_target_valid.restype = ct.c_int
        self.lib.replay_match.argtypes = [ct.c_void_p, ct.POINTER(U64), U32, U64, U64, U32,
                                         ct.POINTER(NativeResult)]
        self.lib.replay_match.restype = ct.c_int
        if self.lib.replay_result_size() != ct.sizeof(NativeResult):
            raise RuntimeError('replay statistics ABI size mismatch')
        self._handle = self.lib.replay_create(n, mod, b)
        if not self._handle:
            raise ValueError('native field validation or allocation failed')

    def validate_target(self, target):
        target_check(self.n, target)
        with self._lock:
            if not self._handle:
                raise RuntimeError('replay is closed')
            if not self.lib.replay_target_valid(self._handle, target.x, target.y, target.inf):
                raise ValueError('public target is not on the curve')

    def match(self, xs, target):
        xs = input_check(self.n, xs, target)
        values, output = (U64 * len(xs))(*xs), NativeResult()
        with self._lock:
            if not self._handle:
                raise RuntimeError('replay is closed')
            code = self.lib.replay_match(self._handle, values, len(xs), target.x, target.y,
                                         target.inf, ct.byref(output))
        if code == 3:
            raise ValueError('invalid replay input or failed internal curve check')
        if code not in (0, 1, 2) or code != output.code:
            raise RuntimeError('unexpected replay result')
        points = [Point(x, output.ys[i]) for i, x in enumerate(xs)] if code == 0 else ()
        return result(code, output.signs if code == 0 else None, output.patterns, points)

    def close(self):
        with self._lock:
            if self._handle:
                self.lib.replay_destroy(self._handle)
                self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def replay(n, mod, b, arm='native', *, sanitizer=False):
    if arm == 'python':
        return PythonReplay(n, mod, b)
    if arm == 'native':
        return NativeReplay(n, mod, b, sanitizer=sanitizer)
    if arm == 'native-or-python':
        if n <= 63:
            return NativeReplay(n, mod, b, sanitizer=sanitizer)
        instance = PythonReplay(n, mod, b)
        instance.backend = 'python-public-point-wide-field-fallback'
        return instance
    raise ValueError('unknown replay arm')
