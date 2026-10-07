"""Native-free mathematics, proof custody and leased-query accounting."""
import argparse
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
from proof_reader import decode
from ownership import ownership
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('oracle95_for101',HERE.parent/'round95/audit.py')
oracle=importlib.util.module_from_spec(spec)
_import_path=sys.path[:]
try:spec.loader.exec_module(oracle)
finally:sys.path[:]=_import_path

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def finite(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
def trace(value):
    if isinstance(value,dict):return {k:trace(v) for k,v in value.items() if not k.endswith(('seconds','_ns')) and k not in ('macaulay_policy','layout_policy')}
    if isinstance(value,list):return [trace(v) for v in value]
    return value

def layout_shape(case,arm):return [case['nvars'],len(case['equations']),min(case['nvars'],6 if case['boundary']=='pdp' else 2),3 if arm=='reused3' else 2]
def layout_check(stats,shape):
    n,e,d,m=shape
    a=sum(math.comb(n,k) for k in range(d+1));b=sum(math.comb(n,k) for k in range(min(n,d+m)+1));c=sum(math.comb(n,k) for k in range(m+1))
    assert stats==dict(support=a,columns=b,multipliers=c,rows=e*c,payload_bytes=8*(a+b+c)+4*a*c,total_seconds=stats['total_seconds'],status=0)
    assert finite(stats['total_seconds']) and stats['payload_bytes']<=67108864


@lru_cache(maxsize=256)
def mathematics(n,rows,basis,proof_bytes,limits):
    polynomials=json.loads(rows);output=json.loads(basis);proof=json.loads(proof_bytes)
    checked=oracle.verify(n,polynomials,output,proof,**json.loads(limits))
    assert checked['verified'],checked
    assert oracle.certify_boolean_basis(n,polynomials,output,monomial_cache=True)['verified']
    return oracle.oracle.expected_liveness(polynomials,proof['nodes'],proof['outputs'])

def proof_bytes(folder,sha,encoding='json-v1'):
    assert isinstance(sha,str) and len(sha)==64 and set(sha)<=set('0123456789abcdef')
    assert encoding in ('json-v1','packed-v1')
    path=folder/'proofs'/(sha+('.json' if encoding=='json-v1' else '.pbin'));assert not path.is_symlink() and path.resolve().is_relative_to(folder.resolve())
    data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==sha
    return json.dumps(decode(data),sort_keys=True,separators=(',',':')).encode() if encoding=='packed-v1' else data

def producer_trace(result):
    return [dict(kind=a['kind'],stats=trace(a['stats'])) for a in result['attempts']]

@lru_cache(maxsize=256)
def _cost(n,rows,basis,proof):
    rows,basis,proof=map(json.loads,(rows,basis,proof))
    words=((1<<n)+63)//64
    uses=[0]*len(proof['nodes'])
    for node in proof['nodes']:
        if node[0]=='mul':uses[node[1]]+=1
        elif node[0]=='xor':uses[node[1]]+=1;uses[node[2]]+=1
    for i in proof['outputs']:uses[i]+=1
    live=peak=word_work=conversion=0
    for i,node in enumerate(proof['nodes']):
        live+=1;peak=max(peak,live)
        if node[0]=='input':word_work+=words;conversion+=len(set(rows[node[1]]))
        else:word_work+=3*words
        operands=node[1:2] if node[0]=='mul' else (node[1:3] if node[0]=='xor' else [])
        for operand in operands:
            uses[operand]-=1
            if not uses[operand]:live-=1
        if not uses[i]:live-=1
    for i in proof['outputs']:
        uses[i]-=1
        if not uses[i]:live-=1
    assert live==0
    return dict(words=words,word_work=word_work,extra_work=word_work+conversion+sum(map(len,basis)),
        nodes=len(proof['nodes']),peak_values=peak)

def proof_cost(n,rows,basis,proof):
    return _cost(n,json.dumps(rows),json.dumps(basis),json.dumps(proof))

def audit(report,folder,*,current_sources=True):
    folder=Path(folder);plan=json.loads((HERE/'panel.json').read_text())
    fixture=HERE.parent/'round13/results/confirmation.json.gz'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest()==oracle.FIXTURE_SHA==plan['fixture_sha256']
    all_cases=json.loads(gzip.decompress(fixture.read_bytes()))['inputs']
    cases=[next(c for c in all_cases if c['name']==name) for name in plan['cases']]
    assert report['schema']=='proof-buffer-reuse-evidence/1' and report['plan']==plan and report['plan_sha256']==digest(plan)
    assert type(report['controls']) is bool and report['timing_eligible'] is False
    assert report['gpu']=={'devices':[],'backend':'host'}
    assert all(report[k] is None for k in ('qualified_speedup','aggregate_speedup','online_speedup'))
    build=report['build'];assert build['schema']=='proof-buffer-reuse-build/1'
    assert len(build['binaries'])==18 and len(build['executables'])==0 and len(build['commands'])==18
    assert {p.split('.')[0] for p in build['binaries']}=={name+suffix for name in ('packed_producer','native_checker','macaulay','packed_dual','scheduled_checker','live_checker','sparse_macaulay','dense_checker','reuse_checker') for suffix in ('','-ubsan')}
    assert build['executables']=={}
    assert set(build['sources'])=={str(p.relative_to(HERE.parent.parent)) for p in source_paths()}
    assert set(build['resources'])=={'summation-polynomials.json','sumpoly_cache.pkl'} and build['polynomial_degree']==4
    assert set(build['generated'])=={'adapter.cpp','engine.inc','f5_reference.py','scheduled_checker.cpp','live_checker.cpp','sparse_macaulay.cpp','dense_checker.cpp','reuse_checker.cpp'}
    for group in ('sources','binaries','executables','generated','resources'):
        for name,sha in build[group].items():
            assert isinstance(sha,str) and len(sha)==64 and set(sha)<=set('0123456789abcdef')
            if current_sources and group=='sources':
                path=(HERE.parent.parent/name).resolve();assert path.is_relative_to(HERE.parents[2])
                assert hashlib.sha256(path.read_bytes()).hexdigest()==sha,name
    rows=iter(report['rows']);last_end=None;seen={};proofs=set();consumed=0
    counts=dict(algebra_verified=0,pdp_verified=0,unsuccessful=0,execution_failures=0,exact_trace_pairs=0,verified_lifetimes=0,equal_bases=0,matrix_verified=0,fallbacks=0)
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
                        prep=row['preparation'];assert set(prep)=={'cases','plans','workspaces','layouts'}
                        assert prep['cases']==plan['cases'] and prep['plans']==12 and prep['workspaces']==4
                        expected={(tuple(layout_shape(c,a)),a) for c in cases for a in ('matrix-packed','matrix-reuse')}
                        actual={(tuple(l['shape']),l['arm']) for l in prep['layouts']}
                        assert actual==expected and len(prep['layouts'])==len(expected)
                        for l in prep['layouts']:assert l['reason'] is None;layout_check(l['stats'],l['shape'])
                        assert finite(row['preparation_seconds']) and type(row['process_peak_rss_bytes']) is int and row['process_peak_rss_bytes']>0
                        assert set(row['phases'])==oracle.PHASES and all(type(v) is int and v>=0 for v in row['phases'].values())
                        assert type(row['wall_ns']) is int and row['wall_ns']==sum(row['phases'].values()) and row['wall_ns']<=row['process_elapsed_ns']
                        r=row['result'];paired[arm]=r
                        material=r['materialization']
                        assert set(material)=={'calls','basis_ns','proof_ns','total_ns','nodes','outputs','raw_payload_bytes'}
                        assert all(type(v) is int and v>=0 for v in material.values())
                        assert material['total_ns']==material['basis_ns']+material['proof_ns']
                        assert material['total_ns']<=row['phases']['algebra_and_certificate_ns']
                        assert material['calls']==int(r['algebra_verified'])
                        if not r['algebra_verified']:assert not any(material.values())
                        assert r['buffer_reuse_policy']==arm and r['proof_transport_policy']==('f4-dense' if arm.startswith('f4-') else 'matrix-packed') and r['proof_value_policy']==('f4-dense' if arm.startswith('f4-') else 'matrix-dense') and r['macaulay_policy']==('baseline' if arm.startswith('f4-') else 'reused2') and r['checker_order']=='completion-first'
                        assert r['retention_policy']=='release-live' and r['layout_policy']==('none' if arm.startswith('f4-') else 'reused')
                        assert r['timing_eligible'] is False and r['qualified_speedup'] is None and finite(r['total_seconds'])
                        assert type(r['verified']) is bool and type(r['algebra_verified']) is bool and r['complete'] is r['algebra_verified']
                        attempts=r['attempts'];assert attempts
                        assert [a['kind'] for a in attempts] in ([['fresh-f4']] if arm.startswith('f4-') else [['macaulay'],['macaulay','fresh-f4']])
                        assert r['work']==sum(a['stats']['work'] for a in attempts) and 0<=r['work']<=budget
                        assert r['check_work']==sum(a.get('certificate',{}).get('stats',{}).get('work',0) for a in attempts) and 0<=r['check_work']<=limits['max_check_work']
                        if arm.startswith('matrix-'):
                            matrix=attempts[0];layout_check(matrix['layout_stats'],layout_shape(case,arm))
                            assert matrix['stats']['work']<=limits['matrix_cap']
                            assert len(attempts)==(1 if matrix['verified'] else 2)
                            counts['matrix_verified']+=int(matrix['verified']);counts['fallbacks']+=int(len(attempts)==2)
                        for a in attempts:
                            cert=a.get('certificate',{})
                            assert all(finite(v) for v in a['stats'].values()) and a['stats']['status'] in (0,1,2,3)
                            assert a['verified'] is cert.get('verified',False)
                            if cert:
                                assert cert['schedule']=='completion-first' and cert['retention_policy']=='release-live'
                                assert all(finite(v) for v in cert['stats'].values())
                                live=cert['liveness'];assert all(type(v) is int and v>=0 for v in live.values())
                                assert live['live_terms']+live['released_terms']==cert['stats']['retained_terms']
                                assert live['peak_terms']>=live['live_terms'] and live['planning_work']<=cert['stats']['work']
                        a=attempts[-1];cert=a.get('certificate',{});live=cert.get('liveness',{})
                        assert r['algebra_verified'] is a['verified']
                        key=(case['name'],budget,arm)
                        value=trace(r)
                        if key in seen:assert seen[key]==value
                        else:seen[key]=value
                        if r['algebra_verified']:
                            counts['algebra_verified']+=1
                            transport=row['proof_transport']
                            assert set(transport)=={'serialization_ns','decode_ns','stored_bytes'}
                            assert all(type(transport[k]) is int and transport[k]>=0 for k in ('serialization_ns','stored_bytes'))
                            assert transport['serialization_ns']<=row['process_elapsed_ns']-row['wall_ns']
                            if arm.startswith('matrix-'):
                                assert type(transport['decode_ns']) is int and 0<=transport['decode_ns']<=row['process_elapsed_ns']-row['wall_ns']
                                assert transport['stored_bytes']==32+16*material['nodes']+4*material['outputs']
                            else:assert transport['decode_ns'] is None
                            assert r['certificate']==cert and cert['status']=='verified' and a['stats']['status']==0
                            assert cert['ideal_equality'] is True and cert['reduced_groebner_basis'] is True
                            assert 'proof' not in r
                            data=proof_bytes(folder,r['proof_sha256'],r['proof_format'])
                            decoded=json.loads(data)
                            if not arm.startswith('matrix-'):assert transport['stored_bytes']==len(data)
                            assert r['proof_format']==('packed-v1' if arm.startswith('matrix-') else 'json-v1')
                            assert material['nodes']==len(decoded['nodes']) and material['outputs']==len(decoded['outputs'])
                            assert material['raw_payload_bytes']==(16*material['nodes']+4*material['outputs'] if arm.startswith('matrix-') else 0)
                            expected,total=mathematics(case['nvars'],json.dumps(case['equations']),json.dumps(r['basis']),data,json.dumps(plan['audit_limits']))
                            assert cert['liveness']==expected and cert['stats']['retained_terms']==total
                            assert live['peak_terms']<=limits['max_terms']
                            counts['verified_lifetimes']+=1;proofs.add(digest([case['nvars'],case['equations'],r['basis'],hashlib.sha256(data).hexdigest()]))
                            if case['boundary']=='pdp':
                                assert r['verified'] is True and r['status']=='solved'
                                assignment=r['assignment'];assert type(assignment) is int and 0<=assignment<1<<case['nvars']
                                assert r['assignments_visited']==assignment+1 and 0<r['roots_replayed']<=r['assignments_visited']
                                assert r['curve_replay'] is True and r['reference_equations_and_curve_replay'] is True
                                assert oracle.solution_check(json.dumps(case,sort_keys=True),assignment);counts['pdp_verified']+=1
                            else:assert r['verified'] is True and r['status']=='gb'
                        else:
                            assert row['proof_transport'] is None
                            assert r['verified'] is False and not any(k in r for k in ('basis','proof','proof_sha256','assignment'))
                            assert r['status']=='inconclusive';counts['unsuccessful']+=1
                    for ref_arm,new_arm in (('f4-dense','f4-reuse'),('matrix-packed','matrix-reuse')):
                        if ref_arm not in paired or new_arm not in paired:continue
                        reference,candidate=paired[ref_arm],paired[new_arm]
                        assert producer_trace(reference)==producer_trace(candidate)
                        assert reference['algebra_verified']==candidate['algebra_verified']
                        def semantic_attempts(value):
                            result=trace(value['attempts'])
                            for attempt in result:
                                cert=attempt.get('certificate',{})
                                cert.pop('reuse',None)
                                cert.get('dense',{}).pop('peak_bytes',None)
                            return result
                        assert semantic_attempts(reference)==semantic_attempts(candidate)
                        for attempt in candidate['attempts']:
                            if 'certificate' not in attempt:continue
                            cert=attempt['certificate'];reuse=cert['reuse'];dense=cert['dense']
                            assert set(reuse)=={'enabled','checks','transfers','left_transfers','right_transfers','payload_allocations','payload_releases'}
                            assert all(type(v) is int and v>=0 for v in reuse.values())
                            assert reuse['enabled']==1
                            assert reuse['transfers']==reuse['left_transfers']+reuse['right_transfers']
                            assert reuse['transfers']+reuse['payload_allocations']==dense['created_values']
                            assert reuse['payload_releases']<=reuse['payload_allocations']
                        if reference['algebra_verified']:
                            assert reference['basis']==candidate['basis']
                            assert reference['proof_sha256']==candidate['proof_sha256']
                            proof=json.loads(proof_bytes(folder,reference['proof_sha256'],reference['proof_format']))
                            expected=proof_cost(case['nvars'],case['equations'],reference['basis'],proof)
                            for enabled,value in ((False,reference),(True,candidate)):
                                dense=value['certificate']['dense']
                                planned=ownership(proof,enabled=enabled)
                                peak=planned.pop('peak_buffers')
                                assert dense['selected']==1 and dense['fallback_large_ring']==0
                                assert dense['words_per_value']==expected['words'] and dense['word_work']==expected['word_work']
                                assert dense['created_values']==dense['released_values']==expected['nodes']
                                assert dense['live_bytes']==0
                                assert dense['peak_bytes']==dense['metadata_bytes']+peak*8*expected['words']
                                assert 0<dense['metadata_bytes']<=expected['nodes']*128
                                assert dense['peak_bytes']<=plan['dense_byte_limit']
                                if enabled:assert value['certificate']['reuse']==planned
                            assert candidate['certificate']['dense']['peak_bytes']<=reference['certificate']['dense']['peak_bytes']
                        counts['exact_trace_pairs']+=1
                    good=[r for r in paired.values() if r['algebra_verified']]
                    if good:
                        basis=lambda r:sorted(tuple(sorted(row)) for row in r['basis'])
                        for other in good[1:]:
                            assert basis(other)==basis(good[0]) and other.get('assignment')==good[0].get('assignment')
                            counts['equal_bases']+=1
    assert next(rows,None) is None and report['status']=='RECORDED_PENDING_AUDIT'
    return dict(status='PASS',rows=consumed,unique_mathematical_checks=len(proofs),unique_deterministic_records=len(seen),**counts,
        native_binaries_loaded=False,timing_eligible=False,qualified_speedup=None,online_speedup=None)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();result=audit(json.loads(a.report.read_text()),a.report.parent)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
