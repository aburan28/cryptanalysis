"""Replay original-equation proofs and verify rebuilt artifact/source bindings."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent/'round5'))
from algebraic_certificate import verify
sys.path.insert(0,str(HERE.parent.parent/'pdp-scaling'))
from descend import make_instance,verify_solution

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def trace(r):
    return {k:r.get(k) for k in ('status','reason','verified','basis','proof','top_stats','chain_stats','assignment','assignments_visited','roots_replayed')}|{
        'producer_stats':{k:v for k,v in r['producer_stats'].items() if not k.endswith('_seconds')}}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    out=args.evidence;bindings_checked=0;proofs={};rows_checked=0;verified=0;inconclusive=0
    fixture=HERE.parent/'round13/results/confirmation.json.gz'
    expected={i['name']:i for i in read(fixture)['inputs']}
    def resolve(name):
        marker='/experiments/'
        if marker in name:
            tail=name.split(marker,1)[1]
            bits=Path(tail).parts
            if bits[0]=='groebner-perf-20260924' and len(bits)>2 and bits[2]=='build':
                return out/'native'/bits[1]/Path(*bits[3:])
            return ROOT/'experiments'/tail
        if '/phases/' in name: return out/'phases'/name.split('/phases/',1)[1]
        raise ValueError('Unrecognized artifact binding: '+name)
    def bindings(mapping):
        nonlocal bindings_checked
        for name,digest in mapping.items():
            p=resolve(name);assert sha(p)==digest,(name,p)
            bindings_checked+=1
    for version in (55,56):
        directory=out/'native'/f'round{version}';receipt=read(directory/'receipt.json')
        for name,d in receipt['sources'].items(): assert sha(HERE.parent/name)==d,name
        for category in ('binaries','generated'):
            for name,d in receipt[category].items(): assert sha(directory/name)==d,name
    configs=(('round55-screen.json.gz',92,('prior','cached','probe'),False),
             ('round56-screen.json.gz',460,('prior','chain','top_new','top_all','chain_top_new','chain_top_all','filter','chain_filter','filter_top','chain_filter_top'),False),
             ('queries.json.gz',120,('prior','chain','filter','chain_filter'),True))
    summaries={}
    for name,count,variants,query in configs:
        report=read(out/name)
        assert report['status']=='PASS' and report['fixture_sha256']==sha(fixture)
        assert report['timing_eligible'] is False and report['candidate_id'] is None and report['online_speedup'] is None
        bindings(report['bindings'])
        inputs={i['name']:i for i in report['inputs']}
        wanted={k:v for k,v in expected.items() if not query or v['boundary']=='pdp'}
        assert inputs==wanted
        assert len(report['rows'])==count
        table={};solved=0;failed=0
        for row in report['rows']:
            key=(row['name'],row['variant'],row['sanitizer']);assert key not in table
            table[key]=row['result'];r=row['result'];item=inputs[row['name']]
            assert row['workload_sha256']==item['workload_sha256']
            assert r['producer_stats']['work']<=report['limits']['max_work']
            assert r['status'] in (('solved','inconclusive') if query else ('gb','inconclusive'))
            assert r['verified']==(r['status']!='inconclusive')
            if r['verified']:
                assert r['certificate']['verified'] and r['python_original_equations_audit']['verified']
                payload=[item['nvars'],item['equations'],r['basis'],r['proof']]
                keyhash=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                if keyhash not in proofs:
                    check=verify(*payload);assert check['verified'],(name,row['name'],check)
                    proofs[keyhash]=check
                if query:
                    instance=make_instance(item['n'],item['m'],item['ell'],seed=item['seed'])
                    assert instance.xR==item['target_x'] and instance.mod==item['mod'] and instance.b==item['b']
                    assert [sorted(p) for p in instance.equations()]==item['equations']
                    assert instance.evaluate(r['assignment'])==0 and verify_solution(instance,r['assignment'])
                    assert r['curve_replay'] and r['reference_equations_and_curve_replay']
                solved+=1
            else:
                assert 'budget' in r['reason']
                failed+=1
        expected_keys={(n,v,u) for n in inputs for v in variants for u in (False,True)
                       if name!='round55-screen.json.gz' or not u or v=='probe'}
        assert set(table)==expected_keys
        for n in inputs:
            bases=[table[n,v,u]['basis'] for v in variants for u in (False,True)
                   if (n,v,u) in table and table[n,v,u]['verified']]
            if bases: assert all(b==bases[0] for b in bases)
            for v in variants:
                if (n,v,True) in table: assert trace(table[n,v,False])==trace(table[n,v,True]),(name,n,v)
        summaries[name]={'rows':count,'verified':solved,'inconclusive':failed}
        rows_checked+=count;verified+=solved;inconclusive+=failed
    phases=read(out/'phases/report.json');assert phases['status']=='PASS' and len(phases['rows'])==46
    assert phases['source_screen_sha256']==sha(out/'round55-screen.json.gz')
    bindings(phases['bindings'])
    screen55={(r['name'],r['variant']):r['result'] for r in read(out/'round55-screen.json.gz')['rows'] if not r['sanitizer']}
    assert {(r['name'],r['variant']) for r in phases['rows']}=={(n,v) for n in expected for v in ('prior','probe')}
    for row in phases['rows']:
        assert sum(row['phases'].values())==row['work']
        assert row['work']==screen55[row['name'],row['variant']]['producer_stats']['work']
    guards=read(out/'probe-guards.json');assert guards['status']=='PASS' and len(guards['results'])==6
    bindings(guards['bindings'])
    for row in guards['results']:
        assert row['result']['work_boundaries']==65 and row['result']['node_boundaries']==9
        assert row['result']['aborted_probes']>0
    result={'status':'PASS','rows':rows_checked,'verified':verified,'inconclusive':inconclusive,'unique_proofs':len(proofs),'bindings_checked':bindings_checked,'summaries':summaries,'runner':read(out/'runner.json'),'timing_eligible':False}
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__': main()
