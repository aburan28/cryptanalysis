"""Bounded packed ANF and witness transport for isolated native controls."""
import ctypes as ct
import hashlib
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
U32, U64 = ct.c_uint32, ct.c_uint64
P32, P64 = ct.POINTER(U32), ct.POINTER(U64)
STATUS = {0: 'verified', 1: 'invalid', 2: 'nonlinear', 3: 'budget', 4: 'capacity', 5: 'internal'}


class Stats(ct.Structure):
    _fields_ = [(name, U64) for name in ('input_terms', 'input_word_xors', 'elimination_row_xors',
        'witness_parities', 'affine_row_xors', 'assignments', 'equation_word_xors', 'work',
        'workspace_bytes', 'witness_rows', 'rank', 'inconsistent')]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


def integer(value, limit, name):
    if type(value) is not int or not 0 <= value <= limit:
        raise ValueError(name)
    return value


class Packed:
    def __init__(self, variables, equations, terms):
        integer(variables, 10, 'variables')
        integer(equations, 128, 'equations')
        if not variables or not equations:
            raise ValueError('nonempty dimensions required')
        self.variables, self.equations = variables, equations
        self.limbs = (equations + 63) // 64
        terms = tuple(terms)
        if len(terms) > 1000000:
            raise ValueError('too many terms')
        masks, coefficients = [], []
        for mask, coefficient in terms:
            integer(mask, (1 << variables) - 1, 'monomial outside ring')
            integer(coefficient, (1 << equations) - 1, 'coefficient outside equations')
            masks.append(mask)
            coefficients.extend((coefficient >> (64 * l)) & ((1 << 64) - 1) for l in range(self.limbs))
        self.masks = (U32 * len(masks))(*masks)
        self.coefficients = (U64 * len(coefficients))(*coefficients)


class Native:
    def __init__(self, variables, equations, *, kind, sanitizer=False):
        integer(variables, 10, 'variables')
        integer(equations, 128, 'equations')
        if not variables or not equations or kind not in ('producer', 'checker'):
            raise ValueError('native dimensions or kind')
        if type(sanitizer) is not bool:
            raise ValueError('sanitizer must be Boolean')
        self.variables, self.equations, self.kind = variables, equations, kind
        self.limbs = (equations + 63) // 64
        self._lock, self._handle = threading.Lock(), None
        suffix = '.dylib' if sys.platform == 'darwin' else '.so'
        self.path = HERE / 'build' / (kind + ('-ubsan' if sanitizer else '') + suffix)
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.lib = lib = ct.CDLL(str(self.path))
        lib.partial_stats_size.restype = U64
        if lib.partial_stats_size() != ct.sizeof(Stats):
            raise RuntimeError('ABI mismatch')
        lib.partial_create.restype, lib.partial_create.argtypes = ct.c_void_p, [U32, U32]
        lib.partial_destroy.restype, lib.partial_destroy.argtypes = None, [ct.c_void_p]
        if kind == 'producer':
            lib.partial_produce.restype = ct.c_int
            lib.partial_produce.argtypes = [ct.c_void_p, P32, P64, U32, U64, P64, U32, P32, ct.POINTER(Stats)]
        else:
            lib.partial_check.restype = ct.c_int
            lib.partial_check.argtypes = [ct.c_void_p, P32, P64, U32, P64, U32, U64, U32,
                                         P32, U32, P32, ct.POINTER(Stats)]
        self._handle = lib.partial_create(variables, equations)
        if not self._handle:
            raise ValueError('native allocation failed')

    def input(self, packed):
        if not isinstance(packed, Packed) or (packed.variables, packed.equations) != (self.variables, self.equations):
            raise ValueError('packed input dimensions differ')
        if len(packed.coefficients) != len(packed.masks) * self.limbs:
            raise ValueError('packed coefficient extent')

    def produce(self, packed, *, work_budget=1 << 24, capacity=128):
        if self.kind != 'producer':
            raise ValueError('producer required')
        self.input(packed)
        integer(work_budget, (1 << 64) - 1, 'work budget')
        integer(capacity, 128, 'witness capacity')
        sentinel = 0xA5A5A5A5A5A5A5A5
        output = (U64 * (capacity * self.limbs + 2))(*([sentinel] * (capacity * self.limbs + 2)))
        count, stats = U32(123), Stats()
        with self._lock:
            if not self._handle:
                raise RuntimeError('producer closed')
            code = self.lib.partial_produce(self._handle, packed.masks, packed.coefficients,
                len(packed.masks), work_budget, output, capacity, ct.byref(count), ct.byref(stats))
        assert output[-1] == output[-2] == sentinel
        if code:
            assert count.value == 0 and all(v == sentinel for v in output)
        witnesses = tuple(sum(output[row * self.limbs + l] << (64 * l) for l in range(self.limbs))
                          for row in range(count.value))
        return {'code': code, 'status': 'produced' if code == 0 else STATUS[code],
                'witnesses': witnesses, 'stats': stats.record()}

    def check(self, packed, witnesses, *, work_budget=1 << 24, assignment_budget=1024, capacity=1024):
        if self.kind != 'checker':
            raise ValueError('checker required')
        self.input(packed)
        integer(work_budget, (1 << 64) - 1, 'work budget')
        integer(assignment_budget, (1 << 32) - 1, 'assignment budget')
        integer(capacity, 1024, 'root capacity')
        witnesses = tuple(witnesses)
        if len(witnesses) > 128:
            raise ValueError('too many witnesses')
        words = []
        for witness in witnesses:
            integer(witness, (1 << self.equations) - 1, 'witness extent')
            words.extend((witness >> (64 * l)) & ((1 << 64) - 1) for l in range(self.limbs))
        raw = (U64 * len(words))(*words)
        sentinel = 0xA5A5A5A5
        output = (U32 * (capacity + 2))(*([sentinel] * (capacity + 2)))
        count, stats = U32(123), Stats()
        with self._lock:
            if not self._handle:
                raise RuntimeError('checker closed')
            code = self.lib.partial_check(self._handle, packed.masks, packed.coefficients,
                len(packed.masks), raw, len(witnesses), work_budget, assignment_budget,
                output, capacity, ct.byref(count), ct.byref(stats))
        assert output[-1] == output[-2] == sentinel
        if code:
            assert count.value == 0 and all(v == sentinel for v in output)
        return {'code': code, 'status': STATUS[code], 'roots': tuple(output[:count.value]), 'stats': stats.record()}

    def close(self):
        with self._lock:
            if self._handle:
                self.lib.partial_destroy(self._handle)
                self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
