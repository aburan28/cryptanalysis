"""Native-free mathematics and exact baseline/profiled trace comparisons."""
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
STAGES=('decode','compute','canonical','multiply','add','ordered_multiple','ordered_add','normal','install','chain','symbolic','column','packed','sparse','compaction')
GROUPS=dict(
    top=('calls','reductions','irreducible_heads','deferred_terms','zero_rows','output_pivots','skipped_reducer_pivots'),
    column=('indexed_matrices','fallback_matrices','columns','peak_columns','converted_terms'),
    scratch=('xors','fresh_vectors','growths','reused','trimmed_pivots','trimmed_capacity_words','peak_capacity_words'),
    packed=('matrices','fallback_matrices','rows','input_terms','peak_width','peak_payload_words','xors','word_xors','output_terms'),
    chain=('mode','candidate_pairs','scanned_leaders','eligible_chains','pruned_pairs','represented_pairs_skipped','field_pairs','probes','probe_zero','probe_nonzero','probe_soft_limits','probe_aborted','probe_work','peak_probe_nodes','cache_hits','product_hits','failed_probe_hits','represented_entries','failed_entries','cache_saturated','raw_zero_pairs','overhead_work'))

def trace(value):
    if isinstance(value,dict):return {k:trace(v) for k,v in value.items() if not k.endswith('seconds') and k not in ('profile','instrumented')}
    if isinstance(value,list):return [trace(v) for v in value]
    return value
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def finite(value):return type(value) in (int,float) and math.isfinite(value) and value>=0

def profile_check(result):
    profile=result['profile'];assert set(profile)=={*GROUPS,'work'}
    for label,names in GROUPS.items():
        assert set(profile[label])==set(names)
        assert all(type(v) is int and 0<=v<1<<64 for v in profile[label].values())
    p=profile['work'];assert set(p)=={'exclusive','inclusive','calls','overflow','active','depth','peak_depth'}
    for name in ('exclusive','inclusive','calls'):
        assert set(p[name])==set(STAGES)
        assert all(type(v) is int and 0<=v<1<<64 for v in p[name].values())
    assert p['overflow']==p['active']==p['depth']==0 and type(p['peak_depth']) is int and p['peak_depth']>=0
    assert sum(p['exclusive'].values())==result['work']
    assert all(p['inclusive'][s]>=p['exclusive'][s] for s in STAGES if s!='decode')
    assert profile['chain']['mode']==1
    stats=result['attempts'][0]['stats']
    assert profile['column']['indexed_matrices']+profile['column']['fallback_matrices']==stats['matrices']
    assert profile['packed']['matrices']+profile['packed']['fallback_matrices']==profile['column']['indexed_matrices']
    assert p['calls']['symbolic'] in (stats['matrices'],stats['matrices']+1)
    assert p['calls']['column']==profile['column']['indexed_matrices']
    assert p['calls']['packed']==profile['packed']['matrices']
    assert profile['packed']['rows']<=stats['matrix_rows']
    assert profile['packed']['peak_width']*64>=profile['column']['peak_columns'] or profile['packed']['fallback_matrices']
    assert profile['top']['skipped_reducer_pivots']<=profile['top']['output_pivots']
    assert profile['chain']['probe_work']<=result['work'] and profile['chain']['overhead_work']<=result['work']

def audit(report,*,current_sources=True):
    plan=json.loads((HERE/'panel.json').read_text());fixture=HERE.parent/'round13/results/confirmation.json.gz'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest()==oracle.FIXTURE_SHA==plan['fixture_sha256']
    cases=json.loads(gzip.decompress(fixture.read_bytes()))['inputs']
    assert report['schema']=='producer-budget-profile-evidence/1' and report['plan']==plan and report['plan_sha256']==digest(plan)
    assert report['controls'] is True and report['timing_eligible'] is False
    assert all(report[k] is None for k in ('qualified_speedup','aggregate_speedup','online_speedup'))
    build=report['build'];assert build['schema']=='producer-profile-build/1'
    assert len(build['binaries'])==14 and len(build['executables'])==2 and len(build['commands'])==16
    assert {p.split('.')[0] for p in build['binaries']}=={name+suffix for name in ('packed_producer','native_checker','macaulay','packed_dual','scheduled_checker','live_checker','profiled_producer') for suffix in ('','-ubsan')}
    assert set(build['executables'])=={'profile_controls.exe','profile_controls-ubsan.exe'}
    assert set(build['sources'])=={str(p.relative_to(HERE.parent.parent)) for p in source_paths()}
    assert set(build['resources'])=={'summation-polynomials.json','sumpoly_cache.pkl'}
    assert build['polynomial_degree']==4
    assert set(build['generated'])=={'adapter.cpp','engine.inc','f5_reference.py','scheduled_checker.cpp','live_checker.cpp','profiled_adapter.cpp','profiled_engine.inc'}
    for group in ('sources','binaries','executables','generated','resources'):
        for name,sha in build[group].items():
            assert isinstance(sha,str) and len(sha)==64 and set(sha)<=set('0123456789abcdef')
            if current_sources and group=='sources':
                p=(HERE.parent.parent/name).resolve();assert p.is_relative_to(HERE.parents[2])
                assert hashlib.sha256(p.read_bytes()).hexdigest()==sha,name
    rows=iter(report['rows']);preparations=iter(report['preparation']);last_end=None;proofs=set();seen_profiles={};pairs=0;verified=pdp=failed=0
    for sanitized in (False,True):
        prep=next(preparations)
        assert prep['sanitized'] is sanitized and prep['cases']==[c['name'] for c in cases]
        assert finite(prep['seconds']) and prep['numerical_training'] is False and prep['plans']==6 and prep['workspaces']==16
        for case in cases:
            for repetition,order in enumerate(plan['orders']):
                paired={}
                for arm in order:
                    row=next(rows);r=row['result'];paired[arm]=r
                    assert (row['name'],row['repetition'],row['arm'])==(case['name'],repetition,arm)
                    assert row['fixture']==case and row['input_sha256']==digest(case) and row['sanitized'] is sanitized and row['role']=='control'
                    start=datetime.datetime.fromisoformat(row['wall_start']);end=datetime.datetime.fromisoformat(row['wall_end'])
                    assert end>=start and (last_end is None or start>=last_end);last_end=end
                    assert set(row['phases'])==oracle.PHASES and all(type(v) is int and v>=0 for v in row['phases'].values())
                    assert type(row['wall_ns']) is int and row['wall_ns']==sum(row['phases'].values())
                    assert r['instrumented'] is (arm=='profiled')
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
                    if arm=='profiled':
                        profile_check(r)
                        if case['name'] in seen_profiles:assert seen_profiles[case['name']]==r['profile']
                        else:seen_profiles[case['name']]=r['profile']
                    else:assert 'profile' not in r
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
                assert trace(paired['baseline'])==trace(paired['profiled']);pairs+=1
    assert next(rows,None) is None and next(preparations,None) is None and report['status']=='RECORDED_PENDING_AUDIT'
    return dict(status='PASS',rows=len(report['rows']),preparations=len(report['preparation']),unique_mathematical_checks=len(proofs),
        exact_trace_pairs=pairs,unique_profiles=len(seen_profiles),algebra_verified=verified,pdp_verified=pdp,unsuccessful=failed,
        native_binaries_loaded=False,timing_eligible=False,qualified_speedup=None,online_speedup=None)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('report',type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();result=audit(json.loads(args.report.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
