"""Audit trusted-source binding, independent mathematics, timing and device use."""
import argparse
import base64
from collections import Counter
from functools import lru_cache
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import statistics

from measure_multipliers import ARMS, CPU_ARMS, SHAPES, LARGE_ARMS, LARGE_CPU_ARMS, LARGE_SHAPES, ROOT, HERE, digest, sources, timing_eligible
from certificate_journal import recover
from quadratic_reference import evaluate, verify_basis
from affine_reference import branch_counts, constant_identity_count, certify_roots, producer_model

_spec = importlib.util.spec_from_file_location("certificate_truth_reference", HERE.parent/"round32/reference.py")
_reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_reference)
truth_roots = _reference.chunked_roots
from sparse_checker import Curve, GF2n, Point
from descend import make_instance

PREFIX = 'experiments/groebner-perf-20260924/'


def ratio_interval(ratios):
    logs = [math.log(v) for v in ratios]
    rng = random.Random(2026092931)
    boot = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs)))) for _ in range(2000))
    return {'pairs': len(logs), 'paired_geomean': math.exp(statistics.mean(logs)),
            'bootstrap95': [boot[49], boot[1949]]}


def audit_sources(report):
    snapshot = report['source_snapshot']
    assert snapshot == sources(), 'audit requires the same trusted checkout; archived source is never executed'
    assert report['source_sha256'] == {k: hashlib.sha256(v.encode()).hexdigest() for k, v in snapshot.items()}
    receipts = report['build_receipts']
    for version in ('17', '18', '20', '23'):
        current = json.loads((HERE.parent/f'round{version}/build/receipt.json').read_text())
        assert receipts[version]['source_sha256'] == current['source_sha256']
        for name, expected in receipts[version]['source_sha256'].items():
            assert report['source_sha256'][name] == expected
    assert receipts['14']['source_sha256'] == report['source_sha256'][PREFIX+'round14/contraction.cpp']
    assert receipts['15']['ordered_source_sha256'] == report['source_sha256'][PREFIX+'round15/ordered_certificate.cpp']
    for name, value in receipts['15']['reference_sha256'].items():
        assert value == report['source_sha256'][PREFIX+'round15/reference/'+name]
    for version in ('31', '32', '33', '34'):
        expected = {k.removeprefix(PREFIX): v for k, v in report['source_sha256'].items()
                    if k.startswith(PREFIX+'round'+version+'/')}
        expected['round27/interpolation.hpp'] = report['source_sha256'][PREFIX+'round27/interpolation.hpp']
        if version in ('32', '33', '34'):
            expected['round31/abi.h'] = report['source_sha256'][PREFIX+'round31/abi.h']
        if version in ('33', '34'):
            expected['round32/abi.h'] = report['source_sha256'][PREFIX+'round32/abi.h']
        if version == '34':
            for name in ('abi.h','producer.cpp','checker.cpp','metal_backend.h','metal_backend.mm','quadratic.metal'):
                expected['round33/'+name] = report['source_sha256'][PREFIX+'round33/'+name]
        assert receipts[version]['sources'] == expected
        if any('producer-metal' in k for k in receipts[version]['binaries']):
            shader = snapshot[PREFIX+'round'+version+'/quadratic.metal']
            generated = {'kernel.inc': hashlib.sha256(
                ('static const char* quadratic_kernel = R"QUADRATIC('+shader+')QUADRATIC";\n').encode()).hexdigest()}
            if version == '34':
                generated['baseline-kernel.inc'] = hashlib.sha256(('static const char* quadratic_kernel = R"QUADRATIC('+snapshot[PREFIX+'round33/quadratic.metal']+')QUADRATIC";\n').encode()).hexdigest()
            assert receipts[version]['generated'] == generated
        else:
            assert receipts[version]['generated'] == {}
    for command in receipts['34']['commands']:
        name = Path(command[-1]).name
        if name.startswith('baseline-'):
            assert '-O3' in command and '-DQUADRATIC_ENUMERATION_BUDGET=134217728' in command
            if name.startswith('baseline-checker'):
                assert '-DBRANCH_CHECK_ENUMERATION_BUDGET=134217728' in command
            assert any('/round33/' in part for part in command if part.endswith(('.cpp','.mm')))
        elif name in ('producer.so','producer.dylib','producer-metal.dylib','checker.so','checker.dylib'):
            assert '-O3' in command and not any(part.startswith('-D') and 'BUDGET' in part for part in command)
    spec = importlib.util.spec_from_file_location('round31_sparse_build', HERE.parent/'round23/build.py')
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    assert receipts['23']['generated_sha256'] == {
        k: hashlib.sha256(v.encode()).hexdigest() for k, v in build.generated_sources(snapshot).items()}
    reference = snapshot[PREFIX+'round15/reference/boolean_certificate.cpp']
    helpers = reference.split('extern "C" int boolean_certificate(', 1)[0]
    checks = '        out->roots = alive;'+reference.split('        out->roots = alive;', 1)[1].split(
        '    } catch (const std::invalid_argument&)', 1)[0]
    assert receipts['18']['generated_sha256'] == {k: hashlib.sha256(v.encode()).hexdigest()
        for k, v in (('certificate_helpers.inc', helpers), ('basis_checks.inc', checks))}


@lru_cache(maxsize=24)
def mathematics(n, m, ell, seed):
    # Cache only offline audit reconstruction, never timed target solving.
    original = make_instance(n, m, ell, seed=seed)
    curve = Curve(GF2n(original.n, original.mod), original.b)
    items = sorted(original.anf.items())
    return (original, curve, truth_roots(original.nvars, n, items) if original.nvars<=24 else None,
            branch_counts(2*ell, ell, n, items))


def check_contradictions(item, raw, byteorder):
    """Direct original-monomial supersets, no native code or zeta transforms."""
    return contradiction_identity(2*item['ell'], item['ell'], item['n'],
                                  tuple(tuple(p) for p in item['reference_anf']), raw, byteorder)


@lru_cache(maxsize=64)
def contradiction_identity(x, y, equations, items, raw, byteorder):
    # Offline audit only: the full immutable ANF and proof bytes are the key.
    # Changed identities are always checked; timed queries never use this cache.
    return constant_identity_count(x, y, equations, items, raw, byteorder)


def audit_report(report, *, check_sources=True):
    assert report['schema'] == 'round34-affine-multipliers/1' and report['status'] == 'RECORDED'
    assert report['candidate_id'] is report['IC_online_ms'] is report['rho_online_ms'] is None
    arms = tuple(report['arms'])
    assert report['candidates'] == {}
    large = report['large_controls']
    assert type(large) is bool
    assert arms in ((LARGE_CPU_ARMS, LARGE_ARMS) if large else (CPU_ARMS, ARMS))
    shapes = LARGE_SHAPES if large else SHAPES
    assert report['limits'] == {
        'variables':27 if large else 20, 'roots':256, 'conditional_branch_bits':20,
        'producer_variables':30, 'certified_variables':30, 'checker_enumeration_budget':4194304,
        'checker_basis_budget':1000000, 'specialization_table_bytes':67108864,
        'enumeration_budget':4194304, 'residual_variables':10, 'native_replay_field_degree':63,
        'replay_requires_odd_degree':True, 'curve_sign_points':12, 'hard_wall_timeout':False,
        'sparse_root_limit':256, 'sparse_membership_budget':65536,
        'multiplier_work_budget':67108864, 'multiplier_branch_budget':65536, 'proof_bytes':67108864,
        'expanded_producer_enumeration_budget':134217728, 'expanded_checker_enumeration_budget':134217728}
    assert type(report['repetitions']) is int and 2 <= report['repetitions'] <= 101
    if check_sources:
        audit_sources(report)
    receipts = report['build_receipts']
    inputs = {}
    assert [(v['n'], v['m'], v['ell'], v['seed']) for v in report['inputs']] == shapes
    for item in report['inputs']:
        frozen = {k: v for k, v in item.items() if k not in ('fixture_ns', 'workload_sha256')}
        assert item['workload_sha256'] == digest(frozen) and item['name'] not in inputs
        original, curve, _, _ = mathematics(item['n'], item['m'], item['ell'], item['seed'])
        assert item['reference_anf'] == [list(p) for p in sorted(original.anf.items())]
        assert item['fixture_points'] == [vars(p) for p in original.points]
        assert item['target'] == vars(curve.sum(original.points))
        assert (item['mod'], item['b'], item['nvars']) == (original.mod, original.b, original.nvars)
        inputs[item['name']] = item
    proofs, groups, statuses = set(), {}, Counter()
    checked_proofs = {}
    payloads = {}
    for identifier, payload in report['proofs'].items():
        assert payload['byteorder'] in ('little', 'big')
        raw = base64.b64decode(payload['base64'], validate=True)
        assert type(payload['bytes']) is int and payload['bytes'] == len(raw)
        assert hashlib.sha256(raw).hexdigest() == identifier
        payloads[identifier] = raw
    branch_binaries = {version: {v for k, v in receipts[version]['binaries'].items()
                       if k in ('checker.so', 'checker.dylib')} for version in ('32', '33', '34')}
    branch_binaries['expanded'] = {v for k,v in receipts['34']['binaries'].items() if k in ('baseline-checker.so','baseline-checker.dylib')}
    exact_roots = {}
    for name,item in inputs.items():
        _,_,roots,_ = mathematics(item['n'],item['m'],item['ell'],item['seed'])
        if roots is None:
            # Establish completeness from independently expanded original-ANF
            # identities before trusting any reported producer/checker roots.
            candidates = [row[a]['result'] for row in report['rows'] if row['name']==name
                          for a in arms if a.startswith('quadratic-multiplier-') and row[a]['result'].get('verified')]
            if candidates:
                answer = candidates[0]
                roots = list(certify_roots(2*item['ell'],item['ell'],item['n'],
                    tuple(tuple(p) for p in item['reference_anf']),payloads[answer['proof_sha256']],answer['proof_byteorder'])[0])
        exact_roots[name] = roots
    verifier_binaries = {v for k, v in receipts['23']['binaries'].items()
                         if k in ('sparse-verifier.so', 'sparse-verifier.dylib')}
    for row in report['rows']:
        item = inputs[row['name']]
        _, curve, _, counts = mathematics(item['n'], item['m'], item['ell'], item['seed'])
        expected_roots = exact_roots[row['name']]
        assert row['workload_id'] == row['workload_sha256'] == item['workload_sha256']
        assert sorted(row['order']) == sorted(arms)
        assert type(row['repetition']) is int and row['warmup'] == (row['repetition'] == 0)
        group = groups.setdefault(row['name'], {})
        assert row['repetition'] not in group
        group[row['repetition']] = row
        for arm in arms:
            sample, answer = row[arm], row[arm]['result']
            statuses[arm+':'+answer['status']] += 1
            assert type(sample['wall_ns']) is int and sample['wall_ns'] > 0
            assert all(type(v) is int and v >= 0 for v in sample['phases_ns'].values())
            assert sample['wall_ns'] == sum(sample['phases_ns'].values())
            assert type(sample['cpu_ns']) is int and sample['cpu_ns'] >= 0
            if not answer.get('verified'):
                continue  # Retained failures cannot contribute a speedup.
            assert expected_roots is not None, 'a verified 27-variable row requires an independently checked completeness proof'
            assert answer['status'] == 'solved' and answer['complete'] and answer['groebner_verified']
            assert answer['query_arm'] == arm and answer['public_target'] == item['target']
            assert all(type(v) is int and v >= 0 for v in answer['phases_ns'].values())
            assert answer['complete_query_ns'] == sum(answer['phases_ns'].values())
            assert answer['complete_query_ns'] <= sample['phases_ns']['public_query']
            basis, certificate = answer['basis_terms'], answer['basis_certificate']
            assert answer['basis_sha256'] == hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()
            assert certificate['verified'] and certificate['ideal_equality'] and certificate['reduced_groebner_basis']
            multiplier = arm.startswith('quadratic-multiplier-')
            expanded = arm.startswith('quadratic-expanded-')
            narrow = multiplier or expanded or arm.startswith('quadratic-narrow-')
            branch_proof = narrow or arm.startswith('quadratic-proof-')
            version = '34' if multiplier or expanded else '33' if narrow else '32' if branch_proof else '31'
            generator_counts = counts
            if branch_proof:
                assert certificate['backend'] == ('independent-quadratic-multiplier-proof' if multiplier else 'independent-quadratic-contradiction-proof')
                identifier = answer['proof_sha256']
                assert answer['proof_byteorder'] == report['proofs'][identifier]['byteorder']
                key = (row['workload_id'], identifier, multiplier)
                if key not in checked_proofs:
                    checked_proofs[key] = (certify_roots(2*item['ell'],item['ell'],item['n'],
                        tuple(tuple(p) for p in item['reference_anf']),payloads[identifier],answer['proof_byteorder'])
                        if multiplier else check_contradictions(item,payloads[identifier],answer['proof_byteorder']))
                stats = certificate['stats']
                assert stats['proof_bytes'] == len(payloads[identifier])
                assert stats['branches'] == counts['branches']
                if multiplier:
                    independent_roots,constant_count,extended,assignments = checked_proofs[key]
                    assert list(independent_roots)==expected_roots
                    assert constant_count == counts['branches']-counts['consistent']
                    assert stats['contradictions']==constant_count+len(extended)
                    assert stats['extended_contradictions']==len(extended)
                    assert stats['enumerated_branches']==counts['consistent']-len(extended)
                    assert stats['assignments']==assignments
                    limbs=(item['n']+63)//64
                    assert stats['multiplier_words']==len(extended)*(item['ell']+1)*limbs
                    assert stats['multiplier_parities']==stats['multiplier_words']*(counts['features']+1)
                    assert math.isfinite(stats['multiplier_check']) and stats['multiplier_check']>=0
                    assert answer['proof_format']=='constant-prefix+affine-multiplier-records-v1'
                    generator,expected_multiplier = producer_model(2*item['ell'],item['ell'],item['n'],
                        tuple(tuple(p) for p in item['reference_anf']),tuple(expected_roots),extended)
                    generator_counts = dict(generator)
                    actual_multiplier = dict(answer['multiplier_stats'])
                    seconds = actual_multiplier.pop('seconds')
                    assert math.isfinite(seconds) and seconds>=0
                    assert actual_multiplier == dict(expected_multiplier)
                else:
                    assert stats['contradictions'] == checked_proofs[key] == counts['branches']-counts['consistent']
                    assert stats['enumerated_branches'] == counts['consistent']
                    assert stats['assignments'] == counts['consistent']*(1 << item['ell'])
                assert stats['roots'] == stats['standard'] == len(expected_roots)
                assert all(math.isfinite(stats[k]) and stats[k] >= 0 for k in ('specialization', 'contradiction_check', 'enumeration', 'basis_check'))
            else:
                assert certificate['backend'] == 'independent-packed-sparse-proof' and certificate['proof_stats']['mode'] == 2
            roots = certificate['solutions']
            assert roots == expected_roots
            assert certificate['root_count'] == certificate['standard_monomials'] == len(roots)
            proof = (row['workload_id'], answer['basis_sha256'], tuple(roots))
            if proof not in proofs:
                assert verify_basis(item['nvars'], item['reference_anf'], roots, basis, len(expected_roots))
                proofs.add(proof)
            metrics = answer['metrics']
            assert metrics['roots'] == len(roots)
            if arm != 'sparse':
                assert all(metrics[k] == v for k, v in generator_counts.items())
                assert metrics['standard'] == len(roots)
                assert all(type(v) is int and v >= 0 for k, v in metrics.items()
                           if k not in ('specialization', 'evaluation', 'interpolation', 'gpu_wall', 'gpu_device'))
                assert all(math.isfinite(metrics[k]) and metrics[k] >= 0 for k in
                           ('specialization', 'evaluation', 'interpolation', 'gpu_wall', 'gpu_device'))
                assert metrics['gpu_wall'] <= metrics['evaluation']
                assert answer['coefficient_copy'] is False
                metal = arm.endswith('-metal')
                supported = item['n'] <= 32 and counts['features'] <= 31
                assert metrics['gpu_used'] == int(metal and supported)
                assert metrics['gpu_shape_fallback'] == int(metal and not supported)
                assert answer['backend_requested'] == ('metal' if metal else 'cpu')
                if metal and supported:
                    assert not answer['device'].startswith('cpu') and metrics['gpu_wall'] > 0
                else:
                    assert answer['device'].startswith('cpu') and metrics['gpu_wall'] == metrics['gpu_device'] == 0
                if narrow:
                    producer_bytes = 4 if item['n'] <= 32 else 8 if item['n'] <= 64 else 16
                    checker_bytes = 4 if item['n'] <= 32 else 8
                    assert answer['producer_coefficient_word_bits'] == producer_bytes*8
                    assert answer['checker_coefficient_word_bits'] == certificate['coefficient_word_bits'] == checker_bytes*8
                    branches, stride, limbs = counts['branches'], counts['features']+1, (item['n']+63)//64
                    assert certificate['stats']['workspace_bytes'] == branches*stride*limbs*checker_bytes
                    expected_bytes = branches*stride*producer_bytes + branches*limbs*8
                    if multiplier:
                        expected_bytes += (answer['multiplier_stats']['proof_capacity_words']-branches*limbs)*8 + answer['multiplier_stats']['workspace_bytes']
                    if metal and supported:
                        expected_bytes += branches*stride*4 + branches*34*4 + 12
                    assert metrics['workspace_bytes'] == expected_bytes
                    assert metrics['transform_xors'] == 2*item['ell']*(branches//2)*stride
                    assert certificate['stats']['transform_xors'] == limbs*metrics['transform_xors']
                tag = '-metal' if metal else ''
                assert answer['binary_sha256'] in {v for k, v in receipts[version]['binaries'].items()
                                                  if k in (('baseline-' if expanded else '')+'producer'+tag+'.so', ('baseline-' if expanded else '')+'producer'+tag+'.dylib')}
            else:
                assert answer['binary_sha256'] in {v for k, v in receipts['20']['binaries'].items()
                                                  if '/round4/build/packed_dual.' in k}
            checking_binaries = branch_binaries['expanded' if expanded else version] if branch_proof else verifier_binaries
            assert answer['verifier_binary_sha256'] in checking_binaries
            assert answer['equation_binary_sha256'] in checking_binaries
            descent_binaries = ({v for k, v in receipts['32']['binaries'].items() if k in ('contraction.so', 'contraction.dylib')}
                                if item['nvars'] > 20 else receipts['14']['binaries'].values())
            assert answer['descent_binary_sha256'] in descent_binaries
            if item['n'] <= 63:
                assert answer['replay_backend'] == 'native-public-point'
                assert answer['replay_binary_sha256'] in receipts['17']['binaries'].values()
            else:
                assert answer['replay_backend'] == 'python-public-point-wide-field-fallback'
                assert answer['replay_binary_sha256'] is None
            assignment = answer['assignment']
            assert assignment in roots and evaluate(item['reference_anf'], assignment) == 0
            assert answer['assignments_checked'] == roots.index(assignment)+1
            points = [Point(**p) for p in answer['curve_witness']['points']]
            assert answer['curve_witness']['verified'] and answer['curve_witness']['code'] == 0
            assert [p.x for p in points] == [(assignment >> (j*item['ell'])) & ((1 << item['ell'])-1) for j in range(item['m'])]
            assert all(curve.on_curve(p) for p in points) and vars(curve.sum(points)) == item['target']
            assert sample['outside_timing_witness_audit']['verified']
        if all(row[a]['result'].get('verified') for a in arms):
            for key in ('basis_sha256', 'assignment', 'curve_witness'):
                assert all(row[a]['result'][key] == row[arms[0]]['result'][key] for a in arms)
    assert set(groups) == set(inputs)
    assert report['admission']['timed_attempts'] == len(report['rows'])*len(arms)
    assert report['admission']['logical_cpus'] == report['host']['logical_cpus']
    limit = report['admission']['max_load_per_cpu']
    assert math.isfinite(limit) and limit > 0
    for load in [report['admission']['load'], report['host']['load_end'],
                 *(r[k] for r in report['rows'] for k in ('load', 'load_end'))]:
        assert len(load) == 3 and all(math.isfinite(v) and v >= 0 for v in load)
    eligible = timing_eligible(report, report['host']['logical_cpus'], limit)
    assert report['timing_qualification']['eligible'] == eligible
    summaries = []
    for name, rows in groups.items():
        assert set(rows) == set(range(report['repetitions']+1))
        good = all(row[a]['result'].get('verified') for row in rows.values() for a in arms)
        summary = {'name': name, 'workload_id': inputs[name]['workload_sha256'], 'all_attempts_verified': good,
                   'timing_eligible': eligible, 'wins': {a: False for a in arms[1:]}}
        if good:
            measured = [r for rep, r in rows.items() if rep]
            summary['median_ms'] = {a: statistics.median(r[a]['wall_ns'] for r in measured)/1e6 for a in arms}
            if not large:
                summary['sparse_over_candidate'] = {a: ratio_interval([r['sparse']['wall_ns']/r[a]['wall_ns'] for r in measured]) for a in arms[1:]}
                summary['wins'] = {a: eligible and summary['sparse_over_candidate'][a]['bootstrap95'][0] > 1 for a in arms[1:]}
                summary['old_cpu_over_new_cpu'] = ratio_interval([r['quadratic-narrow-cpu']['wall_ns']/r['quadratic-multiplier-cpu']['wall_ns'] for r in measured])
                for metal in (a for a in arms if a.endswith('-metal')):
                    comparison = ratio_interval([min(r[a]['wall_ns'] for a in CPU_ARMS)/r[metal]['wall_ns'] for r in measured])
                    executed = all(r[metal]['result']['metrics']['gpu_used'] for r in measured)
                    summary[metal+'_versus_best_cpu'] = {**comparison, 'gpu_executed': executed,
                        'qualified_win': bool(eligible and executed and comparison['bootstrap95'][0] > 1)}
                if 'quadratic-multiplier-metal' in arms:
                    summary['old_metal_over_new_metal'] = ratio_interval([r['quadratic-narrow-metal']['wall_ns']/r['quadratic-multiplier-metal']['wall_ns'] for r in measured])
            else:
                comparison = ratio_interval([r['quadratic-expanded-cpu']['wall_ns']/r['quadratic-multiplier-cpu']['wall_ns'] for r in measured])
                summary['expanded_cpu_over_multiplier_cpu'] = {**comparison, 'qualified_win': bool(eligible and comparison['bootstrap95'][0]>1)}
                summary['baseline_scope'] = 'Previous exact algorithm with enumeration bounds expanded to 2^27; no global strongest-solver claim.'
                for metal in (a for a in arms if a.endswith('-metal')):
                    comparison = ratio_interval([min(r[a]['wall_ns'] for a in LARGE_CPU_ARMS)/r[metal]['wall_ns'] for r in measured])
                    executed = all(r[metal]['result']['metrics']['gpu_used'] for r in measured)
                    summary[metal+'_versus_best_cpu'] = {**comparison, 'gpu_executed': executed, 'qualified_win': bool(eligible and executed and comparison['bootstrap95'][0]>1)}
        summaries.append(summary)
    return {'schema': 'round34-audit/1', 'timing_eligible': eligible, 'statuses': dict(statuses),
            'unique_branch_proofs': len(checked_proofs), 'unique_exact_basis_proofs': len(proofs), 'controls': summaries,
            'scope': 'Frozen planted PDP controls; not full IC recovery or natural relation yield.'}


def audit(path):
    report = json.loads(gzip.decompress(Path(path).read_bytes()))
    restored, info = recover(str(path)+'.journal.gz')
    assert not info['truncated_tail'] and restored == report
    return audit_report(report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.report), indent=2))
