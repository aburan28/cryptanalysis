"""Controlled packed replay/certification variants on the same public query."""
import time

from packed_checker import PackedChecker, PublicQuery, PublicInstance

ARMS = ('baseline', 'packed-replay', 'zeta-certificate', 'combined')


class TruthQuery(PublicQuery):
    def __init__(self, n, mod, b, m, ell, arm='combined', *, sanitizer=False):
        if arm not in ARMS: raise ValueError('unknown query arm')
        self.checker = None
        self.arm = arm
        super().__init__(n, mod, b, m, ell, arm='native-or-python', sanitizer=sanitizer)
        try:
            if arm != 'baseline':
                self.checker = PackedChecker(m*ell, n, sanitizer=sanitizer)
            if arm in ('zeta-certificate', 'combined'):
                self.basis._certify = self.checker.certify_views
                self.basis.verifier_path = self.checker.path
        except Exception:
            self.close()
            raise

    def solve(self, target):
        if self.arm in ('baseline', 'zeta-certificate'):
            answer = super().solve(target)
            answer.update(equation_backend='python-original-anf', equation_binary_sha256=None,
                          query_arm=self.arm)
            return answer
        with self._lock:
            if self._closed: raise RuntimeError('query is closed')
            start = time.perf_counter_ns()
            self.replay.validate_target(target)
            if target.inf: raise ValueError('the descended query requires a finite target')
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
                if solutions is None: raise RuntimeError('solver root bound violated')
                answer['status'] = 'gb-no-verified-solution'
                for assignment in solutions:
                    checked += 1
                    if self.checker.evaluate(anf, assignment):
                        raise RuntimeError('certificate root fails direct packed equation evaluation')
                    trial = self.replay.match(instance.x_from_assignment(assignment), target)
                    if trial['verified']:
                        if self.checker.evaluate(anf, assignment):
                            raise RuntimeError('replayed assignment fails direct packed equations')
                        witness = trial
                        answer.update(status='solved', verified=True, assignment=assignment)
                        break
            finished = time.perf_counter_ns()
            answer.update(assignments_checked=checked, curve_witness=witness,
                          replay_backend=self.replay.backend,
                          replay_binary_sha256=self.replay.binary_sha256,
                          equation_backend='independent-native-direct-packed',
                          equation_binary_sha256=self.checker.binary_sha256, query_arm=self.arm,
                          descent_binary_sha256=self.descent.binary_sha256,
                          public_target=vars(target), complete_query_ns=finished-start,
                          phases_ns={'target_validation': validated-start,
                                     'descent': descended-validated,
                                     'basis_and_certificate': certified-descended,
                                     'equation_and_curve_replay': finished-certified})
            return answer

    def close(self):
        # The parent's query lock protects both the complete call and destruction.
        super().close()
        if self.checker is not None: self.checker.close()
