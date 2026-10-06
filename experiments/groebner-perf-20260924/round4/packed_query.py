"""Opt-in packed ANF query path. No F4/F5 dispatch changes or answer caching.

Coefficient bit j is Boolean equation j. Native solver and verifier decode
these coefficients independently. A workspace owns scratch storage only and
must be closed; its entire numerical table is cleared on every query.
"""
from array import array
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'round2'), str(HERE.parent.parent / 'pdp-scaling')]
from boolean_certificate_native import Certificate, _pack
from solve_dual import DualStats
from descend import verify_solution


def _views(nvars, equations, anf):
    """Copy dictionary keys/values once, without expanding Boolean rows."""
    # Snapshot a dictionary before taking its two views. A caller changing its
    # size between keys/values would otherwise produce mismatched ABI buffers.
    if not isinstance(anf, dict):
        raise ValueError('packed ANF must be a coefficient dictionary')
    anf = dict(anf)
    if len(anf) >= 1 << 32:
        raise ValueError('packed input exceeds uint32 ABI')
    try:
        masks = array('I', anf)
        if equations <= 64:
            coefficients = array('Q', anf.values())
        else:
            limbs = (equations + 63) // 64
            coefficients = array('Q')
            for value in anf.values():
                if not isinstance(value, int) or value < 0 or value >> equations:
                    raise ValueError('coefficient outside the equation bitset')
                coefficients.extend((value >> (64*j)) & ((1 << 64)-1) for j in range(limbs))
    except (TypeError, OverflowError) as error:
        raise ValueError('invalid packed coefficient or monomial') from error
    assert masks.itemsize == ctypes.sizeof(ctypes.c_uint32)
    assert coefficients.itemsize == ctypes.sizeof(ctypes.c_uint64)
    return ((ctypes.c_uint32 * len(masks)).from_buffer(masks),
            (ctypes.c_uint64 * len(coefficients)).from_buffer(coefficients))


class PackedQuery:
    def __init__(self, nvars, equations, *, sanitizer=False):
        if not isinstance(nvars, int) or not 1 <= nvars <= 20:
            raise ValueError('packed query variables: 1..20')
        if not isinstance(equations, int) or not 1 <= equations <= 4096:
            raise ValueError('packed query equation count: 1..4096')
        self.nvars, self.equations = nvars, equations
        self._lock = threading.Lock()
        self._handle = None
        suffix = ('-ubsan' if sanitizer else '') + ('.dylib' if sys.platform == 'darwin' else '.so')
        self.solver_path = HERE / 'build' / ('packed_dual' + suffix)
        self.verifier_path = HERE / 'build' / ('packed_certificate' + suffix)
        self._solver = ctypes.CDLL(str(self.solver_path))
        self._verifier = ctypes.CDLL(str(self.verifier_path))
        u32, u64 = ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64)
        self._solver.packed_workspace_create.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        self._solver.packed_workspace_create.restype = ctypes.c_void_p
        self._solver.packed_workspace_destroy.argtypes = [ctypes.c_void_p]
        self._solver.packed_workspace_destroy.restype = None
        self._solver.packed_dual_compute.argtypes = [ctypes.c_void_p, u32, u64, ctypes.c_uint32,
                                                   ctypes.POINTER(DualStats)]
        self._solver.packed_dual_compute.restype = ctypes.c_void_p
        self._solver.dual_error.restype = ctypes.c_char_p
        self._solver.dual_row_size.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self._solver.dual_row_size.restype = ctypes.c_uint32
        self._solver.dual_row_data.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self._solver.dual_row_data.restype = u32
        self._solver.dual_destroy.argtypes = [ctypes.c_void_p]
        self._solver.dual_destroy.restype = None
        self._verifier.packed_boolean_certificate.argtypes = [ctypes.c_uint32, ctypes.c_uint32,
            u32, u64, ctypes.c_uint32, u32, ctypes.c_uint32, u32, ctypes.c_uint32,
            ctypes.POINTER(Certificate)]
        self._verifier.packed_boolean_certificate.restype = ctypes.c_int
        self._handle = self._solver.packed_workspace_create(nvars, equations)
        if not self._handle:
            raise RuntimeError(self._solver.dual_error().decode())

    def close(self):
        with self._lock:
            if self._handle:
                self._solver.packed_workspace_destroy(self._handle)
                self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def certify(self, anf, basis):
        masks, coefficients = _views(self.nvars, self.equations, anf)
        return self._certify(masks, coefficients, basis)

    def _certify(self, masks, coefficients, basis):
        terms, offsets = _pack(basis, self.nvars)
        result = Certificate()
        code = self._verifier.packed_boolean_certificate(self.nvars, self.equations,
            masks, coefficients, len(masks), terms, len(terms), offsets, len(offsets)-1,
            ctypes.byref(result))
        if code == 6:
            raise ValueError('invalid packed certificate input')
        if code == 7:
            raise RuntimeError('packed certificate allocation or internal failure')
        answer = {'verified': code == 0, 'method': 'exact-Boolean-zeros-and-staircase',
                  'backend': 'independent-packed-decoder+native-direct-anf',
                  'root_count': result.roots, 'standard_monomials': result.standard,
                  'evaluation_counts': {'scatter_words': result.scatter_words,
                                        'scalar_terms': result.scalar_terms}}
        if code:
            answer['reason'] = {1: 'noncanonical or zero basis row', 2: 'basis removes an input root',
                3: 'staircase dimension differs from root count', 4: 'nonminimal leading monomial',
                5: 'nonstandard tail monomial'}[code]
        else:
            answer.update(ideal_equality=True, reduced_groebner_basis=True,
                          solutions=list(result.solutions[:result.solution_count]) if result.roots <= 256 else None)
        return answer

    def compute(self, anf):
        # Serializes workspace lifetime as well as access while ctypes releases
        # the GIL. Different workspaces can execute concurrently.
        with self._lock:
            if not self._handle:
                raise RuntimeError('packed workspace is closed')
            start = time.perf_counter()
            masks, coefficients = _views(self.nvars, self.equations, anf)
            packing = time.perf_counter() - start
            stats = DualStats()
            handle = self._solver.packed_dual_compute(self._handle, masks, coefficients,
                                                     len(masks), ctypes.byref(stats))
            wall = time.perf_counter() - start
            if not handle:
                error = self._solver.dual_error().decode()
                if 'range' in error or 'invalid' in error:
                    raise ValueError(error)
                return {'status': 'inconclusive', 'complete': False, 'wall_seconds': wall,
                        'packing_seconds': packing, 'detail': error}
            try:
                basis = [list(self._solver.dual_row_data(handle, i)[:self._solver.dual_row_size(handle, i)])
                         for i in range(stats.rows)]
            finally:
                self._solver.dual_destroy(handle)
            wall = time.perf_counter() - start
            start = time.perf_counter()
            certificate = self._certify(masks, coefficients, basis)
            verification = time.perf_counter() - start
            return {'status': 'gb' if certificate['verified'] else 'verification-failed',
                    'complete': certificate['verified'], 'basis_terms': basis,
                    'basis_sha256': hashlib.sha256(json.dumps([sorted(g) for g in basis], sort_keys=True).encode()).hexdigest(),
                    'basis_seconds': stats.evaluation + stats.interpolation, 'wall_seconds': wall,
                    'packing_seconds': packing, 'verification_seconds': verification,
                    'basis_certificate': certificate, 'groebner_verified': certificate['verified'],
                    'generators_reduce_to_zero': certificate['verified'], 'transport': 'packed-library',
                    'hard_subprocess_timeout': False, 'verifier': 'independent-native-packed',
                    'algorithm': 'exact-evaluation+buchberger-moller',
                    'metrics': {'roots': stats.roots, 'evaluation_seconds': stats.evaluation,
                                'interpolation_seconds': stats.interpolation,
                                'standard_monomials': stats.standard, 'frontier_visits': stats.frontier},
                    'binary_sha256': hashlib.sha256(self.solver_path.read_bytes()).hexdigest(),
                    'verifier_binary_sha256': hashlib.sha256(self.verifier_path.read_bytes()).hexdigest()}

    def solve(self, instance):
        if (instance.nvars, instance.n) != (self.nvars, self.equations):
            raise ValueError('instance does not match workspace ring')
        result = self.compute(instance.anf)
        result.pop('basis_terms', None)
        if result['status'] != 'gb':
            return result
        start = time.perf_counter()
        # The solver root cap is 256. Successful certificates above that size
        # are supported by certify(), but cannot occur on this solving path.
        solutions = result['basis_certificate']['solutions']
        if solutions is None:
            raise RuntimeError('solver root bound violated')
        checked = 0
        for assignment in solutions:
            checked += 1
            # Original dictionary evaluation and full curve replay are retained.
            if instance.evaluate(assignment) == 0 and verify_solution(instance, assignment):
                result.update(status='solved', verified=True, assignment=assignment)
                break
        if result['status'] == 'gb':
            result['status'] = 'gb-no-verified-solution'
        result.update(assignments_checked=checked, basis_candidates_checked=checked,
                      assignment_search='certified-input-roots',
                      extraction_seconds=time.perf_counter()-start)
        return result
