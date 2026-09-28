"""Independent packed evaluation with an explicitly owned reusable workspace."""
import ctypes as ct
import hashlib
from pathlib import Path
import sys
import threading

HERE = Path(__file__).resolve().parent
_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent / 'round17'))
    from public_query import PublicQuery, PublicInstance, NativeDescent, query
    from public_replay import Curve, GF2n, Point
    from native_descent import PackedANF
    sys.path.insert(0, str(HERE.parent.parent / 'pdp-scaling'))
    from boolean_certificate_native import Certificate, _pack
finally:
    sys.path[:] = _path

U32, U64 = ct.c_uint32, ct.c_uint64


class Result(ct.Structure):
    _fields_ = [('certificate', Certificate), ('zeta_words', U64),
                ('coefficient_bits', U64), ('scratch_bytes', U64)]


class PackedChecker:
    def __init__(self, nvars, equations, *, sanitizer=False):
        if type(nvars) is not int or not 1 <= nvars <= 20:
            raise ValueError('checker variables: 1..20')
        if type(equations) is not int or not 1 <= equations <= 128:
            raise ValueError('checker equations: 1..128')
        self.nvars, self.equations = nvars, equations
        self._lock = threading.Lock()
        suffix = ('-ubsan' if sanitizer else '') + ('.dylib' if sys.platform == 'darwin' else '.so')
        self.path = HERE / 'build' / ('packed-verifier' + suffix)
        self.binary_sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.lib = ct.CDLL(str(self.path))
        u32, u64 = ct.POINTER(U32), ct.POINTER(U64)
        self.lib.truth_create.argtypes = [U32, U32]
        self.lib.truth_create.restype = ct.c_void_p
        self.lib.truth_destroy.argtypes = [ct.c_void_p]
        self.lib.truth_destroy.restype = None
        self.lib.truth_result_size.restype = U64
        if self.lib.truth_result_size() != ct.sizeof(Result):
            raise RuntimeError('checker ABI mismatch')
        self.lib.truth_certify.argtypes = [ct.c_void_p, u32, u64, U32, u32, U32, u32, U32, ct.POINTER(Result)]
        self.lib.truth_certify.restype = ct.c_int
        self.lib.truth_evaluate.argtypes = [ct.c_void_p, u32, u64, U32, U32, u64]
        self.lib.truth_evaluate.restype = ct.c_int
        self._handle = self.lib.truth_create(nvars, equations)
        if not self._handle:
            raise RuntimeError('checker allocation failed')

    def _validate_views(self, masks, coefficients):
        if not isinstance(masks, ct.Array) or masks._type_ is not U32:
            raise ValueError('uint32 mask buffer required')
        if not isinstance(coefficients, ct.Array) or coefficients._type_ is not U64:
            raise ValueError('uint64 coefficient buffer required')
        if len(masks) >= 1 << 32 or len(coefficients) != len(masks) * ((self.equations + 63)//64):
            raise ValueError('packed buffer extents')

    def _views(self, anf):
        if not isinstance(anf, PackedANF) or (anf.nvars, anf.equations) != (self.nvars, self.equations):
            raise ValueError('packed ANF ring mismatch')
        self._validate_views(anf.masks, anf.coefficients)
        return anf.masks, anf.coefficients

    def certify_views(self, masks, coefficients, basis):
        self._validate_views(masks, coefficients)
        terms, offsets = _pack(basis, self.nvars)
        result = Result()
        with self._lock:
            if not self._handle: raise RuntimeError('checker is closed')
            code = self.lib.truth_certify(self._handle, masks, coefficients, len(masks),
                terms, len(terms), offsets, len(offsets)-1, ct.byref(result))
        if code == 6: raise ValueError('invalid packed certificate input')
        if code == 7: raise RuntimeError('certificate allocation or internal failure')
        value = result.certificate
        answer = {'verified': code == 0, 'method': 'exact-Boolean-zeros-and-staircase',
                  'backend': 'independent-packed-bitslice-zeta', 'root_count': value.roots,
                  'standard_monomials': value.standard,
                  'evaluation_counts': {'zeta_words': result.zeta_words,
                                        'coefficient_bits': result.coefficient_bits},
                  'scratch_bytes': result.scratch_bytes}
        if code:
            answer['reason'] = {1: 'noncanonical or zero basis row', 2: 'basis removes an input root',
                3: 'staircase dimension differs from root count', 4: 'nonminimal leading monomial',
                5: 'nonstandard tail monomial'}[code]
        else:
            answer.update(ideal_equality=True, reduced_groebner_basis=True,
                          solutions=list(value.solutions[:value.solution_count]) if value.roots <= 256 else None)
        return answer

    def certify(self, anf, basis):
        return self.certify_views(*self._views(anf), basis)

    def evaluate(self, anf, assignment):
        if type(assignment) is not int or not 0 <= assignment < 1 << self.nvars:
            raise ValueError('assignment outside Boolean ring')
        masks, coefficients = self._views(anf)
        out = (U64 * 2)()
        with self._lock:
            if not self._handle: raise RuntimeError('checker is closed')
            code = self.lib.truth_evaluate(self._handle, masks, coefficients, len(masks), assignment, out)
        if code == 6: raise ValueError('invalid packed equation input')
        if code: raise RuntimeError('packed equation evaluation failed')
        return out[0] | out[1] << 64

    def close(self):
        with self._lock:
            if self._handle:
                self.lib.truth_destroy(self._handle)
                self._handle = None

    def __enter__(self): return self
    def __exit__(self, *_): self.close()
