"""One-query preparation scheduling; immutable packed snapshots and mandatory drain."""
from concurrent.futures import Future, ThreadPoolExecutor
import ctypes as ct
import threading
import time
from types import SimpleNamespace


def snapshot(checker, anf):
    masks, _, coefficients = checker.views(anf)
    return SimpleNamespace(nvars=anf.nvars, equations=anf.equations,
                           masks=type(masks).from_buffer_copy(masks),
                           coefficients=type(coefficients).from_buffer_copy(coefficients))


def prepare_task(checker, anf):
    start = time.perf_counter_ns()
    prepared = checker.prepare(anf)
    return prepared, start, time.perf_counter_ns()


class PreparedChecker:
    def __init__(self, checker, future):
        self.checker, self.future = checker, future
        self.prepared = None
        self.wait_ns = self.certify_enter_ns = 0
        self.task = None
        self.serial_fallback = False

    def __getattr__(self, name):
        return getattr(self.checker, name)

    def certify(self, anf, roots, basis, proof):
        self.certify_enter_ns = time.perf_counter_ns()
        self.task = self.future.result()
        self.wait_ns += time.perf_counter_ns()-self.certify_enter_ns
        self.prepared = self.task[0]
        if self.prepared.code:
            # An unsupported/budget-limited preparation keeps the original
            # checker path. Its executed work remains in the schedule receipt.
            self.serial_fallback = True
            return self.checker.certify(anf, roots, basis, proof)
        return self.checker.certify_prepared(self.prepared, anf, roots, basis, proof)

    def finish(self):
        started = time.perf_counter_ns()
        try:
            self.task = self.future.result()
            self.prepared = self.task[0]
            result = {'preparation_code': self.prepared.code,
                      'preparation': self.prepared.stats,
                      'prepare_start_ns': self.task[1], 'prepare_end_ns': self.task[2]}
        except BaseException as error:
            result = {'preparation_error': repr(error),
                      'preparation': getattr(error, 'preparation_stats', None)}
        finally:
            if self.prepared is not None:
                self.prepared.close()
        result.update(wait_ns=self.wait_ns, drain_ns=time.perf_counter_ns()-started,
                      certify_enter_ns=self.certify_enter_ns, drained=True,
                      serial_fallback=self.serial_fallback,
                      certification_reached=bool(self.certify_enter_ns))
        return result


def basis_class(base):
    class ScheduledBasis(base):
        def __init__(self, *args, **kwargs):
            self._schedule_lock = threading.Lock()
            self._preparation_executor = None
            self.preparation_mode = 'serial'
            super().__init__(*args, **kwargs)

        def configure_preparation(self, mode):
            if type(mode) is not str or mode not in ('serial', 'prepared', 'overlap'):
                raise ValueError('preparation mode must be serial, prepared, or overlap')
            with self._schedule_lock:
                if self._closed:
                    raise RuntimeError('basis workspace is closed')
                if mode == 'overlap' and self._preparation_executor is None:
                    self._preparation_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='gb-prepare53')
                    # Start the reusable worker during target-independent setup.
                    self._preparation_executor.submit(lambda: None).result()
                self.preparation_mode = mode

        def compute(self, anf):
            with self._schedule_lock:
                if self._closed:
                    raise RuntimeError('basis workspace is closed')
                mode = self.preparation_mode
                if mode == 'serial':
                    answer = super().compute(anf)
                    answer['preparation_schedule'] = {'mode': mode, 'worker_count': 1, 'drained': True,
                                                      'input_snapshot_bytes': 0}
                    return answer
                started = time.perf_counter_ns()
                checker = self.checker
                owned = snapshot(checker, anf)
                snapshot_ns = time.perf_counter_ns()-started
                if mode == 'overlap':
                    future = self._preparation_executor.submit(prepare_task, checker, owned)
                else:
                    future = Future()
                    try:
                        future.set_result(prepare_task(checker, owned))
                    except BaseException as error:
                        future.set_exception(error)
                proxy = PreparedChecker(checker, future)
                self.checker = proxy
                answer, failure = None, None
                producer_started = time.perf_counter_ns()
                try:
                    answer = super().compute(owned)
                except BaseException as error:
                    failure = error
                    raise
                finally:
                    producer_finished = time.perf_counter_ns()
                    try:
                        receipt = proxy.finish()
                    finally:
                        self.checker = checker
                    receipt.update(mode=mode, worker_count=2 if mode == 'overlap' else 1,
                                   input_snapshot_bytes=ct.sizeof(owned.masks)+ct.sizeof(owned.coefficients),
                                   snapshot_ns=snapshot_ns, schedule_wall_ns=time.perf_counter_ns()-started,
                                   producer_scope_start_ns=producer_started,
                                   producer_scope_end_ns=proxy.certify_enter_ns or producer_finished)
                    if failure is not None:
                        failure.preparation_schedule = receipt
                    elif answer is not None:
                        answer['preparation_schedule'] = receipt
                        answer['coefficient_copy'] = True
                return answer

        def close(self):
            with self._schedule_lock:
                if self._preparation_executor is not None:
                    self._preparation_executor.shutdown(wait=True)
                    self._preparation_executor = None
                super().close()

    return ScheduledBasis
