"""Audit-only charged-work phases; match every frozen algorithmic result."""
import argparse,ctypes as C,gzip,hashlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
R=Path(__file__).resolve().parent
W=R.parents[2]
NAMES=('initial','pairs','symbolic','elimination','new_rows','final_reduction')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def change(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)
def instrument(s):
    header='\nstruct WorkPhases { uint64_t '+','.join(k+'=0' for k in NAMES)+'; };\nstatic thread_local WorkPhases phase_work{};\n'
    s=change(s,'class Engine {',header+'class Engine {')
    guard='''    struct WorkPhase {
        Engine &e; uint64_t &counter; const uint64_t start;
        WorkPhase(Engine &engine,uint64_t &count):e(engine),counter(count),start(engine.work){}
        ~WorkPhase(){counter+=e.work-start;}
    };
'''
    s=change(s,'    void charge(uint64_t amount = 1) {',guard+'    void charge(uint64_t amount = 1) {')
    s=change(s,'        std::set<Mask> seen;','        { WorkPhase phase(*this,phase_work.symbolic);\n        std::set<Mask> seen;')
    s=change(s,'        ++matrices;matrix_rows+=rows.size();peak_rows=std::max<uint64_t>(peak_rows,rows.size());','        }\n        ++matrices;matrix_rows+=rows.size();peak_rows=std::max<uint64_t>(peak_rows,rows.size());\n        WorkPhase phase(*this,phase_work.elimination);')
    s=change(s,'    void compute(const std::vector<Poly>& input) {','    void compute(const std::vector<Poly>& input) {\n        { WorkPhase phase(*this,phase_work.initial);')
    s=change(s,'        while (!queue.empty() && !unit()) {','        }\n        while (!queue.empty() && !unit()) {')
    s=change(s,'            size_t taken=0;','            size_t taken=0;\n            { WorkPhase phase(*this,phase_work.pairs);')
    s=change(s,'            if (batch.empty()) continue;','            }\n            if (batch.empty()) continue;')
    s=change(s,'            for (auto& row:reduced) {','            for (auto& row:reduced) {\n                WorkPhase phase(*this,phase_work.new_rows);')
    s=change(s,'        bool changed=true;','        WorkPhase phase(*this,phase_work.final_reduction);\n        bool changed=true;')
    return s
class Stats(C.Structure): _fields_=[(n,C.c_uint64) for n in NAMES]
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--screen',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output;out.mkdir(exist_ok=False)
    frozen=json.loads(gzip.decompress(args.screen.read_bytes()))
    assert frozen['status']=='PASS'
    baseline={(r['name'],r['variant']):r['result'] for r in frozen['rows'] if not r['sanitizer']}
    report={'status':'RUNNING','scope':'Charged-work phase audit; not timing evidence','source_screen_sha256':sha(args.screen),'rows':[],'commands':[],'bindings':{},'timing_eligible':False}
    suffix='.dylib' if sys.platform=='darwin' else '.so'
    shared=['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
    for variant in ('prior','probe'):
        folder=out/variant/'build';folder.mkdir(parents=True)
        source=R/'build'/('cached.inc' if variant=='prior' else 'checked.inc')
        s=instrument(source.read_text())
        s=s.replace('#include "../chain_stats.h"','#include "'+str(R/'chain_stats.h')+'"')
        engine=folder/'engine.inc';engine.write_text(s)
        adapter=(W/'experiments/groebner-perf-20260924/round11/packed_producer.cpp').read_text()
        adapter=change(adapter,'#include "build/native_engine.inc"','#include "engine.inc"')
        adapter=change(adapter,'auto start=Clock::now();failure.clear();','auto start=Clock::now();failure.clear();phase_work={};'+('chain_stats={};chain_stats.mode=1;' if variant=='probe' else ''))
        adapter+='\nextern "C" const WorkPhases* producer_phase_work(){return &phase_work;}\n'
        path=folder/'adapter.cpp';path.write_text(adapter)
        binary=folder/('packed_producer'+suffix)
        command=[os.environ.get('CXX','clang++'),'-std=c++17','-O3','-Wall','-Wextra','-Werror',*shared,'-I',str(W/'experiments/groebner-perf-20260924/round11'),'-DPERSISTENT_ORDER=1','-DPIVOT_KEYS=1','-DINDEXED_REDUCERS=0',str(path),'-o',str(binary)]
        subprocess.run(command,check=True);report['commands'].append(command)
        checker=R/'build'/('native_checker'+suffix)
        (folder/checker.name).symlink_to(checker)
        for p in (source,engine,path,binary,checker): report['bindings'][str(p)]=sha(p)
        spec=importlib.util.spec_from_file_location('phase_profile_'+variant,W/'experiments/groebner-perf-20260924/round11/packed_proof.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.HERE=folder.parent;q=module.PackedProof()
        q.producer.producer_phase_work.restype=C.POINTER(Stats)
        for item in frozen['inputs']:
            answer=q.compute(item['nvars'],len(item['equations']),module.anf_from_equations(item['equations']),export_proof=True,**frozen['limits'])
            prior=baseline[item['name'],variant]
            for key in ('status','verified','reason','basis','proof'): assert answer.get(key)==prior.get(key),(item['name'],variant,key)
            logical=lambda a:{k:v for k,v in a['producer_stats'].items() if not k.endswith('_seconds')}
            assert logical(answer)==logical(prior),(item['name'],variant,'work')
            stats=q.producer.producer_phase_work().contents
            phases={k:getattr(stats,k) for k in NAMES}
            phases['input_decode']=answer['producer_stats']['work']-sum(phases.values())
            assert phases['input_decode']>=0
            report['rows'].append({'name':item['name'],'variant':variant,'status':answer['status'],'work':answer['producer_stats']['work'],'phases':phases})
            print('PHASES',item['name'],variant,phases,flush=True)
    for p,d in report['bindings'].items(): assert sha(Path(p))==d,p
    report['status']='PASS';(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('EXACT_TRACE_PHASE_AUDIT_PASS',len(report['rows']),flush=True)
if __name__=='__main__': main()
