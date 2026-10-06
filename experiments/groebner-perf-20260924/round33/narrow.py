"""Width-specialized packed producer and independently reconstructed branch proof."""
import ctypes as ct
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'round31'))
from quadratic import Native, Packed, Inconclusive, Unsupported, U32, U64, P32, P64, Stats


def dimensions(x, y, equations):
    if any(type(v) is not int for v in (x, y, equations)) or not (
            1 <= x <= 20 and 1 <= y <= 10 and x+y <= 30 and 1 <= equations <= 128):
        raise ValueError('x 1..20; y 1..10; x+y<=30; equations 1..128')


class Producer(Native):
    def __init__(self, x, y, equations, *, backend='cpu', sanitizer=False, budget_test=False):
        dimensions(x, y, equations)
        if backend not in ('cpu', 'metal') or (sanitizer and budget_test) or (
                backend == 'metal' and (sanitizer or budget_test)):
            raise ValueError('select a supported backend/build')
        self.x, self.y, self.nvars, self.equations = x, y, x+y, equations
        self.backend = backend
        self._lock, self._handle = threading.Lock(), None
        tag = '-metal' if backend == 'metal' else '-budget' if budget_test else '-ubsan' if sanitizer else ''
        self.path = HERE/'build'/('producer'+tag+('.dylib' if sys.platform == 'darwin' else '.so'))
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.lib = lib = ct.CDLL(str(self.path))
        lib.branch_stats_size.restype = U64
        if lib.branch_stats_size() != ct.sizeof(Stats):
            raise RuntimeError('producer ABI mismatch')
        for name, result, args in (
            ('branch_coefficient_bits', U32, [ct.c_void_p]),
            ('branch_create', ct.c_void_p, [U32, U32, U32]),
            ('branch_destroy', None, [ct.c_void_p]),
            ('branch_solve', ct.c_void_p, [ct.c_void_p, ct.c_void_p, U32, P64, U32, ct.POINTER(Stats)]),
            ('branch_error', ct.c_char_p, []), ('branch_error_code', U32, []),
            ('branch_device', ct.c_char_p, [ct.c_void_p]),
            ('branch_rows', U32, [ct.c_void_p]), ('branch_row_size', U32, [ct.c_void_p, U32]),
            ('branch_row', P64, [ct.c_void_p, U32]), ('branch_roots', P64, [ct.c_void_p]),
            ('branch_proof', P64, [ct.c_void_p]), ('branch_proof_size', U64, [ct.c_void_p]),
            ('branch_result_destroy', None, [ct.c_void_p])):
            fn = getattr(lib, name)
            fn.restype, fn.argtypes = result, args
        self._handle = lib.branch_create(x, y, equations)
        if not self._handle:
            raise ValueError(lib.branch_error().decode())
        self.device = lib.branch_device(self._handle).decode()
        self.coefficient_bits = int(lib.branch_coefficient_bits(self._handle))
        if self.coefficient_bits != (32 if equations <= 32 else 64 if equations <= 64 else 128):
            raise RuntimeError('producer coefficient-width mismatch')

    def produce(self, anf, *, checker=None):
        if checker is not None and (checker.x, checker.y, checker.equations) != (self.x, self.y, self.equations):
            raise ValueError('checker ring/partition mismatch')
        masks, width, coefficients = self.views(anf)
        stats = Stats()
        with self._lock:
            if not self._handle:
                raise RuntimeError('producer is closed')
            started = time.perf_counter()
            result = self.lib.branch_solve(self._handle, masks, width, coefficients, len(masks), ct.byref(stats))
            if not result:
                code, message = self.lib.branch_error_code(), self.lib.branch_error().decode()
                raise {5: Inconclusive, 6: ValueError, 7: Unsupported}.get(code, RuntimeError)(message)
            try:
                roots = list(self.lib.branch_roots(result)[:stats.roots])
                basis = [list(self.lib.branch_row(result, i)[:self.lib.branch_row_size(result, i)])
                         for i in range(self.lib.branch_rows(result))]
                size = self.lib.branch_proof_size(result)
                if size != (1 << self.x)*((self.equations+63)//64):
                    raise RuntimeError('producer proof extent mismatch')
                proof = (U64*size).from_address(ct.addressof(self.lib.branch_proof(result).contents))
                # Retain immutable evidence; verification itself consumes the
                # live native view while this result still owns its storage.
                evidence = bytes(proof)
                proof_sha256 = hashlib.sha256(evidence).hexdigest()
                produced = time.perf_counter()
                certificate = checker.certify(anf, roots, basis, proof) if checker is not None else None
                checked = time.perf_counter()
                return {'roots': roots, 'basis': basis, 'stats': stats.record(),
                        'proof_bytes': evidence, 'proof_sha256': proof_sha256,
                        'proof_byteorder': sys.byteorder, 'certificate': certificate,
                        'producer_wall_seconds': produced-started, 'verification_seconds': checked-produced}
            finally:
                self.lib.branch_result_destroy(result)

    def close(self):
        with self._lock:
            if self._handle:
                self.lib.branch_destroy(self._handle)
                self._handle = None


class CheckStats(ct.Structure):
    _fields_ = [(name, U64) for name in ('branches', 'contradictions', 'enumerated_branches', 'assignments',
        'roots', 'standard', 'work', 'workspace_bytes', 'proof_bytes', 'transform_xors')]
    _fields_ += [(name, ct.c_double) for name in ('specialization', 'contradiction_check', 'enumeration', 'basis_check')]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


class Checker(Native):
    def __init__(self, x, y, equations, *, sanitizer=False, budget_test=False):
        dimensions(x, y, equations)
        if sanitizer and budget_test:
            raise ValueError('select one checker test build')
        self.x, self.y, self.nvars, self.equations = x, y, x+y, equations
        self._lock, self._handle = threading.Lock(), None
        tag = '-budget' if budget_test else '-ubsan' if sanitizer else ''
        self.path = HERE/'build'/('checker'+tag+('.dylib' if sys.platform == 'darwin' else '.so'))
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.lib = lib = ct.CDLL(str(self.path))
        lib.check_stats_size.restype = U64
        if lib.check_stats_size() != ct.sizeof(CheckStats):
            raise RuntimeError('checker ABI mismatch')
        for name, result, args in (
            ('check_coefficient_bits', U32, [ct.c_void_p]),
            ('check_create', ct.c_void_p, [U32, U32, U32]), ('check_destroy', None, [ct.c_void_p]),
            ('branch_check', ct.c_int, [ct.c_void_p, ct.c_void_p, U32, P64, U32,
                P64, U64, P64, U32, P64, U32, P32, U32, ct.POINTER(CheckStats)]),
            ('branch_evaluate', ct.c_int, [ct.c_void_p, ct.c_void_p, U32, P64, U32, U64, P64])):
            fn = getattr(lib, name)
            fn.restype, fn.argtypes = result, args
        self._handle = lib.check_create(x, y, equations)
        if not self._handle:
            raise ValueError('checker allocation or table limit')
        self.coefficient_bits = int(lib.check_coefficient_bits(self._handle))
        if self.coefficient_bits != (32 if equations <= 32 else 64):
            raise RuntimeError('checker coefficient-width mismatch')

    def certify(self, anf, roots, basis, proof):
        masks, width, coefficients = self.views(anf)
        if isinstance(proof, bytes):
            if len(proof)%8:
                raise ValueError('proof byte extent')
            proof = (U64*(len(proof)//8)).from_buffer_copy(proof)
        if not isinstance(proof, ct.Array) or proof._type_ is not U64:
            raise ValueError('uint64 proof array required')
        if len(proof) != (1 << self.x)*((self.equations+63)//64) or len(roots)>256 or len(basis)>4096:
            raise ValueError('certificate extents')
        terms, offsets = [], [0]
        for row in basis:
            terms.extend(row)
            offsets.append(len(terms))
        if len(terms)>1000000 or any(type(v) is not int or not 0<=v<1<<self.nvars for v in [*roots, *terms]):
            raise ValueError('certificate mask or extent')
        rb, tb, ob = (U64*len(roots))(*roots), (U64*len(terms))(*terms), (U32*len(offsets))(*offsets)
        stats = CheckStats()
        with self._lock:
            if not self._handle:
                raise RuntimeError('checker is closed')
            code = self.lib.branch_check(self._handle, masks, width, coefficients, len(masks),
                proof, len(proof), rb, len(roots), tb, len(terms), ob, len(basis), ct.byref(stats))
        if code == 6:
            raise ValueError('invalid packed certificate')
        if code == 8:
            raise RuntimeError('checker internal failure')
        result = {'verified': code == 0, 'code': code,
                  'backend': 'independent-quadratic-contradiction-proof',
                  'method': 'derived-contradictions+complete-residual-enumeration+Boolean-staircase',
                  'root_count': stats.roots if code != 5 else None,
                  'standard_monomials': stats.standard if code == 0 else None,
                  'coefficient_word_bits': self.coefficient_bits, 'stats': stats.record()}
        if code:
            result['reason'] = {1: 'noncanonical basis', 2: 'invalid or repeated root',
                3: 'incomplete root list', 4: 'invalid reduced Boolean basis',
                5: 'proof budget or root limit', 7: 'nonquadratic residual',
                9: 'invalid contradiction identity'}[code]
        else:
            result.update(ideal_equality=True, reduced_groebner_basis=True, solutions=list(roots))
        return result

    def evaluate(self, anf, assignment):
        masks, width, coefficients = self.views(anf)
        if type(assignment) is not int or not 0 <= assignment < 1 << self.nvars:
            raise ValueError('assignment outside ring')
        out = (U64*2)()
        with self._lock:
            if not self._handle:
                raise RuntimeError('checker is closed')
            code = self.lib.branch_evaluate(self._handle, masks, width, coefficients, len(masks), assignment, out)
        if code:
            raise ValueError('invalid equation input') if code == 6 else RuntimeError('evaluation failure')
        return out[0] | out[1]<<64

    def close(self):
        with self._lock:
            if self._handle:
                self.lib.check_destroy(self._handle)
                self._handle = None


class Basis:
    def __init__(self, x, y, equations, *, backend='cpu', sanitizer=False):
        self.producer = Producer(x, y, equations, backend=backend, sanitizer=sanitizer)
        try:
            self.checker = Checker(x, y, equations, sanitizer=sanitizer)
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
                result = self.producer.produce(anf, checker=self.checker)
            except (Inconclusive, Unsupported) as error:
                return {'status': 'inconclusive' if isinstance(error, Inconclusive) else 'unsupported',
                        'complete': False, 'detail': str(error), 'wall_seconds': time.perf_counter()-started}
            certificate = result['certificate']
            good = certificate['verified']
            return {'status': 'gb' if good else 'inconclusive' if certificate['code']==5 else 'verification-failed',
                    'complete': good, 'groebner_verified': good, 'generators_reduce_to_zero': good,
                    'basis_terms': result['basis'], 'basis_certificate': certificate,
                    'basis_sha256': hashlib.sha256(json.dumps(result['basis'], sort_keys=True).encode()).hexdigest(),
                    'proof_bytes': result['proof_bytes'], 'proof_sha256': result['proof_sha256'],
                    'proof_byteorder': result['proof_byteorder'],
                    'wall_seconds': result['producer_wall_seconds'], 'verification_seconds': result['verification_seconds'],
                    'basis_seconds': sum(result['stats'][k] for k in ('specialization', 'evaluation', 'interpolation')),
                    'metrics': result['stats'], 'coefficient_copy': False,
                    'producer_coefficient_word_bits': self.producer.coefficient_bits,
                    'checker_coefficient_word_bits': self.checker.coefficient_bits,
                    'transport': 'packed-native-views-with-narrow-coefficients-and-independent-branch-proof',
                    'algorithm': 'conditional-quadratic+derived-contradictions+exact-residual-fallback',
                    'backend_requested': self.producer.backend, 'device': self.producer.device,
                    'binary_sha256': self.producer.binary_sha256,
                    'verifier_binary_sha256': self.checker.binary_sha256, 'hard_subprocess_timeout': False}

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
