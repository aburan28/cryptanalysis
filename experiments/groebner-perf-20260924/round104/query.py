"""Opt-in checker buffer transfer with unchanged producer, transport and replay."""
import ctypes as C
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('query103_for104', P/'round103/query.py')
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
LiveStats = previous.previous.LiveStats
DenseStats = previous.previous.DenseStats
ARMS = ('f4-dense', 'f4-reuse', 'matrix-packed', 'matrix-reuse')


class ReuseStats(C.Structure):
    _fields_ = [(name, abi.U64) for name in ('enabled', 'checks', 'transfers',
        'left_transfers', 'right_transfers', 'payload_allocations', 'payload_releases')]


class Query(previous.Query):
    def __init__(self, *, sanitizer=False, arm='matrix-reuse', **kwargs):
        if arm not in ARMS:
            raise ValueError('unknown buffer reuse arm')
        self.reuse_arm = arm
        super().__init__(sanitizer=sanitizer,
            arm='f4-dense' if arm.startswith('f4-') else 'matrix-packed', **kwargs)
        suffix = ('-ubsan' if sanitizer else '')+('.dylib' if sys.platform == 'darwin' else '.so')
        path = HERE/'build'/('reuse_checker'+suffix)
        self.reuse = C.CDLL(str(path))
        self.reuse.check_packed_reuse.argtypes = [C.POINTER(abi.PackedInput), C.POINTER(abi.ProofView),
            abi.U64, abi.U64, abi.U32, abi.U32, abi.U32, abi.U64, abi.U32,
            C.POINTER(abi.CheckStats), C.POINTER(LiveStats), C.POINTER(DenseStats), C.POINTER(ReuseStats)]
        self.reuse.check_packed_reuse.restype = C.c_int
        self.reuse.checker_error.argtypes = []
        self.reuse.checker_error.restype = C.c_char_p
        self.reuse.reuse_stats_size.restype = abi.U64
        self.reuse.dense_stats_size.restype = abi.U64
        assert self.reuse.reuse_stats_size() == C.sizeof(ReuseStats)
        assert self.reuse.dense_stats_size() == C.sizeof(DenseStats)
        self.binary_sha256[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def _check(self, input_view, proof_view, max_work, max_retained_terms):
        if not self.reuse_arm.endswith('-reuse'):
            return super()._check(input_view, proof_view, max_work, max_retained_terms)
        abi.integer(max_work, 0, 1 << 64)
        abi.integer(max_retained_terms, 0, 1 << 64)
        stats, live, dense, reuse = abi.CheckStats(), LiveStats(), DenseStats(), ReuseStats()
        code = self.reuse.check_packed_reuse(C.byref(input_view), C.byref(proof_view),
            max_work, max_retained_terms, 1, 2, 1, self.dense_bytes, 1,
            C.byref(stats), C.byref(live), C.byref(dense), C.byref(reuse))
        result = dict(verified=code == 0,
            status=('verified', 'rejected', 'inconclusive', 'checker-failure')[code],
            method='independent-native-derivation-DAG+Boolean-Buchberger',
            stats=abi.fields(stats), liveness=abi.fields(live), dense=abi.fields(dense),
            reuse=abi.fields(reuse), root_count=None, solutions=None,
            schedule=self.checker_order, retention_policy=self.retention)
        if code:
            result['reason'] = self.reuse.checker_error().decode()
        else:
            result.update(ideal_equality=True, reduced_groebner_basis=True)
        return result

    def compute(self, *args, **kwargs):
        result = super().compute(*args, **kwargs)
        result['buffer_reuse_policy'] = self.reuse_arm
        return result
