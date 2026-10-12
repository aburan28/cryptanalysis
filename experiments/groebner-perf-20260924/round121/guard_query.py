"""Reject an incomplete matrix seed by an exact Boolean field-pair witness."""
import ctypes as C
import hashlib
from pathlib import Path
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'round119'))
from bitset_query import Query as PreviousQuery, abi


class FieldObstruction(C.Structure):
    _fields_ = [(name, abi.U64) for name in
                ('work', 'field_pairs', 'reduction_steps', 'witness_row',
                 'witness_term')] + [('witness_bit', abi.U32), ('status', abi.U32)]


class Query(PreviousQuery):
    def __init__(self, *, sanitizer=False, **kwargs):
        super().__init__(sanitizer=sanitizer, **kwargs)
        suffix = ('-ubsan' if sanitizer else '') + ('.dylib' if sys.platform == 'darwin' else '.so')
        path = HERE / 'build' / ('field_obstruction' + suffix)
        self.guard = C.CDLL(str(path))
        self.guard.find_field_obstruction.argtypes = [C.POINTER(abi.PackedInput),
            C.POINTER(abi.ProofView), abi.U64, C.POINTER(FieldObstruction)]
        self.guard.find_field_obstruction.restype = C.c_int
        self.binary_sha256[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self._guard_local = threading.local()

    def _check(self, input_view, proof_view, max_work, max_retained_terms):
        if not getattr(self._guard_local, 'first_check', False):
            return super()._check(input_view, proof_view, max_work, max_retained_terms)
        self._guard_local.first_check = False
        stats = FieldObstruction()
        before = time.perf_counter_ns()
        code = self.guard.find_field_obstruction(C.byref(input_view), C.byref(proof_view),
                                                 min(max_work, 200000), C.byref(stats))
        elapsed = time.perf_counter_ns() - before
        record = dict(code=code, elapsed_ns=elapsed, **abi.fields(stats))
        self._guard_local.records.append(record)
        if code == 1:
            check = abi.CheckStats()
            check.work = stats.work
            check.field_pairs = stats.field_pairs
            check.reduction_steps = stats.reduction_steps
            check.completion_seconds = elapsed / 1e9
            check.total_seconds = elapsed / 1e9
            return dict(verified=False, status='rejected',
                        method='independent-native-Boolean-field-pair-obstruction',
                        reason='implicit Boolean field pair has nonzero normal form',
                        stats=abi.fields(check), field_obstruction=record,
                        root_count=None, solutions=None, schedule=self.checker_order,
                        retention_policy=self.retention)
        if code != 0 or stats.work > max_work:
            raise RuntimeError('field-pair obstruction probe returned invalid accounting')
        result = super()._check(input_view, proof_view, max_work - stats.work,
                                max_retained_terms)
        result['stats']['work'] += stats.work
        result['field_obstruction_probe'] = record
        return result

    def compute(self, *args, **kwargs):
        self._guard_local.first_check = True
        self._guard_local.records = []
        result = super().compute(*args, **kwargs)
        result['field_obstruction_probes'] = list(self._guard_local.records)
        return result
