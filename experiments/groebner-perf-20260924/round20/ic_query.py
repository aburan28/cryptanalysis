"""One public target through packed PDP relations and independent DLP replay.

The bounded toy experiment supports the exact prefix factor base and m=3.
No target or target scalar is supplied to reusable relation preparation.
"""
from collections import Counter
from contextlib import contextmanager
import hashlib
from pathlib import Path
import random
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent/'round18'))
    from truth_query import TruthQuery
    from packed_checker import PublicInstance, Curve, GF2n, Point, PackedANF
    sys.path.insert(0, str(ROOT/'experiments/ic-bench'))
    from bench import endomorphism_record, rho_one_target
    from toycurve import ToyCurve, sha256_hex
    from factor_base import FactorBase
    from monitor import RankTracker
    import kernel
finally:
    sys.path[:] = _path

ARMS = ('baseline', 'packed')
PHASES = ('setup', 'isogeny', 'factor_base', 'precompute', 'queries', 'pdp',
          'relation_check', 'matrix_build', 'relation_la', 'target_descent', 'recovery_check')
ONLINE = ('target_query', 'target_pdp', 'target_relation_check',
          'target_descent', 'target_recovery_check')
IDENTITY = Point(0, 0, True)


def point(pair):
    return IDENTITY if pair[0] == kernel.INF_X else Point(*pair)


def scalar_replay(curve, P, scalar):
    """Independent Python double-and-add; no native curve/DLP implementation."""
    if type(scalar) is not int or scalar < 0:
        raise ValueError('nonnegative integer scalar required')
    result = IDENTITY
    while scalar:
        if scalar & 1:
            result = curve.add(result, P)
        P = curve.add(P, P)
        scalar >>= 1
    return result


class Ledger:
    def __init__(self, names):
        self.ns = dict.fromkeys(names, 0)
        self.active = None

    @contextmanager
    def phase(self, name):
        if self.active is not None or name not in self.ns:
            raise RuntimeError('phase accounting must be exclusive')
        self.active = name
        start = time.perf_counter_ns()
        try:
            yield
        finally:
            self.ns[name] += time.perf_counter_ns() - start
            self.active = None

    def finish(self, start, overhead_phase):
        elapsed = time.perf_counter_ns() - start
        overhead = elapsed - sum(self.ns.values())
        if overhead < 0:
            raise RuntimeError('exclusive phases exceed measured interval')
        self.ns[overhead_phase] += overhead
        return elapsed, overhead


class PDP:
    def __init__(self, fb, arm, *, sanitizer=False):
        if arm not in ARMS:
            raise ValueError('unknown PDP arm')
        if fb.basis != [1 << i for i in range(fb.l)] or fb.curve.a2 != 0:
            raise ValueError('packed descent requires the exact prefix basis and a2=0')
        self.fb, self.arm = fb, arm
        C = fb.curve
        self.query = TruthQuery(C.n, C.mod, C.b, 3, fb.l,
                                'combined' if arm == 'packed' else 'baseline', sanitizer=sanitizer)
        # This lookup contains the complete geometric base, including torsion
        # points whose cofactor projection is zero and contributes no column.
        self.index = fb.point_index()
        self.mapping = {p: (int(fb.col_of[i]), int(fb.col_coeff[i]))
                        for p, i in self.index.items()}

    def decompose(self, R, ledger, *, target=False):
        before = dict(ledger.ns)
        result = self._decompose(R, ledger, target=target)
        names = ('target_query', 'target_pdp', 'target_relation_check') if target else (
            'queries', 'pdp', 'relation_check')
        result['phase_wall_ns'] = {name: ledger.ns[name]-before[name] for name in names}
        return result

    def _decompose(self, R, ledger, *, target=False):
        names = ('target_query', 'target_pdp', 'target_relation_check') if target else (
            'queries', 'pdp', 'relation_check')
        q, fb = self.query, self.fb
        Rpoint = point(R)
        with q._lock:
            if q._closed:
                raise RuntimeError('PDP is closed')
            with ledger.phase(names[0]):
                q.replay.validate_target(Rpoint)
                if Rpoint.inf:
                    raise ValueError('finite PDP target required')
            with ledger.phase(names[1]):
                anf = q.descent.descend_packed(Rpoint.x)
                answer = q.basis.compute(anf)
                instance = PublicInstance(*q.shape, Rpoint, anf)
            result = {'target': list(R), 'basis': answer, 'relations': [],
                      'roots_checked': 0, 'lift_rejections': 0, 'membership_rejections': 0}
            if answer['status'] != 'gb':
                result['status'] = 'budget' if answer['status'] == 'inconclusive' else 'error'
                return result
            cert = answer['basis_certificate']
            if not cert['verified'] or not answer['groebner_verified']:
                raise RuntimeError('uncertified basis cannot produce an IC relation')
            roots = cert['solutions']
            if roots is None:
                raise RuntimeError('producer root limit violated')
            rows = {}
            with ledger.phase(names[2]):
                for assignment in roots:
                    result['roots_checked'] += 1
                    evaluate = (lambda: q.checker.evaluate(anf, assignment)) if self.arm == 'packed' else (
                        lambda: instance.evaluate(assignment))
                    if evaluate():
                        raise RuntimeError('certified root fails direct original equations')
                    trial = q.replay.match(instance.x_from_assignment(assignment), Rpoint)
                    if not trial['verified']:
                        result['lift_rejections'] += 1
                        continue
                    points = [(p['x'], p['y']) for p in trial['points']]
                    if any(p not in self.mapping for p in points):
                        result['membership_rejections'] += 1
                        continue
                    if evaluate():
                        raise RuntimeError('curve witness fails direct original equations')
                    row = {}
                    for p in points:
                        column, coefficient = self.mapping[p]
                        if column >= 0:
                            row[column] = (row.get(column, 0) + coefficient) % fb.curve.r
                    key = tuple(sorted((j, c) for j, c in row.items() if c))
                    if not key:
                        raise RuntimeError('nonzero subgroup target has a zero projected relation')
                    rows.setdefault(key, {'assignment': assignment, 'row': [list(p) for p in key],
                                          'witness': trial})
                result['relations'] = [rows[key] for key in sorted(rows)]
            result['status'] = ('verified_decomposition' if rows else
                                'proved_unsat' if not roots else 'lift_rejected')
            return result

    def close(self):
        self.query.close()


class PreparedIC:
    """A reusable mathematical setup, consumed by exactly one public-target solve."""
    def __init__(self, n=13, ell=3, arm='packed', *, collection_seed='round20-collection-v1',
                 max_collection=10000, max_target=10000, sanitizer=False):
        start = time.perf_counter_ns()
        if type(n) is not int or n not in (11, 13, 17, 19):
            raise ValueError('bounded toy curve degrees: 11, 13, 17, 19')
        if type(ell) is not int or not 1 <= ell <= 6:
            raise ValueError('prefix dimension: 1..6')
        if any(type(v) is not int or not 1 <= v <= 100000 for v in (max_collection, max_target)):
            raise ValueError('attempt limits: 1..100000')
        self._lock, self._closed, self._consumed = threading.Lock(), False, False
        self.backend = None
        self.arm, self.ell = arm, ell
        self.sanitizer = sanitizer
        self.collection_seed, self.max_collection, self.max_target = collection_seed, max_collection, max_target
        self.preparation = {'status': 'preparing', 'attempts': [], 'column_logs': None}
        ledger = Ledger(PHASES)
        try:
            with ledger.phase('setup'):
                self.curve = C = ToyCurve(n)
                self.oracle = Curve(GF2n(n, C.mod), C.b)
                self.G = point(C.G)
                if not self.oracle.on_curve(self.G) or scalar_replay(self.oracle, self.G, C.r) != IDENTITY:
                    raise RuntimeError('independent subgroup generator check failed')
            with ledger.phase('factor_base'):
                self.fb = fb = FactorBase(C, 'prefix', ell, 0)
                self.base_points = []
                for p, i in fb.point_index().items():
                    projected = point((int(fb.px[i]), int(fb.py[i])))
                    j, coefficient = int(fb.col_of[i]), int(fb.col_coeff[i])
                    if not self.oracle.on_curve(point(p)) or scalar_replay(self.oracle, point(p), C.proj_scalar) != projected:
                        raise RuntimeError('independent factor-base projection check failed')
                    if j >= 0:
                        rep = point(fb.column_reps[j])
                        if scalar_replay(self.oracle, rep, coefficient % C.r) != projected:
                            raise RuntimeError('independent factor-base column check failed')
                    elif projected != IDENTITY:
                        raise RuntimeError('omitted nonzero factor-base projection')
                    self.base_points.append({'point': list(p), 'projected': vars(projected),
                                             'column': j, 'coefficient': coefficient})
                if not fb.effective_columns:
                    raise ValueError('factor base has no usable columns')
            with ledger.phase('precompute'):
                self.backend = PDP(fb, arm, sanitizer=sanitizer)
                tracker = RankTracker(fb.effective_columns, C.r)
                rng = random.Random(collection_seed)
                preparation_error = False
            while tracker.rank < fb.effective_columns and len(self.preparation['attempts']) < max_collection:
                with ledger.phase('queries'):
                    k, R = C.random_subgroup_point(rng)
                try:
                    attempt = self.backend.decompose(R, ledger)
                except Exception as error:
                    attempt = {'target': list(R), 'status': 'error', 'relations': [], 'detail': repr(error)}
                    preparation_error = True
                preparation_error |= attempt['status'] == 'error'
                with ledger.phase('matrix_build'):
                    novel = sum(tracker.add(dict(rel['row']), k) for rel in attempt['relations'])
                    attempt.update(k=k, novel_rows=novel, rank=tracker.rank)
                    self.preparation['attempts'].append(attempt)
                if preparation_error:
                    break
            with ledger.phase('relation_la'):
                self.logs = tracker.solve()
                self.preparation.update(final_rank=tracker.rank, effective_columns=fb.effective_columns)
            if tracker.rank == fb.effective_columns:
                with ledger.phase('recovery_check'):
                    checked = [scalar_replay(self.oracle, self.G, self.logs[j]) == point(rep)
                               for j, rep in enumerate(fb.column_reps)]
                    if not all(checked):
                        raise RuntimeError('independent factor-base log replay failed')
                    self.preparation.update(status='ready', column_logs=[self.logs[j] for j in range(len(checked))],
                                            column_replay=checked)
            else:
                self.preparation['status'] = 'error' if preparation_error else 'insufficient_relations'
            with ledger.phase('precompute'):
                seen = {point(a['target']) for a in self.preparation['attempts']}
                seen.add(self.G)
                seen.update(point(rep) for rep in fb.column_reps)
                seen.update(Point(**entry['projected']) for entry in self.base_points)
                self.seen_points = frozenset(seen | {self.oracle.neg(p) for p in seen})
        except Exception:
            if self.backend is not None:
                self.backend.close()
            self._closed = True
            raise
        wall, overhead = ledger.finish(start, 'precompute')
        self.preparation.update(wall_ns=wall, phase_wall_ns=ledger.ns,
                                bookkeeping_ns=overhead, factor_base_projection_verified=True,
                                status_counts=dict(Counter(a['status'] for a in self.preparation['attempts'])))

    def validate_public(self, Q):
        if not isinstance(Q, Point) or Q.inf or type(Q.inf) is not bool:
            raise ValueError('finite public Point required')
        if any(type(x) is not int or not 0 <= x < 1 << self.curve.n for x in (Q.x, Q.y)):
            raise ValueError('public point outside field')
        if not self.oracle.on_curve(Q) or scalar_replay(self.oracle, Q, self.curve.r) != IDENTITY:
            raise ValueError('public point outside target subgroup')
        if Q in self.seen_points:
            raise ValueError('public target was already seen during reusable preparation')

    def recover(self, Q, rerandomization_seed):
        if not isinstance(Q, Point):
            raise ValueError('public Point required')
        with self._lock:
            if self._closed or self._consumed:
                raise RuntimeError('IC context is closed or its single target was already consumed')
            self._consumed = True
            if self.preparation['status'] != 'ready':
                return {'status': self.preparation['status'], 'verified': False, 'scalar': None,
                        'online_wall_ns': None, 'phase_wall_ns': None, 'attempts': []}
            ledger, start = Ledger(ONLINE), time.perf_counter_ns()
            answer = {'status': 'budget', 'verified': False, 'scalar': None, 'attempts': [], 'target': vars(Q)}
            try:
                with ledger.phase('target_query'):
                    self.validate_public(Q)
                    rng = random.Random(rerandomization_seed)
                for i in range(self.max_target):
                    attempt = {'index': i+1, 'status': 'running', 'relations': []}
                    answer['attempts'].append(attempt)
                    with ledger.phase('target_query'):
                        a = rng.randrange(1, self.curve.r)
                        R = self.curve.K.add((Q.x, Q.y), self.curve.K.smul(self.curve.G, a))
                        attempt.update(a=a, target=list(R))
                    if R[0] == kernel.INF_X:
                        # The sampled relation Q+[a]G=O itself determines log(Q).
                        with ledger.phase('target_descent'):
                            attempt['status'] = 'identity_relation'
                            scalar = (-a) % self.curve.r
                    else:
                        attempt.update(self.backend.decompose(R, ledger, target=True))
                        if attempt['status'] == 'error':
                            answer['status'] = 'error'
                            break
                        with ledger.phase('target_descent'):
                            attempt['a'] = a
                            scalar = None
                            if attempt['relations']:
                                row = attempt['relations'][0]['row']
                                scalar = (sum(c*self.logs[j] for j, c in row)-a) % self.curve.r
                    if scalar is not None:
                        with ledger.phase('target_recovery_check'):
                            replayed = scalar_replay(self.oracle, self.G, scalar)
                            answer.update(status='complete' if replayed == Q else 'error',
                                          verified=replayed == Q, scalar=scalar, replayed_point=vars(replayed))
                        break
            except Exception as error:
                answer.update(status='error', verified=False, detail=repr(error))
                if answer['attempts'] and answer['attempts'][-1]['status'] == 'running':
                    answer['attempts'][-1].update(status='error', detail=repr(error))
            wall, overhead = ledger.finish(start, 'target_descent')
            answer.update(online_wall_ns=wall, phase_wall_ns=ledger.ns, bookkeeping_ns=overhead)
            return answer

    def rho(self, Q):
        """Same-point reference with the same independent validation/replay charged."""
        if self._closed:
            raise RuntimeError('IC context is closed')
        start = time.perf_counter_ns()
        self.validate_public(Q)
        answer = rho_one_target(self.curve, (Q.x, Q.y), f'{self.curve.curve_id}|{Q.x}|{Q.y}')
        reference_ns = answer['online_wall_ns']
        if answer['verified']:
            replayed = scalar_replay(self.oracle, self.G, answer['scalar'])
            answer.update(verified=replayed == Q, replayed_point=vars(replayed))
            if not answer['verified']:
                answer['status'] = 'error'
        answer.update(online_wall_ns=time.perf_counter_ns()-start, native_reference_wall_ns=reference_ns,
                      target=vars(Q), independent_replay='Python polynomial-field double-and-add')
        return answer

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                if self.backend is not None:
                    self.backend.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
