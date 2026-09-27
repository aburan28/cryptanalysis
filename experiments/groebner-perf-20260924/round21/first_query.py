"""First usable target relation after exact certification of the complete basis."""
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent/'round20'))
    import ic_query as reference
    from ic_query import Point, PublicInstance, point, Ledger, ONLINE, PHASES, scalar_replay
    from ic_query import ToyCurve, FactorBase, IDENTITY, Curve, GF2n, sha256_hex, kernel
finally:
    sys.path[:] = _path

ARMS = ('all-roots', 'first-usable')


class TargetPDP:
    """Own the existing workspace; leave the collection algorithm unchanged."""
    def __init__(self, parent, policy):
        self.parent, self.policy = parent, policy
        self.query, self.fb, self.mapping = parent.query, parent.fb, parent.mapping

    def close(self):
        self.parent.close()

    def decompose(self, R, ledger, *, target=False):
        if not target or self.policy == 'all-roots':
            answer = self.parent.decompose(R, ledger, target=target)
            if target:
                answer['target_root_policy'] = self.policy
            return answer
        before = dict(ledger.ns)
        answer = self._first(R, ledger)
        answer['phase_wall_ns'] = {p: ledger.ns[p]-before[p] for p in ONLINE[:3]}
        return answer

    def _first(self, R, ledger):
        q, Rpoint = self.query, point(R)
        with q._lock:
            if q._closed:
                raise RuntimeError('PDP is closed')
            with ledger.phase('target_query'):
                q.replay.validate_target(Rpoint)
                if Rpoint.inf:
                    raise ValueError('finite PDP target required')
            with ledger.phase('target_pdp'):
                anf = q.descent.descend_packed(Rpoint.x)
                basis = q.basis.compute(anf)
                instance = PublicInstance(*q.shape, Rpoint, anf)
            answer = {'target': list(R), 'basis': basis, 'relations': [],
                      'roots_checked': 0, 'lift_rejections': 0, 'membership_rejections': 0,
                      'target_root_policy': 'first-usable', 'root_checks': []}
            if basis['status'] != 'gb':
                answer['status'] = 'budget' if basis['status'] == 'inconclusive' else 'error'
                return answer
            cert = basis['basis_certificate']
            if not cert['verified'] or not basis['groebner_verified']:
                raise RuntimeError('uncertified basis cannot produce an IC relation')
            roots = cert['solutions']
            if roots is None:
                raise RuntimeError('producer root limit violated')
            with ledger.phase('target_relation_check'):
                for assignment in roots:
                    answer['roots_checked'] += 1
                    if q.checker.evaluate(anf, assignment):
                        raise RuntimeError('certified root fails direct original equations')
                    trial = q.replay.match(instance.x_from_assignment(assignment), Rpoint)
                    check = {'assignment': assignment, 'status': 'running', 'witness': trial}
                    answer['root_checks'].append(check)
                    if not trial['verified']:
                        answer['lift_rejections'] += 1
                        check['status'] = 'lift_rejected'
                        continue
                    points = [(p['x'], p['y']) for p in trial['points']]
                    if any(p not in self.mapping for p in points):
                        answer['membership_rejections'] += 1
                        check['status'] = 'membership_rejected'
                        continue
                    if q.checker.evaluate(anf, assignment):
                        raise RuntimeError('curve witness fails direct original equations')
                    row = {}
                    for p in points:
                        j, c = self.mapping[p]
                        if j >= 0:
                            row[j] = (row.get(j, 0)+c) % self.fb.curve.r
                    row = [[j, c] for j, c in sorted(row.items()) if c]
                    if not row:
                        raise RuntimeError('nonzero subgroup target has a zero projected relation')
                    check['status'] = 'accepted'
                    answer['relations'] = [{'assignment': assignment, 'row': row, 'witness': trial}]
                    break
            answer['status'] = ('verified_decomposition' if answer['relations'] else
                                'proved_unsat' if not roots else 'lift_rejected')
            return answer


class PreparedIC(reference.PreparedIC):
    def __init__(self, n=13, ell=3, arm='first-usable', **kwargs):
        start = time.perf_counter_ns()
        if arm not in ARMS:
            raise ValueError('unknown target root policy')
        self.target_policy = arm
        super().__init__(n, ell, 'packed', **kwargs)
        self.backend = TargetPDP(self.backend, arm)
        # The wrapper is reusable setup, included in both preparation ledgers.
        elapsed = time.perf_counter_ns()-start
        extra = elapsed-self.preparation['wall_ns']
        if extra < 0:
            raise RuntimeError('preparation exceeds complete constructor interval')
        self.preparation['phase_wall_ns']['precompute'] += extra
        self.preparation['bookkeeping_ns'] += extra
        self.preparation['wall_ns'] = elapsed
