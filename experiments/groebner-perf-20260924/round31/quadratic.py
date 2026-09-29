"""Opt-in quadratic producer with unchanged, independent exhaustive checking."""
import ctypes as ct
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'round27'))
from conditional import Native, Packed, Inconclusive, Unsupported, U32, U64, P32, P64
from full_query import BaselineQuery, complete_query
from sparse_checker import SparseChecker


class Stats(ct.Structure):
    _fields_ = [(name, U64) for name in ('branches', 'consistent', 'roots', 'standard', 'work',
        'lifted_candidates', 'fallback_branches', 'fallback_assignments', 'max_nullity',
        'features', 'workspace_bytes', 'transform_xors', 'gpu_used', 'gpu_shape_fallback')]
    _fields_ += [(name, ct.c_double) for name in ('specialization', 'evaluation', 'interpolation', 'gpu_wall', 'gpu_device')]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


class Producer(Native):
    def __init__(self, x, y, equations, *, sanitizer=False, budget_test=False, backend='cpu'):
        if any(type(v) is not int for v in (x, y, equations)) or not (
                1 <= x <= 20 and 1 <= y <= 10 and x+y <= 30 and 1 <= equations <= 128):
            raise ValueError('x 1..20; y 1..10; x+y<=30; equations 1..128')
        if sanitizer and budget_test:
            raise ValueError('select one test build')
        if backend not in ('cpu', 'metal') or (backend == 'metal' and (sanitizer or budget_test)):
            raise ValueError('backend cpu or metal; test builds are CPU only')
        self.backend = backend
        self.x, self.y, self.nvars, self.equations = x, y, x+y, equations
        self._lock, self._handle = threading.Lock(), None
        tag = '-metal' if backend == 'metal' else '-budget' if budget_test else '-ubsan' if sanitizer else ''
        self.path = HERE/'build'/('producer'+tag+('.dylib' if sys.platform=='darwin' else '.so'))
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.lib = lib = ct.CDLL(str(self.path))
        lib.branch_stats_size.restype = U64
        if lib.branch_stats_size()!=ct.sizeof(Stats):
            raise RuntimeError('quadratic producer ABI mismatch')
        for name, result, args in (
            ('branch_create', ct.c_void_p, [U32, U32, U32]),
            ('branch_destroy', None, [ct.c_void_p]),
            ('branch_solve', ct.c_void_p, [ct.c_void_p, ct.c_void_p, U32, P64, U32, ct.POINTER(Stats)]),
            ('branch_error', ct.c_char_p, []), ('branch_error_code', U32, []),
            ('branch_device', ct.c_char_p, [ct.c_void_p]),
            ('branch_rows', U32, [ct.c_void_p]), ('branch_row_size', U32, [ct.c_void_p, U32]),
            ('branch_row', P64, [ct.c_void_p, U32]), ('branch_roots', P64, [ct.c_void_p]),
            ('branch_result_destroy', None, [ct.c_void_p])):
            fn = getattr(lib, name)
            fn.restype, fn.argtypes = result, args
        self._handle = lib.branch_create(x, y, equations)
        if not self._handle:
            raise ValueError(lib.branch_error().decode())
        self.device = lib.branch_device(self._handle).decode()

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


class Basis:
    def __init__(self, x, y, equations, *, checker=None, sanitizer=False, backend='cpu'):
        if x+y>20:
            raise ValueError('independent exhaustive certificate currently supports at most 20 variables')
        if checker is not None and (checker.nvars, checker.equations) != (x+y, equations):
            raise ValueError('independent checker ring mismatch')
        self.producer = Producer(x, y, equations, sanitizer=sanitizer, backend=backend)
        self._owns_checker = checker is None
        try:
            self.checker = checker or SparseChecker(x+y, equations, sanitizer=sanitizer)
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
                        'complete': False, 'detail': str(error), 'wall_seconds': time.perf_counter()-started}
            produced = time.perf_counter()
            certificate = self.checker.certify(anf, result['basis'])
            good = certificate['verified'] and certificate['solutions']==result['roots']
            finished = time.perf_counter()
            metrics = result['stats']
            return {'status': 'gb' if good else 'verification-failed', 'complete': good,
                    'groebner_verified': good, 'generators_reduce_to_zero': good,
                    'basis_terms': result['basis'], 'basis_certificate': certificate,
                    'basis_sha256': hashlib.sha256(json.dumps(result['basis'], sort_keys=True).encode()).hexdigest(),
                    'basis_seconds': sum(metrics[k] for k in ('specialization', 'evaluation', 'interpolation')),
                    'wall_seconds': produced-started, 'verification_seconds': finished-produced,
                    'coefficient_copy': False, 'transport': 'packed-library-no-coefficient-copy',
                    'algorithm': 'conditional-quadratic-lift+exact-fallback+buchberger-moller',
                    'backend_requested': self.producer.backend, 'device': self.producer.device,
                    'metrics': metrics, 'hard_subprocess_timeout': False,
                    'binary_sha256': self.producer.binary_sha256,
                    'verifier_binary_sha256': self.checker.binary_sha256}

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                self.producer.close()
                if self._owns_checker:
                    self.checker.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class QuadraticQuery(BaselineQuery):
    def __init__(self, n, mod, b, m, ell, *, sanitizer=False, backend='cpu'):
        if m != 3:
            raise ValueError('quadratic query requires three coordinate blocks')
        super().__init__(n, mod, b, m, ell, arm='sparse', sanitizer=sanitizer)
        try:
            self.basis.close()
            self.basis = Basis(2*ell, ell, n, checker=self.checker, sanitizer=sanitizer, backend=backend)
            self.backend = backend
        except Exception:
            self.close()
            raise

    def solve(self, target):
        return complete_query(self, target, 'conditional-quadratic'+('-metal' if self.backend == 'metal' else ''))
