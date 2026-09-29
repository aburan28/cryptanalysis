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

from replay_query import ARMS, RHO_ARMS, CHECKERS, HERE, ROOT, ONLINE, Point, scalar_replay, sha256_hex, rho_policy, arithmetic_policy
from replay_identity import no_floats, candidate, fixture, validate_run
from replay_measure import eligible, SEEDS
from replay_journal import recover

_path = sys.path[:]
try:
    sys.path.insert(0, str(HERE.parent/'round25'))
    import audit as reference
finally:
    sys.path[:] = _path

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


Mathematics = reference.Mathematics

def audit_report(report):
    require(report['schema'] == 'round26-independent-replay-comparison/1' and report['status'] == 'RECORDED', 'incomplete or foreign report')
    require(report['arms'] == [*ARMS, *RHO_ARMS], 'arms')
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
    required += [PREFIX+'round23/'+n for n in ('build.py','sparse_checker.py','proof_types.hpp','sparse_proof.hpp')]
    require(set(required) <= set(hashes), 'missing executed sources')
    builds = report['build_receipts']
    for name, digest in builds['20']['source_sha256'].items():
        require(hashes.get(name) == digest, 'native build source '+name)
    reference = report['source_snapshot'][PREFIX+'round15/reference/boolean_certificate.cpp']
    helpers = reference.split('extern "C" int boolean_certificate(', 1)[0]
    checks = '        out->roots = alive;' + reference.split('        out->roots = alive;', 1)[1].split('    } catch (const std::invalid_argument&)', 1)[0]
    require(builds['18']['generated_sha256'] == {name: hashlib.sha256(text.encode()).hexdigest() for name,text in (
        ('certificate_helpers.inc',helpers),('basis_checks.inc',checks))}, 'generated independent proof code')
    require(set(builds) == {'14','15','17','18','20','23'}, 'complete build receipt set')
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
            arm='packed', target_policy='first-usable', verifier_arm=manifest['implementation']['verifier_arm'], replay_arm=manifest['implementation']['arm'], budget_test=False, sanitizer=False, max_collection=10000, max_target=10000)
        require(candidate(proposed, report['source_snapshot']) == (cid,manifest), 'candidate implementation policy')
    inputs, groups, statuses, run_ids = {}, {}, Counter(), set()
    for item in report['inputs']:
        wid, w = item['workload_id'], item['workload']
        no_floats(w)
        require(wid == sha256_hex(w)[:12] and wid not in inputs and w['target_count'] == 1, 'one-target workload identity')
        m = maths[w['factor_base_policy']['ell']]
        require(w['schema'] == 'round26-single-public-target/1', 'workload schema')
        require(w['basis_checker'] == CHECKERS[m.ell], 'frozen basis checker')
        require(w['rho_reference'] == {'pairing':'same independent arithmetic as the selected IC candidate',
            'policies':{arm:rho_policy(m.C, Point(**w['target']), arm) for arm in ARMS}}, 'same-point matched rho policy')
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
        m = maths[w['factor_base_policy']['ell']]
        require(rep not in group and row['warmup'] == (rep == 0), 'duplicate/mislabeled repetition')
        require(row['run_number'] == report['run_number_start']+rep, 'run number')
        require(sorted(row['order']) == sorted([*ARMS,*RHO_ARMS]) and sorted(row['setup_order']) == sorted(ARMS), 'execution order')
        group[rep] = row
        for arm in ARMS:
            rho = row['results']['rho-'+arm]['answer']
            statuses['rho-'+arm+':'+rho['status']] += 1
            require(rho['reference_policy'] == w['rho_reference']['policies'][arm], 'measured rho policy')
            require(rho['target'] == vars(Q), 'rho same public point')
            require(0 <= rho['native_reference_wall_ns'] <= rho['online_wall_ns'], 'rho replay timing')
            if rho['verified']:
                require(rho['scalar'] == frozen['fixture_scalar'] and rho['target'] == vars(Q) == rho['replayed_point'], 'rho target/result')
                require(scalar_replay(m.curve, m.G, rho['scalar']) == Q, 'independent rho replay')
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
            require(manifest['implementation']['verifier_arm'] == w['basis_checker'], 'selected basis checker')
            require(result['independent_arithmetic'] == arithmetic_policy(arm), 'actual IC independent arithmetic')
            m.verifier_arm = w['basis_checker']
            m.producer_binary = receipt['selected_binary_sha256']['producer']
            m.verifier_binary = receipt['selected_binary_sha256']['certificate']
            seen = m.preparation(prep, w)
            if prep['status'] == 'ready':
                prepared_fixture = SimpleNamespace(curve=m.C, fb=m.fb, ell=m.ell,
                    seen_points=seen, collection_seed=w['collection_seed'],
                    max_collection=10000, max_target=10000, verifier_arm=w['basis_checker'])
                require(fixture(prepared_fixture, w['seed']) == (wid, w, frozen['fixture_scalar']),
                    'frozen workload and prior workload identity')
            fixture_rng = random.Random(f"round20-public-fixture|{m.C.curve_id}|{w['seed']}")
            for draw in range(1, w['fixture_draws']+1):
                k = fixture_rng.randrange(1, m.C.r)
                P = scalar_replay(m.curve, m.G, k)
                require((P not in seen) == (draw == w['fixture_draws']), 'fixture rejection sampling')
            require(k == frozen['fixture_scalar'], 'fixture seed/scalar')
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
                allowed = ([v for p,v in builds['23']['binaries'].items() if p in ('sparse-verifier.so','sparse-verifier.dylib')]
                    if name == 'certificate' and w['basis_checker'] == 'sparse' else
                    [v for p,v in binaries.items() if p in (PREFIX+stem+'.so',PREFIX+stem+'.dylib')])
                require(receipt['selected_binary_sha256'][name] in allowed, 'selected '+name+' binary')
            require(receipt['resource_envelope']['rho_workers'] == 1 and
                receipt['resource_envelope']['rho_distinguished_point_memory_bytes'] == 0, 'rho resource boundary')
            require(receipt['resource_envelope']['native_threads'] == 1, 'IC native thread boundary')
            require(receipt['resource_envelope']['independent_arithmetic'] == arithmetic_policy(arm), 'IC/rho arithmetic resource boundary')
            require(receipt['provenance']['resource_envelope_id'] == 'ENV1h'+sha256_hex(receipt['resource_envelope'])[:12], 'resource envelope digest')
            if result['verified']:
                require(result['scalar'] == frozen['fixture_scalar'] and row['results'][arm]['fixture_scalar_matches'], 'fixture mismatch')
            statuses[arm+':'+result['status']] += 1
    require(set(groups) == set(inputs), 'missing workload groups')
    require(report['admission']['timed_attempts'] == 4*len(report['rows']), 'timed attempt count')
    admitted = eligible(report)
    require(admitted == report['timing_admission_eligible'], 'timing admission flag')
    summaries = []
    for wid, rows in groups.items():
        require(set(rows) == set(range(report['repetitions']+1)), 'missing repetitions')
        w = inputs[wid]['workload']
        verified = all(r['results'][a]['answer']['verified'] for r in rows.values() for a in (*ARMS,*RHO_ARMS))
        s = {'workload_id':wid, 'target':w['target'], 'ell':w['factor_base_policy']['ell'],
             'all_attempts_verified':verified, 'timing_admission_eligible':admitted,
             'qualified_comparison':verified and admitted}
        if verified:
            measured = [r for i,r in rows.items() if i]
            s['online_ms_median'] = {a:statistics.median(r['results'][a]['answer']['online_wall_ns'] for r in measured)/1e6 for a in (*ARMS,*RHO_ARMS)}
            s['rho_over_ic'] = {a:interval([r['results']['rho-'+a]['answer']['online_wall_ns']/r['results'][a]['answer']['online_wall_ns'] for r in measured]) for a in ARMS}
            s['power_over_euclid'] = interval([r['results']['power']['answer']['online_wall_ns']/r['results']['euclid']['answer']['online_wall_ns'] for r in measured])
            s['rho_power_over_euclid'] = interval([r['results']['rho-power']['answer']['online_wall_ns']/r['results']['rho-euclid']['answer']['online_wall_ns'] for r in measured])
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
    report = json.loads(gzip.decompress(Path(path).read_bytes()))
    restored, recovery = recover(str(path)+'.journal.gz')
    require(not recovery['truncated_tail'] and restored == report, 'journal/aggregate disagreement')
    return audit_report(report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    print(json.dumps(audit(parser.parse_args().report), indent=2))
