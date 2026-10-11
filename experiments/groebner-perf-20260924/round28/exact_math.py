"""Offline exact-basis, relation, rank and public-scalar audit of one-target runs.

Only this offline auditor caches repeated proofs. Measured target contexts never
reuse target answers. Audit time is outside the reported online intervals.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import statistics
import sys
from types import SimpleNamespace

from conditional_ic import ARMS, ROOT, PHASES, ONLINE, IDENTITY, Curve, GF2n, Point
from conditional_ic import ToyCurve, FactorBase, point, scalar_replay, sha256_hex

_path = sys.path[:]
try:
    sys.path.insert(0, str(ROOT/'experiments/pdp-degree-heuristics'))
    from descent import Pieces
    sys.path.insert(0, str(ROOT/'experiments/pdp-scaling'))
    from boolean_basis import certify_boolean_basis
finally:
    sys.path[:] = _path

PREFIX = 'experiments/groebner-perf-20260924/'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def phases(values, names, total=None):
    require(set(values) == set(names), 'phase names')
    require(all(type(v) is int and v >= 0 for v in values.values()), 'phase values')
    if total is not None:
        require(sum(values.values()) == total, 'exclusive phase total')


def interval(ratios):
    logs = [math.log(v) for v in ratios]
    rng = random.Random(2026092708)
    samples = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs)))) for _ in range(2000))
    return {'paired_geomean': math.exp(statistics.mean(logs)),
            'bootstrap95': [samples[49], samples[1949]], 'pairs': len(logs)}


class Mathematics:
    def __init__(self, ell, summands):
        require(summands in (2,3), "summands")
        self.ell, self.summands = ell, summands
        self.C = C = ToyCurve(13)
        self.fb = FactorBase(C, 'prefix', ell, 0)
        self.curve = Curve(GF2n(C.n, C.mod), C.b)
        self.G = point(C.G)
        self.pieces = Pieces(self.fb, summands)
        self.proofs, self.witnesses = {}, {}
        self.mapping, self.base_points = {}, []
        for P, i in self.fb.point_index().items():
            j, coefficient = int(self.fb.col_of[i]), int(self.fb.col_coeff[i])
            projected = point((int(self.fb.px[i]), int(self.fb.py[i])))
            require(self.curve.on_curve(point(P)), 'factor-base point')
            require(scalar_replay(self.curve, point(P), C.proj_scalar) == projected, 'projection')
            require((scalar_replay(self.curve, point(self.fb.column_reps[j]), coefficient % C.r)
                     if j >= 0 else IDENTITY) == projected, 'projected column')
            self.mapping[P] = (j, coefficient)
            self.base_points.append({'point': list(P), 'projected': vars(projected),
                                     'column': j, 'coefficient': coefficient})

    def relation(self, R, relation, roots):
        require(relation['assignment'] in roots, 'relation assignment is not a certified root')
        key = sha256_hex([vars(R), relation])
        if key in self.witnesses:
            return
        witness = relation['witness']
        require(witness['verified'] and witness['code'] == 0, 'witness status')
        points = [Point(**p) for p in witness['points']]
        xs = [(relation['assignment'] >> (i*self.ell)) & ((1 << self.ell)-1) for i in range(self.summands)]
        require([p.x for p in points] == xs, 'assignment x coordinates')
        require(all(not p.inf and self.curve.on_curve(p) for p in points), 'witness curve membership')
        require(self.curve.sum(points) == R, 'full signed point sum')
        projected = {}
        for p in points:
            require((p.x, p.y) in self.mapping, 'geometric base membership')
            j, c = self.mapping[p.x, p.y]
            if j >= 0:
                projected[j] = (projected.get(j, 0)+c) % self.C.r
        expected = [[j, c] for j, c in sorted(projected.items()) if c]
        require(expected and relation['row'] == expected, 'projected relation row')
        self.witnesses[key] = True

    def attempt(self, record):
        require(record['status'] in ('verified_decomposition', 'proved_unsat', 'lift_rejected', 'budget', 'error'), 'PDP status')
        answer = record.get('basis')
        if answer is None:
            require(record['status'] == 'error' and not record['relations'] and record.get('detail'), 'unexplained missing basis')
            return
        if answer['status'] != 'gb':
            require(not record['relations'] and record['roots_checked'] == 0, 'failed producer returned relations')
            require(record['status'] == ('budget' if answer['status'] == 'inconclusive' else 'error'), 'producer failure status')
            return
        basis = answer['basis_terms']
        digest = hashlib.sha256(json.dumps([sorted(g) for g in basis], sort_keys=True).encode()).hexdigest()
        require(answer['basis_sha256'] == digest, 'basis digest')
        R = point(record['target'])
        key = R.x, digest
        if key not in self.proofs:
            system = self.pieces.system(R.x)
            equations = [row.tolist() for row in system.equations]
            self.proofs[key] = certify_boolean_basis(self.summands*self.ell, equations, basis, monomial_cache=self.ell <= 4)
        proof, cert = self.proofs[key], answer['basis_certificate']
        require(proof['verified'], 'independent reconstructed-equation basis proof')
        require(answer['groebner_verified'] and cert['verified'], 'online basis verification')
        for field in ('root_count', 'standard_monomials', 'solutions', 'ideal_equality', 'reduced_groebner_basis'):
            require(cert[field] == proof[field], 'certificate '+field)
        if record.get('target_root_policy') == 'first-usable':
            self.prefix(record, proof, R)
        else:
            require(record['roots_checked'] == proof['root_count'], 'all roots examined')
        require(0 <= record['lift_rejections']+record['membership_rejections'] <= proof['root_count'], 'root rejections')
        rows = [rel['row'] for rel in record['relations']]
        require(rows == sorted(rows) and len({sha256_hex(r) for r in rows}) == len(rows), 'relation ordering/deduplication')
        for relation in record['relations']:
            self.relation(R, relation, proof['solutions'])
        expected = 'verified_decomposition' if rows else 'proved_unsat' if not proof['solutions'] else 'lift_rejected'
        require(record['status'] == expected, 'PDP outcome does not match proof')

    def prefix(self, record, proof, R):
        checks, roots = record['root_checks'], proof['solutions']
        require(len(checks) == record['roots_checked'], 'root trace length')
        require([c['assignment'] for c in checks] == roots[:len(checks)], 'ascending root prefix')
        accepted = [c for c in checks if c['status'] == 'accepted']
        if record['relations']:
            require(len(record['relations']) == len(accepted) == 1 and checks[-1] == accepted[0], 'first accepted root must stop search')
            rel = record['relations'][0]
            require(rel['assignment'] == accepted[0]['assignment'] and rel['witness'] == accepted[0]['witness'], 'selected root witness')
        else:
            require(not accepted and len(checks) == len(roots), 'unsuccessful search must exhaust roots')
        for key,status in (('lift_rejections','lift_rejected'),('membership_rejections','membership_rejected')):
            require(record[key] == sum(c['status'] == status for c in checks), 'root rejection accounting')
        for check in checks:
            require(check['status'] in ('accepted','lift_rejected','membership_rejected'), 'root check status')
            if check['status'] == 'accepted': continue
            xs = [(check['assignment'] >> (i*self.ell)) & ((1 << self.ell)-1) for i in range(self.summands)]
            if check['status'] == 'membership_rejected':
                pts = [Point(**p) for p in check['witness']['points']]
                require(check['witness']['verified'] and [p.x for p in pts] == xs and
                        all(self.curve.on_curve(p) for p in pts) and self.curve.sum(pts) == R, 'rejected signed witness')
                require(any((p.x,p.y) not in self.mapping for p in pts), 'false membership rejection')
            else:
                require(not check['witness']['verified'], 'false lift status')
                lifts = [self.curve.lift_x(x) for x in xs]
                if all(p is not None for p in lifts):
                    options = [(p,self.curve.neg(p)) for p in lifts]
                    require(not any(self.curve.sum(list(pts)) == R for pts in itertools.product(*options)), 'usable earlier root was skipped')

    def preparation(self, prep, workload):
        phases(prep['phase_wall_ns'], PHASES, prep['wall_ns'])
        require(0 <= prep['bookkeeping_ns'] <= prep['phase_wall_ns']['precompute'], 'preparation bookkeeping')
        require(prep['factor_base_projection_verified'], 'projection flag')
        rng, pivots = random.Random(workload['collection_seed']), {}
        seen = {self.G, *(point(p) for p in self.fb.column_reps),
                *(Point(**p['projected']) for p in self.base_points)}
        require(len(prep['attempts']) <= workload['resource_limits']['max_collection'], 'collection budget')
        for attempt in prep['attempts']:
            require(len(pivots) < self.fb.effective_columns, 'collection continued after full rank')
            k = rng.randrange(1, self.C.r)
            R = scalar_replay(self.curve, self.G, k)
            require(attempt['k'] == k and point(attempt['target']) == R, 'ordinary query stream')
            seen.add(R)
            self.attempt(attempt)
            if 'phase_wall_ns' in attempt:
                phases(attempt['phase_wall_ns'], ('queries','pdp','relation_check'))
            old_rank = len(pivots)
            for rel in attempt['relations']:
                # A separate dense modular row reduction, not RankTracker.
                vector = [0]*self.fb.effective_columns
                for j, c in rel['row']: vector[j] = c
                for j in range(len(vector)):
                    if not vector[j]: continue
                    if j not in pivots:
                        inv = pow(vector[j], -1, self.C.r)
                        pivots[j] = [(v*inv) % self.C.r for v in vector]
                        break
                    factor = vector[j]
                    vector = [(x-factor*y) % self.C.r for x, y in zip(vector, pivots[j])]
            require(attempt['novel_rows'] == len(pivots)-old_rank and attempt['rank'] == len(pivots), 'independent matrix rank')
        require(prep['final_rank'] == len(pivots) and prep['effective_columns'] == self.fb.effective_columns, 'final rank')
        require(prep['status_counts'] == dict(Counter(a['status'] for a in prep['attempts'])), 'preparation status counts')
        if prep['status'] == 'ready':
            require(len(pivots) == self.fb.effective_columns, 'incomplete reusable preparation')
            require(len(prep['column_logs']) == len(pivots) and all(prep['column_replay']), 'column replay flags')
            for k, P in zip(prep['column_logs'], self.fb.column_reps):
                require(type(k) is int and 0 <= k < self.C.r, 'column scalar range')
                require(scalar_replay(self.curve, self.G, k) == point(P), 'independent column log')
            for a in prep['attempts']:
                for rel in a['relations']:
                    require(sum(c*prep['column_logs'][j] for j, c in rel['row']) % self.C.r == a['k'], 'relation RHS')
        else:
            require(prep['status'] in ('error', 'insufficient_relations') and len(pivots) < self.fb.effective_columns, 'preparation failure')
        seen |= {self.curve.neg(p) for p in seen}
        if prep['status'] == 'ready':
            require(sha256_hex(sorted((p.x,p.y,p.inf) for p in seen)) == workload['excluded_points_by_arm'][self.arm], 'unseen exclusion digest')
        require(Point(**workload['target']) not in seen, 'previously seen public target')
        for phase in ('queries','pdp','relation_check'):
            require(sum(a.get('phase_wall_ns', {}).get(phase, 0) for a in prep['attempts']) <= prep['phase_wall_ns'][phase], 'collection attempt time omitted')
        return seen

    def target(self, result, prep, workload):
        if prep['status'] != 'ready':
            require(not result['verified'] and result['online_wall_ns'] is None and not result['attempts'], 'unready target result')
            return
        phases(result['phase_wall_ns'], ONLINE, result['online_wall_ns'])
        require(0 <= result['bookkeeping_ns'] <= result['phase_wall_ns']['target_descent'], 'online bookkeeping')
        require(result['target'] == workload['target'], 'public target identity')
        Q, rng = Point(**workload['target']), random.Random(workload['rerandomization_seed'])
        require(self.curve.on_curve(Q) and scalar_replay(self.curve, Q, self.C.r) == IDENTITY, 'public subgroup')
        require(len(result['attempts']) <= workload['resource_limits']['max_target'], 'target budget')
        for i, attempt in enumerate(result['attempts']):
            a = rng.randrange(1, self.C.r)
            R = self.curve.add(Q, scalar_replay(self.curve, self.G, a))
            require(attempt['a'] == a and attempt['index'] == i+1 and point(attempt['target']) == R, 'target rerandomization stream')
            scalar = None
            if R.inf:
                require(attempt['status'] == 'identity_relation' and not attempt['relations'], 'identity relation')
                scalar = (-a) % self.C.r
            else:
                self.attempt(attempt)
                if 'phase_wall_ns' in attempt:
                    phases(attempt['phase_wall_ns'], ONLINE[:3])
                if attempt['relations']:
                    scalar = (sum(c*prep['column_logs'][j] for j,c in attempt['relations'][0]['row'])-a) % self.C.r
            if scalar is not None:
                require(i == len(result['attempts'])-1 and result['scalar'] == scalar, 'recovery/stop rule')
            if attempt['status'] == 'error':
                require(i == len(result['attempts'])-1 and result['status'] == 'error', 'error/stop rule')
        if result['verified']:
            require(result['attempts'] and result['status'] == 'complete', 'verified completion')
            require(type(result['scalar']) is int and 0 <= result['scalar'] < self.C.r, 'target scalar range')
            require(scalar_replay(self.curve, self.G, result['scalar']) == Q, 'independent target scalar')
            require(result['replayed_point'] == vars(Q), 'replayed target metadata')
        else:
            require(result['status'] in ('error', 'budget'), 'unverified status')
        for phase in ONLINE[:3]:
            require(sum(a.get('phase_wall_ns', {}).get(phase, 0) for a in result['attempts']) <= result['phase_wall_ns'][phase], 'attempt time omitted')
