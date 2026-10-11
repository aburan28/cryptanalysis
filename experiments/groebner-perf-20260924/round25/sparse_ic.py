"""Install an independent checker per workspace before collection or recovery."""
import hashlib
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent/'round21'))
    import first_query as first
    from first_query import Point, Ledger, ONLINE, PHASES, point, scalar_replay, reference
    from first_query import ToyCurve, FactorBase, IDENTITY, Curve, GF2n, sha256_hex, kernel
    sys.path.insert(0, str(HERE.parent/'round23'))
    from sparse_checker import SparseChecker
finally:
    sys.path[:] = _path

ARMS = ('packed', 'sparse')


def rho_policy(curve, target):
    """Describe the unchanged same-point walk and both charged scalar checks."""
    walk = ROOT/'experiments/ic-bench/bench.py'
    wrapper = HERE.parent/'round20/ic_query.py'
    return {'algorithm': 'three-set Pollard rho', 'worker_count': 1,
        'walk_partition': 'x mod 3: add G, double, add Q',
        'collision_policy': 'Floyd: one slow advance, two fast advances per iteration',
        'distinguished_point_policy': 'none', 'distinguished_point_memory_bytes': 0,
        'cross_target_state': 'none', 'max_restarts': 32,
        'iterations_per_restart': 20*math.isqrt(curve.r)+100,
        'walk_advances_per_iteration': 3,
        'rng_seed': f'icbench-rho|{curve.curve_id}|{target.x}|{target.y}',
        'online_interval': 'before public-point validation through native and independent Python scalar replay',
        'fixture_and_reusable_setup': 'excluded',
        'implementation_sha256': {'walk': hashlib.sha256(walk.read_bytes()).hexdigest(),
                                  'validation_and_replay': hashlib.sha256(wrapper.read_bytes()).hexdigest()}}


class PreparedIC(reference.PreparedIC):
    """Keep the frozen constructor and methods; intercept its backend install.

    The base constructor assigns ``backend`` inside its precompute ledger,
    before it starts collection. This per-instance property installs the
    selected checker at that boundary. No module globals or shared factory
    are replaced. Both arms use the same unchanged first-usable target policy.
    """
    def __init__(self, n=13, ell=3, arm='packed', *, budget_test=False, **kwargs):
        if arm not in ARMS:
            raise ValueError('unknown complete IC verifier arm')
        if type(budget_test) is not bool or (budget_test and arm != 'sparse'):
            raise ValueError('test budget requires the explicit sparse arm')
        self.verifier_arm, self.budget_test = arm, budget_test
        self.target_policy = 'first-usable'
        super().__init__(n, ell, 'packed', **kwargs)

    @property
    def backend(self):
        return self._backend

    @backend.setter
    def backend(self, parent):
        if parent is None:
            self._backend = None
            return
        # The new PDP workspace has not escaped or run a numerical query yet.
        # Failed installation closes its native resources before propagating.
        try:
            if self.verifier_arm == 'sparse':
                query = parent.query
                checker = SparseChecker(3*self.ell, self.curve.n, mode=2,
                    sanitizer=self.sanitizer, budget_test=self.budget_test)
                query.checker.close()
                query.checker = checker
                query.basis._certify = checker.certify_views
                query.basis.verifier_path = checker.path
            self._backend = first.TargetPDP(parent, self.target_policy)
        except BaseException:
            parent.close()
            raise

    def rho(self, target):
        answer = super().rho(target)
        # Receipt construction is outside the arithmetic/replay interval.
        answer['reference_policy'] = rho_policy(self.curve, target)
        return answer
