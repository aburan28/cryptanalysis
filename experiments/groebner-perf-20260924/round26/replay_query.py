"""Select independent field inversion per workspace, equally for IC and rho."""
import hashlib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent/'round25'))
    import sparse_ic as reference
    from sparse_ic import Point, Ledger, ONLINE, PHASES, point, scalar_replay
    from sparse_ic import ToyCurve, FactorBase, IDENTITY, Curve, GF2n, sha256_hex, kernel
finally:
    sys.path[:] = _path
from reference_field import EuclidField

ARMS = ('power', 'euclid')
RHO_ARMS = tuple('rho-'+arm for arm in ARMS)
# An explicit frozen benchmark choice, not an automatic runtime dispatcher.
CHECKERS = {3: 'packed', 6: 'sparse'}


def arithmetic_policy(arm):
    if arm not in ARMS:
        raise ValueError('unknown independent arithmetic arm')
    return {'field': 'polynomial basis GF(2^n); canonical integer coefficients',
        'inversion': 'binary polynomial extended Euclid' if arm == 'euclid' else 'exponentiation by 2^n-2',
        'multiplication_and_curve_law': 'unchanged independent Python reference',
        'scalar_replay': 'unchanged independent Python double-and-add',
        'scope': 'preparation, public-point validation and final scalar replay, equally for IC and rho',
        'target_answer_cache': 'none',
        'sources_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT/'experiments/pdp-scaling/gf2n.py', HERE/'reference_field.py', HERE/'replay_query.py')}}


def rho_policy(curve, target, arm):
    value = reference.rho_policy(curve, target)
    value['independent_arithmetic'] = arithmetic_policy(arm)
    return value


class PreparedIC(reference.PreparedIC):
    def __init__(self, n=13, ell=3, arm='power', *, verifier='packed', **kwargs):
        if arm not in ARMS:
            raise ValueError('unknown independent arithmetic arm')
        self.replay_arm = arm
        super().__init__(n, ell, verifier, **kwargs)

    @property
    def oracle(self):
        return self._oracle

    @oracle.setter
    def oracle(self, value):
        # The frozen constructor assigns this within its setup ledger, before
        # any preparation checks or numerical queries. Other workspaces and the
        # native producer's field arithmetic are never modified.
        if self.replay_arm == 'euclid':
            value = Curve(EuclidField(value.F.n, value.F.mod), value.b)
        self._oracle = value

    def recover(self, target, rerandomization_seed):
        answer = super().recover(target, rerandomization_seed)
        # Metadata assembly is outside the complete arithmetic/replay interval.
        answer['independent_arithmetic'] = arithmetic_policy(self.replay_arm)
        return answer

    def rho(self, target):
        answer = super().rho(target)
        answer['reference_policy'] = rho_policy(self.curve, target, self.replay_arm)
        return answer
