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

from conditional_ic import ARMS, SUMMANDS, CHECKERS, HERE, ROOT, ONLINE, Point, scalar_replay, sha256_hex, arithmetic_policy, rho_policy
from conditional_identity import no_floats, candidate, fixture, validate_run
from conditional_measure import eligible, SEEDS
from conditional_journal import recover
import exact_math as reference

PREFIX = 'experiments/groebner-perf-20260924/'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def interval(ratios):
    logs = [math.log(v) for v in ratios]
    rng = random.Random(2026092708)
    samples = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs)))) for _ in range(2000))
    return {'paired_geomean': math.exp(statistics.mean(logs)),
            'bootstrap95': [samples[49], samples[1949]], 'pairs': len(logs)}


class Mathematics(reference.Mathematics):
    def attempt(self, record):
        super().attempt(record)
        answer = record.get('basis')
        if not answer or answer['status'] != 'gb':
            return
        cert = answer['basis_certificate']
        require(answer['binary_sha256'] == self.producer_binary, 'attempt producer binary')
        require(answer['verifier_binary_sha256'] == self.verifier_binary, 'attempt verifier binary')
        sparse = self.arm == 'two-eval' or (self.arm == 'three-eval' and CHECKERS[self.ell] == 'sparse')
        backend = ('independent-equation-row-elimination' if self.arm == 'two-conditional' else
                   'independent-packed-sparse-proof' if sparse else 'independent-packed-bitslice-zeta')
        require(cert['backend'] == backend, 'actual certificate backend')
        if sparse:
            proof = cert['proof_stats']
            require(proof['mode'] == 2 and proof['budget_limit'] == 65536, 'sparse proof policy')
            require(proof['fallback_reason'] in (0,1,2,3), 'sparse fallback reason')
            require(all(type(v) is int and v >= 0 for k,v in proof.items() if k != 'seconds'), 'sparse counters')
            require(math.isfinite(proof['seconds']) and 0 <= proof['seconds'] <= answer['verification_seconds'], 'sparse timing charged')
        elif self.arm == 'two-conditional':
            require('proof_stats' not in cert and cert['method'] == 'exact-conditional-linear-count-and-Boolean-staircase', 'conditional proof method')
            require(cert['stats']['branches'] == 1 << self.ell and cert['stats']['roots'] == cert['root_count'], 'conditional branch counters')
            require(answer['metrics']['branches'] == 1 << self.ell and answer['metrics']['roots'] == cert['root_count'], 'conditional producer counters')
        else:
            require('proof_stats' not in cert, 'unexpected sparse proof in frozen baseline')


def audit_report(report):
    require(report['schema'] == 'round28-conditional-ic-comparison/1' and report['status'] == 'RECORDED', 'incomplete or foreign report')
    require(report['arms'] == [*ARMS, 'rho'], 'arms')
    require(report['repetitions'] >= 2, 'repetitions')
    require(set(report['dimensions']) <= {3,6} and len(set(report['dimensions'])) == len(report['dimensions']), 'dimensions')
    require(report['seeds'] == ([401] if report['correctness_only'] else list(SEEDS)), 'frozen seeds')
    hashes = {k: hashlib.sha256(v.encode()).hexdigest() for k,v in report['source_snapshot'].items()}
    require(hashes == report['source_sha256'], 'source snapshot hashes')
    required = [PREFIX+'round20/'+n+'.py' for n in ('ic_query','identity','measure','receipts','audit','build')]
    required += ['experiments/pdp-scaling/boolean_basis.py', 'experiments/pdp-degree-heuristics/descent.py']
    required += [PREFIX+'round21/'+n+'.py' for n in ('first_query','first_identity','first_measure','first_audit','journal')]
    required += [PREFIX+'round25/'+n+'.py' for n in ('sparse_ic','ic_identity','measure','audit','journal')]
    required += [PREFIX+'round26/'+n+'.py' for n in ('reference_field','replay_query','replay_identity','replay_measure','replay_audit','replay_journal')]
    required += [str(p.relative_to(ROOT)) for folder in (HERE,HERE.parent/'round27') for p in folder.iterdir() if p.suffix in ('.py','.cpp','.h','.hpp')]
    required += [PREFIX+'round23/'+n for n in ('build.py','sparse_checker.py','proof_types.hpp','sparse_proof.hpp')]
    require(set(required) <= set(hashes), 'missing executed sources')
    require(all((ROOT/name).is_file() and hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest for name,digest in hashes.items()), 'trusted local source differs; use the corresponding checkout')
    builds = report['build_receipts']
    for name, digest in builds['20']['source_sha256'].items():
        require(hashes.get(name) == digest, 'native build source '+name)
    reference = report['source_snapshot'][PREFIX+'round15/reference/boolean_certificate.cpp']
    helpers = reference.split('extern "C" int boolean_certificate(', 1)[0]
    checks = '        out->roots = alive;' + reference.split('        out->roots = alive;', 1)[1].split('    } catch (const std::invalid_argument&)', 1)[0]
    require(builds['18']['generated_sha256'] == {name: hashlib.sha256(text.encode()).hexdigest() for name,text in (
        ('certificate_helpers.inc',helpers),('basis_checks.inc',checks))}, 'generated independent proof code')
    require(set(builds) == {'14','15','17','18','20','23','27'}, 'complete build receipt set')
    import importlib.util
    spec = importlib.util.spec_from_file_location('local_sparse_generator', ROOT/PREFIX/'round23/build.py')
    generated = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generated)
    sparse_sources = set(generated.PINNED) | {PREFIX+'round23/'+name for name in ('build.py','proof_types.hpp','sparse_proof.hpp')}
    require(set(builds['23']['source_sha256']) == sparse_sources, 'sparse source receipt set')
    for name,digest in builds['23']['source_sha256'].items():
        require(hashes[name] == digest, 'sparse build source '+name)
    require(builds['23']['generated_sha256'] == {name:hashlib.sha256(text.encode()).hexdigest()
        for name,text in generated.generated_sources(report['source_snapshot']).items()}, 'generated sparse proof source')
    require(builds['27']['sources'] == {Path(name).name:digest for name,digest in hashes.items() if name.startswith(PREFIX+'round27/') and '/' not in name.removeprefix(PREFIX+'round27/')}, 'conditional native build sources')
    binaries = builds['20']['binaries']
    require(report['kernel_binary_sha256'] in binaries.values(), 'field kernel binary')
    maths = {(ell,arm):Mathematics(ell,SUMMANDS[arm]) for ell in report['dimensions'] for arm in ARMS}
    for (_,arm),m in maths.items():
        m.arm = arm
    for cid, manifest in report['candidates'].items():
        no_floats(manifest)
        require(manifest['implementation']['sources_sha256'] == hashes, 'candidate source identity')
        ell = manifest['factor_base']['nominal_dimension']
        m = maths[ell,manifest['implementation']['arm']]
        base = {**m.fb.record(), 'geometric_points_and_projection': m.base_points,
                'column_representatives': [list(p) for p in m.fb.column_reps]}
        require(manifest['factor_base'] == base and manifest['field'] == m.C.field_record(), 'exact base/field identity')
        require(manifest['curve'] == {**m.C.curve_record(), 'curve_id': m.C.curve_id}, 'curve identity')
        require(cid == f"IC1N13Ckb1fb{m.fb.usable_points}{manifest['point_decomposition']['stage_code']}RCsampleLAgaussTDpdpISO0h{sha256_hex(manifest)[:12]}", 'candidate digest')
        require(manifest['implementation']['arm'] in ARMS, 'candidate arm')
        proposed = SimpleNamespace(curve=m.C, fb=m.fb, base_points=m.base_points,
            arm='packed', target_policy='first-usable',
            verifier_arm=CHECKERS[ell] if manifest['implementation']['arm'] == 'three-eval' else 'sparse', replay_arm='euclid',
            ic_arm=manifest['implementation']['arm'], summands=SUMMANDS[manifest['implementation']['arm']], ell=ell,
            budget_test=False, sanitizer=False, max_collection=10000, max_target=10000)
        require(candidate(proposed, report['source_snapshot']) == (cid,manifest), 'candidate implementation policy')
    inputs, groups, statuses, run_ids = {}, {}, Counter(), set()
    for item in report['inputs']:
        wid, w = item['workload_id'], item['workload']
        no_floats(w)
        require(wid == sha256_hex(w)[:12] and wid not in inputs and w['target_count'] == 1, 'one-target workload identity')
        m = maths[w['factor_base_policy']['ell'],'three-eval']
        require(w['schema'] == 'round28-conditional-single-public-target/1', 'workload schema')
        require(w['rho_reference'] == rho_policy(m.C, Point(**w['target']), 'euclid'), 'same-point rho policy')
        require(w['resource_limits']['processes'] == 1, 'one-process resource envelope')
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
        m = maths[w['factor_base_policy']['ell'],'three-eval']
        require(rep not in group and row['warmup'] == (rep == 0), 'duplicate/mislabeled repetition')
        require(row['run_number'] == report['run_number_start']+rep, 'run number')
        require(sorted(row['order']) == sorted([*ARMS,'rho']) and sorted(row['setup_order']) == sorted(ARMS), 'execution order')
        group[rep] = row
        rho = row['results']['rho']['answer']
        statuses['rho:'+rho['status']] += 1
        require(rho['reference_policy'] == w['rho_reference'], 'measured rho policy')
        require(rho['target'] == vars(Q), 'rho same public point')
        require(0 <= rho['native_reference_wall_ns'] <= rho['online_wall_ns'], 'rho replay timing')
        if rho['verified']:
            require(rho['scalar'] == frozen['fixture_scalar'] and rho['target'] == vars(Q) == rho['replayed_point'], 'rho target/result')
            require(scalar_replay(m.curve, m.G, rho['scalar']) == Q, 'independent rho replay')
        prepared_for_fixture = {}
        for arm in ARMS:
            m = maths[w['factor_base_policy']['ell'],arm]
            receipt, result = row['receipts'][arm], row['results'][arm]['answer']
            validate_run(receipt)
            require(receipt['run_id'] not in run_ids, 'duplicate run id')
            run_ids.add(receipt['run_id'])
            manifest = report['candidates'][receipt['candidate_id']]
            require(manifest['implementation']['arm'] == arm and manifest['factor_base']['nominal_dimension'] == m.ell, 'selected candidate')
            require(receipt['workload_id'] == wid and receipt['target_result'] == result and receipt['rho_measured'] == rho, 'raw result/receipt mismatch')
            require(receipt['run_id'] == f"{receipt['candidate_id']}W{wid}R{row['run_number']}", 'run identity')
            prep = receipt['preparation']
            require(all('target_root_policy' not in a for a in prep['attempts']), 'collection must retain all roots')
            require(result['independent_arithmetic'] == arithmetic_policy('euclid'), 'actual independent arithmetic')
            m.producer_binary = receipt['selected_binary_sha256']['producer']
            m.verifier_binary = receipt['selected_binary_sha256']['certificate']
            seen = m.preparation(prep, w)
            prepared_for_fixture[arm] = SimpleNamespace(curve=m.C, fb=m.fb, ell=m.ell,
                seen_points=seen, collection_seed=w['collection_seed'],
                max_collection=10000, max_target=10000)
            require(all(a.get('target_root_policy') == 'first-usable' for a in result['attempts'] if a.get('basis')), 'target policy/arm mismatch')
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
                        'certificate':'round18/build/packed-verifier'}
            for name, stem in selected.items():
                if arm == 'two-conditional' and name in ('producer','certificate'):
                    stem27 = 'producer' if name == 'producer' else 'checker'
                    allowed = [v for p,v in builds['27']['binaries'].items() if p in (stem27+'.so',stem27+'.dylib')]
                elif name == 'certificate' and (arm != 'three-eval' or CHECKERS[m.ell] == 'sparse'):
                    allowed = [v for p,v in builds['23']['binaries'].items() if p in ('sparse-verifier.so','sparse-verifier.dylib')]
                else:
                    allowed = [v for p,v in binaries.items() if p in (PREFIX+stem+'.so',PREFIX+stem+'.dylib')]
                require(receipt['selected_binary_sha256'][name] in allowed, 'selected '+name+' binary')
            require(receipt['resource_envelope']['rho_workers'] == 1 and
                receipt['resource_envelope']['rho_distinguished_point_memory_bytes'] == 0, 'rho resource boundary')
            require(receipt['resource_envelope']['native_threads'] == 1, 'IC native thread boundary')
            require(receipt['resource_envelope']['independent_arithmetic'] == arithmetic_policy('euclid'), 'IC/rho arithmetic boundary')
            require(receipt['provenance']['resource_envelope_id'] == 'ENV1h'+sha256_hex(receipt['resource_envelope'])[:12], 'resource envelope digest')
            if result['verified']:
                require(result['scalar'] == frozen['fixture_scalar'] and row['results'][arm]['fixture_scalar_matches'], 'fixture mismatch')
            statuses[arm+':'+result['status']] += 1
        require(fixture(prepared_for_fixture,w['seed']) == (wid,w,frozen['fixture_scalar']), 'common unseen fixture reconstruction')
    require(set(groups) == set(inputs), 'missing workload groups')
    require(report['admission']['timed_attempts'] == 4*len(report['rows']), 'timed attempt count')
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
            s['two_eval_over_conditional'] = interval([r['results']['two-eval']['answer']['online_wall_ns']/r['results']['two-conditional']['answer']['online_wall_ns'] for r in measured])
            s['three_eval_over_two'] = {a:interval([r['results']['three-eval']['answer']['online_wall_ns']/r['results'][a]['answer']['online_wall_ns'] for r in measured]) for a in ARMS if a != 'three-eval'}
            s['preparation_ms_median'] = {a:statistics.median(r['receipts'][a]['preparation']['wall_ns'] for r in measured)/1e6 for a in ARMS}
            s['online_phase_ms_median'] = {a:{p:statistics.median(r['results'][a]['answer']['phase_wall_ns'][p] for r in measured)/1e6 for p in ONLINE} for a in ARMS}
            s['candidate_ids'] = {a:measured[0]['receipts'][a]['candidate_id'] for a in ARMS}
            s['preparation_attempts'] = {a:dict(Counter(t['status'] for t in measured[0]['receipts'][a]['preparation']['attempts'])) for a in ARMS}
            s['target_attempts'] = {a:dict(Counter(t['status'] for t in measured[0]['results'][a]['answer']['attempts'])) for a in ARMS}
        summaries.append(s)
    return {'scope':'Controlled 11-bit subgroup, exact single-target online wall; unmetered operation counts remain null. Load admission is necessary, not proof of an exclusive host.',
            'statuses':dict(statuses), 'independent_unique_basis_proofs':sum(len(m.proofs) for m in maths.values()),
            'independent_unique_curve_witnesses':sum(len(m.witnesses) for m in maths.values()),
            'timing_admission_eligible':admitted, 'workloads':summaries}


def audit(path):
    report = json.loads(gzip.decompress(Path(path).read_bytes()))
    restored, recovery = recover(str(path)+'.journal.gz')
    require(not recovery['truncated_tail'] and restored == report, 'journal/aggregate disagreement')
    return audit_report(report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    print(json.dumps(audit(parser.parse_args().report), indent=2))
