"""Native-free mathematics, proof custody and complete-query frontier accounting."""
import argparse
import datetime
from functools import lru_cache
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from build import source_paths
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('oracle99_for100',HERE.parent/'round99/audit.py')
sorting=importlib.util.module_from_spec(spec);spec.loader.exec_module(sorting)
oracle=sorting.oracle

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def finite(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
def trace(value):return sorting.trace(value)

@lru_cache(maxsize=256)
def mathematics(n,rows,basis,proof_bytes,limits):
    polynomials=json.loads(rows);output=json.loads(basis);proof=json.loads(proof_bytes)
    checked=oracle.verify(n,polynomials,output,proof,**json.loads(limits))
    assert checked['verified'],checked
    assert oracle.certify_boolean_basis(n,polynomials,output,monomial_cache=True)['verified']
    return oracle.oracle.expected_liveness(polynomials,proof['nodes'],proof['outputs'])

def proof_bytes(folder,sha):
    assert isinstance(sha,str) and len(sha)==64 and set(sha)<=set('0123456789abcdef')
    path=folder/'proofs'/(sha+'.json');assert not path.is_symlink() and path.resolve().is_relative_to(folder.resolve())
    data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==sha
    return data

def audit(report,folder,*,current_sources=True):
    folder=Path(folder);plan=json.loads((HERE/'panel.json').read_text())
    fixture=HERE.parent/'round13/results/confirmation.json.gz'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest()==oracle.FIXTURE_SHA==plan['fixture_sha256']
    all_cases=json.loads(gzip.decompress(fixture.read_bytes()))['inputs']
    cases=[next(c for c in all_cases if c['name']==name) for name in plan['cases']]
    assert report['schema']=='completion-frontier-evidence/1' and report['plan']==plan and report['plan_sha256']==digest(plan)
    assert type(report['controls']) is bool and report['timing_eligible'] is False
    assert report['gpu']=={'devices':[],'backend':'host'}
    assert all(report[k] is None for k in ('qualified_speedup','aggregate_speedup','online_speedup'))
    build=report['build'];assert build['schema']=='completion-frontier-build/1'
    assert len(build['binaries'])==18 and len(build['executables'])==2 and len(build['commands'])==20
    assert {p.split('.')[0] for p in build['binaries']}=={name+suffix for name in ('packed_producer','native_checker','macaulay','packed_dual','scheduled_checker','live_checker','radix_keys','radix_radix','radix_tiny') for suffix in ('','-ubsan')}
    assert set(build['executables'])=={'radix_controls.exe','radix_controls-ubsan.exe'}
    assert set(build['sources'])=={str(p.relative_to(HERE.parent.parent)) for p in source_paths()}
    assert set(build['resources'])=={'summation-polynomials.json','sumpoly_cache.pkl'} and build['polynomial_degree']==4
    assert set(build['generated'])=={'adapter.cpp','engine.inc','f5_reference.py','scheduled_checker.cpp','live_checker.cpp',*[f'radix_{a}.cpp' for a in ('keys','radix','tiny')],*[f'f4_radix_{a}.inc' for a in ('keys','radix','tiny')]}
    for group in ('sources','binaries','executables','generated','resources'):
        for name,sha in build[group].items():
            assert isinstance(sha,str) and len(sha)==64 and set(sha)<=set('0123456789abcdef')
            if current_sources and group=='sources':
                path=(HERE.parent.parent/name).resolve();assert path.is_relative_to(HERE.parents[2])
                assert hashlib.sha256(path.read_bytes()).hexdigest()==sha,name
    rows=iter(report['rows']);last_end=None;seen={};proofs=set();consumed=0
    counts=dict(algebra_verified=0,pdp_verified=0,unsuccessful=0,execution_failures=0,exact_trace_pairs=0,verified_lifetimes=0)
    for sanitized in ([False,True] if report['controls'] else [False]):
        for case in cases:
            for budget in plan['budgets']:
                limits={**plan['limits'],'max_work':budget}
                for repetition,order in enumerate([plan['arms']] if report['controls'] else plan['orders']):
                    paired={}
                    for arm in order:
                        row=next(rows)
                        assert row['cell']==f'{consumed:04d}';consumed+=1
                        assert (row['name'],row['budget'],row['repetition'],row['arm'])==(case['name'],budget,repetition,arm)
                        assert row['fixture']==case and row['input_sha256']==digest(case) and row['limits']==limits
                        assert row['sanitized'] is sanitized
                        assert row['role']==('control' if report['controls'] else ('warmup' if repetition<plan['warmup_rounds'] else 'observation'))
                        start=datetime.datetime.fromisoformat(row['wall_start']);end=datetime.datetime.fromisoformat(row['wall_end'])
                        assert end>=start and (last_end is None or start>=last_end);last_end=end
                        assert type(row['process_elapsed_ns']) is int and row['process_elapsed_ns']>0
                        assert type(row['exit_code']) is int
                        if row['execution']!='completed':
                            assert row['execution'] in ('timeout','process-failure')
                            if row['execution']=='process-failure':assert row['exit_code']!=0
                            assert not any(k in row for k in ('result','wall_ns','phases'))
                            if row['execution']=='timeout':assert row['process_elapsed_ns']>=plan['worker_timeout_seconds']*10**9
                            counts['execution_failures']+=1;continue
                        assert row['exit_code']==0
                        assert row['preparation']==dict(cases=plan['cases'],plans=9,workspaces=3)
                        assert finite(row['preparation_seconds']) and type(row['process_peak_rss_bytes']) is int and row['process_peak_rss_bytes']>0
                        assert set(row['phases'])==oracle.PHASES and all(type(v) is int and v>=0 for v in row['phases'].values())
                        assert type(row['wall_ns']) is int and row['wall_ns']==sum(row['phases'].values()) and row['wall_ns']<=row['process_elapsed_ns']
                        r=row['result'];paired[arm]=r
                        assert r['monomial_sort_policy']==arm and r['checker_order']=='completion-first'
                        assert r['retention_policy']=='release-live' and r['layout_policy']=='none'
                        assert r['timing_eligible'] is False and r['qualified_speedup'] is None and finite(r['total_seconds'])
                        assert type(r['verified']) is bool and type(r['algebra_verified']) is bool and r['complete'] is r['algebra_verified']
                        assert len(r['attempts'])==1 and r['attempts'][0]['kind']=='fresh-f4'
                        a=r['attempts'][0];cert=a.get('certificate',{})
                        assert r['work']==a['stats']['work'] and 0<=r['work']<=budget
                        assert r['check_work']==cert.get('stats',{}).get('work',0) and 0<=r['check_work']<=limits['max_check_work']
                        assert all(finite(v) for v in a['stats'].values()) and a['stats']['status'] in (0,1,2,3)
                        assert r['algebra_verified'] is a['verified'] and a['verified'] is cert.get('verified',False)
                        if cert:
                            assert cert['schedule']=='completion-first' and cert['retention_policy']=='release-live'
                            assert all(finite(v) for v in cert['stats'].values())
                            live=cert['liveness']
                            assert all(type(v) is int and v>=0 for v in live.values())
                            assert live['live_terms']+live['released_terms']==cert['stats']['retained_terms']
                            assert live['peak_terms']>=live['live_terms'] and live['planning_work']<=cert['stats']['work']
                        if arm!='baseline':
                            values=sorting.sorting_check(r,arm);key=(case['name'],budget,arm)
                            if key in seen:assert seen[key]==values
                            else:seen[key]=values
                        else:assert 'monomial_order' not in r and 'monomial_radix' not in r
                        if r['algebra_verified']:
                            counts['algebra_verified']+=1
                            assert r['certificate']==cert and cert['status']=='verified' and a['stats']['status']==0
                            assert cert['ideal_equality'] is True and cert['reduced_groebner_basis'] is True
                            assert 'proof' not in r
                            data=proof_bytes(folder,r['proof_sha256'])
                            expected,total=mathematics(case['nvars'],json.dumps(case['equations']),json.dumps(r['basis']),data,json.dumps(plan['audit_limits']))
                            assert cert['liveness']==expected and cert['stats']['retained_terms']==total
                            assert live['peak_terms']<=limits['max_terms']
                            counts['verified_lifetimes']+=1;proofs.add(digest([case['nvars'],case['equations'],r['basis'],r['proof_sha256']]))
                            if case['boundary']=='pdp':
                                assert r['verified'] is True and r['status']=='solved'
                                assignment=r['assignment'];assert type(assignment) is int and 0<=assignment<1<<case['nvars']
                                assert r['assignments_visited']==assignment+1 and 0<r['roots_replayed']<=r['assignments_visited']
                                assert r['curve_replay'] is True and r['reference_equations_and_curve_replay'] is True
                                assert oracle.solution_check(json.dumps(case,sort_keys=True),assignment);counts['pdp_verified']+=1
                            else:assert r['verified'] is True and r['status']=='gb'
                        else:
                            assert r['verified'] is False and not any(k in r for k in ('basis','proof','proof_sha256','assignment'))
                            assert r['status']=='inconclusive';counts['unsuccessful']+=1
                    if 'baseline' in paired:
                        for arm in ('keys','radix'):
                            if arm in paired:assert trace(paired['baseline'])==trace(paired[arm]);counts['exact_trace_pairs']+=1
                    if 'keys' in paired and 'radix' in paired:assert paired['keys']['monomial_order']==paired['radix']['monomial_order']
    assert next(rows,None) is None and report['status']=='RECORDED_PENDING_AUDIT'
    return dict(status='PASS',rows=consumed,unique_mathematical_checks=len(proofs),unique_sorting_records=len(seen),**counts,
        native_binaries_loaded=False,timing_eligible=False,qualified_speedup=None,online_speedup=None)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();result=audit(json.loads(a.report.read_text()),a.report.parent)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
