"""Reconstruct complete branch counts, exact bases and signed curve witnesses."""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import statistics

from branch_measure import ARMS, ROOT, HERE, digest, sources, timing_eligible
from branch_journal import recover
from reference import branch_counts, evaluate, verify_basis
from sparse_checker import Curve, GF2n, Point
from descend import make_instance

PREFIX='experiments/groebner-perf-20260924/'
SHAPES=[(n,2,10,s) for n in (31,63) for s in range(201,204)]+[
    (31,2,4,101),(11,2,3,101),(83,2,2,101)]


def ratio_interval(ratios):
    logs=[math.log(v) for v in ratios]
    rng=random.Random(2026092901)
    boot=sorted(math.exp(statistics.mean(rng.choices(logs,k=len(logs)))) for _ in range(2000))
    return {'pairs':len(logs),'paired_geomean':math.exp(statistics.mean(logs)),
            'bootstrap95':[boot[49],boot[1949]]}


def audit_sources(report):
    snapshot=report['source_snapshot']
    assert snapshot==sources(), 'audit requires the same trusted source checkout; never execute archived source'
    assert report['source_sha256']=={k:hashlib.sha256(v.encode()).hexdigest() for k,v in snapshot.items()}
    receipts=report['build_receipts']
    for version in ('17','18','20','23'):
        current=json.loads((HERE.parent/f'round{version}/build/receipt.json').read_text())
        assert receipts[version]['source_sha256']==current['source_sha256']
        for name,expected in receipts[version]['source_sha256'].items():
            assert report['source_sha256'][name]==expected
    assert receipts['14']['source_sha256']==report['source_sha256'][PREFIX+'round14/contraction.cpp']
    assert receipts['15']['ordered_source_sha256']==report['source_sha256'][PREFIX+'round15/ordered_certificate.cpp']
    for name,value in receipts['15']['reference_sha256'].items():
        assert value==report['source_sha256'][PREFIX+'round15/reference/'+name]
    expected={str(Path(k).name):v for k,v in report['source_sha256'].items()
              if k.startswith(PREFIX+'round27/')}
    assert receipts['27']['sources']==expected
    # Regenerate the frozen independent verifier glue from trusted generation code.
    spec=importlib.util.spec_from_file_location('round27_sparse_build',HERE.parent/'round23/build.py')
    build=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    assert receipts['23']['generated_sha256']=={
        k:hashlib.sha256(v.encode()).hexdigest() for k,v in build.generated_sources(snapshot).items()}
    reference=snapshot[PREFIX+'round15/reference/boolean_certificate.cpp']
    helpers=reference.split('extern "C" int boolean_certificate(',1)[0]
    checks='        out->roots = alive;'+reference.split('        out->roots = alive;',1)[1].split(
        '    } catch (const std::invalid_argument&)',1)[0]
    assert receipts['18']['generated_sha256']=={k:hashlib.sha256(v.encode()).hexdigest()
        for k,v in (('certificate_helpers.inc',helpers),('basis_checks.inc',checks))}


def audit_report(report, *, check_sources=True):
    assert report['schema']=='round27-conditional-linear/1'
    assert report['status']=='RECORDED'
    assert report['candidate_id'] is report['IC_online_ms'] is report['rho_online_ms'] is None
    assert report['candidates']=={} and tuple(report['arms'])==ARMS
    if check_sources:
        audit_sources(report)
    receipts=report['build_receipts']
    inputs, mathematics={},{}
    assert len(report['inputs'])==len(SHAPES)
    assert [(v['n'],v['m'],v['ell'],v['seed']) for v in report['inputs']]==SHAPES
    for item in report['inputs']:
        frozen={k:v for k,v in item.items() if k not in ('fixture_ns','workload_sha256')}
        assert item['workload_sha256']==digest(frozen)
        assert item['name'] not in inputs
        original=make_instance(item['n'],item['m'],item['ell'],seed=item['seed'])
        curve=Curve(GF2n(original.n,original.mod),original.b)
        assert item['reference_anf']==[list(p) for p in sorted(original.anf.items())]
        assert item['fixture_points']==[vars(p) for p in original.points]
        assert item['target']==vars(curve.sum(original.points))
        assert (item['mod'],item['b'],item['nvars'])==(original.mod,original.b,original.nvars)
        counts=branch_counts(item['ell'],item['ell'],item['n'],item['reference_anf'])
        mathematics[item['name']]=(counts,curve)
        inputs[item['name']]=item
    proofs,groups,statuses=set(),{},Counter()
    for row in report['rows']:
        item=inputs[row['name']]
        assert row['workload_id']==row['workload_sha256']==item['workload_sha256']
        assert sorted(row['order'])==sorted(ARMS)
        assert type(row['repetition']) is int and row['warmup']==(row['repetition']==0)
        group=groups.setdefault(row['name'],{})
        assert row['repetition'] not in group
        group[row['repetition']]=row
        counts,curve=mathematics[row['name']]
        for arm in ARMS:
            sample=row[arm]
            answer=sample['result']
            statuses[arm+':'+answer['status']]+=1
            assert type(sample['wall_ns']) is int and sample['wall_ns']>0
            assert all(type(v) is int and v>=0 for v in sample['phases_ns'].values())
            assert sample['wall_ns']==sum(sample['phases_ns'].values())
            assert type(sample['cpu_ns']) is int and sample['cpu_ns']>=0
            if not answer.get('verified'):
                continue
            assert answer['status']=='solved' and answer['complete'] and answer['groebner_verified']
            assert answer['query_arm']==arm and answer['public_target']==item['target']
            assert all(type(v) is int and v>=0 for v in answer['phases_ns'].values())
            assert answer['complete_query_ns']==sum(answer['phases_ns'].values())
            assert answer['complete_query_ns']<=sample['phases_ns']['public_query']
            basis=answer['basis_terms']
            assert answer['basis_sha256']==hashlib.sha256(json.dumps(basis,sort_keys=True).encode()).hexdigest()
            certificate=answer['basis_certificate']
            assert certificate['verified'] and certificate['ideal_equality'] and certificate['reduced_groebner_basis']
            roots=certificate['solutions']
            assert certificate['root_count']==certificate['standard_monomials']==len(roots)==counts['root_count']
            proof=(row['workload_id'],answer['basis_sha256'],tuple(roots))
            if proof not in proofs:
                assert verify_basis(item['nvars'],item['reference_anf'],roots,basis,counts['root_count'])
                proofs.add(proof)
            if arm=='conditional-linear':
                assert certificate['backend']=='independent-equation-row-elimination' and certificate['code']==0
                assert certificate['stats']['branches']==answer['metrics']['branches']==1<<item['ell']
                assert certificate['stats']['roots']==answer['metrics']['roots']==len(roots)
                assert certificate['stats']['standard']==answer['metrics']['standard']==len(roots)
                expected_consistent=sum(v['branches'] for v in counts['histogram'] if v['status']=='consistent')
                assert certificate['stats']['consistent']==answer['metrics']['consistent']==expected_consistent
                assert certificate['stats']['work']<=1000000
                for stats in (certificate['stats'],answer['metrics']):
                    assert all(type(stats[k]) is int and stats[k]>=0 for k in ('branches','consistent','roots','standard','work'))
                    assert all(math.isfinite(stats[k]) and stats[k]>=0 for k in ('evaluation','interpolation'))
                assert answer['coefficient_copy'] is False
                assert answer['binary_sha256'] in {v for k,v in receipts['27']['binaries'].items()
                                                   if k in ('producer.so','producer.dylib')}
                expected_binary={v for k,v in receipts['27']['binaries'].items() if k in ('checker.so','checker.dylib')}
            else:
                assert certificate['backend']=='independent-packed-sparse-proof'
                assert certificate['proof_stats']['mode']==2
                assert answer['metrics']['roots']==len(roots)
                assert answer['binary_sha256'] in {v for k,v in receipts['20']['binaries'].items()
                                                   if '/round4/build/packed_dual.' in k}
                expected_binary={v for k,v in receipts['23']['binaries'].items() if k in ('sparse-verifier.so','sparse-verifier.dylib')}
            assert answer['verifier_binary_sha256'] in expected_binary
            assert answer['equation_binary_sha256'] in expected_binary
            assert answer['descent_binary_sha256'] in receipts['14']['binaries'].values()
            if item['n']<=63:
                assert answer['replay_backend']=='native-public-point'
                assert answer['replay_binary_sha256'] in receipts['17']['binaries'].values()
            else:
                assert answer['replay_backend']=='python-public-point-wide-field-fallback'
                assert answer['replay_binary_sha256'] is None
            assignment=answer['assignment']
            assert assignment in roots and evaluate(item['reference_anf'],assignment)==0
            assert answer['assignments_checked']==roots.index(assignment)+1
            # Check the signed public-point witness with the original Python field.
            points=[Point(**p) for p in answer['curve_witness']['points']]
            assert answer['curve_witness']['verified'] and answer['curve_witness']['code']==0
            assert [p.x for p in points]==[(assignment>>(j*item['ell']))&((1<<item['ell'])-1) for j in range(2)]
            assert all(curve.on_curve(p) for p in points) and vars(curve.sum(points))==item['target']
            assert sample['outside_timing_witness_audit']['verified']
        if all(row[a]['result'].get('verified') for a in ARMS):
            for key in ('basis_sha256','assignment','curve_witness'):
                assert row[ARMS[0]]['result'][key]==row[ARMS[1]]['result'][key]
    assert set(groups)==set(inputs)
    assert report['admission']['timed_attempts']==len(report['rows'])*len(ARMS)
    assert report['admission']['logical_cpus']==report['host']['logical_cpus']
    eligible=timing_eligible(report,report['host']['logical_cpus'],report['admission']['max_load_per_cpu'])
    assert report['timing_qualification']['eligible']==eligible
    summaries=[]
    for name,rows in groups.items():
        assert set(rows)==set(range(report['repetitions']+1))
        good=all(row[a]['result'].get('verified') for row in rows.values() for a in ARMS)
        summary={'name':name,'workload_id':inputs[name]['workload_sha256'],'all_attempts_verified':good,
                 'candidate_win':False,'timing_eligible':eligible}
        if good:
            measured=[r for rep,r in rows.items() if rep]
            summary['median_ms']={a:statistics.median(r[a]['wall_ns'] for r in measured)/1e6 for a in ARMS}
            summary['sparse_over_conditional']=ratio_interval(
                [r['sparse']['wall_ns']/r['conditional-linear']['wall_ns'] for r in measured])
            summary['candidate_win']=eligible and summary['sparse_over_conditional']['bootstrap95'][0]>1
        summaries.append(summary)
    return {'schema':'round27-audit/1','timing_eligible':eligible,'statuses':dict(statuses),
            'unique_exact_basis_proofs':len(proofs),'controls':summaries,
            'scope':'Frozen planted PDP controls; not full IC recovery or natural relation yield.'}


def audit(path):
    report=json.loads(gzip.decompress(Path(path).read_bytes()))
    restored,info=recover(str(path)+'.journal.gz')
    assert not info['truncated_tail'] and restored==report
    return audit_report(report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    args=parser.parse_args()
    print(json.dumps(audit(args.report),indent=2))
