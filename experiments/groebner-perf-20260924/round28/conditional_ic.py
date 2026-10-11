"""Compare two- and three-summand PDP inside complete single-target recovery."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent/'round26'))
    import replay_query as reference
    from replay_query import Point, Ledger, ONLINE, PHASES, point, scalar_replay
    from replay_query import ToyCurve, FactorBase, IDENTITY, Curve, GF2n, sha256_hex, kernel
    from replay_query import arithmetic_policy, rho_policy
    sys.path.insert(0, str(HERE.parent/'round27'))
    from full_query import ConditionalQuery, BaselineQuery
finally:
    sys.path[:] = _path

ARMS = ('three-eval', 'two-eval', 'two-conditional')
SUMMANDS = {'three-eval': 3, 'two-eval': 2, 'two-conditional': 2}
CHECKERS = reference.CHECKERS


class PreparedIC(reference.PreparedIC):
    """Select the PDP workspace during charged reusable setup, before queries.

    Collection, exact-base projection, first-usable target extraction and scalar
    recovery remain the frozen implementation. Both IC and rho use the same
    independent Euclidean field arithmetic. No target is accepted by setup.
    """
    def __init__(self, n=13, ell=3, arm='three-eval', **kwargs):
        if arm not in ARMS:
            raise ValueError('unknown conditional IC arm')
        if kwargs.get('budget_test', False):
            raise ValueError('budget-test builds are not complete IC candidates')
        self.ic_arm = arm
        self.summands = SUMMANDS[arm]
        verifier = CHECKERS.get(ell,'sparse') if arm == 'three-eval' else 'sparse'
        super().__init__(n, ell, 'euclid', verifier=verifier, **kwargs)

    @property
    def backend(self):
        return self._backend

    @backend.setter
    def backend(self, parent):
        if parent is None:
            self._backend = None
            return
        try:
            if self.summands == 2:
                query_type = ConditionalQuery if self.ic_arm == 'two-conditional' else BaselineQuery
                replacement = query_type(self.curve.n, self.curve.mod, self.curve.b,
                                         2, self.ell, sanitizer=self.sanitizer)
                old = parent.query
                parent.query = replacement
                old.close()
                self._backend = reference.reference.first.TargetPDP(parent, self.target_policy)
            else:
                reference.PreparedIC.backend.fset(self, parent)
        except BaseException:
            parent.close()
            raise
