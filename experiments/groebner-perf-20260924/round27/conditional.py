"""Opt-in packed conditional-linear solver and separate exact checker.

No ANF dictionary, set, sort, or coefficient copy on the native-descent path.
Buffers must remain immutable during a call; workspace locks protect lifetime.
"""
import ctypes as ct
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
U32, U64 = ct.c_uint32, ct.c_uint64
P64, P32 = ct.POINTER(U64), ct.POINTER(U32)


class Inconclusive(RuntimeError):
    pass


class Unsupported(ValueError):
    pass


class Stats(ct.Structure):
    _fields_ = [(name, U64) for name in ('branches', 'consistent', 'roots', 'standard', 'work')]
    _fields_ += [(name, ct.c_double) for name in ('evaluation', 'interpolation')]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


class Packed:
    """Owned wide-mask input for generic systems beyond the legacy 20-variable ABI."""
    def __init__(self, nvars, equations, items):
        if type(nvars) is not int or not 2 <= nvars <= 63:
            raise ValueError('variables 2..63')
        if type(equations) is not int or not 1 <= equations <= 128:
            raise ValueError('equations 1..128')
        items = list(items)
        if len(items) > 1000000:
            raise ValueError('term bound')
        for m, c in items:
            if type(m) is not int or not 0 <= m < 1 << nvars:
                raise ValueError('mask range')
            if type(c) is not int or not 0 <= c < 1 << equations:
                raise ValueError('coefficient range')
        self.nvars, self.equations = nvars, equations
        self.masks = (U64*len(items))(*(m for m, _ in items))
        limbs = (equations+63)//64
        self.coefficients = (U64*(len(items)*limbs))(
            *((c >> (64*j)) & ((1 << 64)-1) for _, c in items for j in range(limbs)))


def dimensions(x, y, equations):
    if any(type(v) is not int for v in (x, y, equations)) or not (
            1 <= x <= 20 and y >= 1 and x+y <= 63 and 1 <= equations <= 128):
        raise ValueError('x 1..20; y >= 1; x+y <= 63; equations 1..128')


class Native:
    def __init__(self, x, y, equations, name, *, sanitizer=False, budget_test=False):
        dimensions(x, y, equations)
        if sanitizer and budget_test:
            raise ValueError('select one test build')
        self.x, self.y, self.nvars, self.equations = x, y, x+y, equations
        self._lock, self._handle = threading.Lock(), None
        suffix = ('-budget' if budget_test else '-ubsan' if sanitizer else '') + (
            '.dylib' if sys.platform == 'darwin' else '.so')
        self.path = HERE/'build'/(name+suffix)
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.lib = ct.CDLL(str(self.path))

    def views(self, anf):
        if (anf.nvars, anf.equations) != (self.nvars, self.equations):
            raise ValueError('packed ring mismatch')
        masks, coefficients = anf.masks, anf.coefficients
        if not isinstance(masks, ct.Array) or masks._type_ not in (U32, U64):
            raise ValueError('uint32/uint64 masks required')
        if not isinstance(coefficients, ct.Array) or coefficients._type_ is not U64:
            raise ValueError('uint64 coefficients required')
        if len(masks)>1000000 or len(coefficients)!=len(masks)*((self.equations+63)//64):
            raise ValueError('packed extents')
        return masks, ct.sizeof(masks._type_)*8, coefficients

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Producer(Native):
    def __init__(self, x, y, equations, *, sanitizer=False):
        super().__init__(x, y, equations, 'producer', sanitizer=sanitizer)
        lib = self.lib
        lib.branch_stats_size.restype = U64
        if lib.branch_stats_size()!=ct.sizeof(Stats):
            raise RuntimeError('producer ABI mismatch')
        lib.branch_create.argtypes, lib.branch_create.restype = [U32, U32, U32], ct.c_void_p
        lib.branch_destroy.argtypes, lib.branch_destroy.restype = [ct.c_void_p], None
        lib.branch_solve.argtypes = [ct.c_void_p, ct.c_void_p, U32, P64, U32, ct.POINTER(Stats)]
        lib.branch_solve.restype = ct.c_void_p
        lib.branch_error.restype, lib.branch_error_code.restype = ct.c_char_p, U32
        lib.branch_rows.argtypes, lib.branch_rows.restype = [ct.c_void_p], U32
        lib.branch_row_size.argtypes, lib.branch_row_size.restype = [ct.c_void_p, U32], U32
        lib.branch_row.argtypes, lib.branch_row.restype = [ct.c_void_p, U32], P64
        lib.branch_roots.argtypes, lib.branch_roots.restype = [ct.c_void_p], P64
        lib.branch_result_destroy.argtypes, lib.branch_result_destroy.restype = [ct.c_void_p], None
        self._handle = lib.branch_create(x, y, equations)
        if not self._handle:
            raise RuntimeError(lib.branch_error().decode())

    def produce(self, anf):
        masks, width, coefficients = self.views(anf)
        stats = Stats()
        with self._lock:
            if not self._handle:
                raise RuntimeError('producer is closed')
            result = self.lib.branch_solve(self._handle, masks, width, coefficients,
                                          len(masks), ct.byref(stats))
            if not result:
                code, message = self.lib.branch_error_code(), self.lib.branch_error().decode()
                raise {5: Inconclusive, 6: ValueError, 7: Unsupported}.get(code, RuntimeError)(message)
            try:
                roots = list(self.lib.branch_roots(result)[:stats.roots])
                basis = [list(self.lib.branch_row(result, i)[:self.lib.branch_row_size(result, i)])
                         for i in range(self.lib.branch_rows(result))]
            finally:
                self.lib.branch_result_destroy(result)
        return {'roots': roots, 'basis': basis, 'stats': stats.record()}

    def close(self):
        with self._lock:
            if self._handle:
                self.lib.branch_destroy(self._handle)
                self._handle = None


class Checker(Native):
    def __init__(self, x, y, equations, *, sanitizer=False, budget_test=False):
        super().__init__(x, y, equations, 'checker', sanitizer=sanitizer,budget_test=budget_test)
        lib = self.lib
        lib.check_stats_size.restype = U64
        if lib.check_stats_size()!=ct.sizeof(Stats):
            raise RuntimeError('checker ABI mismatch')
        lib.check_create.argtypes, lib.check_create.restype = [U32, U32, U32], ct.c_void_p
        lib.check_destroy.argtypes, lib.check_destroy.restype = [ct.c_void_p], None
        lib.branch_check.argtypes = [ct.c_void_p, ct.c_void_p, U32, P64, U32,
                                    P64, U32, P64, U32, P32, U32, ct.POINTER(Stats)]
        lib.branch_check.restype = ct.c_int
        lib.branch_evaluate.argtypes = [ct.c_void_p, ct.c_void_p, U32, P64, U32, U64, P64]
        lib.branch_evaluate.restype = ct.c_int
        self._handle = lib.check_create(x, y, equations)
        if not self._handle:
            raise RuntimeError('checker allocation failed')

    def certify(self, anf, roots, basis):
        masks, width, coefficients = self.views(anf)
        if len(roots)>256 or len(basis)>4096:
            raise ValueError('certificate extents')
        terms, offsets = [], [0]
        for row in basis:
            terms.extend(row)
            offsets.append(len(terms))
        if len(terms)>1000000 or any(type(v) is not int or not 0<=v<1<<self.nvars
                                    for v in [*roots, *terms]):
            raise ValueError('certificate mask or extent')
        root_buffer, term_buffer = (U64*len(roots))(*roots), (U64*len(terms))(*terms)
        offset_buffer, stats = (U32*len(offsets))(*offsets), Stats()
        with self._lock:
            if not self._handle:
                raise RuntimeError('checker is closed')
            code = self.lib.branch_check(self._handle, masks, width, coefficients, len(masks),
                root_buffer, len(roots), term_buffer, len(terms), offset_buffer, len(basis), ct.byref(stats))
        if code==6:
            raise ValueError('invalid packed certificate')
        if code==8:
            raise RuntimeError('checker internal failure')
        answer = {'verified': code==0, 'code': code,
                  'method': 'exact-conditional-linear-count-and-Boolean-staircase',
                  'backend': 'independent-equation-row-elimination',
                  'stats': stats.record(), 'root_count': stats.roots if code!=5 else None,
                  'standard_monomials': stats.standard if code==0 else None}
        if code:
            answer['reason'] = {1: 'noncanonical basis', 2: 'invalid or repeated root',
                3: 'incomplete root list', 4: 'invalid reduced Boolean basis',
                5: 'exact proof budget or root limit exceeded', 7: 'nonlinear block'}[code]
        else:
            answer.update(ideal_equality=True, reduced_groebner_basis=True, solutions=list(roots))
        return answer

    def evaluate(self, anf, assignment):
        masks, width, coefficients = self.views(anf)
        if type(assignment) is not int or not 0<=assignment<1<<self.nvars:
            raise ValueError('assignment outside ring')
        out = (U64*2)()
        with self._lock:
            if not self._handle:
                raise RuntimeError('checker is closed')
            code = self.lib.branch_evaluate(self._handle, masks, width, coefficients,
                                           len(masks), assignment, out)
        if code:
            raise ValueError('invalid equation input') if code==6 else RuntimeError('evaluation failure')
        return out[0] | out[1]<<64

    def close(self):
        with self._lock:
            if self._handle:
                self.lib.check_destroy(self._handle)
                self._handle = None


class Basis:
    def __init__(self, x, y, equations, *, sanitizer=False):
        self.producer = Producer(x,y,equations,sanitizer=sanitizer)
        try:
            self.checker = Checker(x,y,equations,sanitizer=sanitizer)
        except Exception:
            self.producer.close()
            raise
        self.solver_path, self.verifier_path = self.producer.path, self.checker.path
        self._lock, self._closed = threading.Lock(), False

    def compute(self, anf):
        with self._lock:
            if self._closed:
                raise RuntimeError('basis workspace is closed')
            started = time.perf_counter()
            try:
                result = self.producer.produce(anf)
            except (Inconclusive, Unsupported) as error:
                return {'status': 'inconclusive' if isinstance(error, Inconclusive) else 'unsupported',
                        'complete': False, 'detail': str(error),
                        'wall_seconds': time.perf_counter()-started}
            produced = time.perf_counter()
            certificate = self.checker.certify(anf,result['roots'],result['basis'])
            finished = time.perf_counter()
            good = certificate['verified']
            stats = result['stats']
            return {'status': 'gb' if good else 'inconclusive' if certificate['code']==5 else 'verification-failed',
                'complete': good, 'groebner_verified': good, 'generators_reduce_to_zero': good,
                'basis_terms': result['basis'], 'basis_certificate': certificate,
                'basis_sha256': hashlib.sha256(json.dumps(result['basis'],sort_keys=True).encode()).hexdigest(),
                'basis_seconds': stats['evaluation']+stats['interpolation'],
                'wall_seconds': produced-started, 'verification_seconds': finished-produced,
                'coefficient_copy': False, 'transport': 'packed-library-no-coefficient-copy',
                'algorithm': 'conditional-linear-columns+buchberger-moller',
                'metrics': stats, 'hard_subprocess_timeout': False,
                'binary_sha256': self.producer.binary_sha256,
                'verifier_binary_sha256': self.checker.binary_sha256}

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                self.producer.close()
                self.checker.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
