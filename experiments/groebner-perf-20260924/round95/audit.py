"""Native-free rechecking of complete query results and paired cost boundaries."""
import argparse
from dataclasses import replace
import datetime
from functools import lru_cache
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from build import source_paths
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'round5'),str(HERE.parent.parent/'pdp-scaling')]
from algebraic_certificate import verify
from boolean_basis import certify_boolean_basis
from descend import make_instance,verify_solution
spec=importlib.util.spec_from_file_location('lifetime_oracle94',HERE.parent/'round94/audit.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
FIXTURE_SHA='618bd6d141a06ce55fdeb3e6fc72f4903fc83e3d2ee317dfbcde5b25a78548cf'
ARMS={'legacy':('legacy','baseline'),'completion':('completion-first','baseline'),
      'release-cumulative':('completion-first','release-cumulative'),'release-live':('completion-first','release-live')}
PHASES={'descent_ns','algebra_and_certificate_ns','extraction_and_curve_ns','reference_replay_and_teardown_ns'}

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def counters(stats):return {k:v for k,v in stats.items() if not k.endswith('seconds')}
def nonnegative(value):return type(value) in (int,float) and math.isfinite(value) and value>=0

@lru_cache(maxsize=128)
def reference(encoded):
    case=json.loads(encoded)
    # build_anf=False does not load any pickle or trust a downloaded cache.
    original=make_instance(case['n'],case['m'],case['ell'],seed=case['seed'],build_anf=False)
    assert (original.mod,original.b,original.xR)==(case['mod'],case['b'],case['target_x'])
    anf={}
    for i,row in enumerate(case['equations']):
        for mask in row:anf[mask]=anf.get(mask,0)^(1<<i)
    return replace(original,anf=anf)

@lru_cache(maxsize=256)
def mathematical_check(encoded):
    n,rows,basis,proof=json.loads(encoded)
    checked=verify(n,rows,basis,proof,max_work=200_000_000,max_retained_terms=20_000_000)
    assert checked['verified'],checked
    if n<=12:assert certify_boolean_basis(n,rows,basis,monomial_cache=True)['verified']
    return oracle.expected_liveness(rows,proof['nodes'],proof['outputs'])

@lru_cache(maxsize=128)
def solution_check(encoded,assignment):
    original=reference(encoded)
    return original.evaluate(assignment)==0 and verify_solution(original,assignment)

def audit(report,*,current_sources=True):
    plan=json.loads((HERE/'panel.json').read_text())
    fixture=HERE.parent/'round13/results/confirmation.json.gz'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest()==FIXTURE_SHA==plan['fixture_sha256']
    cases=json.loads(gzip.decompress(fixture.read_bytes()))['inputs']
    assert report['schema']=='complete-query-certification-evidence/1'
    assert report['plan']==plan and report['plan_sha256']==digest(plan)
    assert report['timing_eligible'] is False
    assert all(report[k] is None for k in ('qualified_speedup','aggregate_speedup','online_speedup'))
    build=report['build']
    assert build['schema']=='complete-query-checker-build/1'
    assert set(build['sources'])=={str(p.relative_to(HERE.parent.parent)) for p in source_paths()}
    assert len(build['binaries'])==12
    assert {p.split('.')[0] for p in build['binaries']}=={n+s for n in ('packed_producer','native_checker','macaulay','packed_dual','scheduled_checker','live_checker') for s in ('','-ubsan')}
    assert set(build['resources'])=={'summation-polynomials.json','sumpoly_cache.pkl'} and build['polynomial_degree']==4
    assert set(build['generated'])=={'engine.inc','adapter.cpp','f5_reference.py','scheduled_checker.cpp','live_checker.cpp'}
    for value in [*build['sources'].values(),*build['binaries'].values(),*build['generated'].values(),*build['resources'].values()]:
        assert isinstance(value,str) and len(value)==64 and set(value)<=set('0123456789abcdef')
    if current_sources:
        for name,sha in build['sources'].items():
            p=(HERE.parent.parent/name).resolve()
            assert p.is_relative_to(HERE.parents[2]) and hashlib.sha256(p.read_bytes()).hexdigest()==sha,name
    assert type(report['controls']) is bool
    modes=[False,True] if report['controls'] else [False]
    rows=iter(report['rows']);preparations=iter(report['preparation']);last_end=None;proofs=set()
    counts=dict(algebra_verified=0,pdp_verified=0,unsuccessful=0,producer_pairs=0,checker_counter_pairs=0,verified_lifetimes=0)
    for sanitized in modes:
        prep=next(preparations)
        assert prep['sanitized'] is sanitized and prep['cases']==[c['name'] for c in cases]
        assert nonnegative(prep['seconds']) and prep['numerical_training'] is False
        assert prep['plans']==12 and prep['workspaces']==32
        for case in cases:
            encoded_case=json.dumps(case,sort_keys=True);n=case['nvars'];equations=case['equations']
            reference_basis=None
            for repetition,order in enumerate([plan['arms']] if report['controls'] else plan['orders']):
                paired={}
                for arm in order:
                    row=next(rows);r=row['result'];paired[arm]=r
                    assert (row['name'],row['repetition'],row['arm'])==(case['name'],repetition,arm)
                    assert row['fixture']==case and row['input_sha256']==digest(case) and row['sanitized'] is sanitized
                    assert row['role']==('control' if report['controls'] else ('warmup' if repetition<plan['warmup_rounds'] else 'observation'))
                    start=datetime.datetime.fromisoformat(row['wall_start']);end=datetime.datetime.fromisoformat(row['wall_end'])
                    assert end>=start and (last_end is None or start>=last_end);last_end=end
                    assert set(row['phases'])==PHASES and all(type(v) is int and v>=0 for v in row['phases'].values())
                    assert type(row['wall_ns']) is int and row['wall_ns']==sum(row['phases'].values())
                    assert nonnegative(r['total_seconds']) and r['timing_eligible'] is False and r['qualified_speedup'] is None
                    schedule,policy=ARMS[arm]
                    assert r['checker_order']==schedule and r['retention_policy']==policy and r['layout_policy']=='none'
                    assert type(r['verified']) is bool and type(r['algebra_verified']) is bool
                    assert r['complete'] is r['algebra_verified']
                    attempts=r['attempts'];assert len(attempts)==1 and attempts[0]['kind']=='fresh-f4'
                    a=attempts[0];cert=a.get('certificate',{})
                    assert a['stats']['status'] in (0,1,2,3) and all(nonnegative(v) for v in a['stats'].values())
                    assert r['work']==a['stats']['work'] and 0<=r['work']<=plan['limits']['max_work']
                    assert r['check_work']==cert.get('stats',{}).get('work',0) and 0<=r['check_work']<=plan['limits']['max_check_work']
                    assert r['algebra_verified'] is a['verified'] and a['verified'] is cert.get('verified',False)
                    if cert:
                        assert cert['schedule']==schedule and cert['retention_policy']==policy
                        assert all(nonnegative(v) for v in cert['stats'].values())
                        if policy!='baseline':
                            live=cert['liveness']
                            assert set(live)=={'planning_work','metadata_bytes','live_terms','peak_terms','released_terms','released_nodes'}
                            assert all(type(v) is int and v>=0 for v in live.values())
                            assert live['live_terms']+live['released_terms']==cert['stats']['retained_terms']
                            assert live['peak_terms']>=live['live_terms'] and live['released_nodes']<=cert['stats']['proof_nodes']
                            assert live['planning_work']<=cert['stats']['work']
                    if r['algebra_verified']:
                        counts['algebra_verified']+=1
                        assert a['stats']['status']==0 and cert['status']=='verified'
                        assert cert['ideal_equality'] is True and cert['reduced_groebner_basis'] is True
                        assert r['certificate']==cert
                        encoded=json.dumps([n,equations,r['basis'],r['proof']],sort_keys=True)
                        expected,total=mathematical_check(encoded);proofs.add(digest(json.loads(encoded)))
                        if policy!='baseline':
                            assert cert['liveness']==expected and cert['stats']['retained_terms']==total
                            counts['verified_lifetimes']+=1
                        basis=sorted(tuple(sorted(row)) for row in r['basis'])
                        if reference_basis is None:reference_basis=basis
                        assert basis==reference_basis
                        if case['boundary']=='pdp':
                            assert 0<r['assignments_visited']<=1<<n and 0<r['roots_replayed']<=r['assignments_visited']
                            if r['verified']:
                                assignment=r['assignment']
                                assert type(assignment) is int and 0<=assignment<1<<n
                                assert r['assignments_visited']==assignment+1
                                assert all(sum((m&assignment)==m for m in row)%2==0 for row in r['basis'])
                                assert r['curve_replay'] is True and r['reference_equations_and_curve_replay'] is True
                                assert solution_check(encoded_case,assignment)
                                assert r['status']=='solved';counts['pdp_verified']+=1
                            else:
                                assert r['status'] in ('gb-no-verified-solution','reference-replay-failed')
                                counts['unsuccessful']+=1
                        else:assert r['verified'] is True and r['status']=='gb'
                    else:
                        assert r['verified'] is False and 'basis' not in r and 'proof' not in r and 'assignment' not in r
                        assert r['status'] in ('inconclusive','rejected','invalid-input','producer-failure')
                        counts['unsuccessful']+=1
                left=paired['legacy']
                for arm in plan['arms'][1:]:
                    right=paired[arm]
                    assert counters(left['attempts'][0]['stats'])==counters(right['attempts'][0]['stats'])
                    assert left['work']==right['work'];counts['producer_pairs']+=1
                    if left['algebra_verified'] and right['algebra_verified']:
                        assert (left['basis'],left['proof'])==(right['basis'],right['proof'])
                        ls=counters(left['certificate']['stats']);rs=counters(right['certificate']['stats'])
                        if arm.startswith('release-'):rs['work']-=right['certificate']['liveness']['planning_work']
                        assert ls==rs;counts['checker_counter_pairs']+=1
                        if case['boundary']=='pdp':
                            assert (left['status'],left.get('assignment'),left['assignments_visited'],left['roots_replayed'])==(right['status'],right.get('assignment'),right['assignments_visited'],right['roots_replayed'])
    assert next(rows,None) is None and next(preparations,None) is None
    assert report['status']=='RECORDED_PENDING_AUDIT'
    return dict(status='PASS',rows=len(report['rows']),preparations=len(report['preparation']),unique_mathematical_checks=len(proofs),
        **counts,native_binaries_loaded=False,timing_eligible=False,qualified_speedup=None,online_speedup=None)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('report',type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();result=audit(json.loads(args.report.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
