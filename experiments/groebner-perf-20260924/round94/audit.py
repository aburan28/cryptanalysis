"""Independent native-free proofs, complete coverage, and paired producer invariance."""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from build import source_paths
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'round5'),str(HERE.parent.parent/'pdp-scaling')]
from algebraic_certificate import verify
from boolean_basis import certify_boolean_basis

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def canonical(basis):return sorted(tuple(sorted(row)) for row in basis)
def counters(stats):return {k:v for k,v in stats.items() if not k.endswith('seconds')}
def producer_trace(result):
    return dict(verified=result['verified'],status=result['status'],basis=result.get('basis'),proof=result.get('proof'),
        work=result['work'],attempts=[dict(kind=a['kind'],verified=a['verified'],stats=counters(a['stats'])) for a in result['attempts']])

def audit(report,*,current_sources=True):
    plan=json.loads((HERE/'panel.json').read_text())
    assert report['schema']=='proof-liveness-evidence/1' and report['plan']==plan and report['plan_sha256']==digest(plan)
    assert report['timing_eligible'] is False
    assert all(report[k] is None for k in ('qualified_speedup','aggregate_speedup','online_speedup'))
    build=report['build']
    assert set(build['sources'])=={str(p.relative_to(HERE.parent.parent)) for p in source_paths()}
    assert len(build['binaries'])==12
    assert {p.split('.')[0] for p in build['binaries']}=={n+s for n in ('packed_producer','native_checker','macaulay','packed_dual','scheduled_checker','live_checker') for s in ('','-ubsan')}
    for value in [*build['sources'].values(),*build['binaries'].values(),*build['generated'].values()]:
        assert isinstance(value,str) and len(value)==64 and set(value)<=set('0123456789abcdef')
    if current_sources:
        for name,sha in build['sources'].items():
            p=(HERE.parent.parent/name).resolve()
            assert p.is_relative_to(HERE.parents[2]) and hashlib.sha256(p.read_bytes()).hexdigest()==sha,name
    assert type(report['controls']) is bool
    modes=[False,True] if report['controls'] else [False]
    preparations=iter(report['preparation']);rows=iter(report['rows']);proofs=set();last_end=None
    counts=dict(verified_records=0,unsupported_records=0,other_unsuccessful_records=0,exact_producer_pairs=0,
        successful_checker_counter_pairs=0,early_matrix_rejections=0,verified_lifetimes=0,matrix_baseline_accepted=0,matrix_cumulative_accepted=0,matrix_live_accepted=0)
    for sanitized in modes:
        for family in plan['families']:
            n=family['nvars'];e=len(family['training']);d=family['degree_bound'];r=0 if d<=1 else 1
            preparation=next(preparations)
            assert preparation['family']==family['name'] and preparation['sanitized'] is sanitized
            assert preparation['numerical_training'] is False and preparation['total_seconds']>=0
            assert preparation['shape']==[n,e,d,r]
            assert set(preparation['layouts'])=={'baseline','release-cumulative','release-live'}
            a=sum(math.comb(n,k) for k in range(d+1));b=sum(math.comb(n,k) for k in range(min(n,d+r)+1));c=sum(math.comb(n,k) for k in range(r+1))
            for st in preparation['layouts'].values():
                assert {k:st[k] for k in ('support','columns','multipliers','rows','payload_bytes','status')}==dict(support=a,columns=b,multipliers=c,rows=e*c,payload_bytes=8*(a+b+c)+4*a*c,status=0)
            for target,equations in enumerate(family['targets']):
                reference=None
                for repetition,order in enumerate([plan['arms']] if report['controls'] else plan['orders']):
                    paired={}
                    for arm in order:
                        row=next(rows);result=row['result']
                        assert (row['family'],row['target'],row['nvars'],row['repetition'],row['arm'])==(family['name'],target,n,repetition,arm)
                        assert row['sanitized'] is sanitized
                        assert row['equations']==equations and row['input_sha256']==digest(dict(nvars=n,equations=equations))
                        assert row['role']==('control' if report['controls'] else ('warmup' if repetition<plan['warmup_rounds'] else 'observation'))
                        start=datetime.datetime.fromisoformat(row['wall_start']);end=datetime.datetime.fromisoformat(row['wall_end'])
                        assert end>=start and (last_end is None or start>=last_end);last_end=end
                        assert row['complete_call_seconds']>=0 and result['total_seconds']>=0 and type(result['verified']) is bool
                        algebra=arm not in ('signature','evaluation')
                        if algebra:
                            engine,policy=arm.split('-',1)
                            schedule=plan['checker_order']
                            assert result['checker_order']==schedule and result['retention_policy']==policy
                            assert result['layout_policy']==('none' if engine=='f4' else 'reused')
                            assert result['timing_eligible'] is False and result['qualified_speedup'] is None
                            attempts=result['attempts'];kinds=[a['kind'] for a in attempts]
                            assert kinds in ([['fresh-f4']] if engine=='f4' else [['macaulay'],['macaulay','fresh-f4']])
                            assert result['work']==sum(a['stats']['work'] for a in attempts) and 0<=result['work']<=plan['limits']['max_work']
                            assert result['check_work']==sum(a.get('certificate',{}).get('stats',{}).get('work',0) for a in attempts) and 0<=result['check_work']<=plan['limits']['max_check_work']
                            assert result['complete'] is result['verified'] and result['verified'] is attempts[-1]['verified']
                            for attempt in attempts:
                                assert attempt['stats']['status'] in (0,1,2,3)
                                assert type(attempt['verified']) is bool and attempt['verified'] is attempt.get('certificate',{}).get('verified',False)
                                if 'certificate' in attempt:
                                    cert=attempt['certificate'];assert cert['schedule']==schedule and cert['retention_policy']==policy
                                    if policy!='baseline':
                                        live=cert['liveness']
                                        assert set(live)=={'planning_work','metadata_bytes','live_terms','peak_terms','released_terms','released_nodes'}
                                        assert all(type(v) is int and v>=0 for v in live.values())
                                        assert live['live_terms']+live['released_terms']==cert['stats']['retained_terms']
                                        assert live['peak_terms']>=live['live_terms']
                                        assert live['released_nodes']<=cert['stats']['proof_nodes']
                                        assert live['planning_work']<=cert['stats']['work']
                                    assert all(isinstance(v,(int,float)) and v>=0 for v in cert['stats'].values())
                                if attempt['verified']:
                                    assert attempt['stats']['status']==0
                                    cert=attempt['certificate'];assert cert['status']=='verified' and cert['ideal_equality'] and cert['reduced_groebner_basis']
                            if policy!='baseline' and attempt['verified']:
                                    assert live['live_terms']==0 and live['released_nodes']==cert['stats']['proof_nodes']
                                    assert live['metadata_bytes']==4*cert['stats']['proof_nodes']
                                    counts['verified_lifetimes']+=1
                            if engine=='matrix':
                                first=attempts[0]
                                assert first['stats']['work']<=plan['limits']['matrix_cap']
                                assert counters(first['layout_stats'])==counters(preparation['layouts'][policy])
                                counts[{'baseline':'matrix_baseline_accepted','release-cumulative':'matrix_cumulative_accepted','release-live':'matrix_live_accepted'}[policy]]+=first['verified']
                                cert=first.get('certificate',{})
                                if cert.get('status')=='rejected':
                                    assert cert['stats']['proof_nodes']==0 and cert['stats']['retained_terms']==0 and cert['stats']['derivation_seconds']==0
                                    counts['early_matrix_rejections']+=1
                            paired[arm]=result
                        if result['verified']:
                            counts['verified_records']+=1;assert result['status']=='gb'
                            key=digest([n,equations,result['basis'],result.get('proof')])
                            if key not in proofs:
                                if algebra:
                                    checked=verify(n,equations,result['basis'],result['proof'],max_work=200_000_000,max_retained_terms=20_000_000)
                                    assert checked['verified'],checked
                                if n<=20:assert certify_boolean_basis(n,equations,result['basis'],monomial_cache=n<=12)['verified']
                                proofs.add(key)
                            basis=canonical(result['basis'])
                            if reference is None:reference=basis
                            assert basis==reference,(family['name'],target,arm)
                        else:
                            assert result['status'] in ('inconclusive','unsupported','rejected','invalid-input','producer-failure')
                            assert 'basis' not in result
                            counts['unsupported_records' if result['status']=='unsupported' else 'other_unsuccessful_records']+=1
                    for engine in ('f4','matrix'):
                        left=paired[engine+'-baseline']
                        for policy in ('release-cumulative','release-live'):
                            right=paired[engine+'-'+policy]
                            assert producer_trace(left)==producer_trace(right),(family['name'],target,repetition,engine,policy)
                            counts['exact_producer_pairs']+=1
                            for aa,bb in zip(left['attempts'],right['attempts']):
                                if aa['verified']:
                                    original=counters(aa['certificate']['stats']);actual=counters(bb['certificate']['stats'])
                                    live=bb['certificate']['liveness']
                                    actual['work']-=live['planning_work']
                                    assert original==actual
                                    assert live['planning_work']==actual['proof_nodes']+len(right['basis'])
                                    assert live['released_terms']==actual['retained_terms']
                                    assert live['peak_terms']<=actual['retained_terms']
                                    counts['successful_checker_counter_pairs']+=1
    assert next(rows,None) is None and next(preparations,None) is None and report['status']=='RECORDED_PENDING_AUDIT'
    return dict(status='PASS',rows=len(report['rows']),preparations=len(report['preparation']),unique_mathematical_checks=len(proofs),
        **counts,native_binaries_loaded=False,timing_eligible=False,qualified_speedup=None)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('report',type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();result=audit(json.loads(args.report.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
