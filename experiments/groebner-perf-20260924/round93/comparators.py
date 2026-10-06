"""Declared bounded comparators: interpreted signatures and native interpolation."""
import ctypes as C
import sys
import time
from query import HERE, abi

sys.path[:0] = [str(HERE/'build'), str(HERE.parent.parent/'pdp-scaling')]
from boolean_basis import certify_boolean_basis

class DualStats(C.Structure):
    _fields_ = [(n, abi.U32) for n in ('roots', 'rows', 'standard', 'frontier')] + [
        ('evaluation', C.c_double), ('interpolation', C.c_double)]

def signature(n, original):
    if n > 12:
        return dict(status='unsupported', verified=False, reason='declared dense F5B bound n<=12', total_seconds=0)
    from f5_reference import BooleanF5B
    start = time.perf_counter()
    rows = original.equations()
    engine = BooleanF5B(n, timeout=2, max_pairs=10000)
    try:
        basis = [list(engine.terms(p)) for p in engine.basis([engine.from_terms(r) for r in rows])]
        cert = certify_boolean_basis(n, rows, basis)
        answer = dict(status='gb' if cert['verified'] else 'verification-failed',
                      verified=cert['verified'], basis=basis, certificate=cert)
    except TimeoutError as error:
        answer = dict(status='inconclusive', verified=False, reason=str(error))
    answer.update(total_seconds=time.perf_counter()-start, stats=engine.stats,
                  implementation='interpreted Boolean F5B with Boolean completion',
                  native_interreduce=False, timing_eligible=False, qualified_speedup=None)
    return answer

class Evaluation:
    def __init__(self, n, equations, *, sanitizer=False):
        self.n, self.equations = n, equations
        self.handle = None
        if n > 20 or not equations:
            return
        suffix = ('-ubsan' if sanitizer else '')+('.dylib' if sys.platform=='darwin' else '.so')
        self.lib = C.CDLL(str(HERE/'build'/('packed_dual'+suffix)))
        self.lib.packed_workspace_create.argtypes = [abi.U32, abi.U32]
        self.lib.packed_workspace_create.restype = C.c_void_p
        self.lib.packed_workspace_destroy.argtypes = [C.c_void_p]
        self.lib.packed_workspace_destroy.restype = None
        self.lib.packed_dual_compute.argtypes = [C.c_void_p, abi.P32, abi.P64, abi.U32, C.POINTER(DualStats)]
        self.lib.packed_dual_compute.restype = C.c_void_p
        self.lib.dual_row_size.argtypes = [C.c_void_p, abi.U32]
        self.lib.dual_row_size.restype = abi.U32
        self.lib.dual_row_data.argtypes = [C.c_void_p, abi.U32]
        self.lib.dual_row_data.restype = abi.P32
        self.lib.dual_destroy.argtypes = [C.c_void_p]
        self.lib.dual_destroy.restype = None
        self.lib.dual_error.restype = C.c_char_p
        self.handle = self.lib.packed_workspace_create(n, equations)
        if not self.handle:
            raise RuntimeError(self.lib.dual_error().decode())

    def close(self):
        if self.handle:
            self.lib.packed_workspace_destroy(self.handle)
            self.handle = None

    def compute(self, original):
        if not self.handle:
            return dict(status='unsupported', verified=False, reason='declared evaluation bound n<=20, equations>=1', total_seconds=0)
        start = time.perf_counter()
        # Explicit charged 64-to-32-bit transport for the historical comparator.
        masks = (abi.U32*original.view.terms)(*original.view.masks[:original.view.terms])
        stats = DualStats()
        result = self.lib.packed_dual_compute(self.handle, masks, original.view.coefficients,
                                              original.view.terms, C.byref(stats))
        if not result:
            return dict(status='inconclusive', verified=False, reason=self.lib.dual_error().decode(),
                        total_seconds=time.perf_counter()-start)
        try:
            basis = [list(self.lib.dual_row_data(result, i)[:self.lib.dual_row_size(result, i)]) for i in range(stats.rows)]
            cert = certify_boolean_basis(self.n, original.equations(), basis, monomial_cache=self.n<=12)
            return dict(status='gb' if cert['verified'] else 'verification-failed', verified=cert['verified'],
                        basis=basis, certificate=cert, stats=abi.fields(stats),
                        total_seconds=time.perf_counter()-start, timing_eligible=False, qualified_speedup=None)
        finally:
            self.lib.dual_destroy(result)
