"""Synchronous leased queries with independently checked native continuation.

The opt-in wrapper keeps the round108 CPU kernels and round110 continuation
unchanged. All proof handles remain local to one call; only owned bytes escape.
"""
import ctypes as C
import hashlib
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'round110'))
from native import Native, SeededStats, abi
from query import Query as BaseQuery
from input_plan import BorrowedInput
from capture import capture


class Query(BaseQuery):
    def __init__(self, *, sanitizer=False, **kwargs):
        super().__init__(sanitizer=sanitizer, arm='matrix-block4', **kwargs)
        self.native = Native(sanitizer)
        path = Path(self.native.lib._name)
        self.binary_sha256[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    def compute(self, original, *, layout=None, fresh_shape=None, fallback=True,
                max_work=2_000_000, matrix_cap=1_000_000,
                max_check_work=20_000_000, max_terms=2_000_000,
                max_nodes=1_000_000, max_rows=10000, batch=64,
                export_proof=False):
        start = time.perf_counter_ns()
        if not isinstance(original, BorrowedInput):
            raise ValueError('complete-query transport requires a live input lease')
        original.validate(view_type=abi.PackedInput)
        for value in (max_work, matrix_cap, max_check_work, max_terms):
            abi.integer(value, 0, 1 << 64)
        abi.integer(max_nodes, 1, 10_000_001)
        abi.integer(max_rows, 1, 1_000_001)
        abi.integer(batch, 1, max_rows+1)
        if fresh_shape is not None and layout is not None:
            raise ValueError('choose one layout policy')
        if layout is not None and layout.query is not self:
            raise ValueError('layout belongs to another query')

        phases = dict(matrix_ns=0, seeded_production_ns=0, fresh_f4_ns=0,
                      checker_ns=0, basis_ns=0, proof_copy_ns=0, teardown_ns=0)
        attempts = []
        remaining, check_remaining = max_work, max_check_work
        answer = dict(status='inconclusive', verified=False, complete=False)

        def timed(phase, fn, *args):
            before = time.perf_counter_ns()
            try:
                return fn(*args)
            finally:
                phases[phase] += time.perf_counter_ns()-before

        def checked(view, attempt):
            nonlocal check_remaining, answer
            cert = timed('checker_ns', self._check, original.view, view,
                         check_remaining, max_terms)
            spent = cert['stats']['work']
            if not 0 <= spent <= check_remaining:
                raise RuntimeError('checker exceeded the shared work budget')
            check_remaining -= spent
            attempt.update(verified=cert['verified'], certificate=cert)
            if cert['verified']:
                # Do not call abi.export: materialize only the small basis and
                # copy the checked graph into pointer-free immutable bytes.
                basis = timed('basis_ns', lambda: [list(view.basis_terms[
                    view.offsets[i]:view.offsets[i+1]]) for i in range(view.rows)])
                answer = dict(status='gb', verified=True, complete=True,
                              basis=basis, certificate=cert)
                if export_proof:
                    answer['proof'] = timed('proof_copy_ns', capture, view, abi.Node)

        def charge(work):
            nonlocal remaining
            if not 0 <= work <= remaining:
                raise RuntimeError('producer exceeded the shared work budget')
            remaining -= work

        def continuation(seed):
            stats = SeededStats()
            handle = timed('seeded_production_ns', self.native.lib.seeded_produce,
                C.byref(original.view), C.byref(seed), remaining,
                max_nodes, max_rows, batch, 0, C.byref(stats))
            # The native total already includes bridge, scan, F4 and composition.
            attempt = dict(kind='seeded-f4', verified=False,
                stats={name: getattr(stats, name) for name in
                    ('work', 'bridge_work', 'scan_work', 'f4_started',
                     'composition_started', 'reserved_seed_nodes', 'status')},
                producer=abi.fields(stats.producer), composition=abi.fields(stats.composition))
            attempts.append(attempt)
            try:
                charge(stats.work)
                if handle:
                    checked(self.native.lib.seeded_view(handle).contents, attempt)
                else:
                    attempt['reason'] = self.native.lib.seeded_error().decode()
            finally:
                if handle:
                    timed('teardown_ns', self.native.lib.seeded_destroy, handle)

        temporary = None
        returned_seed = False
        try:
            if fresh_shape is not None:
                temporary = layout = self.layout(*fresh_shape)
            if layout is not None:
                with layout._lock:
                    if not layout._handle:
                        if layout.reason is None:
                            raise RuntimeError('layout is closed')
                        attempts.append(dict(kind='matrix-layout', verified=False,
                            stats=dict(work=0, status=layout.stats['status']),
                            reason=layout.reason, layout_stats=layout.stats))
                    else:
                        stats = self.lib.macaulay_apply.argtypes[-1]._type_()
                        handle = timed('matrix_ns', self.lib.macaulay_apply,
                            layout._handle, C.byref(original.view), min(remaining, matrix_cap),
                            max_nodes, max_rows, C.byref(stats))
                        returned_seed = bool(handle)
                        attempt = dict(kind='macaulay', verified=False, stats=abi.fields(stats),
                            layout_stats=layout.stats, parity=self._parity_local.stats,
                            block=self._block_local.stats)
                        attempts.append(attempt)
                        try:
                            charge(stats.work)
                            if handle:
                                seed = self.lib.macaulay_view(handle).contents
                                checked(seed, attempt)
                                if not answer['verified'] and fallback:
                                    continuation(seed)
                            else:
                                attempt['reason'] = self.lib.macaulay_error().decode()
                        finally:
                            if handle:
                                timed('teardown_ns', self.lib.macaulay_result_destroy, handle)
            if not answer['verified'] and not returned_seed and (layout is None or fallback):
                stats = abi.ProducerStats()
                handle = timed('fresh_f4_ns', self.base.producer.produce_packed,
                    C.byref(original.view), remaining, max_nodes, max_rows, batch, C.byref(stats))
                attempt = dict(kind='fresh-f4', verified=False, stats=abi.fields(stats))
                attempts.append(attempt)
                try:
                    charge(stats.work)
                    if handle:
                        checked(self.base.producer.producer_view(handle).contents, attempt)
                    else:
                        attempt['reason'] = self.base.producer.producer_error().decode()
                finally:
                    if handle:
                        timed('teardown_ns', self.base.producer.producer_destroy, handle)
        finally:
            if temporary is not None:
                timed('teardown_ns', temporary.close)

        if not answer['verified'] and attempts:
            last = attempts[-1]
            answer['status'] = {1: 'invalid-input', 2: 'inconclusive', 3: 'producer-failure'}.get(
                last['stats']['status'], last.get('certificate', {}).get('status', 'inconclusive'))
        elapsed = time.perf_counter_ns()-start
        phases['overhead_ns'] = elapsed-sum(phases.values())
        answer.update(attempts=attempts, work=max_work-remaining,
            check_work=max_check_work-check_remaining, wall_ns=elapsed,
            phases=phases, total_seconds=elapsed/1e9,
            timing_eligible=False, qualified_speedup=None,
            layout_policy='fresh' if fresh_shape is not None else ('reused' if layout is not None else 'none'),
            proof_transport_policy='owned-binary', continuation_policy='native-seeded')
        return answer
