"""Opt-in dense proof values, with unchanged producers and independent completion."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('query101_for102', P/'round101/query.py')
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
DenseInput, MatrixStats, LayoutStats = previous.DenseInput, previous.MatrixStats, previous.LayoutStats
LiveStats = previous.previous.previous.LiveStats
ARMS = ('f4-hash', 'f4-dense', 'matrix-hash', 'matrix-dense')


class DenseStats(C.Structure):
    _fields_ = [(name, abi.U64) for name in ('selected', 'fallback_large_ring',
        'words_per_value', 'word_work', 'metadata_bytes', 'live_bytes', 'peak_bytes',
        'created_values', 'released_values')]


class Query(previous.Query):
    def __init__(self, *, sanitizer=False, arm='f4-dense', dense_bytes=134217728):
        if arm not in ARMS:
            raise ValueError('unknown dense proof query arm')
        abi.integer(dense_bytes, 0, 1 << 64)
        self.proof_arm, self.dense_bytes = arm, dense_bytes
        super().__init__(sanitizer=sanitizer, arm='baseline' if arm.startswith('f4-') else 'reused2')
        suffix = ('-ubsan' if sanitizer else '')+('.dylib' if sys.platform == 'darwin' else '.so')
        path = HERE/'build'/('dense_checker'+suffix)
        self.dense = C.CDLL(str(path))
        self.dense.check_packed_dense.argtypes = [C.POINTER(abi.PackedInput), C.POINTER(abi.ProofView),
            abi.U64, abi.U64, abi.U32, abi.U32, abi.U32, abi.U64,
            C.POINTER(abi.CheckStats), C.POINTER(LiveStats), C.POINTER(DenseStats)]
        self.dense.check_packed_dense.restype = C.c_int
        self.dense.checker_error.argtypes = []
        self.dense.checker_error.restype = C.c_char_p
        self.dense.dense_stats_size.restype = abi.U64
        assert self.dense.dense_stats_size() == C.sizeof(DenseStats)
        self.binary_sha256[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def _check(self, input_view, proof_view, max_work, max_retained_terms):
        if self.proof_arm.endswith('-hash'):
            return super()._check(input_view, proof_view, max_work, max_retained_terms)
        abi.integer(max_work, 0, 1 << 64)
        abi.integer(max_retained_terms, 0, 1 << 64)
        stats, live, dense = abi.CheckStats(), LiveStats(), DenseStats()
        code = self.dense.check_packed_dense(C.byref(input_view), C.byref(proof_view),
            max_work, max_retained_terms, 1, 2, 1, self.dense_bytes,
            C.byref(stats), C.byref(live), C.byref(dense))
        result = dict(verified=code == 0,
            status=('verified', 'rejected', 'inconclusive', 'checker-failure')[code],
            method='independent-native-derivation-DAG+Boolean-Buchberger',
            stats=abi.fields(stats), liveness=abi.fields(live), dense=abi.fields(dense),
            root_count=None, solutions=None, schedule=self.checker_order,
            retention_policy=self.retention)
        if code:
            result['reason'] = self.dense.checker_error().decode()
        else:
            result.update(ideal_equality=True, reduced_groebner_basis=True)
        return result

    def compute(self, *args, **kwargs):
        result = super().compute(*args, **kwargs)
        result['proof_value_policy'] = self.proof_arm
        return result
