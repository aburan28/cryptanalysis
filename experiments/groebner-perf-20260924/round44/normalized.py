"""Complete-query partial affine certificates with independent tagged checking."""
import ctypes as ct
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round34'))
from checker_base import Checker, CheckStats
sys.path.insert(0, str(HERE.parent / 'round31'))
from quadratic import Native, Packed, Inconclusive, Unsupported, U32, U64, P32, P64, Stats


def dimensions(x, y, equations):
    if any(type(v) is not int for v in (x, y, equations)) or not (
            1 <= x <= 20 and 1 <= y <= 10 and x+y <= 30 and 1 <= equations <= 128):
        raise ValueError('x 1..20; y 1..10; x+y<=30; equations 1..128')


class MultiplierStats(ct.Structure):
    _fields_ = [(name, U64) for name in ('attempts', 'certified_branches', 'failed_branches',
        'budget_skips', 'rows', 'row_xors', 'word_xors', 'avoided_assignments',
        'proof_words', 'proof_capacity_words', 'workspace_bytes')]
    _fields_ += [('seconds', ct.c_double)]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


class SymmetryStats(ct.Structure):
    _fields_ = [(name, U64) for name in ('enabled','shape_fallback','asymmetric_fallback',
        'compared_pairs','compared_coefficients','representatives','aliases',
        'constant_copies','affine_copies','affine_copy_words','copy_budget_skips',
        'copied_roots','rootless_aliases','gpu_linearized_branches','workspace_bytes')]
    _fields_ += [(name,ct.c_double) for name in ('check_seconds','expand_seconds')]

    def record(self):
        return {name:getattr(self,name) for name,_ in self._fields_}


class DeferredStats(ct.Structure):
    _fields_ = [(name,U64) for name in ('inserted_pivots','dependency_toggles','reconstruction_attempts',
        'reconstruction_pivots','reconstruction_word_xors','reconstructed_proofs','source_toggles','workspace_bytes')]
    _fields_ += [('reconstruction_seconds',ct.c_double)]

    def record(self):
        return {name:getattr(self,name) for name,_ in self._fields_}


class ProjectionStats(ct.Structure):
    _fields_ = [(name, U64) for name in ['attempts', 'certified_branches', 'rank_fallbacks', 'satisfying_fallbacks', 'budget_skips', 'input_rows', 'row_xors', 'word_xors', 'certificate_xors', 'work', 'stack_bytes']] + [('seconds', ct.c_double)]
    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}

class NormalizationStats(ct.Structure):
    _fields_ = [(name, U64) for name in ['attempts', 'prepared', 'zero_scalars', 'mismatches', 'nonunits', 'budget_skips', 'field_steps', 'guard_columns', 'inverse_steps', 'transpose_parities', 'transport_lookups', 'affine_parities', 'work', 'stack_bytes', 'workspace_bytes']] + [('seconds', ct.c_double)]
    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}

class PartialProduceStats(ct.Structure):
    _fields_ = [(name, U64) for name in ('attempts', 'handled_branches', 'rank_sum',
        'assignments', 'equation_word_xors', 'roots_found', 'proof_rows', 'proof_words',
        'copied_records', 'budget_skips', 'stack_bytes')] + [('seconds', ct.c_double)]

    def record(self):
        return {name: getattr(self, name) for name, _ in self._fields_}


class Producer(Native):
    def __init__(self, x, y, equations, *, backend='cpu', sanitizer=False, budget_test=False, multiplier_budget_test=False, copy_budget_test=False, reconstruction_budget_test=False, enumeration_budget_test=False, partial_commit_budget_test=False, partial=True):
        dimensions(x, y, equations)
        if type(partial) is not bool:
            raise ValueError('partial flag must be Boolean')
        if backend not in ('cpu', 'metal') or sum(bool(v) for v in (sanitizer, budget_test, multiplier_budget_test, copy_budget_test, reconstruction_budget_test, enumeration_budget_test, partial_commit_budget_test)) > 1 or (
                backend == 'metal' and (sanitizer or budget_test or multiplier_budget_test or copy_budget_test or reconstruction_budget_test or enumeration_budget_test or partial_commit_budget_test)):
            raise ValueError('select a supported backend/build')
        self.x, self.y, self.nvars, self.equations = x, y, x+y, equations
        self.backend = backend
        self._lock, self._handle = threading.Lock(), None
        tag = '-metal' if backend == 'metal' else '-enumeration-budget' if enumeration_budget_test else '-partial-commit-budget' if partial_commit_budget_test else '-reconstruction-budget' if reconstruction_budget_test else '-copy-budget' if copy_budget_test else '-multiplier-budget' if multiplier_budget_test else '-budget' if budget_test else '-ubsan' if sanitizer else ''
        self.path = HERE/'build'/('producer'+tag+('.dylib' if sys.platform == 'darwin' else '.so'))
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.lib = lib = ct.CDLL(str(self.path))
        lib.branch_stats_size.restype = U64
        if lib.branch_stats_size() != ct.sizeof(Stats):
            raise RuntimeError('producer ABI mismatch')
        lib.branch_multiplier_stats_size.restype = U64
        if lib.branch_multiplier_stats_size() != ct.sizeof(MultiplierStats):
            raise RuntimeError('multiplier metadata ABI mismatch')
        lib.branch_symmetry_stats_size.restype = U64
        if lib.branch_symmetry_stats_size() != ct.sizeof(SymmetryStats):
            raise RuntimeError('symmetry metadata ABI mismatch')
        lib.branch_deferred_stats_size.restype = U64
        if lib.branch_deferred_stats_size() != ct.sizeof(DeferredStats):
            raise RuntimeError('deferred metadata ABI mismatch')
        lib.branch_projection_stats_size.restype = U64
        if lib.branch_projection_stats_size() != ct.sizeof(ProjectionStats):
            raise RuntimeError('projection accounting ABI mismatch')
        lib.branch_normalization_stats_size.restype = U64
        if lib.branch_normalization_stats_size() != ct.sizeof(NormalizationStats):
            raise RuntimeError('normalization accounting ABI mismatch')
        lib.branch_partial_stats_size.restype = U64
        if lib.branch_partial_stats_size() != ct.sizeof(PartialProduceStats):
            raise RuntimeError('partial accounting ABI mismatch')
        self.normalization_configuration = {'requested': False, 'enabled': False}
        for name, result, args in (
            ('branch_partial_stats', ct.POINTER(PartialProduceStats), [ct.c_void_p]),
            ('branch_last_partial_stats', ct.POINTER(PartialProduceStats), []),
            ('branch_partial_configure', ct.c_int, [ct.c_void_p, U32]),
            ('branch_normalization_transport', ct.c_int, [ct.c_void_p, ct.c_uint32, ct.POINTER(ct.c_uint32), ct.c_uint32]),
            ('branch_normalization_stats', ct.POINTER(NormalizationStats), [ct.c_void_p]),
            ('branch_last_normalization_stats', ct.POINTER(NormalizationStats), []),
            ('branch_normalization_configure', ct.c_int, [ct.c_void_p, U64]),
            ('branch_projection_stats', ct.POINTER(ProjectionStats), [ct.c_void_p]),
            ('branch_last_projection_stats', ct.POINTER(ProjectionStats), []),
            ('branch_deferred_stats', ct.POINTER(DeferredStats), [ct.c_void_p]),
            ('branch_last_deferred_stats', ct.POINTER(DeferredStats), []),
            ('branch_symmetry_stats', ct.POINTER(SymmetryStats), [ct.c_void_p]),
            ('branch_last_symmetry_stats', ct.POINTER(SymmetryStats), []),
            ('branch_multiplier_stats', ct.POINTER(MultiplierStats), [ct.c_void_p]),
            ('branch_last_multiplier_stats', ct.POINTER(MultiplierStats), []),
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

        try:
            self.configure_partial(partial)
        except Exception:
            self.close()
            raise

    def configure_partial(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('partial flag must be Boolean')
        with self._lock:
            if not self._handle:
                raise RuntimeError('producer is closed')
            result = self.lib.branch_partial_configure(self._handle, enabled)
            if result < 0:
                raise ValueError('partial configuration rejected')
            self.partial_enabled = bool(result)
            return self.partial_enabled

    def configure_normalization(self, modulus):
        if type(modulus) is not int or modulus < 0:
            raise ValueError('explicit nonnegative integer modulus required')
        with self._lock:
            if not self._handle:
                raise RuntimeError('producer is closed')
            if self.equations > 31 or self.y < 3 or 3*self.y-4 >= self.equations:
                self.normalization_configuration = {'requested': bool(modulus), 'enabled': False, 'reason': 'unsupported shape', 'modulus': modulus}
                return False
            if modulus >= 1 << 64:
                raise ValueError('normalization modulus does not fit native ABI')
            # The native request disables the old configuration before it
            # validates a replacement. Preserve that state on rejection.
            self.normalization_configuration = {'requested': bool(modulus), 'enabled': False, 'modulus': modulus}
            result = self.lib.branch_normalization_configure(self._handle, modulus)
            if result < 0:
                self.normalization_configuration['reason'] = 'rejected modulus'
                raise ValueError(self.lib.branch_error().decode())
            self.normalization_configuration = {'requested': bool(modulus), 'enabled': bool(result), 'modulus': modulus}
            return bool(result)

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
                error = {5: Inconclusive, 6: ValueError, 7: Unsupported}.get(code, RuntimeError)(message)
                error.metrics = stats.record()
                error.partial_stats = self.lib.branch_last_partial_stats().contents.record()
                error.projection_stats = self.lib.branch_last_projection_stats().contents.record()
                error.normalization_stats = self.lib.branch_last_normalization_stats().contents.record()
                error.deferred_stats = self.lib.branch_last_deferred_stats().contents.record()
                error.symmetry_stats = self.lib.branch_last_symmetry_stats().contents.record()
                error.multiplier_stats = self.lib.branch_last_multiplier_stats().contents.record()
                raise error
            try:
                roots = list(self.lib.branch_roots(result)[:stats.roots])
                basis = [list(self.lib.branch_row(result, i)[:self.lib.branch_row_size(result, i)])
                         for i in range(self.lib.branch_rows(result))]
                size = self.lib.branch_proof_size(result)
                prefix = (1 << self.x)*((self.equations+63)//64)
                entry = 1+(self.y+1)*((self.equations+63)//64)
                if size < prefix or size > (64<<20)//8 or (size-prefix)%entry:
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
                        'partial_stats': self.lib.branch_partial_stats(result).contents.record(),
                        'projection_stats': self.lib.branch_projection_stats(result).contents.record(),
                        'normalization_stats': self.lib.branch_normalization_stats(result).contents.record(),
                        'multiplier_stats': self.lib.branch_multiplier_stats(result).contents.record(),
                        'deferred_stats': self.lib.branch_deferred_stats(result).contents.record(),
                        'symmetry_stats': self.lib.branch_symmetry_stats(result).contents.record(),
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


class Basis:
    def __init__(self, x, y, equations, *, backend='cpu', sanitizer=False, partial=True):
        self.producer = Producer(x, y, equations, backend=backend, sanitizer=sanitizer, partial=partial)
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
                        'complete': False, 'detail': str(error), 'wall_seconds': time.perf_counter()-started,
                        'metrics': getattr(error, 'metrics', {}),
                        'partial_stats': getattr(error, 'partial_stats', {}),
                        'partial_enabled': self.producer.partial_enabled,
                        'projection_stats': getattr(error, 'projection_stats', {}),
                        'normalization_stats': getattr(error, 'normalization_stats', {}),
                        'normalization_configuration': self.producer.normalization_configuration,
                        'multiplier_stats': getattr(error, 'multiplier_stats', {}),
                        'deferred_stats': getattr(error, 'deferred_stats', {}),
                        'symmetry_stats': getattr(error, 'symmetry_stats', {})}
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
                    'metrics': result['stats'], 'multiplier_stats': result['multiplier_stats'],
                    'partial_stats': result['partial_stats'],
                    'partial_enabled': self.producer.partial_enabled,
                    'projection_stats': result['projection_stats'],
                    'normalization_stats': result['normalization_stats'],
                    'normalization_configuration': self.producer.normalization_configuration,
                    'deferred_stats': result['deferred_stats'],
                    'symmetry_stats': result['symmetry_stats'], 'coefficient_copy': False,
                    'proof_format': 'constant-prefix+tagged-affine-records-v2',
                    'producer_coefficient_word_bits': self.producer.coefficient_bits,
                    'checker_coefficient_word_bits': self.checker.coefficient_bits,
                    'transport': 'packed-native-views-with-independent-tagged-affine-proof',
                    'algorithm': 'guarded-normalized+partial-affine-subspace+exact-fallback',
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
