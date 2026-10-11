"""Offline exact-basis, relation, rank and public-scalar audit of one-target runs.

Only this offline auditor caches repeated proofs. Measured target contexts never
reuse target answers. Audit time is outside the reported online intervals.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
from types import SimpleNamespace

from ic_query import ARMS, ROOT, PHASES, ONLINE, IDENTITY, Curve, GF2n, Point
from ic_query import ToyCurve, FactorBase, point, scalar_replay, sha256_hex
from identity import no_floats, candidate
from measure import eligible, SEEDS
from receipts import validate_run

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
    def __init__(self, ell):
        self.ell = ell
        self.C = C = ToyCurve(13)
        self.fb = FactorBase(C, 'prefix', ell, 0)
        self.curve = Curve(GF2n(C.n, C.mod), C.b)
        self.G = point(C.G)
        self.pieces = Pieces(self.fb, 3)
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
        xs = [(relation['assignment'] >> (i*self.ell)) & ((1 << self.ell)-1) for i in range(3)]
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
            self.proofs[key] = certify_boolean_basis(3*self.ell, equations, basis, monomial_cache=self.ell <= 4)
        proof, cert = self.proofs[key], answer['basis_certificate']
        require(proof['verified'], 'independent reconstructed-equation basis proof')
        require(answer['groebner_verified'] and cert['verified'], 'online basis verification')
        for field in ('root_count', 'standard_monomials', 'solutions', 'ideal_equality', 'reduced_groebner_basis'):
            require(cert[field] == proof[field], 'certificate '+field)
        require(record['roots_checked'] == proof['root_count'], 'all roots examined')
        require(0 <= record['lift_rejections']+record['membership_rejections'] <= proof['root_count'], 'root rejections')
        rows = [rel['row'] for rel in record['relations']]
        require(rows == sorted(rows) and len({sha256_hex(r) for r in rows}) == len(rows), 'relation ordering/deduplication')
        for relation in record['relations']:
            self.relation(R, relation, proof['solutions'])
        expected = 'verified_decomposition' if rows else 'proved_unsat' if not proof['solutions'] else 'lift_rejected'
        require(record['status'] == expected, 'PDP outcome does not match proof')

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
            require(sha256_hex(sorted((p.x,p.y,p.inf) for p in seen)) == workload['excluded_points_sha256'], 'unseen exclusion digest')
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


def audit_report(report):
    require(report['schema'] == 'round20-one-target-comparison/1' and report['status'] == 'RECORDED', 'incomplete or foreign report')
    require(report['arms'] == [*ARMS, 'rho'], 'arms')
    require(report['repetitions'] >= 2, 'repetitions')
    require(set(report['dimensions']) <= {3,6} and len(set(report['dimensions'])) == len(report['dimensions']), 'dimensions')
    require(report['seeds'] == ([401] if report['correctness_only'] else list(SEEDS)), 'frozen seeds')
    hashes = {k: hashlib.sha256(v.encode()).hexdigest() for k,v in report['source_snapshot'].items()}
    require(hashes == report['source_sha256'], 'source snapshot hashes')
    required = [PREFIX+'round20/'+n+'.py' for n in ('ic_query','identity','measure','receipts','audit','build')]
    required += ['experiments/pdp-scaling/boolean_basis.py', 'experiments/pdp-degree-heuristics/descent.py']
    require(set(required) <= set(hashes), 'missing executed sources')
    builds = report['build_receipts']
    for name, digest in builds['20']['source_sha256'].items():
        require(hashes.get(name) == digest, 'native build source '+name)
    reference = report['source_snapshot'][PREFIX+'round15/reference/boolean_certificate.cpp']
    helpers = reference.split('extern "C" int boolean_certificate(', 1)[0]
    checks = '        out->roots = alive;' + reference.split('        out->roots = alive;', 1)[1].split('    } catch (const std::invalid_argument&)', 1)[0]
    require(builds['18']['generated_sha256'] == {name: hashlib.sha256(text.encode()).hexdigest() for name,text in (
        ('certificate_helpers.inc',helpers),('basis_checks.inc',checks))}, 'generated independent proof code')
    binaries = builds['20']['binaries']
    require(report['kernel_binary_sha256'] in binaries.values(), 'field kernel binary')
    maths = {ell: Mathematics(ell) for ell in report['dimensions']}
    for cid, manifest in report['candidates'].items():
        no_floats(manifest)
        require(manifest['implementation']['sources_sha256'] == hashes, 'candidate source identity')
        ell = manifest['factor_base']['nominal_dimension']
        m = maths[ell]
        base = {**m.fb.record(), 'geometric_points_and_projection': m.base_points,
                'column_representatives': [list(p) for p in m.fb.column_reps]}
        require(manifest['factor_base'] == base and manifest['field'] == m.C.field_record(), 'exact base/field identity')
        require(manifest['curve'] == {**m.C.curve_record(), 'curve_id': m.C.curve_id}, 'curve identity')
        require(cid == f'IC1N13Ckb1fb{m.fb.usable_points}PDP3evalRCsampleLAgaussTDpdpISO0h{sha256_hex(manifest)[:12]}', 'candidate digest')
        require(manifest['implementation']['arm'] in ARMS, 'candidate arm')
        proposed = SimpleNamespace(curve=m.C, fb=m.fb, base_points=m.base_points,
            arm=manifest['implementation']['arm'], sanitizer=False, max_collection=10000, max_target=10000)
        require(candidate(proposed, report['source_snapshot']) == (cid,manifest), 'candidate implementation policy')
    inputs, groups, statuses, run_ids = {}, {}, Counter(), set()
    for item in report['inputs']:
        wid, w = item['workload_id'], item['workload']
        no_floats(w)
        require(wid == sha256_hex(w)[:12] and wid not in inputs and w['target_count'] == 1, 'one-target workload identity')
        m = maths[w['factor_base_policy']['ell']]
        require(w['factor_base_policy'] == {'family':'prefix', 'ell':m.ell, 'record_sha256':m.fb.digest}, 'workload base')
        require(w['curve_id'] == m.C.curve_id and w['seed'] in report['seeds'], 'workload curve/seed')
        require(scalar_replay(m.curve, m.G, item['fixture_scalar']) == Point(**w['target']), 'external fixture scalar')
        inputs[wid] = item
    require({(v['workload']['factor_base_policy']['ell'],v['workload']['seed']) for v in inputs.values()} ==
            {(ell,seed) for ell in report['dimensions'] for seed in report['seeds']}, 'frozen workload coverage')
    require(len(inputs) == len(report['dimensions'])*len(report['seeds']), 'workload count')
    for row in report['rows']:
        wid, rep = row['workload_id'], row['repetition']
        frozen, group = inputs[wid], groups.setdefault(wid, {})
        w, Q = frozen['workload'], Point(**frozen['workload']['target'])
        m = maths[w['factor_base_policy']['ell']]
        require(rep not in group and row['warmup'] == (rep == 0), 'duplicate/mislabeled repetition')
        require(row['run_number'] == report['run_number_start']+rep, 'run number')
        require(sorted(row['order']) == sorted([*ARMS,'rho']) and sorted(row['setup_order']) == sorted(ARMS), 'execution order')
        group[rep] = row
        rho = row['results']['rho']['answer']
        if rho['verified']:
            require(rho['scalar'] == frozen['fixture_scalar'] and rho['target'] == vars(Q) == rho['replayed_point'], 'rho target/result')
            require(scalar_replay(m.curve, m.G, rho['scalar']) == Q, 'independent rho replay')
        for arm in ARMS:
            receipt, result = row['receipts'][arm], row['results'][arm]['answer']
            validate_run(receipt)
            require(receipt['run_id'] not in run_ids, 'duplicate run id')
            run_ids.add(receipt['run_id'])
            manifest = report['candidates'][receipt['candidate_id']]
            require(manifest['implementation']['arm'] == arm and manifest['factor_base']['nominal_dimension'] == m.ell, 'selected candidate')
            require(receipt['workload_id'] == wid and receipt['target_result'] == result and receipt['rho_measured'] == rho, 'raw result/receipt mismatch')
            require(receipt['run_id'] == f"{receipt['candidate_id']}W{wid}R{row['run_number']}", 'run identity')
            prep = receipt['preparation']
            seen = m.preparation(prep, w)
            fixture_rng = random.Random(f"round20-public-fixture|{m.C.curve_id}|{w['seed']}")
            for draw in range(1, w['fixture_draws']+1):
                k = fixture_rng.randrange(1, m.C.r)
                P = scalar_replay(m.curve, m.G, k)
                require((P not in seen) == (draw == w['fixture_draws']), 'fixture rejection sampling')
            require(k == frozen['fixture_scalar'], 'fixture seed/scalar')
            m.target(result, prep, w)
            cold = dict(prep['phase_wall_ns'])
            if result['phase_wall_ns'] is not None:
                require(receipt['online']['ic_online_ns'] == result['online_wall_ns'] and
                        receipt['online']['phase_wall_ns'] == result['phase_wall_ns'], 'raw online phase accounting')
                cold['target_descent'] += sum(v for p,v in result['phase_wall_ns'].items() if p != 'target_recovery_check')
                cold['recovery_check'] += result['phase_wall_ns']['target_recovery_check']
            require(receipt['phase_wall_ns'] == cold and receipt['charged_preparation_and_online_ns'] == sum(cold.values()), 'supplementary cold accounting')
            require(receipt['wall_ns'] == row['results'][arm]['elapsed_from_preparation_start_ns'], 'scheduling interval')
            require(receipt['provenance']['workload_fixture_sha256'] == sha256_hex(w) and
                    receipt['provenance']['source_sha256'] == sha256_hex(hashes), 'receipt provenance')
            require(receipt['counts']['ordinary_queries'] == len(prep['attempts']) and receipt['counts']['descent_attempts'] == len(result['attempts']), 'attempt accounting')
            require(receipt['counts']['final_rank'] == prep['final_rank'] and receipt['counts']['novel_rows'] == sum(a['novel_rows'] for a in prep['attempts']), 'rank accounting')
            require(receipt['counts']['verified_relations'] == sum(len(a['relations']) for a in prep['attempts']), 'relation count')
            for status, name in (('verified_decomposition','pdp_verified'),('proved_unsat','pdp_proved_unsat'),
                                 ('budget','pdp_budget'),('error','pdp_error'),('lift_rejected','pdp_lift_rejected')):
                require(receipt['counts'][name] == sum(a['status'] == status for a in prep['attempts']), 'PDP status accounting')
            require(receipt['stage']['actual_base_points'] == m.fb.usable_points and receipt['stage']['folded_columns'] == m.fb.effective_columns, 'stage base counts')
            require(set(receipt['selected_binary_sha256']) == {'producer','certificate','descent','curve_replay'}, 'selected native binaries')
            selected = {'producer':'round4/build/packed_dual', 'descent':'round14/build/contraction',
                        'curve_replay':'round17/build/replay',
                        'certificate':'round15/build/ordered' if arm == 'baseline' else 'round18/build/packed-verifier'}
            for name, stem in selected.items():
                require(receipt['selected_binary_sha256'][name] in [v for p,v in binaries.items() if p in (PREFIX+stem+'.so',PREFIX+stem+'.dylib')], 'selected '+name+' binary')
            if result['verified']:
                require(result['scalar'] == frozen['fixture_scalar'] and row['results'][arm]['fixture_scalar_matches'], 'fixture mismatch')
            statuses[arm+':'+result['status']] += 1
    require(set(groups) == set(inputs), 'missing workload groups')
    require(report['admission']['timed_attempts'] == 3*len(report['rows']), 'timed attempt count')
    admitted = eligible(report)
    require(admitted == report['timing_admission_eligible'], 'timing admission flag')
    summaries = []
    for wid, rows in groups.items():
        require(set(rows) == set(range(report['repetitions']+1)), 'missing repetitions')
        w = inputs[wid]['workload']
        verified = all(r['results'][a]['answer']['verified'] for r in rows.values() for a in (*ARMS,'rho'))
        s = {'workload_id':wid, 'target':w['target'], 'ell':w['factor_base_policy']['ell'],
             'all_attempts_verified':verified, 'timing_admission_eligible':admitted,
             'qualified_comparison':verified and admitted}
        if verified:
            measured = [r for i,r in rows.items() if i]
            s['online_ms_median'] = {a:statistics.median(r['results'][a]['answer']['online_wall_ns'] for r in measured)/1e6 for a in (*ARMS,'rho')}
            s['rho_over_ic'] = {a:interval([r['results']['rho']['answer']['online_wall_ns']/r['results'][a]['answer']['online_wall_ns'] for r in measured]) for a in ARMS}
            s['baseline_over_packed'] = interval([r['results']['baseline']['answer']['online_wall_ns']/r['results']['packed']['answer']['online_wall_ns'] for r in measured])
            s['preparation_ms_median'] = {a:statistics.median(r['receipts'][a]['preparation']['wall_ns'] for r in measured)/1e6 for a in ARMS}
            s['online_phase_ms_median'] = {a:{p:statistics.median(r['results'][a]['answer']['phase_wall_ns'][p] for r in measured)/1e6 for p in ONLINE} for a in ARMS}
            s['candidate_ids'] = {a:measured[0]['receipts'][a]['candidate_id'] for a in ARMS}
            s['target_attempts'] = {a:dict(Counter(t['status'] for t in measured[0]['results'][a]['answer']['attempts'])) for a in ARMS}
        summaries.append(s)
    return {'scope':'Controlled 11-bit subgroup, exact single-target online wall; unmetered operation counts remain null. Load admission is necessary, not proof of an exclusive host.',
            'statuses':dict(statuses), 'independent_unique_basis_proofs':sum(len(m.proofs) for m in maths.values()),
            'independent_unique_curve_witnesses':sum(len(m.witnesses) for m in maths.values()),
            'timing_admission_eligible':admitted, 'workloads':summaries}


def audit(path):
    return audit_report(json.loads(gzip.decompress(Path(path).read_bytes())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    print(json.dumps(audit(parser.parse_args().report), indent=2))
