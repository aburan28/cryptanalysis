"""Opt-in checker buffer transfer with unchanged producer, transport and replay."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('query104_for105', P/'round104/query.py')
previous = importlib.util.module_from_spec(spec)
_path = sys.path[:]
try:
    spec.loader.exec_module(previous)
finally:
    sys.path[:] = _path
module = previous
while module is not None:
    module.HERE = HERE
    if hasattr(module, 'abi'):
        module.abi.HERE = HERE
    module = getattr(module, 'previous', None)
abi = previous.abi
PackedDescentPlan = previous.PackedDescentPlan
LiveStats = previous.LiveStats
DenseStats = previous.DenseStats
ReuseStats = previous.ReuseStats
ARMS = ('f4-reuse', 'f4-quotient', 'matrix-reuse', 'matrix-quotient')


class NormalStats(C.Structure):
    _fields_ = [(name, abi.U64) for name in ('mode', 'selected', 'fallback_large_ring',
        'fallback_sparse', 'fallback_dimension', 'fallback_bytes', 'input_terms',
        'universe', 'dimension', 'peak_bytes', 'planning_work', 'table_products',
        'table_terms', 'input_xors', 'work')]


class Query(previous.Query):
    def __init__(self, *, sanitizer=False, arm='matrix-quotient', normal_bytes=1048576, **kwargs):
        if arm not in ARMS:
            raise ValueError('unknown quotient membership arm')
        abi.integer(normal_bytes, 0, 1 << 64)
        self.normal_arm, self.normal_bytes = arm, normal_bytes
        super().__init__(sanitizer=sanitizer,
            arm='f4-reuse' if arm.startswith('f4-') else 'matrix-reuse', **kwargs)
        suffix = ('-ubsan' if sanitizer else '')+('.dylib' if sys.platform == 'darwin' else '.so')
        path = HERE/'build'/('normal_checker'+suffix)
        self.normal = C.CDLL(str(path))
        self.normal.check_packed_normal.argtypes = [C.POINTER(abi.PackedInput), C.POINTER(abi.ProofView),
            abi.U64, abi.U64, abi.U32, abi.U32, abi.U32, abi.U64, abi.U32,
            abi.U32, abi.U64, C.POINTER(NormalStats), C.POINTER(abi.CheckStats),
            C.POINTER(LiveStats), C.POINTER(DenseStats), C.POINTER(ReuseStats)]
        self.normal.check_packed_normal.restype = C.c_int
        self.normal.checker_error.argtypes = []
        self.normal.checker_error.restype = C.c_char_p
        self.normal.normal_stats_size.restype = abi.U64
        assert self.normal.normal_stats_size() == C.sizeof(NormalStats)
        self.binary_sha256[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def _check(self, input_view, proof_view, max_work, max_retained_terms):
        if not self.normal_arm.endswith('-quotient'):
            return super()._check(input_view, proof_view, max_work, max_retained_terms)
        abi.integer(max_work, 0, 1 << 64)
        abi.integer(max_retained_terms, 0, 1 << 64)
        stats, live, dense = abi.CheckStats(), LiveStats(), DenseStats()
        reuse, normal = ReuseStats(), NormalStats()
        code = self.normal.check_packed_normal(C.byref(input_view), C.byref(proof_view),
            max_work, max_retained_terms, 1, 2, 1, self.dense_bytes, 1,
            1, self.normal_bytes, C.byref(normal), C.byref(stats), C.byref(live),
            C.byref(dense), C.byref(reuse))
        result = dict(verified=code == 0,
            status=('verified', 'rejected', 'inconclusive', 'checker-failure')[code],
            method='independent-native-derivation-DAG+Boolean-Buchberger',
            stats=abi.fields(stats), liveness=abi.fields(live), dense=abi.fields(dense),
            reuse=abi.fields(reuse), normal=abi.fields(normal), root_count=None, solutions=None,
            schedule=self.checker_order, retention_policy=self.retention)
        if code:
            result['reason'] = self.normal.checker_error().decode()
        else:
            result.update(ideal_equality=True, reduced_groebner_basis=True)
        return result

    def compute(self, *args, **kwargs):
        result = super().compute(*args, **kwargs)
        result['normal_form_policy'] = self.normal_arm
        return result
