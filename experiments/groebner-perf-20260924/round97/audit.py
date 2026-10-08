"""Native-free mathematics, exact traces and bounded scratch accounting."""
import argparse
import datetime
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from build import source_paths
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('oracle95_for96',HERE.parent/'round95/audit.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
CAPS={'fresh':0,'scratch':32768,'tiny':4}
NAMES=('calls','completed','charged_terms','fresh_vectors','growths','reused','oversized_releases','released_capacity_words','peak_scratch_capacity','peak_retained_scratch_capacity','overflow')

def trace(value):
    if isinstance(value,dict):return {k:trace(v) for k,v in value.items() if not k.endswith('seconds') and k not in ('normal_scratch','normal_storage_policy')}
    if isinstance(value,list):return [trace(v) for v in value]
    return value
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def finite(value):return type(value) in (int,float) and math.isfinite(value) and value>=0

def storage_check(result,arm):
    stats=result['normal_scratch'];cap=CAPS[arm]
    assert set(stats)==set(NAMES) and all(type(v) is int and 0<=v<1<<64 for v in stats.values())
    assert stats['overflow']==0 and stats['completed']<=stats['calls']
    assert stats['calls']==stats['fresh_vectors']+stats['growths']+stats['reused']
    assert stats['charged_terms']<=result['work']
    assert stats['peak_retained_scratch_capacity']<=cap and stats['peak_retained_scratch_capacity']<=stats['peak_scratch_capacity']
    assert stats['oversized_releases']<=stats['completed']
    if arm=='fresh':assert stats['fresh_vectors']==stats['calls'] and stats['growths']==stats['reused']==0
    return stats

def audit(report,*,current_sources=True):
    plan=json.loads((HERE/'panel.json').read_text());fixture=HERE.parent/'round13/results/confirmation.json.gz'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest()==oracle.FIXTURE_SHA==plan['fixture_sha256']
    cases=json.loads(gzip.decompress(fixture.read_bytes()))['inputs']
    assert report['schema']=='normal-scratch-evidence/1' and report['plan']==plan and report['plan_sha256']==digest(plan)
    assert type(report['controls']) is bool and report['timing_eligible'] is False
    assert all(report[k] is None for k in ('qualified_speedup','aggregate_speedup','online_speedup'))
    build=report['build'];assert build['schema']=='normal-scratch-build/1'
    assert len(build['binaries'])==18 and len(build['executables'])==2 and len(build['commands'])==20
    assert {p.split('.')[0] for p in build['binaries']}=={name+suffix for name in ('packed_producer','native_checker','macaulay','packed_dual','scheduled_checker','live_checker','normal_fresh','normal_scratch','normal_tiny') for suffix in ('','-ubsan')}
    assert set(build['executables'])=={'normal_controls.exe','normal_controls-ubsan.exe'}
    assert set(build['sources'])=={str(p.relative_to(HERE.parent.parent)) for p in source_paths()}
    assert set(build['resources'])=={'summation-polynomials.json','sumpoly_cache.pkl'}
    assert build['polynomial_degree']==4
    assert set(build['generated'])=={'adapter.cpp','engine.inc','f5_reference.py','scheduled_checker.cpp','live_checker.cpp',*[f'normal_{a}.cpp' for a in CAPS],*[f'f4_normal_{a}.inc' for a in CAPS]}
    for group in ('sources','binaries','executables','generated','resources'):
        for name,sha in build[group].items():
            assert isinstance(sha,str) and len(sha)==64 and set(sha)<=set('0123456789abcdef')
            if current_sources and group=='sources':
                p=(HERE.parent.parent/name).resolve();assert p.is_relative_to(HERE.parents[2])
                assert hashlib.sha256(p.read_bytes()).hexdigest()==sha,name
    rows=iter(report['rows']);preparations=iter(report['preparation']);last_end=None;proofs=set();seen_storage={};pairs=0;verified=pdp=failed=0
    for sanitized in ([False,True] if report['controls'] else [False]):
        prep=next(preparations)
        assert prep['sanitized'] is sanitized and prep['cases']==[c['name'] for c in cases]
        assert finite(prep['seconds']) and prep['numerical_training'] is False and prep['plans']==12 and prep['workspaces']==32
        for case in cases:
            for repetition,order in enumerate([plan['arms']] if report['controls'] else plan['orders']):
                paired={}
                for arm in order:
                    row=next(rows);r=row['result'];paired[arm]=r
                    assert (row['name'],row['repetition'],row['arm'])==(case['name'],repetition,arm)
                    assert row['fixture']==case and row['input_sha256']==digest(case) and row['sanitized'] is sanitized
                    assert row['role']==('control' if report['controls'] else ('warmup' if repetition<plan['warmup_rounds'] else 'observation'))
                    start=datetime.datetime.fromisoformat(row['wall_start']);end=datetime.datetime.fromisoformat(row['wall_end'])
                    assert end>=start and (last_end is None or start>=last_end);last_end=end
                    assert set(row['phases'])==oracle.PHASES and all(type(v) is int and v>=0 for v in row['phases'].values())
                    assert type(row['wall_ns']) is int and row['wall_ns']==sum(row['phases'].values())
                    assert r['normal_storage_policy']==arm
                    assert r['checker_order']=='legacy' and r['retention_policy']=='baseline' and r['layout_policy']=='none'
                    assert r['timing_eligible'] is False and r['qualified_speedup'] is None and finite(r['total_seconds'])
                    assert type(r['verified']) is bool and type(r['algebra_verified']) is bool and r['complete'] is r['algebra_verified']
                    assert len(r['attempts'])==1 and r['attempts'][0]['kind']=='fresh-f4'
                    a=r['attempts'][0];cert=a.get('certificate',{})
                    assert r['work']==a['stats']['work'] and 0<=r['work']<=plan['limits']['max_work']
                    assert r['check_work']==cert.get('stats',{}).get('work',0) and 0<=r['check_work']<=plan['limits']['max_check_work']
                    assert all(finite(v) for v in a['stats'].values()) and a['stats']['status'] in (0,1,2,3)
                    assert r['algebra_verified'] is a['verified'] and a['verified'] is cert.get('verified',False)
                    if cert:
                        assert cert['schedule']=='legacy' and cert['retention_policy']=='baseline'
                        assert all(finite(v) for v in cert['stats'].values())
                    if arm!='baseline':
                        stats=storage_check(r,arm);key=(case['name'],arm)
                        if key in seen_storage:assert seen_storage[key]==stats
                        else:seen_storage[key]=stats
                    else:assert 'normal_scratch' not in r
                    if r['algebra_verified']:
                        verified+=1
                        assert r['certificate']==cert and cert['status']=='verified' and a['stats']['status']==0
                        assert cert['ideal_equality'] is True and cert['reduced_groebner_basis'] is True
                        encoded=json.dumps([case['nvars'],case['equations'],r['basis'],r['proof']],sort_keys=True)
                        oracle.mathematical_check(encoded);proofs.add(digest(json.loads(encoded)))
                        if case['boundary']=='pdp':
                            assert r['verified'] is True and r['status']=='solved'
                            assignment=r['assignment'];assert type(assignment) is int and 0<=assignment<1<<case['nvars']
                            assert r['assignments_visited']==assignment+1 and 0<r['roots_replayed']<=r['assignments_visited']
                            assert all(sum((m&assignment)==m for m in terms)%2==0 for terms in r['basis'])
                            assert r['curve_replay'] is True and r['reference_equations_and_curve_replay'] is True
                            assert oracle.solution_check(json.dumps(case,sort_keys=True),assignment);pdp+=1
                        else:assert r['verified'] is True and r['status']=='gb'
                    else:
                        assert r['verified'] is False and 'basis' not in r and 'proof' not in r and 'assignment' not in r
                        assert r['status']=='inconclusive';failed+=1
                for arm in CAPS:
                    assert trace(paired['baseline'])==trace(paired[arm]);pairs+=1
                    assert all(paired['fresh']['normal_scratch'][k]==paired[arm]['normal_scratch'][k] for k in ('calls','completed','charged_terms'))
    assert next(rows,None) is None and next(preparations,None) is None and report['status']=='RECORDED_PENDING_AUDIT'
    return dict(status='PASS',rows=len(report['rows']),preparations=len(report['preparation']),unique_mathematical_checks=len(proofs),
        exact_trace_pairs=pairs,unique_storage_records=len(seen_storage),algebra_verified=verified,pdp_verified=pdp,unsuccessful=failed,
        native_binaries_loaded=False,timing_eligible=False,qualified_speedup=None,online_speedup=None)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('report',type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();result=audit(json.loads(args.report.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
