"""Independent sparse proof; retain the frozen packed evaluator and validation."""
import ctypes as ct
import hashlib
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent / 'round18'))
    from packed_checker import (PackedChecker, PackedANF, Certificate, U32, U64,
                                Curve, GF2n, Point, query, _pack)
    from truth_query import TruthQuery
finally:
    sys.path[:] = _path


class ProofStats(ct.Structure):
    _fields_ = [(name, U32) for name in
                ('mode', 'root_list_used', 'staircase_used', 'fallback_reason')]
    _fields_ += [(name, U64) for name in ('root_blocks_scanned', 'root_parity_tests',
                 'divisibility_tests', 'standard_visited', 'workspace_bytes',
                 'dense_table_bytes', 'budget_limit')]
    _fields_ += [('seconds', ct.c_double)]


class Result(ct.Structure):
    _fields_ = [('certificate', Certificate), ('zeta_words', U64),
                ('coefficient_bits', U64), ('scratch_bytes', U64), ('proof', ProofStats)]


class SparseChecker(PackedChecker):
    def __init__(self, nvars, equations, *, mode=2, sanitizer=False, budget_test=False):
        if type(nvars) is not int or not 1 <= nvars <= 20:
            raise ValueError('checker variables: 1..20')
        if type(equations) is not int or not 1 <= equations <= 128:
            raise ValueError('checker equations: 1..128')
        if type(mode) is not int or mode not in (0, 1, 2):
            raise ValueError('proof mode must be 0, 1 or 2')
        if sanitizer and budget_test:
            raise ValueError('select one explicit test build')
        self.nvars, self.equations, self.mode = nvars, equations, mode
        self._lock = threading.Lock()
        tag = '-budget' if budget_test else '-ubsan' if sanitizer else ''
        suffix = '.dylib' if sys.platform == 'darwin' else '.so'
        self.path = HERE / 'build' / ('sparse-verifier' + tag + suffix)
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.lib = ct.CDLL(str(self.path))
        u32, u64 = ct.POINTER(U32), ct.POINTER(U64)
        self.lib.truth_create.argtypes = [U32, U32]
        self.lib.truth_create.restype = ct.c_void_p
        self.lib.truth_create_mode.argtypes = [U32, U32, U32]
        self.lib.truth_create_mode.restype = ct.c_void_p
        self.lib.truth_destroy.argtypes = [ct.c_void_p]
        self.lib.truth_destroy.restype = None
        self.lib.truth_result_size.restype = U64
        if self.lib.truth_result_size() != ct.sizeof(Result):
            raise RuntimeError('sparse checker ABI mismatch')
        self.lib.truth_certify.argtypes = [ct.c_void_p, u32, u64, U32, u32, U32, u32, U32, ct.POINTER(Result)]
        self.lib.truth_certify.restype = ct.c_int
        self.lib.truth_evaluate.argtypes = [ct.c_void_p, u32, u64, U32, U32, u64]
        self.lib.truth_evaluate.restype = ct.c_int
        self._handle = self.lib.truth_create_mode(nvars, equations, mode)
        if not self._handle:
            raise RuntimeError('checker allocation failed')

    def certify_views(self, masks, coefficients, basis):
        self._validate_views(masks, coefficients)
        terms, offsets = _pack(basis, self.nvars)
        result = Result()
        with self._lock:
            if not self._handle:
                raise RuntimeError('checker is closed')
            code = self.lib.truth_certify(self._handle, masks, coefficients, len(masks),
                terms, len(terms), offsets, len(offsets)-1, ct.byref(result))
        if code == 6:
            raise ValueError('invalid packed certificate input')
        if code == 7:
            raise RuntimeError('certificate allocation or internal failure')
        value = result.certificate
        answer = {'verified': code == 0, 'method': 'exact-Boolean-zeros-and-staircase',
                  'backend': 'independent-packed-sparse-proof', 'root_count': value.roots,
                  'standard_monomials': value.standard,
                  'evaluation_counts': {'zeta_words': result.zeta_words,
                                        'coefficient_bits': result.coefficient_bits},
                  'scratch_bytes': result.scratch_bytes,
                  'proof_stats': {name: getattr(result.proof, name) for name, _ in ProofStats._fields_}}
        if code:
            answer['reason'] = {1: 'noncanonical or zero basis row', 2: 'basis removes an input root',
                3: 'staircase dimension differs from root count', 4: 'nonminimal leading monomial',
                5: 'nonstandard tail monomial'}[code]
        else:
            answer.update(ideal_equality=True, reduced_groebner_basis=True,
                          solutions=list(value.solutions[:value.solution_count]) if value.roots <= 256 else None)
        return answer


ARMS = ('cpu', 'root-list', 'sparse')


class SparseQuery(TruthQuery):
    def __init__(self, n, mod, b, m, ell, arm='sparse', *, sanitizer=False):
        if arm not in ARMS:
            raise ValueError('unknown sparse proof query arm')
        self.variant = arm
        super().__init__(n, mod, b, m, ell, arm='combined', sanitizer=sanitizer)
        try:
            if arm != 'cpu':
                self.checker.close()
                self.checker = SparseChecker(m*ell, n, mode=1 if arm == 'root-list' else 2,
                                             sanitizer=sanitizer)
                self.basis._certify = self.checker.certify_views
                self.basis.verifier_path = self.checker.path
        except Exception:
            self.close()
            raise

    def solve(self, target):
        answer = super().solve(target)
        answer['query_arm'] = self.variant
        return answer
