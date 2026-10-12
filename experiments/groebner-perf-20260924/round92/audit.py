"""Native-free artifact audit: exact ideals, complete coverage and trace parity."""
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

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def canonical(basis): return sorted(tuple(sorted(row)) for row in basis)
def protected(result):
    return dict(status=result['status'],verified=result['verified'],basis=result.get('basis'),proof=result.get('proof'),
        work=result['work'],check_work=result['check_work'],attempts=[dict(kind=a['kind'],verified=a['verified'],
        stats={k:v for k,v in a['stats'].items() if not k.endswith('seconds')},
        certificate={k:v for k,v in a.get('certificate',{}).items() if k!='stats'},
        checker_stats={k:v for k,v in a.get('certificate',{}).get('stats',{}).items() if not k.endswith('seconds')}) for a in result['attempts']])

def audit(report,*,current_sources=True):
    plan=json.loads((HERE/'panel.json').read_text())
    assert report['schema']=='reusable-macaulay-evidence/1' and report['plan']==plan and report['plan_sha256']==digest(plan)
    assert report['timing_eligible'] is False
    assert all(report[k] is None for k in ('qualified_speedup','aggregate_speedup','online_speedup'))
    build=report['build']
    assert set(build['sources'])=={str(p.relative_to(HERE.parent.parent)) for p in source_paths()}
    assert len(build['binaries'])==8
    assert {p.split('.')[0] for p in build['binaries']}=={n+s for n in ('packed_producer','native_checker','macaulay','packed_dual') for s in ('','-ubsan')}
    for value in [*build['sources'].values(),*build['binaries'].values(),*build['generated'].values()]:
        assert isinstance(value,str) and len(value)==64 and set(value)<=set('0123456789abcdef')
    if current_sources:
        for name,sha in build['sources'].items():
            p=(HERE.parent.parent/name).resolve()
            assert p.is_relative_to(HERE.parents[2]) and hashlib.sha256(p.read_bytes()).hexdigest()==sha,name
    assert type(report['controls']) is bool
    modes=[False,True] if report['controls'] else [False]
    preparations=iter(report['preparation']);rows=iter(report['rows']);proofs=set()
    counts=dict(verified_records=0,unsupported_records=0,other_unsuccessful_records=0,accepted_r1=0,accepted_r2=0,r1_fallbacks=0,r2_fallbacks=0,exact_trace_pairs=0)
    last_end=None
    for sanitized in modes:
        for family in plan['families']:
            n=family['nvars'];e=len(family['training']);d=family['degree_bound']
            preparation=next(preparations)
            assert preparation['family']==family['name'] and preparation['sanitized'] is sanitized
            assert preparation['numerical_training'] is False and preparation['total_seconds']>=0
            for label,r in [('r1',0 if d<=1 else 1),('r2',0 if d<=1 else 2)]:
                assert preparation['shape_'+label]==[n,e,d,r]
                a=sum(math.comb(n,k) for k in range(d+1));b=sum(math.comb(n,k) for k in range(min(n,d+r)+1));c=sum(math.comb(n,k) for k in range(r+1))
                st=preparation[label+'_stats']
                assert {k:st[k] for k in ('support','columns','multipliers','rows','payload_bytes','status')}==dict(support=a,columns=b,multipliers=c,rows=e*c,payload_bytes=8*(a+b+c)+4*a*c,status=0)
            for target,equations in enumerate(family['targets']):
                reference=None
                orders=[plan['arms']] if report['controls'] else plan['orders']
                for repetition,order in enumerate(orders):
                    pair={}
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
                            attempts=result['attempts'];kinds=[a['kind'] for a in attempts]
                            assert kinds==['fresh-f4'] if arm=='fresh-f4' else kinds in (['macaulay'],['macaulay','fresh-f4'])
                            assert result['layout_policy']==('none' if arm=='fresh-f4' else 'fresh' if arm=='fresh-layout-r1' else 'reused')
                            assert result['work']==sum(a['stats']['work'] for a in attempts) and 0<=result['work']<=plan['limits']['max_work']
                            assert result['check_work']==sum(a.get('certificate',{}).get('stats',{}).get('work',0) for a in attempts) and 0<=result['check_work']<=plan['limits']['max_check_work']
                            assert result['complete'] is result['verified'] and result['verified'] is attempts[-1]['verified']
                            for a in attempts:
                                assert a['stats']['status'] in (0,1,2,3)
                                assert type(a['verified']) is bool and a['verified'] is a.get('certificate',{}).get('verified',False)
                                if a['verified']:
                                    assert a['stats']['status']==0
                                    cert=a['certificate'];assert cert['status']=='verified' and cert['ideal_equality'] and cert['reduced_groebner_basis']
                            if arm!='fresh-f4':
                                assert attempts[0]['stats']['work']<=plan['limits']['matrix_cap']
                                label='r2' if arm=='reused-r2' else 'r1'
                                assert {k:v for k,v in attempts[0]['layout_stats'].items() if k!='total_seconds'}=={k:v for k,v in preparation[label+'_stats'].items() if k!='total_seconds'}
                                if arm in ('reused-r1','reused-r2'):
                                    counts['accepted_'+label]+=attempts[0]['verified']
                                    counts[label+'_fallbacks']+=len(attempts)==2
                            if arm in ('fresh-layout-r1','reused-r1'): pair[arm]=protected(result)
                        if result['verified']:
                            counts['verified_records']+=1;assert result['status']=='gb'
                            key=digest([n,equations,result['basis'],result.get('proof')])
                            if key not in proofs:
                                if algebra:
                                    check=verify(n,equations,result['basis'],result['proof'],max_work=200_000_000,max_retained_terms=20_000_000)
                                    assert check['verified'],check
                                if n<=20:
                                    assert certify_boolean_basis(n,equations,result['basis'],monomial_cache=n<=12)['verified']
                                proofs.add(key)
                            basis=canonical(result['basis'])
                            if reference is None: reference=basis
                            assert basis==reference,(family['name'],target,arm)
                        else:
                            assert result['status'] in ('inconclusive','unsupported','rejected','invalid-input','producer-failure')
                            assert 'basis' not in result
                            counts['unsupported_records' if result['status']=='unsupported' else 'other_unsuccessful_records']+=1
                    assert pair['fresh-layout-r1']==pair['reused-r1'],(family['name'],target,repetition)
                    counts['exact_trace_pairs']+=1
    assert next(rows,None) is None and next(preparations,None) is None and report['status']=='RECORDED_PENDING_AUDIT'
    return dict(status='PASS',rows=len(report['rows']),preparations=len(report['preparation']),unique_mathematical_checks=len(proofs),
        **counts,native_binaries_loaded=False,timing_eligible=False,qualified_speedup=None)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('report',type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();result=audit(json.loads(args.report.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
