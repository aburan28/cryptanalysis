"""Full packed query whose only target-dependent input is the public point."""
from dataclasses import dataclass
import sys
import threading
import time

from public_replay import HERE, Point, replay

_import_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent / 'round15'))
    from ordered_query import NativeDescent, query
    from descend import Instance
finally:
    # Older adapters prepend their own directories. Do not let those imports
    # redirect this round's benchmark/audit modules or the caller's imports.
    sys.path[:] = _import_path

_query_import_lock = threading.Lock()


@dataclass(frozen=True)
class PublicInstance:
    n: int
    mod: int
    b: int
    m: int
    l: int
    target: Point
    anf: object

    @property
    def nvars(self):
        return self.m * self.l

    # Keep the existing independent original-equation evaluation unchanged.
    evaluate = Instance.evaluate
    x_from_assignment = Instance.x_from_assignment


class PublicQuery:
    def __init__(self, n, mod, b, m, ell, arm='native-or-python', *, sanitizer=False):
        self._lock, self._closed = threading.Lock(), False
        self.shape = (n, mod, b, m, ell)
        self.replay = replay(n, mod, b, arm, sanitizer=sanitizer)
        self.descent = self.basis = None
        try:
            self.descent = NativeDescent(n, mod, b, m, ell)
            with _query_import_lock:
                previous = sys.path[:]
                try:
                    self.basis = query(m * ell, n, 'ordered')
                finally:
                    sys.path[:] = previous
        except Exception:
            self.close()
            raise

    def solve(self, target):
        with self._lock:
            if self._closed:
                raise RuntimeError('query is closed')
            start = time.perf_counter_ns()
            self.replay.validate_target(target)
            if target.inf:
                raise ValueError('the descended query requires a finite target')
            validated = time.perf_counter_ns()
            anf = self.descent.descend_packed(target.x)
            descended = time.perf_counter_ns()
            instance = PublicInstance(*self.shape, target, anf)
            answer = self.basis.compute(anf)
            answer.pop('basis_terms', None)
            certified = time.perf_counter_ns()
            checked, witness = 0, None
            if answer['status'] == 'gb':
                solutions = answer['basis_certificate']['solutions']
                if solutions is None:
                    raise RuntimeError('solver root bound violated')
                answer['status'] = 'gb-no-verified-solution'
                for assignment in solutions:
                    checked += 1
                    if instance.evaluate(assignment) != 0:
                        raise RuntimeError('certificate root fails original equation evaluation')
                    trial = self.replay.match(instance.x_from_assignment(assignment), target)
                    if trial['verified']:
                        # Preserve a second independent original-equation scan,
                        # as in the previous complete query's replay boundary.
                        if instance.evaluate(assignment) != 0:
                            raise RuntimeError('replayed assignment fails original equations')
                        witness = trial
                        answer.update(status='solved', verified=True, assignment=assignment)
                        break
            finished = time.perf_counter_ns()
            answer.update(assignments_checked=checked, curve_witness=witness,
                          replay_backend=self.replay.backend,
                          replay_binary_sha256=self.replay.binary_sha256,
                          descent_binary_sha256=self.descent.binary_sha256,
                          public_target=vars(target),
                          complete_query_ns=finished - start,
                          phases_ns={'target_validation': validated-start,
                                     'descent': descended-validated,
                                     'basis_and_certificate': certified-descended,
                                     'equation_and_curve_replay': finished-certified})
            return answer

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self.basis is not None:
                self.basis.close()
            if self.descent is not None:
                self.descent.close()
            self.replay.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
